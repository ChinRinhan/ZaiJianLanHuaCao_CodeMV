# -*- coding: utf-8 -*-
"""One-shot probe: what is actually in the piano movement (147-162 s)?

The design needs note events, not an energy curve: when does a key get struck, how hard,
and roughly which register (left hand low / right hand high)? "不求真音高" (导演拍板 5)
means the film does not have to be pitch-accurate, but the ROLL must at least move in the
register the music moves in, or the keyboard looks like random noise.

Method (cheap, no model): STFT on the `other` stem (piano sits there), positive log-freq
flux as onset strength, peak pick, then for each onset the spectral centroid + the
dominant peak in 100-3000 Hz -> a rough MIDI number.

Run: ./.venv-audio/Scripts/python.exe src/probes/piano_score.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / "data" / "audio" / "stems_wav" / "other.wav"
OUT = ROOT / "data" / "piano_score.json"

N_FFT = 2048
HOP = 256
T0, T1 = 124.0, 246.0


def main():
    mono, sr = sf.read(str(WAV), dtype="float32")
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    a, b = int(T0 * sr), int(T1 * sr)
    seg = mono[a:b]
    rate = sr / HOP
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + (len(seg) - N_FFT) // HOP
    idx = np.arange(n)[:, None] * HOP + np.arange(N_FFT)[None, :]
    frames = seg[idx] * win
    spec = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)

    # log-compress, and work only above 60 Hz (rumble) — piano fundamentals live here
    band = (freqs > 60) & (freqs < 6000)
    S = np.log1p(spec[:, band] * 40.0)
    fb = freqs[band]
    diff = np.diff(S, axis=0, prepend=S[:1])
    onset = np.maximum(0.0, diff).sum(axis=1)

    # local, not global: over 122 s the shout section is 30x the piano movement, so a
    # whole-file threshold either drowns the piano or floods the shout. Peak-pick against
    # a rolling 3 s reference, and normalise the strength against it too.
    WIN = int(3.0 * rate)
    ref = np.zeros_like(onset)
    for i in range(0, len(onset), 12):
        a0, b0 = max(0, i - WIN // 2), min(len(onset), i + WIN // 2)
        ref[i:i + 12] = np.percentile(onset[a0:b0], 97) + 1e-9
    strength = np.clip(onset / ref, 0.0, 1.0)

    peaks = []
    i = 2
    min_gap = int(0.12 * rate)
    while i < len(onset) - 2:
        loc = onset[max(0, i - 2):i + 3]
        if onset[i] == loc.max() and strength[i] > 0.55 and onset[i] > 0:
            peaks.append(i)
            i += min_gap
        else:
            i += 1

    ev = []
    for i in peaks:
        s = spec[i][band]
        fsub = fb
        # harmonic-sum salience: a real piano note has energy at f0, 2f0, 3f0 ... A plain
        # argmax lands on whichever partial is loudest, which jumps octaves between notes.
        best_f, best_v = 0.0, -1.0
        for f0 in np.exp(np.linspace(np.log(80.0), np.log(1100.0), 220)):
            v = 0.0
            for h in range(1, 7):
                fh = f0 * h
                if fh >= 6000:
                    break
                j = int(np.argmin(np.abs(fsub - fh)))
                if abs(fsub[j] - fh) < f0 * 0.045:
                    v += s[j] / h
            if v > best_v:
                best_v, best_f = v, f0
        f0 = best_f
        midi = int(round(69 + 12 * np.log2(max(40.0, f0) / 440.0)))
        cens = float((S[i] * fb).sum() / (S[i].sum() + 1e-9))
        ev.append({
            "t": round(T0 + i / rate, 3),
            "s": round(float(strength[i]), 3),
            "midi": int(max(21, min(96, midi))),
            "cen": round(cens, 1),
        })

    # note histogram in the window we actually film
    film = [e for e in ev if 147.0 <= e["t"] < 162.0]
    mids = [e["midi"] for e in film]
    print(f"onsets total {len(ev)}  in-film {len(film)}  "
          f"rate {len(film)/15.0:.2f}/s")
    if mids:
        print("midi  min %d  p10 %d  median %d  p90 %d  max %d"
              % (min(mids), np.percentile(mids, 10), np.median(mids),
                 np.percentile(mids, 90), max(mids)))
    hist = {}
    for m in mids:
        hist[m // 12] = hist.get(m // 12, 0) + 1
    print("octave histogram (C-octave: count)", dict(sorted(hist.items())))
    print("first 12 in-film:", [(e["t"], e["midi"], e["s"]) for e in film[:12]])
    OUT.write_text(json.dumps({"t0": T0, "t1": T1, "rate": rate, "events": ev},
                              indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
