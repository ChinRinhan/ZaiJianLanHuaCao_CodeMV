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


# ---- the boot console: one command per lift, one module per command -----------------
# plan/19: "前奏每一个起伏就CRT上电出不同模块". Each row is a measured +4..+9 dB jump in
# the mix; the command prints in the console (the token band) and the module opens through
# its CRT aperture in whatever zone it lives in. The console line and the module are ONE
# event — that is the command-line grammar the director asked for.
#
#   t      dB   command           module that opens             where
#   5.2   --    mount ui/         the four-zone workbench       whole frame
#   6.6  +6.7   load meter        LEVEL meter                   ops
#  15.0  +4.1   load wave         SIGNAL plate + waveform       content
#  20.0  +8.7   load spectrum     22 bands                      content
#  32.0  +8.7   load playlist     PLAYLIST 13                   entity
#  38.0  +5.3   load score        SCORE / CH                    ops
#  42.0  +6.8   load syslog       telemetry read-outs           content
#  47.0  +7.6   load sleeve       nameplate (the album card)    entity
#  64.0  -10.8   standby          all modules dim, wait         whole machine
BOOT_CMDS = [
    (5.20, "mount ui/",     "skeleton"),
    (6.60, "load meter",    "meter"),
    (15.0, "load wave",     "wave"),
    (20.0, "load spectrum", "spectrum"),
    (32.0, "load playlist", "playlist"),
    (38.0, "load score",    "score"),
    (42.0, "load syslog",   "ticker"),
    (47.0, "load sleeve",   "sleeve"),
    (64.0, "standby",       None),
]
REVEAL = 0.55          # how long one CRT aperture takes to open


def _boot_state(t: float):
    """{module: reveal u} while the intro is assembling, None once the song starts."""
    if t >= 67.85:
        return None
    st = {}
    for t0, _cmd, key in BOOT_CMDS:
        if key is None:
            continue
        st[key] = 0.0 if t < t0 else min(1.0, (t - t0) / REVEAL)
    # standby: powered but idle — the machine waits for the voice (crt.py's idle state)
    st["idle"] = 0.0 if t < 64.0 else min(1.0, (t - 64.0) / 1.2)
    return st


def _console_for(t: float):
    """What the terminal would print: one line per command, locked when its module is up."""
    out = []
    for t0, cmd, key in BOOT_CMDS:
        if t < t0:
            break
        tail = "" if key is None else ("  ok" if t - t0 >= REVEAL else "  ..")
        out.append((t0, f"$ {cmd}{tail}"))
    return out


# ---- the emotional rise into B① (导演: 0:25 起情绪逐渐上升，到「给我…」画面要提高) ----
# Rising points measured from the stems, the per-character times and the analysis video
# (see the work log 2026-10-26). The vocal pace is itself a ladder: 0.61 → 0.33 → 0.18
# s/字 across lines 8-10 — the words arrive 3.3x faster as the emotion climbs, and the
# picture has to climb with them. 97-101 keeps its breath (「谁记得」的吸气) but the
# envelope is rising throughout.
#   89.0   bass walks in                 94.83  「茶花樱花满山开」世界打开
#   97.11  唱速翻倍                      99.30  全曲最快句（吸气）
#   103.84 「给我…」炸开                 126    呐喊
RISE_KEYS = [
    (87.0, 0.00), (89.0, 0.18), (94.83, 0.45), (97.11, 0.62),
    (99.30, 0.72), (103.84, 0.88), (107.0, 1.00), (124.0, 1.00),
]


def _rise(t: float) -> float:
    """How far the emotional climb has gone, 0..1 (pure function of t)."""
    return _ramp(t, RISE_KEYS)


# ---- the poem in the world: 胡适's first line, rewritten once ---------------------
# 导演三条: 世界里只放首句「我从山中来」(一次，克制)；替换动效 = 旧字划掉→新字 decode
# 打上去（与机器层同语法）；清空期诗句静淡一行不闪。
# The world carries 1921's line. The machine's REWRITE 01 (我→谁) propagates INTO the
# world when its hold expires — "the machine edited, now the world accepts it". When the
# mountain rises the line lands on the ridge: once in the whole film (plan/05 §3.2).
POEM_OLD = "我从山中来"
POEM_FADE = (67.85, 68.60)     # 静淡一行，慢淡入，不闪
POEM_STRIKE = 70.39            # REWRITE 01 hold ends → the world takes the edit
POEM_TYPE = 70.65              # 谁 decode-typed in place
POEM_RIDGE = (94.20, 96.50)    # horizon copy → ridge copy, riding the rising mountain
POEM_OUT = (101.90, 103.50)    # fades before B① takes the screen


