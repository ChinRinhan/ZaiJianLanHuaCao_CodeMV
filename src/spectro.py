# -*- coding: utf-8 -*-
"""Real band energies for the SIGNAL plate.

The old `tk.spectrum` drew `sin(t*2.1 + i*0.55) * level` — a travelling sine wave in a mask.
It never read the song. This module computes what the plate should have been showing all along:

    data/audio/bands24.npy   (9504, 22) float32, one row per video frame, per-band 0..1

Per-band normalisation is deliberate: each band is scaled by its own 10th/99th percentile across
the whole song, so a quiet band still shows *change* instead of sitting flat at the bottom.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "audio" / "mono22050.wav"
OUT = ROOT / "data" / "audio" / "bands24.npy"

FPS = 24.0
WIN = 2048
BARS = 22
LO_HZ, HI_HZ = 55.0, 11000.0


def band_edges(sr: int, n_bins: int):
    edges = np.geomspace(LO_HZ, HI_HZ, BARS + 1)
    freqs = np.fft.rfftfreq(n_bins, 1.0 / sr)
    idx = [int(np.searchsorted(freqs, f)) for f in edges]
    return [max(0, min(len(freqs) - 1, i)) for i in idx]


def main():
    w = wave.open(str(SRC), "rb")
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    dur = len(x) / sr
    n_frames = int(round(dur * FPS))

    edges = band_edges(sr, WIN)
    win = np.hanning(WIN).astype(np.float32)
    out = np.zeros((n_frames, BARS), dtype=np.float32)

    for k in range(n_frames):
        c = int((k / FPS) * sr)
        a = max(0, c - WIN // 2)
        seg = x[a:a + WIN]
        if len(seg) < WIN:
            seg = np.pad(seg, (0, WIN - len(seg)))
        spec = np.abs(np.fft.rfft(seg * win)) ** 2
        for b in range(BARS):
            s, e = edges[b], max(edges[b] + 1, edges[b + 1])
            out[k, b] = spec[s:e].mean()

    db = 10.0 * np.log10(out + 1e-12)
    lo = np.percentile(db, 10, axis=0)
    hi = np.percentile(db, 99.5, axis=0)
    # ceiling at 0.88, never 1.0 — same rule as the 92% gauze: nothing in this film tops out.
    norm = np.clip((db - lo) / np.maximum(1e-6, hi - lo), 0.0, 1.0) ** 0.85 * 0.88

    np.save(OUT, norm.astype(np.float32))
    print(f"{OUT}  shape={norm.shape}  {OUT.stat().st_size/1024:.0f} KB")

    for name, a, b in [("间奏骤静 147-161", 147, 161), ("间奏全奏 122-146", 122, 146),
                       ("A3 顶点 313-358", 313, 358), ("尾 388-395", 388, 395)]:
        m = norm[int(a * FPS):int(b * FPS)]
        print(f"  {name:18s} mean={m.mean():.3f}  hi-band(>2k)={m[:, -6:].mean():.3f}")


if __name__ == "__main__":
    main()
