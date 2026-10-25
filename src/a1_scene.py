# -*- coding: utf-8 -*-
"""A① (67.85-103.84) — the section the director asked to take all the way to 1:43.

Rules from the director:
  ① right pane keeps something while it is empty  (border + label + timestamp + a faint horizon)
  ② the mountain, the beam and the instrument plate arrive in three separate waves
  ③ the pot shrinks all the way back on the last line
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

import preview
import scene
import tk

OUT = Path(__file__).resolve().parents[1] / "out" / "a1"
T0, T1 = 67.85, 103.84

# t, orchid height
HEIGHT = [
    (67.20, 0.0), (67.85, 108.0), (78.88, 158.0), (90.58, 214.0),
    (94.83, 240.0), (97.11, 258.0), (99.30, 278.0), (100.50, 278.0),
    (101.90, 132.0), (103.84, 126.0),
]

# ② 三层各走各的
W_TERRAIN = [(94.20, 0.0), (94.83, 0.10), (97.11, 0.45), (99.30, 0.80), (100.50, 1.0)]
W_BEAM = [(96.80, 0.0), (97.11, 0.30), (99.30, 0.70), (101.50, 1.0)]
W_HUD = [(99.10, 0.0), (99.30, 0.18), (101.20, 0.62), (102.60, 1.0)]


def _ramp(t, keys):
    if t <= keys[0][0]:
        return keys[0][1]
    for i in range(len(keys) - 1):
        t0, v0 = keys[i]
        t1, v1 = keys[i + 1]
        if t0 <= t <= t1:
            u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return v0 + (v1 - v0) * u
    return keys[-1][1]


def frame(t: float) -> Image.Image:
    cur, nxt = scene.line_at(t)
    rw = scene.rewrite_at(t)
    lyric = ("", "")
    if cur and not rw:
        lyric = (cur["text"], nxt["text"] if nxt else "")
    pen = None
    if cur and not rw:
        span = (nxt["t"] - cur["t"]) if nxt else 2.6
        pen = min(1.0, max(0.0, (t - cur["t"]) / max(0.5, span * 0.86)))

    img = preview.compose(
        t,
        lyric=lyric, cue=None, score=scene.score_at(t), level=scene.level_at(t),
        mood=0.12, cold=0.0, flower=0.0, entity=0.55, rain=0.10, spiral=0.0,
        seed=3 + int(t // 30), glow=0.55, progress=t / scene.DUR,
        amp_scale=scene.amp_at(t, 0.85), flower_x=0.72, flower_count=1,
        rewrite=rw, pen=pen,
        pen_times=(cur.get("times") if (cur and not rw) else None),
        w_terrain=_ramp(t, W_TERRAIN), w_beam=_ramp(t, W_BEAM), w_hud=_ramp(t, W_HUD),
    )

    x0, y0, x1, y1 = preview.RIGHT
    wt = _ramp(t, W_TERRAIN)
    if wt < 0.9:
        # ① the horizon stays even when the world is gone — otherwise the pane reads as a render failure
        d = ImageDraw.Draw(img)
        yh = y0 + (y1 - y0) * 0.615
        d.line([(x0 + 10, yh), (x1 - 10, yh)], fill=tk.fade(tk.BLUE_HI, 0.09 * (1 - wt)))

    h = _ramp(t, HEIGHT)
    if h > 6:
        tk.orchid(img, x0 + (x1 - x0) * 0.845, y1 - 16, h, t, alpha=1.0, blooms=2)
    return img.point(tk._gauze)


if __name__ == "__main__":
    for name, t in [("01-0689-起笔", 68.9), ("02-0806-慢写", 80.6),
                    ("03-0954-山起", 95.4), ("04-0985-光来", 98.5),
                    ("05-1020-表亮", 102.0), ("06-1035-交接", 103.5)]:
        frame(t).save(OUT / f"F-{name}.png")
        print("wrote", name)
