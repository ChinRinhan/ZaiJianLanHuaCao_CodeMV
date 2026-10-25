# -*- coding: utf-8 -*-
"""The music clock. Everything in the film reads its time from here.

The reference PV (world-execute-me-dsh-pv) does exactly this and it is why its motion feels
coordinated rather than authored: one beat grid, one decaying envelope, and every element that
moves is a function of `pulse(t)` or of a grid point — never of its own private linear ramp.

    beat_index(t)  which beat we are on
    beat_t(i)      when beat i happened
    pulse(t)       exp decay since the last beat (1.0 on the beat, ~0 by the next)
    snap(t, div)   the nearest grid point at 1/div of a beat
"""
from __future__ import annotations

BPM = 167.65          # fitted: mean spectral flux on the grid, 160-175 BPM x 5 ms phase sweep
PHASE = 0.235         # first beat
DECAY = 0.14          # pulse half-life-ish, seconds (reference uses 0.14)

BEAT = 60.0 / BPM
END = 395.667


def beat_t(i: int) -> float:
    return PHASE + i * BEAT


def beat_index(t: float) -> int:
    return int((t - PHASE) // BEAT)


def beat_phase(t: float) -> float:
    """0 on the beat, 1 just before the next one."""
    return ((t - PHASE) % BEAT) / BEAT


def pulse(t: float) -> float:
    """1.0 on the beat, decaying to ~0 by the next. The shared heartbeat of every read-out."""
    import math
    return math.exp(-max(0.0, t - beat_t(beat_index(t))) / DECAY)


def snap(t: float, div: int = 3) -> float:
    """Nearest 1/div-beat grid point."""
    step = BEAT / div
    k = round((t - PHASE) / step)
    return PHASE + k * step
