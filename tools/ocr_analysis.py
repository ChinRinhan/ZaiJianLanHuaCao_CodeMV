# -*- coding: utf-8 -*-
"""OCR the commentary band of the analysis video into a timestamped text file."""
from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "out" / "ref-frames"
OUT = ROOT / "out" / "analysis-video-ocr.txt"

engine = RapidOCR()
rows = []
for p in sorted(FRAMES.glob("c*.png")):
    t = int(re.search(r"c(\d+)", p.name).group(1))
    res, _ = engine(str(p))
    txt = " ".join(r[1] for r in res) if res else ""
    txt = re.sub(r"\s+", " ", txt).strip()
    rows.append((t, txt))
    print(f"{t:4d}s  {txt}", flush=True)

# collapse repeats (the same caption stays for seconds)
merged = []
for t, txt in rows:
    if merged and merged[-1][1] == txt:
        merged[-1] = (merged[-1][0], txt, t)
    else:
        merged.append((t, txt, t))

lines = []
for item in merged:
    a, txt, b = item if len(item) == 3 else (item[0], item[1], item[0])
    if txt:
        lines.append(f"[{a:3d}-{b:3d}s] {txt}")
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"\nwrote {OUT}  ({len(lines)} distinct captions)")