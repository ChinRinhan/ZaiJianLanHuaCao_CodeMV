# -*- coding: utf-8 -*-
"""The music clock. Everything in the film reads its time from here.

The reference PV (world-execute-me-dsh-pv) does exactly this and it is why its motion feels
coordinated rather than authored: one beat grid, one decaying envelope, and every element that
moves is a function of `pulse(t)` or of a grid point — never of its own private linear ramp.

WHY THIS FILE CHANGED (2026-10-26, second pass)
-----------------------------------------------
The previous version hard-coded `BPM = 167.65, PHASE = 0.235`, obtained by sweeping spectral
flux of the *mix* against a pure BPM grid. That number is wrong for this song, and four
independent measurements now say so:

    source                              result
    librosa.beat.beat_track            112.35 BPM  (731 beats)
    librosa.feature.tempo              112.3  BPM
    dsh-soundcheck (whole song)        112 / 56 BPM
    DFT of drum-stem onsets (212-246)  111.2 / 113.0 BPM  (peaks at 1.853 and 1.883 Hz)
    normalised autocorr of drum onsets 113.2 BPM  (lag 0.530 s)

167.65 and 112.0 are in a 3:2 ratio, which is exactly the inter-onset relation between a
quarter note and a dotted-quarter / "shuffle" subdivision. A pure-BPM comb over a shuffle
groove happily locks onto the 3-side and reports 1.5x the real tempo. That is what happened.

We do not just divide by 1.5 and call it fixed: the beat interval drifts (the 60-120 s block
sits at 105.5 BPM, the rest at 112.3), so an analytic grid accumulates error. Instead the beat
times measured off the audio are stored as a table (`data/beat_times.json`) and this module
looks them up. It is still a pure function of t — a table is as deterministic as a formula, and
`frame(t)` remains reproducible for any single frame.

    beat_index(t)  which beat we are on
    beat_t(i)      when beat i happened
    beat_pos(t)    0..1 position between the two surrounding beats (fractional beat index)
    pulse(t)       exp decay since the last beat (1.0 on the beat, ~0 by the next)
    snap(t, div)   the nearest grid point at 1/div of a beat
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BEATS_PATH = ROOT / "data" / "beat_times.json"

END = 395.667
DECAY = 0.14          # pulse decay constant, seconds (reference PV uses 0.14)

# fallback constants, used only if the beat table is missing
BPM_FALLBACK = 112.35
PHASE_FALLBACK = 0.569


def _load_beats() -> list[float]:
    if _BEATS_PATH.exists():
        try:
            data = json.loads(_BEATS_PATH.read_text(encoding="utf-8"))
            beats = [float(x) for x in data.get("beats", [])]
            if len(beats) > 8:
                return beats
        except Exception:
            pass
    step = 60.0 / BPM_FALLBACK
    return [PHASE_FALLBACK + i * step for i in range(int(END / step) + 2)]


BEATS = _load_beats()
_BPM = 60.0 / ((BEATS[-1] - BEATS[0]) / max(1, len(BEATS) - 1))
BPM = round(_BPM, 2)
BEAT = 60.0 / BPM          # nominal only; real intervals come from the table


def beat_t(i: int) -> float:
    """Time of beat i. Extrapolates with the nominal interval outside the table."""
    if 0 <= i < len(BEATS):
        return BEATS[i]
    if i < 0:
        return BEATS[0] + i * BEAT
    return BEATS[-1] + (i - len(BEATS) + 1) * BEAT


def beat_index(t: float) -> int:
    """Index of the last beat at or before t. -1 before the first beat."""
    lo, hi = 0, len(BEATS) - 1
    if t < BEATS[0]:
        return -1
    if t >= BEATS[-1]:
        return len(BEATS) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if BEATS[mid] <= t:
            lo = mid
        else:
            hi = mid - 1
    return lo


def beat_pos(t: float) -> float:
    """Fractional beat position: 3.5 means halfway between beat 3 and beat 4."""
    i = beat_index(t)
    t0 = beat_t(i)
    t1 = beat_t(i + 1)
    span = t1 - t0
    return i + (0.0 if span <= 0 else (t - t0) / span)


def beat_phase(t: float) -> float:
    """0 on the beat, 1 just before the next one."""
    return beat_pos(t) % 1.0


def beat_len(t: float | None = None) -> float:
    """Interval of the beat we are inside (or the nominal one if t is None)."""
    if t is None:
        return BEAT
    i = beat_index(t)
    d = beat_t(i + 1) - beat_t(i)
    return d if d > 0 else BEAT


def pulse(t: float) -> float:
    """1.0 on the beat, decaying to ~0 by the next. The shared heartbeat of every read-out."""
    return math.exp(-max(0.0, t - beat_t(beat_index(t))) / DECAY)


def snap(t: float, div: int = 3) -> float:
    """Nearest 1/div-beat grid point, using the real local beat interval."""
    pos = beat_pos(t)
    k = round(pos * div)
    i = math.floor(k / div)
    frac = (k - i * div) / div
    t0 = beat_t(i)
    t1 = beat_t(i + 1)
    return t0 + (t1 - t0) * frac


def grid(div: int = 1) -> list[float]:
    """Every grid point in the song at 1/div of a beat (used to check lyric alignment)."""
    out = []
    for i in range(len(BEATS) - 1):
        t0, t1 = BEATS[i], BEATS[i + 1]
        for k in range(div):
            out.append(t0 + (t1 - t0) * k / div)
    out.append(BEATS[-1])
    return out


if __name__ == "__main__":
    print(f"beats={len(BEATS)}  mean BPM={BPM}")
    for t in (67.85, 80.0, 122.0, 150.0, 212.0, 320.0, 386.0):
        print(f"t={t:7.2f}  beat#{beat_index(t):4d}  pos={beat_pos(t):7.3f}  "
              f"pulse={pulse(t):.3f}  local_beat={beat_len(t):.4f}s")
