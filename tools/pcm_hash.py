#!/usr/bin/env python3
import argparse, hashlib, wave
from pathlib import Path

def pcm_hash(path: Path):
    with wave.open(str(path), "rb") as w:
        params = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
        h = hashlib.sha256()
        while True:
            data = w.readframes(65536)
            if not data: break
            h.update(data)
    return params, h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("wav", nargs="+", type=Path); ns = ap.parse_args()
    for p in ns.wav:
        params, h = pcm_hash(p)
        print(h, *params, p)
if __name__ == "__main__": main()
