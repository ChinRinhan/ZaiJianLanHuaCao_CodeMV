# -*- coding: utf-8 -*-
"""Extract the VOCALS stem and its spectral flux — the input for per-character alignment.

plan/17 §7 (档 B): "人声轨谱通量 + 网格 Viterbi". The 100 Hz RMS envelopes that
data/audio/stem_*.npy hold are far too coarse to place a single character: at 100 Hz one
sample is 10 ms, but what we need is the *syllable* onsets inside a line. So this script
re-runs the separator (the model is local) and keeps the actual waveform of the vocals,
then writes a spectral-flux curve at ~172 Hz.

Outputs:
  data/audio/stems_wav/vocals.wav     mono 44.1 kHz, 16-bit
  data/audio/vocals_flux.npy          positive spectral flux, ~172 Hz
  data/audio/vocals_flux.json         {sr, hop, n_fft, rate, len}

Run with the audio venv:
  ./.venv-audio/Scripts/python.exe src/stems_flux.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "input" / "song.flac"
MODEL_DIR = ROOT / "data" / "models" / "stems"
AUD = ROOT / "data" / "audio"
WAV_DIR = AUD / "stems_wav"

os.environ.setdefault("DSH_AUDIO_MODEL_DIR", str(MODEL_DIR))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from demucs_onnx import inference as inf  # noqa: E402

_local = MODEL_DIR / "htdemucs_fp16weights.onnx"
if _local.exists():
    inf.download_single_model = lambda *a, **k: str(_local)  # noqa: ARG005

N_FFT = 1024
HOP = 256


def main():
    import soundfile as sf

    WAV_DIR.mkdir(parents=True, exist_ok=True)
    vw = WAV_DIR / "vocals.wav"
    if vw.exists():
        # the separator already ran once; re-running it costs minutes and gives the same wav
        print("using existing", vw, flush=True)
        mono, sr = sf.read(str(vw), dtype="float32")
        if mono.ndim == 2:
            mono = mono.mean(axis=1)
    else:
        print("separating ...", flush=True)
        res = inf.separate(str(SRC), None, model="htdemucs", precision="fp16weights",
                           cache_dir=str(MODEL_DIR), progress=False)
        sr = inf.SAMPLE_RATE
        print("sample rate", sr, "stems", list(res.keys()), flush=True)
        for name, wav in res.items():
            arr = np.asarray(wav, dtype=np.float32)
            m = arr.mean(axis=0) if arr.ndim == 2 else arr
            p = WAV_DIR / f"{name}.wav"
            sf.write(str(p), m, sr, subtype="PCM_16")
            print(f"  {name}: wav {p.stat().st_size/1048576:.1f} MB", flush=True)
            if name == "vocals":
                mono = m

    flux_out = _flux(mono, sr)
    np.save(AUD / "vocals_flux.npy", flux_out["flux"])
    (AUD / "vocals_flux.json").write_text(
        json.dumps({k: v for k, v in flux_out.items() if k != "flux"}, indent=1),
        encoding="utf-8")
    print("wrote", AUD / "vocals_flux.npy", flux_out["len"], "frames @",
          round(flux_out["rate"], 2), "Hz", flush=True)


def _flux(mono: np.ndarray, sr: int):
    """Positive spectral flux: how much NEW acoustic energy appears at each hop.

    A syllable onset in a sung line is a step up in the magnitude spectrum. Plain RMS
    cannot see it (a sustained vowel keeps the level high), but the positive difference
    of the magnitude spectrum can: it spikes at the attack and decays during the vowel.

    The whole file is processed in blocks, carrying the previous block's last frame
    forward, so the peak memory is one block instead of the whole spectrogram
    (a full-file rfft of 17.4 M samples needs more RAM than the machine has).
    """
    win = np.hanning(N_FFT).astype(np.float32)
    n = (len(mono) // HOP) * HOP
    mono = mono[:n]
    n_frames = n // HOP
    flux = np.zeros(max(0, n_frames - 1), dtype=np.float32)
    prev = None
    BLOCK = 4096
    for b0 in range(0, n_frames - 1, BLOCK):
        b1 = min(n_frames, b0 + BLOCK + 1)
        idx = np.arange(b0, b1) * HOP
        # the last frame needs N_FFT more samples, so clip the tail of the file
        keep = idx[:, None] + np.arange(N_FFT)[None, :]
        keep = keep[keep[:, -1] < len(mono)]
        frames = mono[keep]
        spec = np.abs(np.fft.rfft(frames * win, axis=1))
        if prev is not None:
            spec = np.vstack([prev[None, :], spec])
        diff = np.maximum(0.0, np.diff(spec, axis=0)).sum(axis=1)
        out_b0 = b0 - 1 if prev is not None else b0
        out_b1 = min(len(flux), out_b0 + len(diff))
        flux[out_b0:out_b1] = diff[:out_b1 - out_b0]
        prev = spec[-1]
    # log-compress: the loudest attack should not swamp a soft one by 40 dB
    flux = np.log1p(flux * 100.0)
    return {"flux": flux.astype(np.float32), "sr": sr, "hop": HOP, "n_fft": N_FFT,
            "rate": sr / HOP, "len": int(len(flux))}


if __name__ == "__main__":
    main()
