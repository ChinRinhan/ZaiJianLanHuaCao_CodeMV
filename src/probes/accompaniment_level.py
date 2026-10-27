# -*- coding: utf-8 -*-
"""How loud is the accompaniment in A② vs A③ vs A④?

The picture for A② empties the world out ("只剩声音"): the ridge, the orchids, the
spectrum plate and the human columns all fade away, and only the chorus lines stay.
That decision rests on ONE measurement — A② is the most accompaniment-free section of
the song. If A③ / A④ have their accompaniment back, the same empty world would be a
lie, and the ending would show a stage that the recording does not support.

So: measure every instrumental stem's RMS level, per section, relative to the lead
vocal. The stems are the director's 17-track separation.

Run: ./.venv-audio/Scripts/python.exe src/probes/accompaniment_level.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "再见 兰花草 - 张雨生_分轨"
OUT = ROOT / "data" / "accompaniment_level.json"

SECTIONS = [
    ("A1", 67.85, 103.84),
    ("B1", 103.84, 136.60),
    ("B2", 245.79, 266.31),
    ("A2", 266.31, 312.45),
    ("A3", 312.45, 358.92),
    ("A4", 358.92, 387.00),
]

# the accompaniment (everything that is not a voice)
INSTRUMENTS = [
    "低音提琴", "军鼓", "吉他", "嗵鼓", "小提琴", "底鼓", "弦乐合奏",
    "拉弦乐器", "电吉他", "贝斯", "踩镲(Hi-Hat)", "钢琴", "键盘", "鼓组",
]
LEAD = "主唱人声"
BACK = "背景和声"


def _load(name):
    x, sr = sf.read(str(STEMS / f"再见 兰花草 - 张雨生_{name}.mp3"), dtype="float32")
    if x.ndim == 2:
        x = x.mean(axis=1)
    return x, sr


def _rms_db(x, sr, a, b):
    s = x[int(a * sr):int(b * sr)]
    if s.size == 0:
        return -120.0
    return float(20.0 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-12))


def main():
    if not STEMS.exists():
        print("no separated stems at", STEMS)
        return
    lead, sr = _load(LEAD)
    back, _ = _load(BACK)
    tracks = {}
    for name in INSTRUMENTS:
        x, s2 = _load(name)
        tracks[name] = (x, s2)

    res = {}
    print("%-4s %8s %8s   %s" % ("sec", "lead", "back", "  ".join("%-9s" % n[:9] for n in INSTRUMENTS)))
    for name, a, b in SECTIONS:
        ld = _rms_db(lead, sr, a, b)
        bd = _rms_db(back, sr, a, b)
        row = {"lead_db": round(ld, 1), "back_db": round(bd, 1), "stems": {}}
        cells = []
        for iname in INSTRUMENTS:
            x, s2 = tracks[iname]
            d = _rms_db(x, s2, a, b)
            rel = d - ld
            row["stems"][iname] = round(rel, 1)
            cells.append("%-9.1f" % rel)
        # the accompaniment as a whole: the loudest single instrument, and their mean
        vals = list(row["stems"].values())
        row["max_instrument_rel_db"] = round(max(vals), 1)
        row["mean_instrument_rel_db"] = round(float(np.mean(vals)), 1)
        res[name] = row
        print("%-4s %8.1f %8.1f   %s" % (name, ld, bd, "  ".join(cells)))
        print("     -> loudest instrument %+.1f dB vs lead, mean %+.1f dB"
              % (row["max_instrument_rel_db"], row["mean_instrument_rel_db"]))
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
