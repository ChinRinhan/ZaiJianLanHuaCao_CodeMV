# -*- coding: utf-8 -*-
"""Two questions the ear cannot settle precisely:
   1. how many semitones does the key move at A③ (312.45) and again at A④?
   2. where exactly does the final fade become inaudible?
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import librosa

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "input" / "song.flac"
MIX = ROOT / "data" / "audio" / "mono22050.wav"

y, sr = librosa.load(str(MIX), sr=22050, mono=True)
print(f"loaded {len(y)/sr:.1f}s @ {sr}")

SECTIONS = [("A②", 266.31, 312.45), ("A③", 312.45, 358.92), ("A④", 358.92, 380.99),
            ("B①", 103.84, 122.0), ("A①", 67.85, 103.84)]

chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512, bins_per_octave=36)
times = librosa.times_like(chroma, sr=sr, hop_length=512)

def profile(a, b):
    m = (times >= a) & (times < b)
    v = chroma[:, m].mean(axis=1)
    return v / (v.sum() + 1e-12)

prof = {name: profile(a, b) for name, a, b in SECTIONS}

def best_shift(p, q):
    """Rotate q against p; return the semitone shift (0..11) that best matches."""
    scores = []
    for k in range(12):
        scores.append(float(np.dot(p, np.roll(q, k))))
    k = int(np.argmax(scores))
    return k, scores[k], scores

print("\nkey-shift estimates (semitones up from the earlier section):")
for a, b in [("A②", "A③"), ("A③", "A④"), ("A①", "A②"), ("B①", "A②")]:
    k, s, _ = best_shift(prof[a], prof[b])
    print(f"  {a} -> {b}: +{k} semitones   (match {s:.3f})")

# per-section key estimate (Krumhansl-ish, major/minor templates)
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
for name in ("A①", "B①", "A②", "A③", "A④"):
    p = prof[name]
    best = max(((float(np.corrcoef(np.roll(MAJ, i), p)[0, 1]), f"{NAMES[i]} major") for i in range(12)))
    bestm = max(((float(np.corrcoef(np.roll(MIN, i), p)[0, 1]), f"{NAMES[i]} minor") for i in range(12)))
    pick = best if best[0] >= bestm[0] else bestm
    print(f"  {name}: {pick[1]:10} r={pick[0]:+.2f}")

# ---- the fade
print("\nfinal fade, 0.5 s windows (dBFS):")
db = []
for t0 in np.arange(378, 395.5, 0.5):
    seg = y[int(t0 * sr):int((t0 + 0.5) * sr)]
    if len(seg) < sr // 4:
        break
    db.append((round(float(t0), 1), round(float(20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)), 1)))
for i in range(0, len(db), 4):
    print("  " + "  ".join(f"{t:5.1f}:{v:5.1f}" for t, v in db[i:i + 4]))
last_audible = max((t for t, v in db if v > -50), default=None)
print(f"\nlast window above -50 dB: {last_audible} s")
