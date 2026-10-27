# -*- coding: utf-8 -*-
"""One-shot probe: how many DISTINCT pitches sound at once in the vocals stem?

Previous probes failed because they asked "is there non-harmonic energy", which is a
property of any voice with formants. The question the director asked is simpler and
sharper: at 1:43 (the first declaration) there is ONE voice; at 4:05 (the second) there
are several — the backing vocal lines.

So: track the spectral peaks of the vocals stem frame by frame, convert each to a MIDI
number, and count how many DIFFERENT MIDI numbers (more than 2 semitones apart, so
vibrato and formant wobble do not count twice) are present at the same time.

If Demucs put the whole chorus into the vocals stem, this will show it. If it did not
separate them, the count will be the same in both declarations and the director's
impression comes from the RECORD, not from our stems.

Run: ./.venv-audio/Scripts/python.exe src/probes/vocal_pitches.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / "data" / "audio" / "stems_wav" / "vocals.wav"
OUT = ROOT / "data" / "vocal_pitches.json"

N_FFT = 4096
HOP = 256
SR = 22050
T0, T1 = 100.0, 268.0

MARKERS = {
    "B1_demands": (103.8, 112.9),
    "B1_release": (112.95, 119.7),
    "B2_demands": (245.79, 254.4),
    "B2_release": (254.36, 263.98),
    "A2_chorus": (266.31, 280.0),
}


def hz_to_midi(f):
    return 69.0 + 12.0 * np.log2(np.maximum(f, 1e-6) / 440.0)


def main():
    mono, sr = sf.read(str(WAV), dtype="float32")
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    win = np.hanning(N_FFT).astype(np.float32)
    a, b = int(T0 * sr), int(T1 * sr)
    seg = mono[a:b]
    n = 1 + (len(seg) - N_FFT) // HOP
    idx = np.arange(n)[:, None] * HOP + np.arange(N_FFT)[None, :]
    spec = np.abs(np.fft.rfft(seg[idx] * win, axis=1))
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)
    band = (freqs > 110) & (freqs < 1200)
    S = spec[:, band]
    fb = freqs[band]
    rate = sr / HOP
    times = T0 + np.arange(len(S)) / rate

    # per frame: peaks, in MIDI, folded to one octave (so an octave doubling of the SAME
    # voice does not read as a second voice) and then counted
    counts = np.zeros(len(S), dtype=int)
    midis = np.full(len(S), np.nan)
    for i in range(len(S)):
        row = S[i]
        if row.max() <= 1e-7:
            continue
        thr = row.max() * 10 ** (-14.0 / 20.0)
        peaks = []
        for k in range(1, len(row) - 1):
            if row[k] < thr or row[k] < row[k - 1] or row[k] < row[k + 1]:
                continue
            f = fb[k]
            if f < 110:
                continue
            m = hz_to_midi(f)
            # harmonic test: is there a stronger peak at ~f/2, f/3 ... ?
            harm = False
            for h in (2, 3, 4):
                near = np.argmin(abs(fb - f / h))
                if abs(fb[near] - f / h) < 12 and row[near] > row[k] * 0.85:
                    harm = True
                    break
            if harm:
                continue
            peaks.append((m, row[k]))
        if not peaks:
            continue
        peaks.sort(key=lambda p: -p[1])
        kept = []
        for m, amp in peaks:
            # fold to the same octave as the strongest peak, then merge near-duplicates
            mm = m
            while mm - peaks[0][0] > 6:
                mm -= 12
            while peaks[0][0] - mm > 6:
                mm += 12
            if any(abs(mm - k[0]) < 2.0 for k in kept):
                continue
            kept.append((mm, amp))
            if len(kept) >= 6:
                break
        counts[i] = len(kept)
        midis[i] = kept[0][0] if kept else np.nan

    res = {}
    for name, (t0, t1) in MARKERS.items():
        m = (times >= t0) & (times < t1)
        c = counts[m]
        res[name] = {
            "frames": int(len(c)),
            "voices_mean": round(float(c.mean()), 3),
            "voices_p50": int(np.percentile(c, 50)),
            "voices_p90": int(np.percentile(c, 90)),
            "voices_max": int(c.max()),
            "frac_2plus": round(float((c >= 2).mean()), 3),
        }
        print("%-12s voices mean %.2f  p50 %d  p90 %d  max %d  >=2 voices %.0f%%"
              % (name, c.mean(), np.percentile(c, 50), np.percentile(c, 90), c.max(),
                 100.0 * (c >= 2).mean()))
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
