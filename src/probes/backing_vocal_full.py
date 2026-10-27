# -*- coding: utf-8 -*-
"""One-shot probe: the backing vocal, line by line, through the whole second half.

导演（19:26）：「最开始一段（指预备场那一段）还没有『合唱』，后面逐渐增加」

The first measurement (`backing_vocal.py`) covered only the four 「给我…」lines. This one
walks every sung line from B① (1:43) to the end, on the director's 17-track separation
(主唱人声 vs 背景和声), and records how close the backing voice is to the lead.

The result matters for the picture: the relative level is what the number of voices on
screen should follow — it is not a straight line, and pretending it is would be decoration.

Run: ./.venv-audio/Scripts/python.exe src/probes/backing_vocal_full.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "再见 兰花草 - 张雨生_分轨"
OUT = ROOT / "data" / "backing_vocal_full.json"

# every sung line in the second half (word_times_v2, measured)
LINES = [
    ("B1", 1, 103.84, 106.21, "给我一把吉他我来唱"),
    ("B1", 2, 106.21, 108.38, "给我一枝铅笔让我来画"),
    ("B1", 3, 108.38, 110.70, "给我一对翅膀我来飞"),
    ("B1", 4, 110.70, 112.95, "给我一个空间让我转圈"),
    ("B1", 5, 112.95, 115.18, "直到那一天我爱上她"),
    ("B1", 6, 115.18, 117.39, "直到那一天我眼泪滑下"),
    ("B1", 7, 117.39, 119.70, "你只要给我五分钟"),
    ("B1", 8, 119.70, 122.10, "我给你完全不同的感受"),
    ("B2", 1, 245.79, 247.95, "给我一把吉他我来唱"),
    ("B2", 2, 247.95, 249.99, "给我一枝铅笔让我来画"),
    ("B2", 3, 249.99, 252.21, "给我一对翅膀我来飞"),
    ("B2", 4, 252.21, 254.36, "给我一个空间让我转圈"),
    ("B2", 5, 254.36, 256.49, "直到那一天我爱上她"),
    ("B2", 6, 256.49, 260.91, "直到那一天我眼泪滑下"),
    ("B2", 7, 260.91, 263.98, "你只要给我五分钟"),
    ("B2", 8, 263.98, 266.31, "我给你完全不同的感受"),
    ("A2", 1, 266.31, 273.24, "谁从山中来带着兰花草"),
    ("A2", 2, 273.24, 278.57, "也曾勤灌溉长得一园好"),
    ("A2", 3, 278.57, 281.46, "虽然经过许多年"),
    ("A2", 4, 281.46, 284.26, "其人其事渐湮灭"),
    ("A2", 5, 284.26, 289.64, "我就是不能忘掉那盆兰花草"),
    ("A2", 6, 289.64, 296.08, "我往山中行寻找兰花草"),
    ("A2", 7, 296.08, 301.47, "梵音在弦外醉翁意韵妙"),
    ("A2", 8, 301.47, 304.37, "茶花樱花满山开"),
    ("A2", 9, 304.37, 307.11, "杜鹃木棉沿街栽"),
    ("A2", 10, 307.11, 312.45, "谁记得曾经有那一盆兰花草"),
]


def main():
    if not STEMS.exists():
        print("no separated stems at", STEMS)
        return
    lead, sr = sf.read(str(STEMS / "再见 兰花草 - 张雨生_主唱人声.mp3"), dtype="float32")
    back, _ = sf.read(str(STEMS / "再见 兰花草 - 张雨生_背景和声.mp3"), dtype="float32")
    if lead.ndim == 2:
        lead = lead.mean(axis=1)
    if back.ndim == 2:
        back = back.mean(axis=1)

    def db(x, a, b):
        s = x[int(a * sr):int(b * sr)]
        if s.size == 0:
            return -120.0
        return float(20.0 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-12))

    res = []
    for grp, n, t0, t1, text in LINES:
        ld, bk = db(lead, t0, t1), db(back, t0, t1)
        rel = bk - ld
        # how many voices the picture should show: the backing is at -9 dB -> nobody is
        # really there; at -6 dB -> a couple; at 0 dB -> the backing is as loud as the lead.
        if rel < -8.0:
            voices = 1
        elif rel < -6.0:
            voices = 2
        elif rel < -3.5:
            voices = 3
        elif rel < -1.5:
            voices = 4
        elif rel < 0.5:
            voices = 5
        else:
            voices = 6
        res.append({"group": grp, "n": n, "t0": round(t0, 2), "t1": round(t1, 2),
                    "text": text, "lead_db": round(ld, 1), "back_db": round(bk, 1),
                    "rel_db": round(rel, 1), "voices": voices})
        print("%-3s #%-2d  %-14s  lead %6.1f  back %6.1f  rel %+5.1f dB  -> %d voices"
              % (grp, n, text[:12], ld, bk, rel, voices))
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
