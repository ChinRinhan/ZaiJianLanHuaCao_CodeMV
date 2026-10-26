# -*- coding: utf-8 -*-
"""score3: the interlude's note table — what the instruments are actually playing.

The third chapter is instrumental, so the picture has to be driven by NOTES, not by an
energy envelope: "the piano movement" needs to know when a key is struck and roughly
where on the keyboard. `data/piano_score.json` is that table, extracted once by
`probes/piano_score.py` (spectral flux -> onsets, harmonic-sum salience -> a rough MIDI
number).

导演拍板 5: 不求真音高. The pitch is a *visual* coordinate here, not a claim about the
recording — it only has to move where the music moves (register up when the line goes up),
and the probe's octave histogram (C3 14 / C4 30 / C5 4) says it does.

This module is a pure lookup: no state, no numpy at import time beyond the json load.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PATH = ROOT / "data" / "piano_score.json"

# (t, midi, strength, dur) — dur is filled in below as the gap to the next onset
NOTES: list[tuple[float, int, float, float]] = []

MIN_DUR, MAX_DUR = 0.22, 2.20

if _PATH.exists():
    _raw = json.loads(_PATH.read_text(encoding="utf-8"))
    _ev = sorted(_raw.get("events", []), key=lambda e: e["t"])
    for i, e in enumerate(_ev):
        gap = (_ev[i + 1]["t"] - e["t"]) if i + 1 < len(_ev) else 1.0
        # a struck note rings until the next one takes over, clamped: a 90 ms gap must not
        # produce a 90 ms bar (it would read as a broken grid), and a 4 s silence must not
        # stretch one bar across the whole roll
        dur = max(MIN_DUR, min(MAX_DUR, gap * 0.92))
        NOTES.append((float(e["t"]), int(e["midi"]), float(e["s"]), round(dur, 3)))
    SOURCE = f"measured ({_PATH.name}, {len(NOTES)} onsets)"
else:
    SOURCE = "empty (piano_score.json missing)"


# ---- the guitar's onsets, for the A① TAB cell (probes/onset_probe.py other 80 92) ----
_GTR_PATH = ROOT / "data" / "onsets_other.json"
GTR: list[tuple[float, int, float]] = []
if _GTR_PATH.exists():
    for _e in json.loads(_GTR_PATH.read_text(encoding="utf-8")).get("events", []):
        GTR.append((float(_e["t"]), int(_e["midi"]), float(_e["s"])))
    GTR.sort()


def _load_onsets(name: str) -> list[tuple[float, int, float]]:
    fp = ROOT / "data" / ("onsets_%s.json" % name)
    out = []
    if fp.exists():
        for e in json.loads(fp.read_text(encoding="utf-8")).get("events", []):
            out.append((float(e["t"]), int(e["midi"]), float(e["s"])))
        out.sort()
    return out


DRUM = _load_onsets("drums")
BASS = _load_onsets("bass")


def window(t0: float, t1: float) -> list[tuple[float, int, float, float]]:
    """Notes whose attack falls inside [t0, t1). Linear scan — the table is short."""
    return [n for n in NOTES if t0 <= n[0] < t1]


def canon(notes, *, delay: float = 0.534, semis: int = 7, lo: int = 36, hi: int = 71):
    """A strict canon of the same figure: up a fifth, one beat later.

    巴洛克对位感 — the director asked for it, and a canon is the honest way to get a second
    voice out of one measured line: it is a delay line, not invented music. Drawn in a
    second colour, at low alpha, and labelled `CANON +7 / 1b` so nothing pretends to be
    transcribed from the record.
    """
    out = []
    for (t, m, s, d) in notes:
        mm = m + semis
        if mm > hi:
            mm -= 12
        if lo <= mm:
            out.append((t + delay, mm, s * 0.8, d))
    return out


if __name__ == "__main__":
    print(SOURCE)
    for n in window(147.0, 150.0):
        print("  %.3f  midi %3d  s %.2f  dur %.2f" % n)
