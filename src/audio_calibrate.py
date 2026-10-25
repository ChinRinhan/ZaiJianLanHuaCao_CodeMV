# -*- coding: utf-8 -*-
"""M0 pass 2: vocal-band onset, global LRC offset calibration, and the ending, at fine resolution."""
from __future__ import annotations
import json, wave
from pathlib import Path

import numpy as np
from scipy.signal import stft

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "data" / "audio"
SR, HOP, WIN = 22050, 220, 1024
FA = SR / HOP

with wave.open(str(AUD / "mono22050.wav"), "rb") as w:
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
dur = len(pcm) / SR

f, t, Z = stft(pcm, fs=SR, nperseg=WIN, noverlap=WIN - HOP, boundary=None, padded=False)
mag = np.abs(Z)
band = (f >= 300) & (f <= 3000)          # voice-heavy band
vflux = np.maximum(0.0, np.diff(mag[band], axis=1)).sum(axis=0)
vflux = np.concatenate([[0.0], vflux])
vflux /= (np.percentile(vflux, 99) + 1e-9)

db = 20 * np.log10(np.maximum(np.sqrt(np.convolve(pcm ** 2, np.ones(WIN) / WIN, mode="same"))[::HOP][: mag.shape[1]], 1e-6))

tl = json.loads((ROOT / "data" / "timeline.json").read_text(encoding="utf-8"))
lines = tl["lines"]

def best(t0, lo=-0.25, hi=0.85, env=vflux):
    a, b = int((t0 + lo) * FA), int((t0 + hi) * FA)
    a, b = max(0, a), min(len(env), b)
    if b <= a:
        return None, 0.0
    i = a + int(np.argmax(env[a:b]))
    return i / FA, float(env[i])

offs, strengths = [], []
for ln in lines:
    if ln["t"] < 5:                        # credits lines are not sung
        continue
    on, s = best(ln["t"])
    if on is None:
        continue
    offs.append(on - ln["t"]); strengths.append(s)

offs = np.array(offs); strengths = np.array(strengths)
w = strengths > np.percentile(strengths, 20)
med = float(np.median(offs[w])); mad = float(np.median(np.abs(offs[w] - med)))
print(f"vocal-band onset vs LRC, {len(offs)} lines")
print(f"  median offset {med:+.3f} s   MAD {mad:.3f} s   mean {offs[w].mean():+.3f}")
print(f"  quantiles 10/25/50/75/90: {np.percentile(offs, [10,25,50,75,90]).round(3)}")

BOUND = [("前奏","A①",67.85),("A①","B①",103.84),("B①","间奏",122.00),("间奏","B②",245.79),
         ("B②","A②-上",266.31),("A②-上","A②-下",289.64),("A②-下","A③-上",312.45),
         ("A③-上","A③-下",334.69),("A③-下","A④-上",358.92),("A④-上","A④-下",380.99)]
print("\nboundaries with vocal-band flux:")
rows = []
for prev, nxt, t0 in BOUND:
    on, s = best(t0, -0.3, 0.9)
    rows.append({"from": prev, "to": nxt, "t_lrc": t0, "onset": round(on, 3),
                 "offset": round(on - t0, 3), "strength": round(s, 2)})
    print(f"  {prev:>6}->{nxt:<6} lrc {t0:7.2f}  vocal-onset {on:7.2f}  d={on-t0:+.3f}  s={s:.2f}")

print("\nfirst 3 s, 0.1 s windows (dB):")
print("  " + " ".join(f"{i*0.1:.1f}:{np.percentile(db[int(i*0.1*FA):int((i*0.1+0.1)*FA)],90):.0f}" for i in range(30)))
print("\nlast 12 s, 0.25 s windows (dB):")
print("  " + " ".join(f"{384+i*0.25:.2f}:{np.percentile(db[int((384+i*0.25)*FA):int((384+i*0.25+0.25)*FA)],90):.0f}"
                      for i in range(47)))

tl["calibration"] = {"median_lrc_offset_s": round(med, 3), "mad_s": round(mad, 3),
                     "n_lines": int(len(offs)), "vocal_onset_boundaries": rows}
tl["song"]["leading_silence_s"] = round(next(i for i, v in enumerate(db) if v > -45) / FA, 3)
(ROOT / "data" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nupdated timeline.json")
