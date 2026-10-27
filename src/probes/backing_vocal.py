# -*- coding: utf-8 -*-
"""One-shot probe: the backing vocal, measured on the REAL stems (not on Demucs' four).

导演（10:5x）：「第一次『宣言』的时候明显只有宝哥一个声音，到 4:05 的第二次的时候，就有宝哥
多音轨的和声或『合唱』，刚好预告最后的『齐唱』段」。

我们手上原来只有 Demucs 的四轨（vocals / other / bass / drums），而 Demucs 把原唱的所有人声
压进 vocals 一轨——所以三次探针（vocal_layers / vocal_harmony / vocal_pitches）都测不出差别。
导演随后放进来一份**原曲分轨**（17 轨，data 目录同级的「再见 兰花草 - 张雨生_分轨/」），
里面有 `主唱人声` 和 `背景和声` 两轨——这才是这条线索的证据。

这份探针把两轨的**相对电平**按四句分别量出来，交给画面：层数与亮度 = 实测的和声占比。
不是编的。

Run: ./.venv-audio/Scripts/python.exe src/probes/backing_vocal.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "再见 兰花草 - 张雨生_分轨"
OUT = ROOT / "data" / "backing_vocal.json"

# 四句「给我…」的实测起音（word_times_v2）；B② 的句子比 B① 长一点，按实测切
B1 = [("B1", 1, 103.84, 106.20), ("B1", 2, 106.21, 108.38), ("B1", 3, 108.38, 110.70),
      ("B1", 4, 110.70, 112.95)]
B2 = [("B2", 1, 245.79, 247.95), ("B2", 2, 247.95, 249.99), ("B2", 3, 249.99, 252.21),
      ("B2", 4, 252.21, 254.36)]


def rms_db(x, sr, t0, t1):
    seg = x[int(t0 * sr):int(t1 * sr)]
    if seg.size == 0:
        return -120.0
    return float(20.0 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12))


def main():
    if not STEMS.exists():
        print("no separated stems at", STEMS)
        return
    lead_p = STEMS / "再见 兰花草 - 张雨生_主唱人声.mp3"
    back_p = STEMS / "再见 兰花草 - 张雨生_背景和声.mp3"
    lead, sr = sf.read(str(lead_p), dtype="float32")
    back, _ = sf.read(str(back_p), dtype="float32")
    if lead.ndim == 2:
        lead = lead.mean(axis=1)
    if back.ndim == 2:
        back = back.mean(axis=1)

    res = {"B1": [], "B2": []}
    for grp, lines in (("B1", B1), ("B2", B2)):
        for g, i, t0, t1 in lines:
            ld = rms_db(lead, sr, t0, t1)
            bk = rms_db(back, sr, t0, t1)
            rel = bk - ld                       # 和声比主唱低多少 dB
            res[grp].append({"n": i, "t0": round(t0, 2), "t1": round(t1, 2),
                              "lead_db": round(ld, 1), "back_db": round(bk, 1),
                              "rel_db": round(rel, 1)})
            print("%s #%d  lead %6.1f  back %6.1f  rel %6.1f dB"
                  % (grp, i, ld, bk, rel))

    b1 = res["B1"][-1]["rel_db"]
    b2 = res["B2"][-1]["rel_db"]
    print("\n第 4 句的和声相对电平：B1 %+.1f dB  →  B2 %+.1f dB  (近了 %.1f dB)"
          % (b1, b2, b2 - b1))
    # 画面用的层数：和声每近 3 dB 多一层（-12 dB 无人，-6 dB 两层，-3 dB 三层）
    for grp in ("B1", "B2"):
        for row in res[grp]:
            rel = row["rel_db"]
            layers = 1 if rel < -9 else (2 if rel < -6 else 3)
            row["layers"] = layers
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
