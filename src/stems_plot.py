# -*- coding: utf-8 -*-
"""Draw a one-page overview of the four stem envelopes against the section map."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "stems-overview.png"
W, H = 1280, 720
BG = (10, 10, 14)
F = "C:/Windows/Fonts/consola.ttf"
FC = "C:/Windows/Fonts/msyh.ttc"

env = {n: np.load(ROOT / "data" / "audio" / f"stem_{n}.npy") for n in ("vocals", "drums", "bass", "other")}
N = len(env["vocals"])
DUR = N / 100.0

SECTIONS = [
    ("前奏", 0, 67.85, (40, 40, 60)), ("A①", 67.85, 103.84, (40, 55, 80)),
    ("B①", 103.84, 122.0, (70, 45, 40)), ("间奏", 122.0, 245.79, (30, 45, 45)),
    ("B②", 245.79, 266.31, (60, 45, 45)), ("A②", 266.31, 312.45, (40, 55, 80)),
    ("A③", 312.45, 358.92, (80, 50, 40)), ("A④", 358.92, 380.99, (45, 40, 55)),
    ("尾", 380.99, 395.67, (25, 25, 30)),
]

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
title = ImageFont.truetype(FC, 18)
lab = ImageFont.truetype(F, 12)
small = ImageFont.truetype(F, 10)

LEFT, RIGHT = 70, W - 30
TOP, BOT = 70, H - 60
def X(t): return LEFT + (RIGHT - LEFT) * t / DUR

# section bands + labels
for name, a, b, col in SECTIONS:
    d.rectangle([X(a), TOP - 18, X(b), BOT], fill=col)
    d.line([(X(a), TOP - 18), (X(a), BOT)], fill=(70, 70, 80))
    d.text((X(a) + 3, TOP - 34), name, font=lab, fill=(190, 190, 200))
d.text((LEFT, 18), "四轨包络 × 段落（100 Hz，dBFS）", font=title, fill=(230, 230, 235))

# lanes
lanes = [("vocals", (240, 140, 120)), ("drums", (120, 200, 240)), ("bass", (150, 220, 160)), ("other", (220, 200, 120))]
lane_h = (BOT - TOP) / 4
for i, (name, col) in enumerate(lanes):
    top = TOP + i * lane_h
    bot = top + lane_h - 8
    d.text((8, top + 4), name, font=lab, fill=col)
    d.line([(LEFT, bot), (RIGHT, bot)], fill=(40, 40, 50))
    e = env[name]
    pts = []
    for px in range(LEFT, RIGHT, 2):
        t = (px - LEFT) / (RIGHT - LEFT) * DUR
        j = int(t * 100)
        v = float(e[max(0, j - 6):j + 6].max()) if j < len(e) else 0.0
        db = 20 * np.log10(v + 1e-9)
        u = (db + 70) / 50.0
        u = max(0.0, min(1.0, u))
        pts.append((px, bot - u * (lane_h - 16)))
    d.line(pts, fill=col, width=1)

# the 14 s drop
a, b = 147.0, 161.0
d.rectangle([X(a), TOP - 18, X(b), BOT], outline=(255, 120, 90))
d.text((X(a) + 3, BOT + 6), "147–161 骤静", font=small, fill=(255, 150, 120))
d.text((X(387) + 3, BOT + 6), "387 硬切", font=small, fill=(255, 150, 120))

# time axis
for t in range(0, 400, 30):
    d.line([(X(t), BOT), (X(t), BOT + 4)], fill=(90, 90, 100))
    d.text((X(t) - 8, BOT + 16), f"{t//60}:{t%60:02d}", font=small, fill=(140, 140, 150))

img.save(OUT)
print("wrote", OUT)
