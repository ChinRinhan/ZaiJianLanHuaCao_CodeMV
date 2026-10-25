# -*- coding: utf-8 -*-
"""M0 pass 3: unbiased global LRC shift (cross-correlation), first-crossing onsets, tempo candidates."""
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
band = (f >= 300) & (f <= 3000)
v = np.maximum(0.0, np.diff(mag[band], axis=1)).sum(axis=0)
v = np.concatenate([[0.0], v])
v /= (np.percentile(v, 99) + 1e-9)

tl = json.loads((ROOT / "data" / "timeline.json").read_text(encoding="utf-8"))
lines = [l for l in tl["lines"] if l["t"] >= 5]
T = np.array([l["t"] for l in lines])

shifts = np.arange(-0.6, 1.21, 0.01)
score = []
for s in shifts:
    idx = np.clip(((T + s) * FA).astype(int), 0, len(v) - 1)
    score.append(v[idx].mean())
score = np.array(score)
best = shifts[int(np.argmax(score))]
print(f"best global shift (LRC -> audio): {best:+.2f} s   score {score.max():.3f} (at 0: {score[np.argmin(abs(shifts))]:.3f})")

# first-crossing onsets after the (shifted) line start
def first_cross(t0, thr=0.25, guard=0.12):
    a = int((t0 + guard) * FA)
    b = min(len(v), int((t0 + 1.2) * FA))
    seg = v[a:b]
    hits = np.where(seg > thr)[0]
    return (a + hits[0]) / FA if len(hits) else None

offs = []
for t0 in T:
    on = first_cross(t0 + best)
    if on is not None:
        offs.append(on - (t0 + best))
offs = np.array(offs)
print(f"first-crossing offsets after shift: n={len(offs)} median {np.median(offs):+.3f} MAD {np.median(np.abs(offs-np.median(offs))):.3f}")
print(f"  quantiles 10/50/90: {np.percentile(offs,[10,50,90]).round(3)}")

# tempo candidates
env = v - v.mean()
ac = np.correlate(env, env, mode="full")[len(env)-1:]
ac /= ac[0]
cands = []
for lag in range(int(FA*60/220), int(FA*60/50)):
    if ac[lag] > ac[lag-1] and ac[lag] > ac[lag+1]:
        cands.append((60*FA/lag, ac[lag]))
cands.sort(key=lambda x: -x[1])
print("tempo candidates (BPM, score):", [(round(b,1), round(s,3)) for b, s in cands[:6]])

# beat phase for the best candidate
bpm = cands[0][0]
period = 60/bpm
print(f"chosen {bpm:.2f} BPM, period {period:.3f} s; phase fit:")
best_phase, best_score = 0, -1
for ph in np.arange(0, period, 0.01):
    k = np.arange(ph, dur, period)
    idx = np.clip((k*FA).astype(int), 0, len(v)-1)
    sc = v[idx].mean()
    if sc > best_score:
        best_score, best_phase = sc, ph
print(f"  phase {best_phase:.2f} s (first beat), score {best_score:.3f}")

tl["calibration"]["global_shift_s"] = round(float(best), 3)
tl["calibration"]["first_crossing"] = {"n": int(len(offs)), "median": round(float(np.median(offs)), 3)}
tl["song"]["bpm_candidates"] = [[round(b, 1), round(s, 3)] for b, s in cands[:6]]
tl["song"]["beat_period_s"] = round(period, 4)
tl["song"]["beat_phase_s"] = round(float(best_phase), 3)
(ROOT / "data" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
print("updated timeline.json")
