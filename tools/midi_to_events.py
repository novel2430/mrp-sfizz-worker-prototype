#!/usr/bin/env python3
"""Convert a Standard MIDI File to MRP prototype frame events.

Semantics deliberately match sfizz_render's useful subset:
- note on/off (velocity-zero note_on becomes note_off)
- CC
- pitch bend
Other channel messages are ignored.
Timing is flattened to absolute sample frames at the requested sample rate.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import mido


def convert(midi_path: Path, out_path: Path, sample_rate: int) -> dict:
    mid = mido.MidiFile(midi_path)
    merged = mido.merge_tracks(mid.tracks)
    tempo = 500_000
    seconds = 0.0
    rows: list[tuple[int, str, int, int | None]] = []
    channels: set[int] = set()

    for msg in merged:
        seconds += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
        frame = int(seconds * sample_rate)  # sfizz_render effectively floors to a sample index
        if msg.is_meta:
            if msg.type == "set_tempo":
                tempo = msg.tempo
            continue
        if hasattr(msg, "channel"):
            channels.add(msg.channel)
        if msg.type == "note_on":
            if msg.velocity == 0:
                rows.append((frame, "note_off", msg.note, 0))
            else:
                rows.append((frame, "note_on", msg.note, msg.velocity))
        elif msg.type == "note_off":
            rows.append((frame, "note_off", msg.note, msg.velocity))
        elif msg.type == "control_change":
            rows.append((frame, "cc", msg.control, msg.value))
        elif msg.type == "pitchwheel":
            rows.append((frame, "pitch", msg.pitch, None))

    end_frame = int(seconds * sample_rate)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"MRPEV1 {sample_rate}\n")
        f.write(f"# source={midi_path}\n")
        f.write(f"# ticks_per_beat={mid.ticks_per_beat} channels={','.join(map(str, sorted(channels)))}\n")
        for frame, kind, a, b in rows:
            if b is None:
                f.write(f"{frame} {kind} {a}\n")
            else:
                f.write(f"{frame} {kind} {a} {b}\n")
        f.write(f"END {end_frame}\n")
    return {"events": len(rows), "end_frame": end_frame, "channels": sorted(channels), "seconds": seconds}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("midi", type=Path)
    ap.add_argument("events", type=Path)
    ap.add_argument("--sample-rate", type=int, default=48000)
    ns = ap.parse_args()
    info = convert(ns.midi, ns.events, ns.sample_rate)
    print(f"events={info['events']} end_frame={info['end_frame']} channels={info['channels']} seconds={info['seconds']:.6f}")

if __name__ == "__main__":
    main()