def _poem_state(t: float):
    """The world-layer poem's state at t, or None. Pure function of t."""
    if not (POEM_FADE[0] <= t < POEM_OUT[1]):
        return None
    a = min(1.0, max(0.0, (t - POEM_FADE[0]) / (POEM_FADE[1] - POEM_FADE[0])))
    if t >= POEM_OUT[0]:
        a *= max(0.0, (POEM_OUT[1] - t) / (POEM_OUT[1] - POEM_OUT[0]))
    if t < POEM_RIDGE[0]:
        ridge = 0.0
    elif t < POEM_RIDGE[1]:
        u = (t - POEM_RIDGE[0]) / (POEM_RIDGE[1] - POEM_RIDGE[0])
        ridge = u * u * (3 - 2 * u)
    else:
        ridge = 1.0
    type_age = (t - POEM_TYPE) if t >= POEM_TYPE else None
    # the strike and the dead glyph fade out once the new one has locked, so the line
    # settles to 「谁从山中来」 with no scar left behind
    if type_age is None:
        strike_a = min(1.0, max(0.0, (t - POEM_STRIKE) / 0.25))
    elif type_age < 1.0:
        strike_a = 1.0
    else:
        strike_a = max(0.0, 1.0 - (type_age - 1.0) / 0.6)
    return {
        "alpha": a,
        # the horizon copy gets out of the way early so the handover to the ridge
        # never shows the line twice
        "horizon": max(0.0, 1.0 - ridge * 1.8),
        "ridge": ridge,
        "strike": t >= POEM_STRIKE,
        "strike_u": min(1.0, max(0.0, (t - POEM_STRIKE) / 0.35)),
        "strike_a": strike_a,
        "type_age": type_age,
        "box_a": (min(1.0, max(0.0, (t - POEM_STRIKE) / 0.2))
                  * max(0.0, min(1.0, (POEM_TYPE + 2.2 - t) / 0.8)))
        if t >= POEM_STRIKE else 0.0,
    }


