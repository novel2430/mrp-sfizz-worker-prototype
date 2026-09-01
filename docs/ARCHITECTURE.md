# Prototype architecture

This repository is a standalone prototype for one narrow renderer contract. It is not an MRP integration patch.

## Contract

A worker process owns one `sfizz_synth_t` and one resident SFZ instrument for its entire lifetime:

```text
process start
  -> create Synth
  -> LOAD one SFZ in RAM mode
  -> capture canonical offline baseline
  -> RENDER(seed)
  -> RENDER(seed)
  -> ...
  -> process exit
```

`LOAD` is intentionally one-shot. Loading another instrument requires starting another worker process.

Every `RENDER` automatically calls the patched libsfizz `sfizz_prepare_offline_task(synth, seed)` before dispatching MIDI events. Fresh-task restoration is therefore part of the renderer contract, not a selectable reset policy.

## Required libsfizz extension

The worker requires these two symbols in addition to the public sfizz 1.x C ABI used for rendering:

```c
void sfizz_capture_offline_baseline(sfizz_synth_t* synth);
void sfizz_prepare_offline_task(sfizz_synth_t* synth, unsigned int seed);
```

The current Phase 01 build helper still applies the exact 1.2.3 experiment patch. Moving that patch into a pinned sfizz fork is intentionally deferred to Phase 02.

## RAM loading

The prototype currently reads the root SFZ text, forces `hint_ram_based=1`, and calls `sfizz_load_string()` with the original SFZ path as the virtual path. This keeps sample/include resolution relative to the original instrument while avoiding the streaming path.

This source-text injection is still prototype machinery. A cleaner sfizz-side RAM-loading API may replace it in a later phase.

## Process isolation

One process has one Synth and renders tasks serially. Multiple worker processes may run concurrently, but there is no concurrent access to a Synth and no attempt to share sample memory between Synth instances.

This matches the already validated minimal offline-baseline implementation, including its process-wide deterministic RNG reset. It does not claim safe concurrent Synth sessions inside one process.

## Protocol v3

Commands are tab-separated:

```text
LOAD    <sfz-path>
RENDER  <event-file>  <wav-path>  <seed>
PING
QUIT
```

There is deliberately no `RESET`, reload mode, streaming mode, or recreate mode.

## Host diagnostics

The Python host continuously drains worker stderr into a bounded diagnostic tail. This prevents libsfizz background-loading warnings from filling a pipe and blocking the loader thread. Diagnostics remain quiet by default and can be mirrored live with `--debug-worker-stderr`.

## Future MRP boundary

This prototype proves renderer semantics only. MRP-side instrument affinity, resident-worker admission, RAM budgets, eviction, cache identity, and scheduler integration are separate work and are not implemented here.
