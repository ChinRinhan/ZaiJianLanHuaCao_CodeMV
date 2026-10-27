# -*- coding: utf-8 -*-
"""Check the stereo claim: 江建民 left / 李庭匡 right guitar solos in the 121 s break."""
from __future__ import annotations

import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2]))   # 让 import preview/tk 仍然可用

import subprocess, wave
from pathlib import Path
import numpy as np
from scipy.signal import stft

ROOT = Path(__file__).resolve().parents[2]
from media import FFMPEG as FF  # noqa: E402
SRC = ROOT / "input" / "song.flac"
OUT = ROOT / "data" / "audio" / "stereo22050.wav"
OUT.parent.mkdir(parents=True, exist_ok=True)

if not OUT.exists():
    subprocess.run([str(FF), "-v", "error", "-y", "-i", str(SRC), "-ac", "2", "-ar", "22050",
                    "-c:a", "pcm_s16le", str(OUT)], check=True)

with wave.open(str(OUT), "rb") as w:
    n, ch = w.getnframes(), w.getnchannels()
    raw = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
pcm = raw.reshape(-1, 2)
sr = 22050
hop = 220
print(f"stereo: {len(pcm)/sr:.3f}s  ch={ch}")

def env(x):
    return np.sqrt(np.convolve(x ** 2, np.ones(1024) / 1024, mode="same"))[::hop]

L, R = env(pcm[:, 0]), env(pcm[:, 1])
n = min(len(L), len(R))
L, R = L[:n], R[:n]
mid = (L + R) / 2
side = (L - R) / 2
print(f"frames {n} @ {sr/hop:.0f} fps")

def db(x):
    return 20 * np.log10(np.maximum(x, 1e-6))

# section-wise side/mid ratio
sections = [("intro", 0, 67.85), ("A1", 67.85, 103.84), ("B1", 103.84, 122.0),
            ("break", 122.0, 245.79), ("B2", 245.79, 266.31), ("A2", 266.31, 312.45),
            ("A3", 312.45, 358.92), ("A4", 358.92, 395.667)]
print("\nsection   mid dB   side dB  side-mid  corr(L,R)")
for name, a, b in sections:
    i0, i1 = int(a * sr / hop), int(min(n, b * sr / hop))
    if i1 <= i0:
        continue
    m, s_ = mid[i0:i1], side[i0:i1]
    l, r = L[i0:i1], R[i0:i1]
    corr = float(np.corrcoef(l, r)[0, 1])
    print(f"{name:8} {db(m).mean():7.1f} {db(s_).mean():8.1f} {db(s_).mean()-db(m).mean():+8.1f} {corr:8.3f}")

# inside the break: who is louder, per 2 s window
print("\nbreak 122-246 s, 2 s windows: L-R balance (+ = right louder)")
i0, i1 = int(122 * sr / hop), int(246 * sr / hop)
rows = []
for k in range(i0, i1, int(2 * sr / hop)):
    seg_l, seg_r = db(L[k:k + int(2 * sr / hop)]).mean(), db(R[k:k + int(2 * sr / hop)]).mean()
    rows.append((k * hop / sr, seg_l, seg_r, seg_r - seg_l))
for t, l, r, d in rows[::3]:
    bar = ("R" * int(max(0, d))) + ("L" * int(max(0, -d)))
    print(f"  {t:6.1f}s  L {l:6.1f}  R {r:6.1f}  d {d:+5.1f}  {bar}")

# spectral: is one side brighter (lead) vs darker (rhythm)?
f, _, ZL = stft(pcm[:, 0], fs=sr, nperseg=1024, noverlap=804, boundary=None, padded=False)
_, _, ZR = stft(pcm[:, 1], fs=sr, nperseg=1024, noverlap=804, boundary=None, padded=False)
def centroid(Z):
    m = np.abs(Z)
    return (f[:, None] * m).sum(0) / (m.sum(0) + 1e-9)
cL, cR = centroid(ZL), centroid(ZR)
j0, j1 = int(122 * 100), int(246 * 100)
print(f"\nbreak centroid: L {cL[j0:j1].mean():.0f} Hz  R {cR[j0:j1].mean():.0f} Hz")
print(f"whole song:     L {cL.mean():.0f} Hz  R {cR.mean():.0f} Hz")
