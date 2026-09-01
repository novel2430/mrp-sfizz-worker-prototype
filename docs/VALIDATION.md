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
