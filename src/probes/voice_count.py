# -*- coding: utf-8 -*-
"""One-shot probe: how many voices are singing RIGHT NOW, and does it grow?

导演（19:26）：「最开始一段（指预备场那一段）还没有『合唱』，后面逐渐增加」

If the backing vocal really carries more and more singers as A② goes on, then "the chorus
builds" is a fact in the recording, not a drawing decision. So: count the **simultaneous
pitch clusters** in the 背景和声 stem (the director's 17-track separation), frame by frame.

A pitch cluster = a spectral peak that is (a) strong enough, (b) not a harmonic of a
stronger peak below it, and (c) more than ~2 semitones from the neighbouring peak. One
singer's harmonic series therefore counts as ONE voice, not five.

Run: ./.venv-audio/Scripts/python.exe src/probes/voice_count.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "再见 兰花草 - 张雨生_分轨"
OUT = ROOT / "data" / "voice_count.json"
# the per-frame curve is ~350 KB; it is gitignored (nothing reads it)
CURVE_OUT = ROOT / "data" / "voice_count_curve.json"

N_FFT = 4096
HOP = 1024
SR = 22050

SPANS = {
    "B1": (103.84, 136.60),
    "B2": (245.79, 266.31),
    "A2": (266.31, 312.45),
    "A3": (312.45, 358.92),
    "A4": (358.92, 387.00),
}


def hz_to_midi(f):
    return 69.0 + 12.0 * np.log2(max(f, 1e-6) / 440.0)


def count_voices(x, sr, t0, t1):
    """Per-frame count of simultaneous pitch clusters."""
    a, b = int(t0 * sr), int(t1 * sr)
    seg = x[a:b]
    if seg.size < N_FFT * 4:
        return [], []
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + (len(seg) - N_FFT) // HOP
    idx = np.arange(n)[:, None] * HOP + np.arange(N_FFT)[None, :]
    spec = np.abs(np.fft.rfft(seg[idx] * win, axis=1))
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)
    band = (freqs > 150) & (freqs < 1600)
    S, fb = spec[:, band], freqs[band]
    times = t0 + np.arange(len(S)) / (sr / HOP)
    counts, energies = [], []
    for i in range(len(S)):
        row = S[i]
        if row.max() <= 1e-7:
            counts.append(0)
            energies.append(0.0)
            continue
        thr = row.max() * 10 ** (-16.0 / 20.0)
        peaks = []
        for k in range(1, len(row) - 1):
            if row[k] < thr or row[k] < row[k - 1] or row[k] < row[k + 1]:
                continue
            f = fb[k]
            # reject harmonics: a stronger peak at f/2, f/3 ... means this is not a root
            harm = False
            for h in (2, 3, 4):
                near = int(np.argmin(np.abs(fb - f / h)))
                if abs(fb[near] - f / h) < 14 and row[near] > row[k] * 0.80:
                    harm = True
                    break
            if harm:
                continue
            # merge peaks closer than ~2 semitones (vibrato / formant wobble)
            if peaks and f - peaks[-1] < f * 0.12:
                continue
            peaks.append(f)
        counts.append(len(peaks))
        energies.append(float(np.sqrt(np.mean(row ** 2))))
    return times, counts, energies


def main():
    if not STEMS.exists():
        print("no separated stems at", STEMS)
        return
    x, sr = sf.read(str(STEMS / "再见 兰花草 - 张雨生_背景和声.mp3"), dtype="float32")
    if x.ndim == 2:
        x = x.mean(axis=1)
    lead, _ = sf.read(str(STEMS / "再见 兰花草 - 张雨生_主唱人声.mp3"), dtype="float32")
    if lead.ndim == 2:
        lead = lead.mean(axis=1)

    res = {}
    curves = {}
    for name, (t0, t1) in SPANS.items():
        times, counts, energies = count_voices(x, sr, t0, t1)
        # the backing's level relative to the lead, per frame
        rel = []
        for i, t in enumerate(times):
            i0, i1 = int(t * sr), int(t * sr) + HOP * 4
            bl = float(np.sqrt(np.mean(lead[i0:i1] ** 2))) + 1e-12
            bb = float(np.sqrt(np.mean(x[i0:i1] ** 2))) + 1e-12
            rel.append(20.0 * np.log10(bb / bl))
        c = np.array(counts, dtype=float)
        r = np.array(rel)
        # the curve the picture can use: voices present, gated by whether the backing is audible
        audible = r > -22.0
        voiced = np.where(audible, c, 0)
        res[name] = {
            "t0": t0, "t1": t1,
            "voices_mean": round(float(c[audible].mean()) if audible.any() else 0.0, 2),
            "voices_p90": round(float(np.percentile(c[audible], 90)) if audible.any() else 0.0, 1),
            "voices_max": int(c.max()),
            "rel_db_mean": round(float(r.mean()), 2),
            "audible_frac": round(float(audible.mean()), 3),
        }
        print("%-3s voices mean %.2f p90 %.0f max %d | back/lead %+.1f dB | audible %.0f%%"
              % (name, res[name]["voices_mean"], res[name]["voices_p90"],
                 res[name]["voices_max"], res[name]["rel_db_mean"],
                 100.0 * res[name]["audible_frac"]))
        # The per-frame curve is ~350 KB and nothing reads it — the picture uses the
        # per-line measurement in `backing_vocal_full.py` / `backing_vocal_tail.py`
        # instead (relative level per sung line, which is both smaller and steadier).
        # So the summary goes to the repo and the curve goes to a gitignored file.
        if CURVE_OUT.exists():
            CURVE_OUT.unlink()
        curves[name] = [[round(float(t), 2), int(v)] for t, v in zip(times, voiced)]
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    CURVE_OUT.write_text(json.dumps(curves, indent=1), encoding="utf-8")
    print("wrote", OUT, "and", CURVE_OUT)


if __name__ == "__main__":
    main()
