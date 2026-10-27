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
from media import FFMPEG as FF  # noqa: E402
SRC = ROOT / "input" / "song.flac"
FPS = 24


def _init(frames_dir: str, scene_module: str):
    global scene, _FRAMES
    import importlib
    scene = importlib.import_module(scene_module)
    _FRAMES = Path(frames_dir)


def _render_one(n: int) -> str:
    t = n / FPS
    im = scene.frame(t)
    p = _FRAMES / f"{n:05d}.png"
    im.save(p, compress_level=1)
    return str(p)


def _render_serial(nums, scene_module: str, frames_dir: str, workers: int):
    """Render without multiprocessing.

    The multiprocessing Pool needs named pipes, and the Windows sandbox denies
    CreateFile on them (WinError 5) — so `Pool` cannot be used here at all. Threads do
    not need pipes, and PIL releases the GIL for most of the drawing, so a thread pool
    still gives most of the speed-up. If threads are unavailable too, this runs plainly
    serial, which is slower but always works.
    """
    _init(frames_dir, scene_module)
    t_start = time.time()
    done = 0
    if workers > 1:
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for _ in ex.map(_render_one, nums, chunksize=4):
                    done += 1
                    if done % 96 == 0:
                        _tick(done, len(nums), t_start)
            return
        except Exception as e:                       # noqa: BLE001
            print(f"thread pool unavailable ({e}); falling back to serial", flush=True)
            _init(frames_dir, scene_module)
    for n in nums:
        _render_one(n)
        done += 1
        if done % 96 == 0:
            _tick(done, len(nums), t_start)


def _tick(done, total, t_start):
    el = time.time() - t_start
    print(f"  {done}/{total} frames  {el:.1f}s  ({el/done*1000:.0f} ms/frame)", flush=True)


_FRAMES: Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("out", type=str)
    ap.add_argument("--workers", type=int, default=8)
    # which frame function to render. `scene` is the old two-pane layout that produced
    # out/film.mp4; `scene4` is the four-zone layout with the A① shot table.
    ap.add_argument("--scene", type=str, default="scene")
    args = ap.parse_args()

    # plan/16 §0「断言式时间轴」：覆盖不上就当场失败，而不是渲完两分钟才发现段落漏了。
    # 原案 engine.py:355-362 就在开渲前 raise；我们之前只有 __main__ 里一个自检。
    import shots
    shots.assert_coverage()

    global _FRAMES
    tag = f"{args.t0:.2f}-{args.t1:.2f}".replace(".", "")
    if args.scene != "scene":
        tag += "-" + args.scene
    _FRAMES = ROOT / "out" / "frames" / tag
    if _FRAMES.exists():
        shutil.rmtree(_FRAMES)
    _FRAMES.mkdir(parents=True, exist_ok=True)

    n0, n1 = int(round(args.t0 * FPS)), int(round(args.t1 * FPS))
    nums = list(range(n0, n1))
    t_start = time.time()
    _render_serial(nums, args.scene, str(_FRAMES), args.workers)
    el = time.time() - t_start
    print(f"rendered {len(nums)} frames in {el:.1f}s ({el/len(nums)*1000:.0f} ms/frame)")

    out = ROOT / "out" / args.out
    out = out.resolve()
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
