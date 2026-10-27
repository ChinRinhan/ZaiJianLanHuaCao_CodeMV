# -*- coding: utf-8 -*-
"""One-shot probe: is the second declaration really sung with added voices?

The first probe counted spectral peaks and could not separate the two declarations
(everywhere "3 layers") because a single voice has peaks at f, 2f, 3f.

The decisive question is different: does the vocals stem contain energy at intervals that
are NOT integer multiples of the strongest fundamental? A second voice a third or a fifth
above/below the lead puts energy at f0*1.2 .. f0*1.35 (a minor third), f0*1.5 (a fifth),
f0*0.67 (a fifth below) and so on. A single voice with vibrato and formant changes does not.

So: per frame, take the strongest peak as the lead fundamental, then measure the share of
the frame's energy that sits at NON-harmonic ratios (1.15..1.9, 0.55..0.85) to the lead,
relative to the frame's total in-band energy. If the second statement really carries added
voices, this share must be visibly higher there.

Run: ./.venv-audio/Scripts/python.exe src/probes/vocal_harmony.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / "data" / "audio" / "stems_wav" / "other.wav"
OUT = ROOT / "data" / "other_harmony.json"

N_FFT = 4096
HOP = 512
SR = 22050

WINDOWS = {
    "B1_demands": (103.8, 112.9),
    "B1_release": (112.95, 119.7),
    "B2_demands": (245.79, 254.4),
    "B2_release": (254.36, 263.98),
    "A2_chorus": (266.31, 280.0),
    "A1_quiet": (40.0, 70.0),
}


def main():
    mono, sr = sf.read(str(WAV), dtype="float32")
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    win = np.hanning(N_FFT).astype(np.float32)
    res = {}
    for name, (t0, t1) in WINDOWS.items():
        a, b = int(t0 * sr), int(t1 * sr)
        seg = mono[a:b]
        n = 1 + (len(seg) - N_FFT) // HOP
        idx = np.arange(n)[:, None] * HOP + np.arange(N_FFT)[None, :]
        spec = np.abs(np.fft.rfft(seg[idx] * win, axis=1))
        freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)
        band = (freqs > 90) & (freqs < 2500)
        S = spec[:, band]
        fb = freqs[band]
        ratios, shares = [], []
        for i in range(len(S)):
            row = S[i]
            if row.max() <= 1e-7:
                continue
            # the lead fundamental: the strongest peak that is not a harmonic of something
            # below it. Take the strongest peak in 90..600 Hz and check for a stronger
            # sub-octave; if there is one, step down until the lowest strong peak wins.
            f0 = fb[np.argmax(row)]
            for _ in range(4):
                below = fb < f0 / 1.8
                if below.any() and row[below].max() > row[np.argmin(abs(fb - f0))] * 0.75:
                    cand = fb[below][row[below] > row[below].max() * 0.75]
                    f0 = float(cand.max()) if cand.size else f0
                    continue
                break
            r = fb / max(f0, 1e-6)
            harm = (np.abs(r - np.round(r)) < 0.06) & (r > 0.8)     # integer multiples
            nonh = (r > 1.15) & (r < 1.9)                              # a third / a fifth
            e = row ** 2
            tot = e.sum()
            if tot <= 1e-12:
                continue
            ratios.append(float(f0))
            shares.append(float(e[nonh].sum() / tot))
        s = np.array(shares)
        res[name] = {
            "frames": int(len(s)),
            "nonharmonic_share_mean": round(float(s.mean()), 4),
            "nonharmonic_share_p75": round(float(np.percentile(s, 75)), 4),
            "lead_f0_median": float(np.median(ratios)) if ratios else 0.0,
        }
        print("%-12s non-harmonic share mean %.4f p75 %.4f   lead f0 med %.1f Hz"
              % (name, s.mean(), np.percentile(s, 75), res[name]["lead_f0_median"]))
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
