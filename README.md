# MRP persistent sfizz worker prototype

A standalone prototype for the future MidiRenderPipeline SFZ backend.

The proof-of-concept question is now resolved: a RAM-based persistent sfizz worker can keep a large instrument resident and render independent tasks from a deterministic canonical baseline without reloading the SFZ between tasks.

This repository now expresses only that successful path.

## Renderer model

```text
worker process
  -> create one Synth
  -> LOAD one SFZ once (RAM-based)
  -> capture offline baseline
  -> RENDER(seed) -> prepare fresh task -> render
  -> RENDER(seed) -> prepare fresh task -> render
  -> ...
  -> exit
```

A worker never changes instruments. Start another process for another SFZ.

There are no legacy reset/reload/recreate modes and no streaming mode in the worker protocol.

## Included

- `mrp-sfizz-worker`: C++17 persistent worker using libsfizz through `dlopen`.
- required offline-baseline ABI supplied by the pinned sfizz 1.2.3 experiment patch.
- RAM-mode SFZ injection with `hint_ram_based=1`.
- sample-frame event dispatch for note on/off, CC, and pitch bend.
- stereo PCM16 WAV output with a bounded silence-tail render.
- deterministic per-task seed.
- `run_sequence.py` for A/A/A, A/B/A, and fresh-worker checks.
- `parallel_pool_probe.py` for later independent-process concurrency validation.
- continuously drained worker stderr with a bounded diagnostic tail.
- small self-contained host/protocol tests using a fake libsfizz.

See `docs/ARCHITECTURE.md` for the contract and `docs/VALIDATION.md` for the real-instrument results already obtained.

## Build

```bash
python -m pip install -r requirements.txt
make
make test
```

The binary itself has no Python or mido runtime dependency. Python is used by the experiment drivers to prepare event files.

## Build the current patched sfizz 1.2.3

Phase 01 intentionally leaves sfizz dependency migration for Phase 02. For now the existing helper still builds the exact validated base and applies the experiment patch:

```bash
tools/build_sfizz_1_2_3.sh
export LIBSFIZZ="$PWD/.deps/sfizz-install/lib64/libsfizz.so.1.2.3"
tools/verify_offline_build.sh "$LIBSFIZZ"
```

The exact upstream base is:

```text
tag:    1.2.3
commit: 4e70dc0bef53b41f2853ed46e26f5911114c92d0
```

The worker now requires the offline ABI. Loading an unpatched libsfizz fails at startup rather than silently falling back to an old reset strategy.

## Sequence probe

```bash
python tools/run_sequence.py \
  --libsfizz "$LIBSFIZZ" \
  --sfz "$PIANO_SFZ" \
  --seed 0 \
  --out-dir /tmp/mrp-sfizz-aba \
  "$PIANO_A" "$PIANO_B" "$PIANO_A"
```

Important output:

- `OK LOAD ...`: the single cold instrument load.
- `OK RENDER ... instrument_loads=1`: warm render and proof that no task reloaded the instrument.
- `pcm_sha256=...`: decoded PCM identity.
- `rss_kb=...`: process resident memory.

Worker stderr is drained continuously. Add `--debug-worker-stderr` to mirror diagnostics live; recent diagnostics are automatically attached if a worker fails.

## Concurrent-process probe

```bash
python tools/parallel_pool_probe.py \
  --libsfizz "$LIBSFIZZ" \
  --sfz "$PIANO_SFZ" \
  --midi "$PIANO_A" \
  --seed 0 \
  --concurrency 3 \
  --rounds 10 \
  --out-dir /tmp/mrp-sfizz-pool
```

This uses independent processes. It is not a shared-Synth or shared-Session test.

## Boundaries

- This is not an MRP patch and does not implement MRP scheduling or cache policy.
- One worker process owns one Synth, one loaded instrument, and executes one render at a time.
- The current sfizz patch is still the minimal validated implementation; formalizing it is Phase 03, after moving it to a fork in Phase 02.
- Real instrument assets are not part of `make test`; their validated results are recorded in `docs/VALIDATION.md`.
