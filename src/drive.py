# -*- coding: utf-8 -*-
"""drive: turn the four stem envelopes into smooth control signals for the renderer.

Everything here is a pure lookup on time: `frame(t)` stays a function of t.
"""
from __future__ import annotations

import json
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


def db_at(name: str, t: float, win: float = 0.12) -> float:
    import math
    return 20 * math.log10(_at(_env(name), t, win) + 1e-9)


def norm(name: str, t: float, floor_db: float, ceil_db: float, win: float = 0.12) -> float:
    """Map a stem's level to 0..1 between two dB anchors."""
    d = db_at(name, t, win)
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


def vocal_present(t: float, thresh_db: float = -45.0) -> bool:
    """Is anyone singing right now? Used to gate the lyric band and the rewrite."""
    return db_at("vocals", t, 0.25) > thresh_db


def summary() -> dict:
    p = AUD / "stems_summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


if __name__ == "__main__":
    for t in (10, 60, 80, 150, 180, 220, 320, 390):
        print(f"t={t:5.1f}s  vocals={vocals(t):.2f} drums={drums(t):.2f} "
              f"bass={bass(t):.2f} other={other(t):.2f}  singing={vocal_present(t)}")