# ---- the lyric as token chips -------------------------------------------------------
def _lyric_state(t):
    """(chars, typed, struck, cursor, old, times) for the token band / the page.

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
        return [], 0, None, True, None, None

    chars = list(cur["text"])
    times = line_times(cur)
    n = 0
    if times and len(times) == len(chars):
        while n < len(chars) and times[n] <= t + 1e-6:
            n += 1
    else:
        times = None
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
        return chars, n, struck, n < len(chars), old, times
    return chars, n, None, n < len(chars), None, times


def _cue_at(t):
    """The stage direction, if one is happening now (啊预备唱 / 第二步 / 升key / 再升).

    plan/19 §2 row 3: the four stage directions are NOT lyric text — they are shown as
    their own red `>>` line, never mixed into the words.
    """
    cur, _nxt = scene.line_at(t)
    if cur and cur.get("cue") and t >= cur["cue_at"] - scene.LEAD:
        return cur["cue"]
    return None


def _b1_big(t):
    """B①' four demands, stamped across the whole frame (plan/05 §4).

    This is the only place in the film where type covers both panes — the loudest 18 s
    get the whole screen. The same words must not also crawl through the token band, so
    the token band is emptied while they are up.

    Returns (word, alpha, age) — age lets the drawing layer land the phrase like thunder.
    """
    if not (103.84 <= t < 124.0):
        return None
    w, a_in, a_out, age = scene._b1_word(t)
    if not w:
        return None
    return w, a_in * a_out, age


def _undo_at(t):
    """The one character that goes back to its pre-rewrite version, for 0.6 s (plan/16 §2.3)."""
    return scene.undo_at(t)


# ---- the world state for a given time ----------------------------------------------
def _world_kw(t, *, mode="W", collapse=0.0):
    """The content zone's keyword arguments at time t."""
    sec = scene.section_at(t)
    sid = sec[0]
    _id, _s, _e, mood, cold, flower, entity, rain, spiral, amp, fx, cnt = sec

    # A①' three waves (plan/12 ②). Before 94.20 the world is EMPTY on purpose: the
    # mountain is supposed to appear with the line that says the mountain is full of flowers.
    if t < 67.85:
        # the intro: the WORLD is dark — the machine is getting ready and the world has
        # not been put on yet (plan/19 §4). The SIGNAL plate is not the world, it is the
        # machine's own instrument, so it powers on with `load wave` / `load spectrum`.
        n = scene.intro_layer(t)
        idle = 1.0 if t < 64.0 else max(0.0, 1.0 - (t - 64.0) / 3.0)
        ramp = lambda k: min(1.0, max(0.0, (t - (scene.INTRO_LAYERS[k][0] - 0.6)) / 1.2))
        return dict(sky_a=0.0, ridge_a=0.0, star_a=0.0, rain_a=0.0, plate_a=1.0,
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
    # B① 雷霆: the demands do not sit on a still image — the world shakes as they land
    if 103.84 <= t < 124.0:
        amp_scale *= 1.0 + 0.22 * drive.drum_hit(t)
    # the emotional climb (导演: 画面要有提高和上升) — the world gains energy as 宝哥 does
    rise = _rise(t)
    if 87.0 <= t < 124.0:
        amp_scale *= 0.88 + 0.24 * rise

    # the column: it exists only while someone is singing, and in A① it also waits for
    # the beam wave (plan/12 ②). The climb makes it taller — 宝哥的情绪在往上走.
    col = entity
    if in_a1:
        col = entity * w_beam
    if 87.0 <= t < 124.0:
        col *= 1.0 + 0.40 * rise

    return dict(
        # the sky comes with the terrain: plan/12 ② says the WORLD arrives in waves, and
        # a sky that is already there while the mountain is not is a different film.
        sky_a=w_ter if in_a1 else 1.0,
        ridge_a=w_ter,
        star_a=max(0.0, 1.0 - 0.55 * mood) * (w_ter if in_a1 else 1.0),
        rain_a=rain,
        # the SIGNAL plate is the MACHINE's instrument, not the world — it powered on
        # during the prelude (`load wave`) and stays on. Only A④'s subtraction drains it.
        plate_a=w_hud if t >= 358.92 else 1.0,
        pot_a=pot,
        pot_count=1 if in_a1 else cnt,
        pot_x=0.845 if in_a1 else fx,
        column_a=col,
        floor=floor,
        amp_scale=amp_scale,
        x_off=x_off,
        # the climb (导演: 画面要有提高和上升) — drives sky warmth, star brightness, glow
        rise=rise,
        # plan/12 ①: the ground stays even when the world is gone. The horizon fades out
        # as the mountain arrives, so it never cuts across a ridge.
        horizon=(1.0 - w_ter) if in_a1 else 0.0,
        # the poem's first line lives in the world during A① (导演三条)
        poem=_poem_state(t),
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
    # 0-5.2 s: the code stream — a disc goes into a machine and the machine reads it.
    # That part is finished and the director likes it; it runs unchanged.
    if t < 5.2:
        return preview.intro_scene(t)
    # 5.2 s on: NO crossfade into the workbench. A command line brings the workbench up
    # through its CRT aperture (`> mount ui/`), and every prelude lift runs one more
    # command that opens one more module. The console in the token band is the grammar.
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

    chars, typed, struck, cursor, old, times = _lyric_state(t)
    cue = _cue_at(t)
    big = _b1_big(t)
    undo = _undo_at(t)
    playing = 67.85 <= t < 386.5
    state = "PLAY" if playing else ("LOAD" if t < 67.85 else "READY")

    # B①' demands are stamped over the world; the same words must not also crawl
    # through the token band (plan/05 §4: one text, one place)
    if big:
        chars, typed, struck = [], 0, None

    # the UNDO: one character goes back to its pre-rewrite version for 0.6 s
    if undo:
        _idx, _oldch = undo
        if _idx < len(chars):
            chars = list(chars)
            chars[_idx] = _oldch

    kw = _world_kw(t, mode=mode, collapse=collapse)
    # B① 界面过载（plan/05 §4: 评分冲顶、播放列表被挤、口令闪）— the machine is being
    # blasted; the interface visibly suffers for it.
    if 103.84 <= t < 124.0:
        ov = min(1.0, max(0.0, (t - 103.84) / 1.6)) * min(1.0, max(0.0, (124.0 - t) / 1.2))
    else:
        ov = 0.0
    ent = dict(tray=0.0, disc=True, rpm=8.3 if t >= 2.24 else 0.0,
               state=state, power="PLAY" if playing else "ON",
               nameplate=True, squeeze=ov)

    boot = _boot_state(t)
    paper_kw = dict(sub=None, horizon=0.10)
    if mode == "P":
        # the page: the lyric large and centred, one horizon at the foot
        return layout4.frame(
            t, mode="P", chars=chars, typed=typed, struck=struck, cursor=cursor,
            state=state, playing=playing, paper_kw=paper_kw, old=old, cue=cue,
            times=times, boot=boot)

    return layout4.frame(
        t, mode="W", collapse=collapse,
        entity_kw=ent, content_kw=kw,
        score=scene.score_at(t), level=scene.level_at(t),
        chars=chars, typed=typed, struck=struck, cursor=cursor,
        state=state, playing=playing,
        old=old, cue=cue, big=big, times=times, boot=boot, overload=ov,
        glow=0.30 + 0.16 * _rise(t),
        log=_console_for(t) if boot is not None else None)


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
