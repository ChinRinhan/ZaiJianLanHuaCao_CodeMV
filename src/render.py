# -*- coding: utf-8 -*-
"""render: frames -> mp4 for a time range. Deterministic, parallel, audio muxed from the FLAC."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FF = ROOT / "tools" / "ffmpeg.exe"
SRC = ROOT / "input" / "song.flac"
FPS = 24


def _init(frames_dir: str):
    global scene, _FRAMES
    import scene as _s
    scene = _s
    _FRAMES = Path(frames_dir)


def _render_one(n: int) -> str:
    t = n / FPS
    im = scene.frame(t)
    p = _FRAMES / f"{n:05d}.png"
    im.save(p, compress_level=1)
    return str(p)


_FRAMES: Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("out", type=str)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    global _FRAMES
    tag = f"{args.t0:.2f}-{args.t1:.2f}".replace(".", "")
    _FRAMES = ROOT / "out" / "frames" / tag
    if _FRAMES.exists():
        shutil.rmtree(_FRAMES)
    _FRAMES.mkdir(parents=True, exist_ok=True)

    n0, n1 = int(round(args.t0 * FPS)), int(round(args.t1 * FPS))
    nums = list(range(n0, n1))
    t_start = time.time()
    with Pool(args.workers, initializer=_init, initargs=(str(_FRAMES),)) as pool:
        done = 0
        for _ in pool.imap_unordered(_render_one, nums, chunksize=4):
            done += 1
            if done % 96 == 0:
                el = time.time() - t_start
                print(f"  {done}/{len(nums)} frames  {el:.1f}s  ({el/done*1000:.0f} ms/frame)", flush=True)
    el = time.time() - t_start
    print(f"rendered {len(nums)} frames in {el:.1f}s ({el/len(nums)*1000:.0f} ms/frame)")

    out = ROOT / "out" / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = (n1 - n0) / FPS
    cmd = [
        str(FF), "-v", "error", "-y",
        "-framerate", str(FPS), "-start_number", str(n0), "-i", str(_FRAMES / "%05d.png"),
        "-ss", f"{args.t0:.3f}", "-t", f"{dur:.3f}", "-i", str(SRC),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "256k", "-shortest",
        "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True)
    print("wrote", out, f"{out.stat().st_size/1048576:.1f} MB")


if __name__ == "__main__":
    main()
