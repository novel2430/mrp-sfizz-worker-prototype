#!/usr/bin/env python3
"""Phase 04: concurrent resident-worker determinism acceptance probe."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import re
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

from midi_to_events import convert
from worker_process import WorkerProcess


_LOADS_RE = re.compile(r"\binstrument_loads=(\d+)\b")


@dataclass(frozen=True)
class RenderResult:
    worker_index: int
    reply: str
    pcm_sha256: str
    instrument_loads: int | None


def pcm_hash(path: Path) -> str:
    with wave.open(str(path), "rb") as w:
        h = hashlib.sha256()
        while True:
            block = w.readframes(65536)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def parse_instrument_loads(reply: str) -> int | None:
    match = _LOADS_RE.search(reply)
    return int(match.group(1)) if match else None


def render_round(
    workers: list[WorkerProcess],
    event_path: Path,
    output_paths: list[Path],
    seed: int,
) -> list[RenderResult]:
    """Start one render on every worker at the same barrier."""
    barrier = threading.Barrier(len(workers))

    def run_one(index: int) -> RenderResult:
        worker = workers[index]
        barrier.wait()
        worker.send(
            f"RENDER\t{event_path.resolve()}\t{output_paths[index].resolve()}\t{seed}"
        )
        reply = worker.read_reply()
        return RenderResult(
            worker_index=index,
            reply=reply,
            pcm_sha256=pcm_hash(output_paths[index]),
            instrument_loads=parse_instrument_loads(reply),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as pool:
        futures = [pool.submit(run_one, i) for i in range(len(workers))]
        results = [future.result() for future in futures]
    return sorted(results, key=lambda result: result.worker_index)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Concurrent persistent RAM-worker acceptance probe"
    )
    ap.add_argument("--worker", default="build/mrp-sfizz-worker")
    ap.add_argument("--libsfizz", required=True)
    ap.add_argument("--sfz", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sample-rate", type=int, default=48000)
    ap.add_argument("--block-size", type=int, default=1024)
    ap.add_argument("--polyphony", type=int, default=256)
    ap.add_argument("--quality", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=Path("parallel-pool-out"))
    ap.add_argument("--debug-worker-stderr", action="store_true")
    ap.add_argument("--diagnostic-lines", type=int, default=200)
    ap.add_argument(
        "midi",
        nargs="+",
        type=Path,
        help="render sequence, e.g. A.mid or A.mid B.mid A.mid",
    )
    ns = ap.parse_args()

    if ns.workers <= 0:
        ap.error("--workers must be > 0")

    ns.out_dir.mkdir(parents=True, exist_ok=True)

    event_paths: list[Path] = []
    for sequence_index, midi in enumerate(ns.midi, 1):
        event_path = ns.out_dir / f"{sequence_index:02d}-{midi.stem}.mrpev"
        convert(midi, event_path, ns.sample_rate)
        event_paths.append(event_path)

    command = [
        ns.worker,
        "--libsfizz",
        ns.libsfizz,
        "--sample-rate",
        str(ns.sample_rate),
        "--block-size",
        str(ns.block_size),
        "--polyphony",
        str(ns.polyphony),
        "--quality",
        str(ns.quality),
    ]

    workers: list[WorkerProcess] = []
    sequence_hashes: list[list[str]] = [[] for _ in range(ns.workers)]
    cross_worker_ok = True
    load_once_ok = True

    try:
        workers = [
            WorkerProcess(
                command,
                debug=ns.debug_worker_stderr,
                diagnostic_lines=ns.diagnostic_lines,
            )
            for _ in range(ns.workers)
        ]

        for i, worker in enumerate(workers):
            print(f"worker[{i}] pid={worker.pid} {worker.read_reply()}")

        # Cold loading may overlap, but Phase 04 gates correctness on render
        # concurrency rather than load throughput.
        sfz_path = Path(ns.sfz).resolve()
        for worker in workers:
            worker.send(f"LOAD\t{sfz_path}")
        for i, worker in enumerate(workers):
            print(f"worker[{i}] {worker.read_reply()}")

        for sequence_index, (midi, event_path) in enumerate(
            zip(ns.midi, event_paths), 1
        ):
            output_paths = [
                ns.out_dir / f"{sequence_index:02d}-{midi.stem}-w{i:02d}.wav"
                for i in range(ns.workers)
            ]
            results = render_round(workers, event_path, output_paths, ns.seed)

            round_hashes = {result.pcm_sha256 for result in results}
            if len(round_hashes) != 1:
                cross_worker_ok = False

            for result in results:
                sequence_hashes[result.worker_index].append(result.pcm_sha256)
                if result.instrument_loads != 1:
                    load_once_ok = False
                print(
                    f"step={sequence_index} midi={midi.name} "
                    f"worker={result.worker_index} {result.reply} "
                    f"pcm_sha256={result.pcm_sha256}"
                )

        for worker in workers:
            worker.send("QUIT")
        for worker in workers:
            worker.read_reply()
            worker.wait(timeout=10)
    finally:
        for worker in workers:
            worker.close()

    aba_requested = (
        len(ns.midi) >= 2 and ns.midi[0].resolve() == ns.midi[-1].resolve()
    )
    aba_ok = True
    if aba_requested:
        aba_ok = all(hashes[0] == hashes[-1] for hashes in sequence_hashes)

    print("\nPHASE04 SUMMARY")
    print(f"workers={ns.workers}")
    print(f"sequence={' -> '.join(midi.name for midi in ns.midi)}")
    print("cross_worker_match=" + ("YES" if cross_worker_ok else "NO"))
    if aba_requested:
        print("per_worker_A...A_match=" + ("YES" if aba_ok else "NO"))
    print("instrument_loads_once=" + ("YES" if load_once_ok else "NO"))

    passed = cross_worker_ok and load_once_ok and aba_ok
    print("RESULT=" + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
