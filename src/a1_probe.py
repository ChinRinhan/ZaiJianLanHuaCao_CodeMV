# -*- coding: utf-8 -*-
"""A① probe v2: typed lyrics with a nib caret + a potted 国兰. No handwriting, no ruled paper."""
from __future__ import annotations

from pathlib import Path

import preview
import scene
import tk

OUT = Path(__file__).resolve().parents[1] / "out" / "a1"
OUT.mkdir(parents=True, exist_ok=True)


def shot(t: float, name: str, orchid_h: float = 190.0, orchid_x: float = 0.845, orch: bool = True):
    # A① 期间关掉程序化的"雏菊"，只留盆花
    scene.SECTIONS[1] = ("A1", 67.85, 103.84, 0.12, 0.00, 0.00, 0.55, 0.10, 0.0, 0.85, 0.72, 1)
    img = scene.frame(t)
    if orch:
        x0, y0, x1, y1 = preview.RIGHT
        tk.orchid(img, x0 + (x1 - x0) * orchid_x, y1 - 16, orchid_h, t, alpha=1.0, blooms=2)
        img = img.point(tk._gauze)
    img.save(OUT / f"{name}.png")
    print("wrote", name)


if __name__ == "__main__":
    shot(68.6, "v2-01-typing-early", 160, 0.855)
    shot(71.0, "v2-02-typing-mid", 190, 0.845)
    shot(73.3, "v2-03-typing-done", 205, 0.840)
    shot(101.0, "v2-04-late", 225, 0.830)
