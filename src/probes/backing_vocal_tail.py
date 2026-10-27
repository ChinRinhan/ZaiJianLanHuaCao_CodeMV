# -*- coding: utf-8 -*-
"""The backing vocal, line by line, through A③ and A④ as well.

`backing_vocal_full.py` measured B① / B② / A②. But A③ (5:12.45, key change) and A④
(5:58.92) are the *last two thirds* of the film, and they are the loudest chorus in the
whole song — the section-level cosine already says so:

    A2  back/lead −3.85 dB   spectral_cos 0.513
    A3  back/lead −1.75 dB   spectral_cos 0.404
    A4  back/lead −0.10 dB   spectral_cos 0.375   <- the backing is as loud as the lead

A④ is where the backing voice matches the lead almost exactly (0.1 dB apart). If the
picture draws A④ with the same number of voices as A②, it is under-stating the ending.
So A③/A④ need their own per-line measurement, on the same footing as A②.

The line boundaries come from `data/word_times_v2.json` (measured per-character onsets),
not from guesswork: each sung line starts at its first character's onset, and ends where
the next line starts (the last line of A④ ends at the song's end).

Run: ./.venv-audio/Scripts/python.exe src/probes/backing_vocal_tail.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "再见 兰花草 - 张雨生_分轨"
OUT = ROOT / "data" / "backing_vocal_tail.json"
WORD_TIMES = ROOT / "data" / "word_times_v2.json"

# the song ends at 387.00 (A④'s last line runs to the end; there is no outro)
SONG_END = 387.00


def _lines():
    """(group, n, t0, t1, text) for A③ and A④, from the measured per-character onsets."""
    wt = json.loads(WORD_TIMES.read_text(encoding="utf-8"))
    rows = wt["lines"]
    starts = [(float(r["t0"]), r["text"]) for r in rows]

    def pick(a, b):
        return [(t, x) for t, x in starts if a <= t < b]

    out = []
    for grp, a, b in (("A3", 312.45, 358.92), ("A4", 358.92, SONG_END)):
        got = pick(a, b)
        for i, (t0, text) in enumerate(got):
            t1 = got[i + 1][0] if i + 1 < len(got) else b
            out.append((grp, i + 1, round(t0, 2), round(t1, 2), text))
    return out


def _voices_for(rel: float) -> int:
    """How many voices the picture should show, from the backing's level vs the lead.

    Same thresholds as `backing_vocal_full.py` (they were set against B① / B② and
    re-checked against A②), so the three sections stay comparable.
    """
    if rel < -8.0:
        return 1
    if rel < -6.0:
        return 2
    if rel < -3.5:
        return 3
    if rel < -1.5:
        return 4
    if rel < 0.5:
        return 5
    return 6


def main():
    if not STEMS.exists():
        print("no separated stems at", STEMS)
        return
    lead, sr = sf.read(str(STEMS / "再见 兰花草 - 张雨生_主唱人声.mp3"), dtype="float32")
    back, _ = sf.read(str(STEMS / "再见 兰花草 - 张雨生_背景和声.mp3"), dtype="float32")
    if lead.ndim == 2:
        lead = lead.mean(axis=1)
    if back.ndim == 2:
        back = back.mean(axis=1)

    def db(x, a, b):
        s = x[int(a * sr):int(b * sr)]
        if s.size == 0:
            return -120.0
        return float(20.0 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-12))

    res = []
    for grp, n, t0, t1, text in _lines():
        ld, bk = db(lead, t0, t1), db(back, t0, t1)
        rel = bk - ld
        res.append({"group": grp, "n": n, "t0": t0, "t1": t1, "text": text,
                    "lead_db": round(ld, 1), "back_db": round(bk, 1),
                    "rel_db": round(rel, 1), "voices": _voices_for(rel)})
        print("%-3s #%-2d  %-16s  lead %6.1f  back %6.1f  rel %+5.1f dB  -> %d voices"
              % (grp, n, text[:14], ld, bk, rel, res[-1]["voices"]))
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
