# -*- coding: utf-8 -*-
"""The chorus, take 1: six voices converge into one.

导演（12:15）：「我不想回到开头那样，我认为不够亮眼，我需要在 4:25 之后有『完全不同的感受』」
导演（12:14）：「去原案仓库里找找思路或者画面线索」

原案的合唱段（`sec_chorus1.py` / `sec_chorus2.py`）给出的隐喻是**向量收敛**：
`shot_unite` 让 `me` 和 `you` 从两侧飞向中央融成一个 `we`，下面配一张 t-SNE 散点图，
底下写 `cos(me, you) = 0.9939`；`shot_flood` 更极端——60×28 的格子阵被 `me` 一格一格淹没。

我们借它的**隐喻**，不用它的数字。`src/probes/chorus_cosine.py` 在导演放进来的 17 轨分轨上
量了主唱与背景和声的谱相似度：

    段     和声/主唱    spectral_cos
    A①     −64.2 dB      （没有和声，不可用）
    B①     −9.3 dB      0.353
    B②     −6.4 dB      0.277
    A②     −3.9 dB      0.513     ← 这一段合唱真的唱成了一片
    A③     −1.8 dB      0.404
    A④     −0.1 dB      0.375

所以 A② 的画面是：**六条声部线从散开收敛成一条**，汇合处写我们自己的
`cos(v1…v6) = 0.513`。A③（5:12）伴奏回来、升 key 时再散开——全片最大的一次视觉反差。

这个镜头只覆盖 04:26.3 起的第一句「谁从山中来带着兰花草」。

Run: python src/probes/chorus_sample.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import tk  # noqa: E402
from tk import AMBER, BLUE_HI, fade, font  # noqa: E402

W, H = tk.W, tk.H
OUT = ROOT / "out" / "review-frames" / "chorus-sample"

# 我们的数字（src/probes/chorus_cosine.py 实测）
COS = 0.513
N_VOICES = 6

# 六条线的散开端（相对中线的偏移比例）和合拢端
SPREAD = (0.40, 0.28, 0.17, -0.17, -0.28, -0.40)
GATHER = (0.055, 0.035, 0.015, -0.015, -0.035, -0.055)   # 合拢后仍分开一点点（不是一根线）

T0 = 266.31          # A② 的第一句
CONVERGE = 3.2       # 收敛用掉的时间（秒）


def _bez(p0, p1, p2, p3, n=48):
    pts = []
    for i in range(n + 1):
        u = i / n
        v = 1 - u
        x = v**3*p0[0] + 3*v*v*u*p1[0] + 3*v*u*u*p2[0] + u**3*p3[0]
        y = v**3*p0[1] + 3*v*v*u*p1[1] + 3*v*u*u*p2[1] + u**3*p3[1]
        pts.append((x, y))
    return pts


def frame(t: float) -> Image.Image:
    """One frame of the sample: six voices converging into one."""
    img = Image.new("RGB", (W, H), (2, 3, 8))
    d = ImageDraw.Draw(img)

    u = max(0.0, min(1.0, (t - T0) / CONVERGE))
    # the gather itself: smooth, so it accelerates like the music does
    g = u * u * (3 - 2 * u)

    # the world pane, with a light frame so it does not float in the void
    x0, y0, x1, y1 = 150, 120, W - 150, H - 170
    d.rectangle([x0, y0, x1, y1], outline=fade(AMBER, 0.22), width=1)
    mid = (y0 + y1) / 2

    for i in range(N_VOICES):
        sy = mid + (y1 - y0) * SPREAD[i] / 2
        gy = mid + (y1 - y0) * GATHER[i] / 2
        # start outside the frame, end at the gathered row
        sx = x0 - 120
        ex = x1 - 150
        pts = _bez((sx, sy), (x0 + (ex - x0) * 0.35, sy),
                   (ex - (ex - x0) * 0.30, gy), (ex, gy))
        # only the part that has been "sung" so far is drawn
        k = min(len(pts) - 1, int(len(pts) * g))
        if k < 2:
            continue
        head = pts[k]
        col = AMBER if i % 2 == 0 else BLUE_HI
        a = 0.30 + 0.55 * g
        d.line(pts[:k + 1], fill=fade(col, a * 0.85), width=2)
        d.ellipse([head[0] - 4, head[1] - 4, head[0] + 4, head[1] + 4],
                  fill=fade(col, min(1.0, a + 0.25)))
        # the voice's own label at the start of its line
        d.text((x0 + 6, sy - 12), "V%d" % (i + 1), font=font(tk.MONO, 8),
               fill=fade(col, 0.45 * (1.0 - g) + 0.15))

    # the gathered line: one voice, drawn solid across the middle
    if g > 0.55:
        a = (g - 0.55) / 0.45
        yy = mid
        d.line([(ex, yy), (x1 - 40, yy)], fill=fade(AMBER, 0.95 * a), width=3)
        d.text((ex + 10, yy - 14), "WE", font=font(tk.MONO_B, 11),
               fill=fade(AMBER, 0.95 * a))

    # the number: ours, measured (src/probes/chorus_cosine.py)
    if g > 0.72:
        a = (g - 0.72) / 0.28
        lab = "cos(v1..v6) = %.3f" % COS
        f = font(tk.MONO_B, 13)
        tw = d.textlength(lab, font=f)
        d.rectangle([x1 - 40 - tw - 12, y0 + 14, x1 - 34, y0 + 36], fill=(2, 3, 8))
        d.text((x1 - 40 - tw, y0 + 18), lab, font=f, fill=fade((255, 246, 224), 0.95 * a))

    # the counter: six became one
    lab2 = "VOICES %02d -> 01" % N_VOICES
    f2 = font(tk.MONO, 10)
    d.text((x0 + 8, y1 + 14), lab2, font=f2, fill=fade(BLUE_HI, 0.55))
    d.text((x0 + 8, y0 - 26), "CHORUS // WHO CAME FROM THE HILLS", font=font(tk.MONO, 10),
           fill=fade(AMBER, 0.45))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ts = [T0 + i * 0.5 for i in range(12)]
    for i, t in enumerate(ts):
        frame(t).save(OUT / ("s%02d.png" % i))
    print("wrote", len(ts), "frames to", OUT)


if __name__ == "__main__":
    main()
