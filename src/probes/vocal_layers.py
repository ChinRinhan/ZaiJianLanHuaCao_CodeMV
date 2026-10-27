# -*- coding: utf-8 -*-
"""One-shot probe: how many singing layers are there in the two declarations?

导演（10:5x）：「第一次『宣言』的时候明显只有宝哥一个声音，到 4:05 的第二次的时候，就有宝哥
多音轨的和声或『合唱』，刚好预告最后的『齐唱』段」。

So the question is measurable: at 1:37-2:02 (B①) and at 4:05-4:24 (B②), how many distinct
vocal pitches sound at the same time? If B② is really doubled/harmonised, the answer must be
> 1 simultaneous pitch most of the time; if B① is a solo, it must be ~1.

Method (no model): STFT on the `vocals` stem, then at each frame count how many local maxima
of the spectrum stand above a relative threshold AND are separated by more than a semitone
(so one harmonic series does not count as two voices). Harmonics are the trap: a single voice
has peaks at f, 2f, 3f. So we also require the candidate to be a *fundamental*: below it there
must be no significant peak in the previous 6 bins.

Run: ./.venv-audio/Scripts/python.exe src/probes/vocal_layers.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / "data" / "audio" / "stems_wav" / "vocals.wav"
OUT = ROOT / "data" / "vocal_layers.json"

N_FFT = 4096
HOP = 512
SR = 22050

WINDOWS = {
    "B1_demands": (103.8, 112.9),     # 四句「给我…」第一次
    "B1_release": (112.95, 119.7),    # 直到那天 + 五分钟
    "B2_demands": (245.79, 254.4),    # 四句「给我…」第二次
    "B2_release": (254.36, 263.98),   # 直到那天 + 五分钟
    "A2_chorus": (266.31, 280.0),     # 合唱段
}


def f0_of(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


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
        # only where the singer is: 100 Hz .. 2 kHz (the vocal range of a pop chorus)
        band = (freqs > 100) & (freqs < 2000)
        S = spec[:, band]
        fb = freqs[band]
        # per-frame relative threshold: 12 dB under the frame's own peak
        thr = S.max(axis=1, keepdims=True) * 10 ** (-12.0 / 20.0)
        counts = []
        for i in range(len(S)):
            row = S[i]
            peaks = []
            for k in range(2, len(row) - 2):
                if row[k] < thr[i, 0]:
                    continue
                if row[k] < row[k - 1] or row[k] < row[k + 1]:
                    continue
                f = fb[k]
                # a fundamental: nothing significant in the octave below it
                below = row[(fb > f / 1.8) & (fb < f / 1.15)]
                if below.size and below.max() > row[k] * 0.8:
                    continue
                # and it must be far enough from the last one to be a separate voice
                if peaks and f - peaks[-1] < f0_of(1.2):   # > ~1.2 semitones apart
                    continue
                peaks.append(f)
            counts.append(len(peaks))
        c = np.array(counts)
        res[name] = {
            "frames": int(len(c)),
            "mean_layers": round(float(c.mean()), 3),
            "p50": int(np.percentile(c, 50)),
            "p90": int(np.percentile(c, 90)),
            "max": int(c.max()),
            "frac_multi": round(float((c >= 2).mean()), 3),
        }
        print("%-12s mean %.2f  p50 %d  p90 %d  max %d  multi %.0f%%"
              % (name, c.mean(), np.percentile(c, 50), np.percentile(c, 90),
                 c.max(), 100.0 * (c >= 2).mean()))

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
