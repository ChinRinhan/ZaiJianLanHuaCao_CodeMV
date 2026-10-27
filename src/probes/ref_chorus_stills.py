# -*- coding: utf-8 -*-
"""Render the reference PV's chorus shots as stills, without the whole pipeline.

The reference repo (`world-execute-me-dsh-pv-main`) renders its PV with PIL, but the full
build also needs Node + Playwright (the left pane is HTML screenshots). We only want the
RIGHT pane's chorus shots, so we construct the engine's `Ctx` by hand and call the shot
functions directly.

Shots:
  shot_unite     two tokens ('me' / 'you') fly together and fuse into 'we'  (sec_chorus1)
  shot_deeply    the same idea in embedding space                            (sec_chorus1)
  shot_moe_dense the MoE router lights up 6 -> 384 experts                   (sec_chorus2)
  shot_flood     six 'ME' flood the machine cell by cell, then a red plate   (sec_chorus2)

Run: python src/probes/ref_chorus_stills.py
"""
from __future__ import annotations

import random
import sys
import types
from pathlib import Path

REF = Path(r"F:\dafeiyu\repo-analysis\world-execute-me-dsh-pv-main\film\tui_pv_world_execute_20260926\full")
sys.path.insert(0, str(REF))

# Python 3.13 removed `audioop`; the reference repo's `music.py` imports it for the LEFT pane
# (the mascot's audio). We only render the right pane, but the import still happens, so a
# tiny stub keeps the module importable.
if "audioop" not in sys.modules:
    try:
        import audioop  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("audioop")
        stub.rms = lambda frag, width: 0.0
        stub.mul = lambda frag, factor: frag
        stub.avg = lambda frag, width: 0.0
        stub.max = lambda frag, width: 0
        stub.min = lambda frag, width: 0
        stub.findfit = lambda frag, target: (frag, 1.0)
        sys.modules["audioop"] = stub

from PIL import Image, ImageDraw  # noqa: E402

import engine  # noqa: E402

# We are rendering the RIGHT pane's chorus shots as stills, not the PV. The reference
# engine resolves lyric anchors at import time against the real song's LRC, which this
# checkout does not ship (only the source is here). So: replace the resolver with a
# permissive one that returns a synthetic time. Every shot we call draws from `c.t` /
# `c.u` and its own geometry, so the exact anchor values do not matter for the look.
def _lyric_start(prefix, after=0.0):
    for a, _b, s in engine.LYRICS:
        if a >= after - 1e-6 and s.lower().startswith(str(prefix).lower()):
            return a
    return 60.0


engine.lyric_start = _lyric_start

# `me_pane` draws the LEFT pane (the chat window's mascot) and needs the real pose
# sprite files, which this checkout does not ship. We are after the RIGHT pane only, so
# the mascot is stubbed out; the shots' own drawings are unaffected.
engine.me_pane = lambda *a, **k: None

import sec_chorus1 as c1  # noqa: E402
import sec_chorus2 as c2  # noqa: E402

for _mod in (c1, c2):
    if hasattr(_mod, "lyric_start"):
        _mod.lyric_start = _lyric_start
    if hasattr(_mod, "me_pane"):
        _mod.me_pane = lambda *a, **k: None

OUT = Path(__file__).resolve().parents[2] / "out" / "review-frames" / "ref-chorus"


def shot(fn, name, u: float, dur: float = 4.0, t: float = 100.0):
    """Call one shot function with a hand-made Ctx."""
    img = Image.new("RGB", (engine.W, engine.H), engine.BG)
    c = engine.Ctx(img, ImageDraw.Draw(img), t, u * dur, dur, random.Random(11))
    fn(c)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / ("%s_u%03d.png" % (name, int(u * 100)))
    img.save(p)
    return p


def main():
    made = []
    for u in (0.15, 0.55, 0.95):
        made.append(shot(c1.shot_unite, "unite", u))
        made.append(shot(c2.shot_flood, "flood", u))
    made.append(shot(c1.shot_deeply, "deeply", 0.6))
    made.append(shot(c2.shot_moe_dense, "moe", 0.5))
    for p in made:
        print("wrote", p)


if __name__ == "__main__":
    main()
