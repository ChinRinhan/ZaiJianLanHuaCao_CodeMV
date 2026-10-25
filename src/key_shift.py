# -*- coding: utf-8 -*-
"""How many semitones does the key move between the A rounds?

The same phrase ("谁从山中来…") is sung in A①/A②/A③/A④. Separate just those few seconds,
then compare the vocal stem's median f0 between rounds.
"""
from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np
import librosa

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "models" / "stems"
MIX = ROOT / "data" / "audio" / "mono22050.wav"
os.environ.setdefault("DSH_AUDIO_MODEL_DIR", str(MODEL_DIR))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from demucs_onnx import inference as inf  # noqa: E402

_local = MODEL_DIR / "htdemucs_fp16weights.onnx"
if _local.exists():
    inf.download_single_model = lambda *a, **k: str(_local)  # noqa: ARG005

ROUNDS = [("A①", 68.2), ("A②上", 267.0), ("A②下", 290.3), ("A③上", 313.1), ("A③下", 335.4), ("A④上", 359.6)]
WIN = 7.0


def cut(a: float, b: float, out: Path):
    with wave.open(str(MIX), "rb") as w:
        sr = w.getframerate()
        w.setpos(int(a * sr))
        with wave.open(str(out), "wb") as o:
            o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr)
            o.writeframes(w.readframes(int((b - a) * sr)))


def median_f0(x, sr):
    f, vf, _ = librosa.pyin(x, fmin=90, fmax=800, sr=sr, frame_length=2048)
    ok = f[~np.isnan(f)]
    if len(ok) < 10:
        return None, 0.0
    return float(np.median(ok)), float(len(ok) / max(1, len(f)))


results = {}
tmp = ROOT / "data" / "audio" / "_slice.wav"
for name, a in ROUNDS:
    cut(a, a + WIN, tmp)
    res = inf.separate(str(tmp), None, model="htdemucs", precision="fp16weights",
                       cache_dir=str(MODEL_DIR), progress=False)
    sr = inf.SAMPLE_RATE
    voc = np.asarray(res["vocals"], dtype=np.float32)
    if voc.ndim == 2:
        voc = voc.mean(axis=0)
    # downsample for pyin speed
    voc22 = librosa.resample(voc, orig_sr=sr, target_sr=22050)
    med, voiced = median_f0(voc22, 22050)
    results[name] = med
    print(f"{name} start {a:6.1f}s  f0={med if med is None else round(med,1)} Hz  voiced={voiced*100:.0f}%", flush=True)

base = results.get("A①")
print("\nsemitone differences vs A①:")
for name, med in results.items():
    if med and base:
        st = 12 * np.log2(med / base)
        print(f"  {name}: {st:+.1f} semitones")
