# -*- coding: utf-8 -*-
"""scene4: the film, rendered in the four-zone layout.

WHY A SEPARATE MODULE (and not "layout4 replaces preview.py").

`preview.py` is 1300 lines and carries the whole film: the disc-insertion opening, the
cell-by-cell CRT fill, the seven intro modules, the GAME SET card and the 3% black. All of
that is *finished and verified* — it is what produced out/film.mp4. `layout4.py` is a
different layout: a 512 px entity column, a 752 px world, an 80 px ops column and a 90 px
token band, with the lyric as character chips.

Two options:

  (a) rewrite preview.py to draw in the new layout — that means re-doing the opening, the
      fill, the ending and every module, and the old film stops existing;
  (b) keep both, and have this module drive the new layout.

(b) is what this file is. The old film stays renderable (`scene.frame`), the new one is
`scene4.frame`, and they can be compared side by side on the same second. The pieces that
are layout-independent are *reused*, not reimplemented: the opening and the ending are
still preview's, because they are about the machine, and the machine is in both layouts.

What is new here:
  - the four zones, for the whole film, not just for A①;
  - the three shot modes W / P / V, and the 10-shot table for A① (src/shots.py);
  - the per-character times from the measured alignment (data/word_times_v2.json);
  - the world, rebuilt inside the content zone so the entity column does not fight it.

The frame is still a pure function of t: no state, no previous frame, any second can be
re-rendered alone.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import clock
import drive
import layout4
import preview
import scene
import shots
import tk
from layout4 import AMBER, BG, BLUE_HI, BLUE_MID, GREEN, RED, fade, font, mix

ROOT = Path(__file__).resolve().parents[1]
FPS = 24
DUR = scene.DUR

# ---- the per-character times: measured, not spread ---------------------------------
# plan/17 §7 档 B. If data/word_times_v2.json is missing the film still renders, using
# the old spread times — a missing data file must not take the film down.
#
# Two shifts have to be undone, or every lookup misses and the film silently falls back
# to spread times (which is exactly what happened on the first attempt):
#
#   1. scene.LINES stores t as `lrc_t + OFFSET - LEAD`, i.e. 0.06 s EARLIER than the LRC
#      time, because the lyric appears a hair before the attack.
#   2. the alignment table's `text` still carries the leading instruction
#      ("（啊预备唱）谁从山中来带着兰花草"), so its per-character times include the cue
#      characters. scene.py cuts them off; so must this.
_WT_V2 = ROOT / "data" / "word_times_v2.json"
TIMES = {}
if _WT_V2.exists():
    _wt = json.loads(_WT_V2.read_text(encoding="utf-8"))
    for _l in _wt["lines"]:
        _txt = _l["text"]
        _cue, _body = scene._split_cue(_txt)
        _cut = len(_cue) + 2 if _cue else 0
        _times = _l["times"][_cut:][:len(_body)] if _cut else _l["times"][:len(_body)]
        if len(_times) != len(_body):
            continue          # the table does not match this line: fall back for it
        # the times are on the LRC clock; the scene wants them on the video clock
        _vt = [x + scene.OFFSET - scene.LEAD for x in _times]
        TIMES[round(float(_l["t0"]) + scene.OFFSET - scene.LEAD, 3)] = _vt
        TIMES[round(float(_l["t0"]), 3)] = _vt
    TIMES_SOURCE = "measured (vocals flux + grid DP)"
else:
    TIMES_SOURCE = "spread (word_times_v2.json missing)"


def line_times(line):
    """The measured per-character times for a scene line, or None."""
    if not line:
        return None
    return TIMES.get(round(line["t"], 3))


# ---- the world, drawn into the content zone ----------------------------------------
# layout4.content() is the four-zone world. The A① wave tables (plan/12 ②) are layered on
# top of it: the mountain, the beam and the instrument plate arrive in three waves, and
# the pot shrinks all the way back on the last line.

#  t, orchid height (plan/12 / plan/11 §4)
ORCHID = [
    (67.20, 0.0), (67.85, 108.0), (78.88, 158.0), (90.58, 214.0),
    (94.83, 240.0), (97.11, 258.0), (99.30, 278.0), (100.50, 278.0),
    (101.90, 132.0), (103.84, 126.0),
]
W_TERRAIN = [(94.20, 0.0), (94.83, 0.10), (97.11, 0.45), (99.30, 0.80), (100.50, 1.0)]
W_BEAM = [(96.80, 0.0), (97.11, 0.30), (99.30, 0.70), (101.50, 1.0)]
W_HUD = [(99.10, 0.0), (99.30, 0.18), (101.20, 0.62), (102.60, 1.0)]


def _ramp(t, keys):
    if t <= keys[0][0]:
        return keys[0][1]
    for i in range(len(keys) - 1):
        t0, v0 = keys[i]
        t1, v1 = keys[i + 1]
        if t0 <= t <= t1:
            u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * (u * u * (3 - 2 * u))
    return keys[-1][1]


def _orchid_h(t):
    return _ramp(t, ORCHID)


# ---- the ops column: what the machine is doing, one name per beat ------------------
# plan/19 §5 item 2 needs the ops column to name the real operations. These are the
# measured events of the intro (scene.INTRO_BOOTS) and the section names of the body.
def _ops_names(t):
    if t < 67.85:
        names = ["BOOT", "FW 1.04", "STANDBY"]
        for t_at, mid, lab in scene.INTRO_BOOTS:
            if t >= t_at:
                names.append(lab.split()[0])
        return names[-6:]
    sec = scene.section_at(t)
    sid = sec[0]
    base = {
        "A1": ["PLAY 013", "RMS", "FFT.22", "TYPE"],
        "B1": ["PLAY 013", "PEAK", "STAMP", "TYPE"],
        "shout": ["NO VOCAL", "SHOUT", "FULL BLAST"],
        "boutro": ["IDLE", "TAIL", "THINNING"],
        "piano": ["PIANO SOLO", "ONE LINE", "WAIT"],
        "duet": ["DUET", "TRADE", "WAIT"],
        "bass": ["BASS", "GUITAR", "WAIT"],
        "roar": ["GUITAR", "ROAR", "FULL"],
        "cool": ["THIN", "COOL", "WAIT"],
        "B2": ["PLAY 013", "RMS", "TYPE"],
        "A2a": ["PLAY 013", "RMS", "TYPE"],
        "A2b": ["PLAY 013", "KEY +1", "TYPE"],
        "A3a": ["PLAY 013", "PEAK", "KEY +3", "TYPE"],
        "A3b": ["PLAY 013", "PEAK", "KEY +3", "TYPE"],
        "A4a": ["PLAY 013", "SUBTRACT", "TYPE"],
        "A4b": ["PLAY 013", "SUBTRACT", "TYPE"],
    }
    return base.get(sid, ["PLAY", "RMS", "TYPE"])


def _ops_hi(t):
    """Which ops row is the live one — the most recent operation."""
    names = _ops_names(t)
    return max(0, len(names) - 1)


# ---- the boot log for the opening ---------------------------------------------------
BOOT = [
    (0.4, "LD-1994  LASER KARAOKE SYSTEM"),
    (0.9, "FW 1.04   SRV 0001  OK"),
    (1.6, "TRAY OPEN"),
    (2.6, "DISC INSERTED  CD-DA"),
    (3.4, "SEAT OK   CLAMP ON"),
    (4.2, "SPINDLE START"),
    (5.2, "FOCUS OK   TRACKING ON"),
    (6.2, "TOC READ  SECTOR 000000"),
    (7.4, "TOC OK    013 TRACKS"),
    (8.0, "READY     SIDE A"),
]
MOUNT = [
    (9.0, "MOUNT     WORLD/         OK"),
    (20.0, "SKY.CFG   16:9  4.7 MB   OK"),
    (32.0, "TERRAIN   3 LAYERS       OK"),
    (38.0, "ANALOG    22 BAND        OK"),
    (47.0, "FLORA     1 POT 2 BLOOM  OK"),
    (64.0, "ALL MODULES LOADED"),
]


def _log_for(t):
    return BOOT + (MOUNT if t >= 9.0 else [])


# ---- the lyric as token chips -------------------------------------------------------
def _lyric_state(t):
    """(chars, typed, struck, cursor, old) for the token band / the page.

    The typing is driven by the MEASURED per-character times when they are available, so a
    character lands when it is actually sung instead of when an even spread says so.

    The rewrite does NOT replace the line (plan/10 §5.1: "字写了一半，突然变成对照表，像
    故障而不像设计"). The old version is struck through above and the new one keeps being
    written underneath — plan/11 §3: 纸不动，笔不停. So during a rewrite the pen keeps
    moving on the SAME clock, and the line simply continues after the rewrite window.
    """
    cur, nxt = scene.line_at(t)
    rw = scene.rewrite_at(t)
    if not cur:
        return [], 0, None, True, None

    chars = list(cur["text"])
    times = line_times(cur)
    n = 0
    if times and len(times) == len(chars):
        while n < len(chars) and times[n] <= t + 1e-6:
            n += 1
    else:
        span = 2.6
        nxt_t = nxt["t"] if nxt else cur["t"] + span
        span = max(0.5, (nxt_t - cur["t"]) * 0.86)
        n = int(min(1.0, max(0.0, (t - cur["t"]) / span)) * len(chars))

    if rw:
        old, _new, idx, _label = rw
        # The line being sung is ALREADY the new version — scene.LINES carries the sung
        # text, and REWRITES only records the pair for the display. So the pen keeps
        # running on the measured clock of the current line and the old version is shown
        # struck through above it. (REWRITES 03/04 replace TWO lines with one, so using
        # the table's "new" string would type 14 characters on a 7-character clock.)
        struck = idx if 0 <= idx < len(chars) else None
        return chars, n, struck, n < len(chars), old
    return chars, n, None, n < len(chars), None


def _cue_at(t):
    cur, _nxt = scene.line_at(t)
    if cur and cur.get("cue"):
        return cur["cue"]
    return None


# ---- the world state for a given time ----------------------------------------------
def _world_kw(t, *, mode="W", collapse=0.0):
    """The content zone's keyword arguments at time t."""
    sec = scene.section_at(t)
    sid = sec[0]
    _id, _s, _e, mood, cold, flower, entity, rain, spiral, amp, fx, cnt = sec

    # A①' three waves (plan/12 ②). Before 94.20 the world is EMPTY on purpose: the
    # mountain is supposed to appear with the line that says the mountain is full of flowers.
    if t < 67.85:
        # the intro: the right pane is dark. The machine is getting ready; the world has
        # not been put on yet (plan/19 §4, and commit d95f739).
        n = scene.intro_layer(t)
        idle = 1.0 if t < 64.0 else max(0.0, 1.0 - (t - 64.0) / 3.0)
        ramp = lambda k: min(1.0, max(0.0, (t - (scene.INTRO_LAYERS[k][0] - 0.6)) / 1.2))
        return dict(sky_a=0.0, ridge_a=0.0, star_a=0.0, rain_a=0.0, plate_a=0.0,
                    pot_a=0.0, column_a=0.30 * ramp(0) * idle * 0.35, floor=0.70,
                    label="WORLD // VALLEY")

    w_ter = _ramp(t, W_TERRAIN)
    w_beam = _ramp(t, W_BEAM)
    w_hud = _ramp(t, W_HUD)

    # The A① wave tables are A①' contract. Outside A① the world runs on the section
    # table: the interlude's six movements are framed by BREAK_CAMERA, and A②/A③ are
    # full-strength. If the A① tables leaked past 103.84 the whole back half would be
    # pinned to A①'s mountain, which is the "right pane never moves" complaint again.
    in_a1 = 67.85 <= t < 103.84
    if not in_a1:
        w_ter = 1.0
        w_beam = 1.0
        w_hud = 1.0

    if t >= 358.92:
        # A④ is subtraction (plan/03 §4): the mountain, the beam and the plate drain away
        u4 = (t - 358.92) / (386.5 - 358.92)
        w_ter = 1.0 - 0.90 * u4
        w_beam = 1.0 - 1.00 * u4
        w_hud = 1.0 - 0.62 * u4

    # the pot: A①' shrink-to-fit table inside A①, the section's flower outside it
    if in_a1:
        pot = _orchid_h(t) / 235.0
    elif t >= 386.5:
        pot = max(0.0, 0.42 - (t - 380.99) / (386.5 - 380.99) * 0.42)
    else:
        pot = flower

    # the interlude's six movements each get their own framing (plan/19 §3.1)
    cam = scene.BREAK_CAMERA.get(sid)
    x_off, scale, floor = cam if cam else (0.0, 1.0, 0.70)
    amp_scale = amp * scale

    # the column: it exists only while someone is singing, and in A① it also waits for
    # the beam wave (plan/12 ②)
    col = entity
    if in_a1:
        col = entity * w_beam

    return dict(
        # the sky comes with the terrain: plan/12 ② says the WORLD arrives in waves, and
        # a sky that is already there while the mountain is not is a different film.
        sky_a=w_ter if in_a1 else 1.0,
        ridge_a=w_ter,
        star_a=max(0.0, 1.0 - 0.55 * mood) * (w_ter if in_a1 else 1.0),
        rain_a=rain,
        plate_a=w_hud,
        pot_a=pot,
        pot_count=1 if in_a1 else cnt,
        pot_x=0.845 if in_a1 else fx,
        column_a=col,
        floor=floor,
        amp_scale=amp_scale,
        x_off=x_off,
        # plan/12 ①: the ground stays even when the world is gone. The horizon fades out
        # as the mountain arrives, so it never cuts across a ridge.
        horizon=(1.0 - w_ter) if in_a1 else 0.0,
        label=("WORLD // " + sid.upper()) if sid in scene.BREAK_CAMERA else "WORLD // VALLEY",
    )


# ---- the frame ----------------------------------------------------------------------
def frame(t: float) -> Image.Image:
    """One frame of the four-zone film. Pure function of t."""
    # the ending chain is layout-independent and already finished: GAME SET, hard cut,
    # 3% black, the cursor, [谢谢收听]. Reused as-is (plan/19 §2 row 4).
    if t >= 386.5:
        return preview.ending_frame(t, cursor_on=True)
    if t >= scene.END_CUT:
        return preview.black_frame(t, cursor_on=t < DUR - 0.35, thanks=t >= 391.0,
                                   thanks_alpha=1.0 if t < 393.0
                                   else max(0.0, 1.0 - (t - 393.0) / 1.6))
    # the opening: the disc goes in, the machine comes up. preview's opening is about the
    # machine and is finished; reuse it rather than re-implementing it in a new layout.
    if t < 6.4:
        if t < 5.6:
            return preview.intro_scene(t)
        u = (t - 5.6) / 0.8
        return Image.blend(preview.intro_scene(t), _body(t), u)
    return _body(t)


def _body(t: float) -> Image.Image:
    """Everything from 6.4 s to 386.5 s, in the four-zone layout."""
    shot = shots.shot_at(t)
    mode = shot[3] if shot else "W"
    # during A① the three modes apply; everywhere else the film is one wide shot
    if t < 67.85 or t >= 103.84:
        mode = "W"

    # the entity column withdraws during the interlude: the machine physically gives the
    # frame to the world (layout4's own docstring).
    collapse = 0.0
    if 124.0 <= t < 245.79:
        u = min(1.0, (t - 124.0) / 1.2) if t < 138.0 else \
            min(1.0, max(0.0, 1.0 - (t - 240.0) / 5.0))
        collapse = u
    if mode == "V":
        collapse = 1.0

    chars, typed, struck, cursor, old = _lyric_state(t)
    cue = _cue_at(t)
    ops = _ops_names(t)
    playing = 67.85 <= t < 386.5
    state = "PLAY" if playing else ("LOAD" if t < 67.85 else "READY")

    kw = _world_kw(t, mode=mode, collapse=collapse)
    ent = dict(tray=0.0, disc=True, rpm=8.3 if t >= 2.24 else 0.0,
               state=state, power="PLAY" if playing else "ON",
               nameplate=True)
    if t < 5.6:
        ent = dict(tray=0.0, disc=False, rpm=0.0, state="STANDBY", power="ON")

    paper_kw = dict(sub=None, horizon=0.10)
    if mode == "P":
        # the page: the lyric large and centred, one horizon at the foot
        return layout4.frame(
            t, mode="P", chars=chars, typed=typed, struck=struck, cursor=cursor,
            state=state, playing=playing, paper_kw=paper_kw, old=old)

    return layout4.frame(
        t, mode="W", collapse=collapse,
        entity_kw=ent, content_kw=kw,
        ops_names=ops, ops_hi=_ops_hi(t),
        chars=chars, typed=typed, struck=struck, cursor=cursor,
        state=state, playing=playing,
        old=old,
        log=_log_for(t) if t < 67.85 else None)


if __name__ == "__main__":
    import sys
    out = Path(__file__).resolve().parents[1] / "out" / "scene4"
    out.mkdir(parents=True, exist_ok=True)
    ts = [float(x) for x in sys.argv[1:]] or [2.0, 8.5, 22.0, 40.0, 65.5, 69.0, 73.0,
                                              82.0, 86.0, 92.0, 95.5, 98.0, 100.0, 102.5,
                                              150.0, 320.0, 380.0, 386.7, 390.0]
    for t in ts:
        p = out / f"t{t:07.2f}.png"
        frame(t).save(p)
        print("wrote", p.name)
