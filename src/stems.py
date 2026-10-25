# -*- coding: utf-8 -*-
"""Split the song into 4 stems and save 100 Hz RMS envelopes.

Outputs:
  data/audio/stem_{vocals,drums,bass,other}.npy   (100 Hz, float32)
  data/audio/stems_summary.json                   (per-section means + conflict checks)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "input" / "song.flac"
MODEL_DIR = ROOT / "data" / "models" / "stems"
AUD = ROOT / "data" / "audio"
AUD.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("DSH_AUDIO_MODEL_DIR", str(MODEL_DIR))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from demucs_onnx import inference as inf  # noqa: E402

_local = MODEL_DIR / "htdemucs_fp16weights.onnx"
if _local.exists():
    inf.download_single_model = lambda *a, **k: str(_local)  # noqa: ARG005

print("separating ...", flush=True)
res = inf.separate(str(SRC), None, model="htdemucs", precision="fp16weights",
                   cache_dir=str(MODEL_DIR), progress=False)
SR = inf.SAMPLE_RATE
print("sample rate", SR, "stems", list(res.keys()), flush=True)

HOP = 441          # 100 Hz at 44.1 kHz
names = []
for name, wav in res.items():
    arr = np.asarray(wav, dtype=np.float32)
    if arr.ndim == 2:                       # (channels, samples)
        mono = arr.mean(axis=0)
    else:
        mono = arr
    n = len(mono) // HOP * HOP
    env = np.sqrt((mono[:n].reshape(-1, HOP) ** 2).mean(axis=1)).astype(np.float32)
    np.save(AUD / f"stem_{name}.npy", env)
    names.append(name)
    print(f"  {name}: {len(env)} frames, mean {20*np.log10(env.mean()+1e-9):.1f} dBFS", flush=True)

# ---- section means (LRC times, no offset)
SECTIONS = [
    ("intro", 0.0, 67.85), ("A1", 67.85, 103.84), ("B1", 103.84, 122.0),
    ("break_a", 122.0, 146.0), ("break_quiet", 147.0, 161.0), ("break_solo", 162.0, 190.0),
    ("break_chunks", 190.0, 210.0), ("break_full", 211.0, 245.79),
    ("B2", 245.79, 266.31), ("A2", 266.31, 312.45), ("A3", 312.45, 358.92),
    ("A4", 358.92, 380.99), ("tail", 387.0, 395.0),
]
envs = {n: np.load(AUD / f"stem_{n}.npy") for n in names}
summary = {"sample_rate": SR, "sections": {}, "checks": {}}
for label, a, b in SECTIONS:
    row = {}
    for n, e in envs.items():
        seg = e[int(a * 100):int(b * 100)]
        row[n] = round(float(20 * np.log10(seg.mean() + 1e-9)), 1) if len(seg) else None
    summary["sections"][label] = row
    print(f"{label:13} " + "  ".join(f"{k}={v}" for k, v in row.items()), flush=True)

# ---- the 0:48 question: is the vocals stem a voice or instrument bleed?
def band_ratio(x, sr, lo, hi):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float(spec[(f >= lo) & (f < hi)].sum() / (spec.sum() + 1e-9))

def pitch_salience(x, sr, fmin=80, fmax=1000):
    """Normalised autocorrelation peak: high for a sustained pitched sound, low for broadband."""
    x = x - x.mean()
    if len(x) < sr // 10:
        return 0.0
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    lo, hi = int(sr / fmax), int(sr / fmin)
    seg = ac[lo:hi]
    if len(seg) == 0:
        return 0.0
    return float(seg.max() / (ac[0] + 1e-12))

voc = np.asarray(res["vocals"], dtype=np.float32)
if voc.ndim == 2:
    voc = voc.mean(axis=0)
def probe(label, a, b):
    seg = voc[int(a * SR):int(b * SR)]
    if len(seg) < SR // 2:
        return None
    # flatten frequency: a voice concentrates energy in 300-3000, an instrument solo may not
    r = band_ratio(seg, SR, 300, 3000)
    p = pitch_salience(seg[: SR * 2], SR)
    db = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)
    print(f"  {label:12} {a:6.1f}-{b:5.1f}s  rms {db:6.1f} dB  band300-3k {r:.2f}  pitch {p:.2f}")
    return {"rms_db": round(float(db), 1), "band_ratio": round(r, 3), "pitch_salience": round(p, 3)}

print("\nvocal stem probes:", flush=True)
summary["checks"]["vocals_48_56"] = probe("48-56", 48, 56)
summary["checks"]["vocals_58_66"] = probe("58-66", 58, 66)
summary["checks"]["vocals_70_80"] = probe("70-80", 70, 80)
summary["checks"]["vocals_90_100"] = probe("90-100", 90, 100)
summary["checks"]["vocals_150_158"] = probe("150-158", 150, 158)
summary["checks"]["vocals_180_190"] = probe("180-190", 180, 190)
summary["checks"]["vocals_230_240"] = probe("230-240", 230, 240)

(AUD / "stems_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwrote", AUD / "stems_summary.json", flush=True)
