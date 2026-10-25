# -*- coding: utf-8 -*-
"""scene: map song time -> one frame of the film.

Frame = f(t). No cross-frame state. Video time = LRC time + OFFSET (the LRC runs 0.90 s early,
measured by cross-correlating 53 lyric lines against the vocal-band onset envelope).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import preview
import tk

ROOT = Path(__file__).resolve().parents[1]
TL = json.loads((ROOT / "data" / "timeline.json").read_text(encoding="utf-8"))
OFFSET = 0.0          # LRC is the reference; +0.90 was a bad estimate (locked onto sustained vocal energy)
LEAD = 0.06           # lyrics appear a hair before the attack, like a real karaoke machine
FPS = 24
DUR = 395.667
END_CUT = 387.0

LINES = [{"t": l["t"] + OFFSET - LEAD, "text": l["text"]} for l in TL["lines"] if l["t"] >= 5]

# per-character sung times, snapped to the 1/3-beat grid (see clock.py / word_times.json)
_WT_PATH = ROOT / "data" / "word_times.json"
if _WT_PATH.exists():
    _WT = json.loads(_WT_PATH.read_text(encoding="utf-8"))["lines"]
    for _ln, _w in zip(LINES, _WT):
        if _w["text"] == _ln["text"]:
            _ln["times"] = [x + OFFSET - LEAD for x in _w["times"]]
RMS = np.load(ROOT / "data" / "audio" / "rms.npy")
RMS_HZ = 100.0

# the four displacements of A①, on video time
REWRITES = [
    {"at": LINES[0]["t"], "old": "我从山中来 带着兰花草", "new": "谁从山中来 带着兰花草", "idx": 0, "label": "REWRITE 01"},
    {"at": LINES[1]["t"], "old": "种在小园中 希望花开好", "new": "也曾勤灌溉 长得一园好", "idx": -1, "label": "REWRITE 02"},
    {"at": LINES[7]["t"], "old": "一日望三回", "new": "茶花樱花满山开 杜鹃木棉沿街栽", "idx": -1, "label": "REWRITE 03"},
    {"at": LINES[9]["t"], "old": "祝汝满盆花", "new": "谁记得曾经有那一盆兰花草", "idx": -1, "label": "REWRITE 04"},
]
REWRITE_HOLD = 2.6          # seconds a diff stays on screen when its line starts

SECTIONS = [
    # id, start, end, mood, cold, flower, entity, rain, spiral, amp, flower_x, count
    ("intro", 0.0, 67.85, 0.00, 0.00, 0.00, 0.00, 0.00, 0.0, 0.55, 0.72, 1),
    ("A1", 67.85, 103.84, 0.12, 0.00, 0.55, 0.55, 0.10, 0.0, 0.85, 0.72, 1),
    ("B1", 103.84, 122.0, 0.35, 0.00, 0.65, 0.70, 0.15, 0.3, 1.00, 0.70, 1),
    ("break", 122.0, 245.79, 0.25, 0.00, 0.55, 0.00, 0.00, 0.0, 0.55, 0.72, 1),
    ("B2", 245.79, 266.31, 0.10, 0.00, 0.60, 0.35, 0.00, 0.0, 0.80, 0.70, 1),
    ("A2", 266.31, 312.45, 0.00, 0.35, 0.80, 0.80, 0.10, 0.2, 1.00, 0.66, 3),
    ("A3", 312.45, 358.92, 0.00, 1.00, 1.00, 0.95, 0.25, 1.0, 1.20, 0.62, 5),
    ("A4", 358.92, 380.99, 0.00, 0.20, 0.45, 0.25, 0.00, 0.0, 0.85, 0.50, 1),
]


def rms_at(t: float) -> float:
    i = int(t * RMS_HZ)
    if i < 0 or i >= len(RMS):
        return 0.0
    seg = RMS[max(0, i - 12):i + 12]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def section_at(t: float):
    for s in SECTIONS:
        if s[1] <= t < s[2]:
            return s
    return SECTIONS[-1]


def line_at(t: float):
    cur = None
    nxt = None
    for i, l in enumerate(LINES):
        if l["t"] <= t:
            cur = l
            nxt = LINES[i + 1] if i + 1 < len(LINES) else None
        else:
            break
    return cur, nxt


def rewrite_at(t: float):
    for r in REWRITES:
        if r["at"] <= t < r["at"] + REWRITE_HOLD:
            return (r["old"], r["new"], r["idx"], r["label"])
    return None


def score_at(t: float) -> float:
    if t < 67.85:
        return 0.0
    if t < 103.84:
        return 61.0 + 17.0 * (t - 67.85) / 36.0
    if t < 122.0:
        return 99.4
    if t < 245.79:
        return 0.0
    if t < 266.31:
        return 0.0
    if t < 312.45:
        return 70.0 + 20.0 * (t - 266.31) / 46.14
    if t < 358.92:
        return 99.1
    return max(0.0, 99.1 * (1 - (t - 358.92) / 22.0))


def level_at(t: float) -> float:
    r = rms_at(t)
    return max(0.02, min(1.0, (r / 0.16) ** 0.6))


def amp_at(t: float, base: float) -> float:
    """Ridge amplitude follows the low-frequency energy: quiet passages flatten the mountains."""
    return base * (0.55 + 1.05 * level_at(t))


def _normal(t: float):
    s = section_at(t)
    _id, _s, _e, mood, cold, flower, entity, rain, spiral, amp, fx, cnt = s
    cur, nxt = line_at(t)
    rw = rewrite_at(t)
    lyric = ("", "")
    if cur and not rw:
        lyric = (cur["text"], nxt["text"] if nxt else "")
    progress = t / DUR
    pen = None
    if cur and not rw:
        span = (nxt["t"] - cur["t"]) if nxt else 2.6
        pen = min(1.0, max(0.0, (t - cur["t"]) / max(0.5, span * 0.86)))
    return preview.compose(
        t,
        boot=1.0 if t >= 8.0 else max(0.12, t / 8.0),
        lyric=lyric,
        cue="KEY  +2" if 312.45 <= t < 318.0 else None,
        score=score_at(t),
        level=level_at(t),
        mood=mood, cold=cold, flower=flower, entity=entity, rain=rain, spiral=spiral,
        seed=3 + int(t // 30),
        glow=0.55 if cold < 0.5 else 0.75,
        progress=progress,
        amp_scale=amp_at(t, amp),
        flower_x=fx,
        flower_count=cnt,
        rewrite=rw,
        collapsed=t >= 266.31,
        pen=pen,
        pen_times=(cur.get("times") if (cur and not rw) else None),
    )


def frame(t: float):
    """0-5.6 s: the disc goes in. 5.6-6.4 s: crossfade into the running machine."""
    if t < 5.6:
        return preview.intro_scene(t)
    if t < 6.4:
        u = (t - 5.6) / 0.8
        return Image.blend(preview.intro_scene(t), _normal(t), u)
    return _normal(t)
