#!/usr/bin/env python3
"""Drive one resident-instrument worker through an arbitrary MIDI sequence."""
from __future__ import annotations

import argparse
import hashlib
import wave
from pathlib import Path

from midi_to_events import convert
from worker_process import WorkerProcess


def pcm_hash(path: Path):
    with wave.open(str(path), "rb") as w:
        meta = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
        h = hashlib.sha256()
        while True:
            b = w.readframes(65536)
            if not b:
                break
            h.update(b)
    return h.hexdigest(), meta


def rss_kb(pid: int):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description="Persistent RAM-based libsfizz sequence probe")
    ap.add_argument("--worker", type=Path, default=Path("build/mrp-sfizz-worker"))
    ap.add_argument("--libsfizz", required=True)
    ap.add_argument("--sfz", required=True)
    ap.add_argument("--sample-rate", type=int, default=48000)
    ap.add_argument("--block-size", type=int, default=1024)
    ap.add_argument("--polyphony", type=int, default=256)
    ap.add_argument("--quality", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0, help="deterministic task seed")
    ap.add_argument("--out-dir", type=Path, default=Path("probe-out"))
    ap.add_argument("--debug-worker-stderr", action="store_true", help="mirror drained worker diagnostics to stderr")
    ap.add_argument("--diagnostic-lines", type=int, default=200, help="number of recent worker stderr lines retained for failures")
    ap.add_argument("midi", nargs="+", type=Path, help="sequence, e.g. A.mid B.mid A.mid")
    ns = ap.parse_args()
    ns.out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(ns.worker),
        "--libsfizz", ns.libsfizz,
        "--sample-rate", str(ns.sample_rate),
        "--block-size", str(ns.block_size),
        "--polyphony", str(ns.polyphony),
        "--quality", str(ns.quality),
    ]
    with WorkerProcess(cmd, debug=ns.debug_worker_stderr, diagnostic_lines=ns.diagnostic_lines) as worker:
        print(worker.read_reply())
        worker.send(f"LOAD\t{Path(ns.sfz).resolve()}")
        load_reply = worker.read_reply()
        print(load_reply, f"rss_kb={rss_kb(worker.pid)}")

        hashes = []
        for i, midi in enumerate(ns.midi, 1):
            ev = ns.out_dir / f"{i:02d}-{midi.stem}.mrpev"
            wav = ns.out_dir / f"{i:02d}-{midi.stem}.wav"
            info = convert(midi, ev, ns.sample_rate)
            worker.send(f"RENDER\t{ev.resolve()}\t{wav.resolve()}\t{ns.seed}")
            reply = worker.read_reply()
            h, meta = pcm_hash(wav)
            hashes.append(h)
            print(f"[{i}] {midi.name} {reply} pcm_sha256={h} meta={meta} rss_kb={rss_kb(worker.pid)} events={info['events']}")

        worker.send("QUIT")
        print(worker.read_reply())
        worker.wait(timeout=10)

    print("hash sequence:")
    for i, h in enumerate(hashes, 1):
        print(f"  {i}: {h}")
    if len(hashes) >= 2 and ns.midi[0].resolve() == ns.midi[-1].resolve():
        print("A...A deterministic:", "YES" if hashes[0] == hashes[-1] else "NO")


if __name__ == "__main__":
    main()
