# -*- coding: utf-8 -*-
"""A/B proof: the same 12 s rendered twice — old continuous motion vs. quantised + accumulating.

    out/proof/A_old.mp4   MOTION_V2 = False  (scroll, spin, sliding pen)
    out/proof/B_new.mp4   MOTION_V2 = True   (step, hold, history trace)

Silent, 24 fps. Encodes with OpenCV so it does not depend on the broken ffmpeg.exe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

import preview
import scene

OUT = Path(__file__).resolve().parents[1] / "out" / "proof"
OUT.mkdir(parents=True, exist_ok=True)

T0, T1 = 266.31, 278.31
FPS = 24


def render(tag: str, motion_v2: bool):
    preview.MOTION_V2 = motion_v2
    n = int(round((T1 - T0) * FPS))
    p = OUT / f"{tag}.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (1280, 720))
    if not w.isOpened():
        raise RuntimeError("VideoWriter refused to open")
    for i in range(n):
        t = T0 + i / FPS
        im = scene.frame(t).convert("RGB")
        w.write(cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR))
    w.release()
    print(f"{tag}: {n} frames -> {p} ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else "both"
    if only in ("both", "old"):
        render("A_old", False)
    if only in ("both", "new"):
        render("B_new", True)
