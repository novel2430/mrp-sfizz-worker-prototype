# Validation record

Phase 01 keeps only the behavior that has already passed the real-instrument proof-of-concept.

## Piano

Using one persistent RAM-based worker and seed 0:

- A/A/A: bit-identical PCM across all three renders.
- A/B/A: first and final A are bit-identical after rendering a different MIDI in between.
- fresh-worker parity: a newly started worker's first A matches the persistent-worker A hash.
- `instrument_loads=1` throughout the persistent sequences.

Observed A PCM SHA-256:

```text
6effe3f137966b06932cf691059c76785490cf99e996c7b7bb5897f0f169d9cc
```

## SM_Drums

The large RAM-resident workload also passed both isolation tests.

Cold load:

```text
regions=3358
preloaded_samples=3358
load ~= 6.8 s
RSS ~= 4.81 GB
```

A/A/A with seed 0:

```text
A1 == A2 == A3
instrument_loads=1
warm render ~= 3.0 s
RSS stayed ~= 4.81 GB
```

A/B/A with seed 0:

```text
A(first) == A(last)
instrument_loads=1
```

Observed A PCM SHA-256:

```text
9fd7c679a61850674426d7b8607528efc300a06fcdeb17b9274e22d3c9350ab1
```

The intermediate B used a different MIDI history and produced a different hash, while the final A returned exactly to the original hash. This is the key cross-task isolation result.

## What is not yet validated

The remaining renderer-level validation is multiple independent RAM-based persistent worker processes rendering concurrently. `tools/parallel_pool_probe.py` is retained for that Phase 04 check.

Real Piano/SM_Drums files are intentionally not part of the automated test suite because they are local heavyweight assets. `make test` only covers self-contained host/protocol regressions.

## Phase 04 concurrency acceptance

Phase 04 intentionally keeps the test matrix small. It validates the production
execution primitive only: multiple independent resident worker processes, each
with one Synth and one RAM-resident instrument, rendering concurrently.

The probe starts every render step behind a thread barrier and checks only three
properties:

- all workers produce the same PCM hash for the same step and seed;
- for an `A B A` sequence, each worker's first and final A match;
- every render reports `instrument_loads=1`.

Recommended checks:

```bash
# Piano: three resident processes rendering the same task concurrently.
python tools/parallel_pool_probe.py \
  --libsfizz "$LIBSFIZZ" \
  --sfz "$PIANO_SFZ" \
  --workers 3 \
  --seed 0 \
  --out-dir /tmp/mrp-piano-c3 \
  "$PIANO_MIDI"

# SM_Drums: two ~4.8 GB resident processes rendering concurrently.
python tools/parallel_pool_probe.py \
  --libsfizz "$LIBSFIZZ" \
  --sfz "$DRUM_SFZ" \
  --workers 2 \
  --seed 0 \
  --out-dir /tmp/mrp-drums-c2 \
  "$DRUM_MIDI"

# SM_Drums: concurrency plus cross-task isolation.
python tools/parallel_pool_probe.py \
  --libsfizz "$LIBSFIZZ" \
  --sfz "$DRUM_SFZ" \
  --workers 2 \
  --seed 0 \
  --out-dir /tmp/mrp-drums-c2-aba \
  "$DRUM_MIDI" "$DRUM_MIDI_B" "$DRUM_MIDI"
```

A successful run ends with `RESULT=PASS`.
