#!/usr/bin/env python3
"""Run several independent resident-instrument workers concurrently."""
from __future__ import annotations

import argparse
import collections
import hashlib
import wave
from pathlib import Path

from midi_to_events import convert
from worker_process import WorkerProcess


def pcm_hash(path: Path) -> str:
    with wave.open(str(path), "rb") as w:
        h = hashlib.sha256()
        while True:
            b = w.readframes(65536)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Concurrent persistent RAM-worker determinism probe")
    ap.add_argument("--worker", default="build/mrp-sfizz-worker")
    ap.add_argument("--libsfizz", required=True)
    ap.add_argument("--sfz", required=True)
    ap.add_argument("--midi", required=True, type=Path)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--sample-rate", type=int, default=48000)
    ap.add_argument("--block-size", type=int, default=1024)
    ap.add_argument("--polyphony", type=int, default=256)
    ap.add_argument("--quality", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0, help="deterministic task seed")
    ap.add_argument("--out-dir", type=Path, default=Path("parallel-pool-out"))
    ap.add_argument("--debug-worker-stderr", action="store_true", help="mirror drained worker diagnostics to stderr")
    ap.add_argument("--diagnostic-lines", type=int, default=200, help="number of recent stderr lines retained per worker")
    ns = ap.parse_args()
    if ns.concurrency <= 0:
        ap.error("--concurrency must be > 0")
    if ns.rounds <= 0:
        ap.error("--rounds must be > 0")
    ns.out_dir.mkdir(parents=True, exist_ok=True)
    ev = ns.out_dir / "input.mrpev"
    convert(ns.midi, ev, ns.sample_rate)

    base = [
        ns.worker,
        "--libsfizz", ns.libsfizz,
        "--sample-rate", str(ns.sample_rate),
        "--block-size", str(ns.block_size),
        "--polyphony", str(ns.polyphony),
        "--quality", str(ns.quality),
    ]
    workers = []
    try:
        workers = [WorkerProcess(base, debug=ns.debug_worker_stderr, diagnostic_lines=ns.diagnostic_lines) for _ in range(ns.concurrency)]
        for i, worker in enumerate(workers):
            print(f"worker[{i}]", worker.read_reply())

        # Load the same resident instrument in each process concurrently.
        for worker in workers:
            worker.send(f"LOAD\t{Path(ns.sfz).resolve()}")
        for i, worker in enumerate(workers):
            print(f"worker[{i}]", worker.read_reply())

        hashes = []
        for r in range(1, ns.rounds + 1):
            paths = []
            for i, worker in enumerate(workers):
                out = ns.out_dir / f"r{r:02d}-w{i:02d}.wav"
                paths.append(out)
                worker.send(f"RENDER\t{ev.resolve()}\t{out.resolve()}\t{ns.seed}")
            for i, worker in enumerate(workers):
                line = worker.read_reply()
                print(f"round={r} worker={i} {line}")
            hashes.extend(pcm_hash(x) for x in paths)

        for worker in workers:
            worker.send("QUIT")
        for worker in workers:
            worker.read_reply()
            worker.wait(timeout=10)
    finally:
        for worker in workers:
            worker.close()

    counts = collections.Counter(hashes)
    print("\nPCM hash counts:")
    for h, n in counts.most_common():
        print(f"  {n:4d} {h}")
    print(f"unique={len(counts)} total={len(hashes)}")
    print("DETERMINISTIC=" + ("YES" if len(counts) == 1 else "NO"))


if __name__ == "__main__":
    main()
