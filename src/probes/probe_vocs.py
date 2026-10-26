# -*- coding: utf-8 -*-
"""Answer one question only: is there a voice in 0:44-1:04, or is that the guitar leaking into the vocal stem?

Separates two short slices (intro and a known-sung line), then compares the vocal stem's
harmonicity (autocorrelation salience) and band concentration.
"""
from __future__ import annotations

import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2]))   # 让 import preview/tk 仍然可用


import os
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "data" / "models" / "stems"
os.environ.setdefault("DSH_AUDIO_MODEL_DIR", str(MODEL_DIR))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from demucs_onnx import inference as inf  # noqa: E402

_local = MODEL_DIR / "htdemucs_fp16weights.onnx"
if _local.exists():
    inf.download_single_model = lambda *a, **k: str(_local)  # noqa: ARG005

SLICES = {
    "intro_44_64": (44.0, 64.0),      # disputed: tool says vocals start at 48
    "verse_70_90": (70.0, 90.0),      # known sung line ("谁从山中来…")
}


def cut(src: Path, a: float, b: float, out: Path):
    with wave.open(str(src), "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        w.setpos(int(a * sr))
        frames = w.readframes(min(int((b - a) * sr), n - int(a * sr)))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr); w.writeframes(frames)


def pitch_salience(x, sr, fmin=80, fmax=800):
    x = x - x.mean()
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    lo, hi = int(sr / fmax), int(sr / fmin)
    if hi >= len(ac) or hi <= lo:
        return 0.0
    return float(ac[lo:hi].max() / (ac[0] + 1e-12))


def band_concentration(x, sr, lo=300, hi=3000):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float(spec[(f >= lo) & (f < hi)].sum() / (spec.sum() + 1e-9))


def spectral_flatness(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) + 1e-9
    return float(np.exp(np.mean(np.log(spec))) / np.mean(spec))


mix_wav = ROOT / "data" / "audio" / "mono22050.wav"
mono = ROOT / "data" / "audio" / "_slice.wav"
print("cutting slices from mono mix (22.05 kHz) ...", flush=True)

for name, (a, b) in SLICES.items():
    cut(mix_wav, a, b, mono)
    print(f"\n=== {name} {a:.0f}-{b:.0f}s ===", flush=True)
    res = inf.separate(str(mono), None, model="htdemucs", precision="fp16weights",
                       cache_dir=str(MODEL_DIR), progress=False)
    sr = inf.SAMPLE_RATE
    for stem in ("vocals", "other", "drums", "bass"):
        if stem not in res:
            continue
        arr = np.asarray(res[stem], dtype=np.float32)
        if arr.ndim == 2:
            arr = arr.mean(axis=0)
        # take the middle 4 s, away from edges
        mid = arr[len(arr) // 2 - sr * 2: len(arr) // 2 + sr * 2]
        if len(mid) < sr:
            continue
        rms = 20 * np.log10(np.sqrt((mid ** 2).mean()) + 1e-9)
        print(f"  {stem:7} rms {rms:6.1f} dB | pitch salience {pitch_salience(mid, sr):.3f} "
              f"| band 300-3k {band_concentration(mid, sr):.2f} | flatness {spectral_flatness(mid, sr):.4f}",
              flush=True)
