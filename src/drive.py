# -*- coding: utf-8 -*-
"""drive: turn the four stem envelopes into smooth control signals for the renderer.

Everything here is a pure lookup on time: `frame(t)` stays a function of t.

WHY THIS FILE NOW MATTERS
-------------------------
For most of this project the four stems existed but nothing drew from them. Every element
moved on its own private ramp — which is exactly the "平移 + 淡入淡出" the director called
cheap (plan/06 §5.1). The mapping below is the contract from plan/17 §7:

    vocals -> beam height and brightness      (only lights up when someone is singing)
    bass   -> ridge amplitude                 (the mountain breathes with the low end)
    other  -> rain density / character noise  (density change, not translation)
    drums  -> threshold events                (a flash when it crosses, not a sliding value)

`vocal_present()` is the gate for the lyric band: the measured threshold (-45 dB) matches the
LRC exactly (plan/17 §6), so it can be used to decide whether the machine is "hearing" anyone.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "data" / "audio"
HZ = 100.0                      # envelopes are 100 fps


@lru_cache(maxsize=4)
def _env(name: str) -> np.ndarray:
    return np.load(AUD / f"stem_{name}.npy").astype(np.float32)


def _at(env: np.ndarray, t: float, win: float = 0.12) -> float:
    i = int(t * HZ)
    a, b = max(0, i - int(win * HZ)), min(len(env), i + int(win * HZ) + 1)
    return float(env[a:b].max()) if b > a else 0.0


def _mean(env: np.ndarray, t: float, win: float = 0.25) -> float:
    """Smoother than max: for slow signals (bass -> mountain) a peak-hold looks jittery."""
    i = int(t * HZ)
    a, b = max(0, i - int(win * HZ)), min(len(env), i + int(win * HZ) + 1)
    return float(env[a:b].mean()) if b > a else 0.0


def db_at(name: str, t: float, win: float = 0.12) -> float:
    return 20 * math.log10(_at(_env(name), t, win) + 1e-9)


def norm(name: str, t: float, floor_db: float, ceil_db: float, win: float = 0.12) -> float:
    """Map a stem's level to 0..1 between two dB anchors."""
    d = db_at(name, t, win)
    return max(0.0, min(1.0, (d - floor_db) / (ceil_db - floor_db)))


def norm_smooth(name: str, t: float, floor_db: float, ceil_db: float, win: float = 0.35) -> float:
    d = 20 * math.log10(_mean(_env(name), t, win) + 1e-9)
    return max(0.0, min(1.0, (d - floor_db) / (ceil_db - floor_db)))


# ---- the four control signals -------------------------------------------------
def vocals(t: float) -> float:
    return norm("vocals", t, -55.0, -20.0)


def drums(t: float) -> float:
    return norm("drums", t, -55.0, -25.0)


def bass(t: float) -> float:
    return norm("bass", t, -50.0, -24.0)


def other(t: float) -> float:
    return norm("other", t, -45.0, -24.0)


def vocals_smooth(t: float) -> float:
    return norm_smooth("vocals", t, -55.0, -20.0)


def bass_smooth(t: float) -> float:
    return norm_smooth("bass", t, -52.0, -24.0)


def other_smooth(t: float) -> float:
    return norm_smooth("other", t, -46.0, -24.0)


def vocal_present(t: float, thresh_db: float = -45.0) -> bool:
    """Is anyone singing right now? Used to gate the lyric band and the rewrite."""
    return db_at("vocals", t, 0.25) > thresh_db


def drum_hit(t: float, thresh: float = 0.55) -> float:
    """A threshold event, not a sliding value.

    Returns the pulse of the most recent drum attack if it happened within the last pulse
    window, else 0. Used for "flash once when it crosses" instead of "brightness follows a
    slider" — plan/07 §2.1: quantised beats continuous,累积 beats 清零.
    """
    import clock
    i = int(t * HZ)
    a = max(0, i - 4)
    prev = float(_env("drums")[a:i].mean()) if i > a else 0.0
    cur = float(_env("drums")[i]) if 0 <= i < len(_env("drums")) else 0.0
    if cur - prev > thresh * 4:
        return clock.pulse(t)
    return 0.0


def summary() -> dict:
    p = AUD / "stems_summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


if __name__ == "__main__":
    for t in (10, 60, 80, 150, 180, 220, 320, 390):
        print(f"t={t:5.1f}s  vocals={vocals(t):.2f} drums={drums(t):.2f} "
              f"bass={bass(t):.2f} other={other(t):.2f}  singing={vocal_present(t)}")
