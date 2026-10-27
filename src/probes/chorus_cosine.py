# -*- coding: utf-8 -*-
"""One-shot probe: how close are the lead and the backing voice? (a real number for A②)

The reference PV's chorus shows `cos(me, you) = 0.9939` — the cosine similarity of two
token embeddings. We cannot borrow that number: it is theirs. We need OUR number, measured
on the real stems (导演 put the 17-track separation in the repo: 主唱人声 + 背景和声).

Two honest metrics, both computed from the audio:

  spectral_cos : per STFT frame, the cosine similarity of the two vocals' magnitude
                 spectra in the vocal band (200–2000 Hz), averaged over frames where the
                 backing voice is actually audible. "Do these two voices occupy the same
                 spectral space?" — the audible meaning of "六个人唱成一片".
  env_corr     : the correlation of the two smoothed envelopes. "Do they move together?"

Both are computed for every section, so the picture can show the contrast: B① (one voice,
the backing is 9.7 dB down) must come out LOW, and A② (the chorus) must come out HIGH —
otherwise the number is decoration, not a measurement.

Run: ./.venv-audio/Scripts/python.exe src/probes/chorus_cosine.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "再见 兰花草 - 张雨生_分轨"
OUT = ROOT / "data" / "chorus_cosine.json"

LEAD = STEMS / "再见 兰花草 - 张雨生_主唱人声.mp3"
BACK = STEMS / "再见 兰花草 - 张雨生_背景和声.mp3"

N_FFT = 2048
HOP = 512

SECTIONS = {
    "A1": (67.85, 103.84),
    "B1": (103.84, 136.60),
    "B2": (245.79, 266.31),
    "A2": (266.31, 312.45),
    "A3": (312.45, 358.92),
    "A4": (358.92, 387.00),
}


def _load(p):
    x, sr = sf.read(str(p), dtype="float32")
    if x.ndim == 2:
        x = x.mean(axis=1)
    return x, sr


def main():
    if not STEMS.exists():
        print("no separated stems at", STEMS)
        return
    lead, sr = _load(LEAD)
    back, _ = _load(BACK)
    n = min(len(lead), len(back))
    lead, back = lead[:n], back[:n]

    res = {}
    for name, (t0, t1) in SECTIONS.items():
        a, b = int(t0 * sr), int(t1 * sr)
        seg_l = lead[a:b]
        seg_b = back[a:b]
        if seg_l.size < N_FFT * 4:
            continue
        # STFT of both, magnitude spectra, vocal band only
        win = np.hanning(N_FFT).astype(np.float32)
        frames = 1 + (len(seg_l) - N_FFT) // HOP
        idx = np.arange(frames)[:, None] * HOP + np.arange(N_FFT)[None, :]
        L = np.abs(np.fft.rfft(seg_l[idx] * win, axis=1))
        B = np.abs(np.fft.rfft(seg_b[idx] * win, axis=1))
        freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)
        band = (freqs > 200) & (freqs < 2000)
        L, B = L[:, band], B[:, band]
        # frames where the backing voice is actually there
        energy = (L ** 2).sum(axis=1)
        gate = energy > np.percentile(energy, 55)
        num = (L[gate] * B[gate]).sum(axis=1)
        den = np.sqrt((L[gate] ** 2).sum(axis=1) * (B[gate] ** 2).sum(axis=1)) + 1e-12
        spec_cos = float(np.mean(num / den)) if gate.any() else 0.0
        # envelope correlation
        def env(x):
            e = np.sqrt(np.convolve(x ** 2, np.ones(256) / 256, mode="same"))
            return e - e.mean()
        el, eb = env(seg_l), env(seg_b)
        env_corr = float(np.corrcoef(el, eb)[0, 1])
        res[name] = {"t0": t0, "t1": t1,
                     "spectral_cos": round(spec_cos, 4),
                     "env_corr": round(env_corr, 4),
                     "back_rel_db": round(float(20 * np.log10(
                         (np.sqrt(np.mean(seg_b ** 2)) + 1e-12) /
                         (np.sqrt(np.mean(seg_l ** 2)) + 1e-12))), 2)}
        print("%-4s  spectral_cos %.4f   env_corr %+.4f   back/lead %+6.2f dB"
              % (name, spec_cos, env_corr, res[name]["back_rel_db"]))
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
