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
import instruments
import layout4
import preview
import scene
import score3
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
    if not (103.84 <= t < scene.B1_END):
        return None
    w, a_in, a_out, age = scene._b1_word(t)
    if not w:
        return None
    # The slot closes BEFORE the first stamp (导演: 先画框再填). B1_T0 + B1_TYPE_WAIT is
    # where the pen finishes, so the first phrase is held back to that frame and lands at
    # 0.55 alpha already inside a closed form — a stamp, not a fade-up. Later phrases keep
    # their own start times, which is also what closes the gap between phrases (D).
    lt = max(t - age, B1_T0 + B1_TYPE_WAIT)
    if t < lt:
        return None                  # the slot is still closing: nothing is stamped yet
    a = 0.55 + 0.45 * min(1.0, (t - lt) / 0.14)
    return w, a * a_out, t - lt


# ---- 器乐格：一块东西的三个形态 ---------------------------------------------------
# 导演 (04:12)：1:42「给我…」到 2:00 是过渡，慢慢把界面转化成器乐合奏；位置不变。
#
# So the instrument column is ONE object with three states, all in frame coordinates:
#
#   83.35  292 px   column    three tracks (guitar / drums / bass)
#   102.4  grows    -> 640 px, the machine's own panel collapses to a lamp strip
#   103.84 640 px   FORM      the four demands are stamped INSIDE it
#   112.6  shrinks  -> 292 px, two 「直到」 lines travel in and land in the 05 slot
#   117.39 292 px   CLOCK     05 is assigned 02:25 (the distance to the chorus at 4:25)
#   118.6  fades    -> the six lanes come back: the form has become the band
CELL_T0 = 83.35
CELL_END = 245.79
CELL_W_COL = 292.0
CELL_W_FORM = 640.0
FORM_T0, FORM_T1 = 102.40, 103.80
FORM_HOLD, FORM_BACK = 112.60, 117.40
FORM_OUT0, FORM_OUT1 = 118.60, 120.00
LANES_T0 = 113.40
FORM_ROLL = 114.60          # the sheet rolls up into the strip by here
BASS_IN = 90.50


def _smooth(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _cell_w(t: float) -> float:
    """The column's width at t, in pixels (0 = not on screen)."""
    if t < CELL_T0 or t >= CELL_END:
        return 0.0
    if t > 243.60:
        return CELL_W_COL * max(0.0, (245.00 - t) / 1.40)
    if t < FORM_T0:
        return CELL_W_COL * min(1.0, (t - CELL_T0) / 0.55)
    if t < FORM_T1:
        return CELL_W_COL + (CELL_W_FORM - CELL_W_COL) * _smooth((t - FORM_T0) / (FORM_T1 - FORM_T0))
    if t < FORM_HOLD:
        return CELL_W_FORM
    if t < FORM_BACK:
        return CELL_W_FORM - (CELL_W_FORM - CELL_W_COL) * _smooth((t - FORM_HOLD) / (FORM_BACK - FORM_HOLD))
    return CELL_W_COL


def _form_collapse(t: float) -> float:
    """The machine gets out of its own way while the form is being stamped."""
    if t < FORM_T0 or t >= FORM_BACK:
        return 0.0
    if t < FORM_T1:
        return _smooth((t - FORM_T0) / (FORM_T1 - FORM_T0))
    if t < FORM_HOLD:
        return 1.0
    return 1.0 - _smooth((t - FORM_HOLD) / (FORM_BACK - FORM_HOLD))


def _cell_state(t):
    """The column's tracks at t (empty while the form is in it)."""
    w = _cell_w(t)
    if w <= 2.0:
        return None
    tracks = []
    if t >= scene.B1_END:
        # ⑤-A: six lanes, always all six — a lane is a CHAIR, not a spotlight. The one that
        # is playing is brighter and its notation moves; the others stay as quiet rails, so
        # the frame always answers "how many people are in this band".
        live = _stage_kw(t, scene.section_at(t)[0])["live"]
        lanes = [("GTR", "TAB", dict(onsets=score3.GTR, tuning=instruments.TUNING6,
                                     marks=())),
                 ("BAS", "TAB", dict(onsets=score3.BASS, tuning=instruments.TUNING4,
                                     marks=())),
                 ("DRM", "GRID", dict(onsets=score3.DRUM)),
                 ("PNO", "ROLL", dict(onsets=score3.NOTES)),
                 ("VLN", "CURVE", dict(onsets=score3.GTR)),
                 ("VOX", "COL", dict())]
        for name, kind, pay in lanes:
            pay["level"] = live.get(name, 0.0)
            tracks.append((name, kind, pay))
    elif t < FORM_T0 or t >= LANES_T0:
        tracks = [("GTR", "TAB", {"onsets": score3.GTR, "tuning": instruments.TUNING6,
                                  "level": drive.other(t),
                                  "marks": (106.15, 108.32, 110.64)})]
        if t >= 86.00 or t >= LANES_T0:
            tracks.append(("DRM", "GRID", {"onsets": score3.DRUM, "level": drive.drums(t)}))
        if t >= BASS_IN or t >= LANES_T0:
            tracks.append(("BAS", "TAB", {"onsets": score3.BASS, "tuning": instruments.TUNING4,
                                          "level": drive.bass(t)}))
    strum = -1.0
    if 86.00 <= t < 86.18:
        strum = (t - 86.00) / 0.18
    # the form needs a floor to be drawn on while its own content is absent
    return {"w": w, "cell": min(1.0, w / CELL_W_COL), "tracks": tracks,
            "alpha": min(1.0, w / 40.0),
            "sub": "A1" if t < scene.B1_END else scene.section_at(t)[0].upper(),
            "solo": None if t < scene.B1_END else MOVE_SOLO.get(scene.section_at(t)[0]),
            "strum": strum}


# ---- the form: the four demands, and the fifth line that is never asked for ------
# 导演 (04:12) ③: 倒计时只留短的 —— 2:00 → 4:25，正好 145 秒 = 2:25，而 4:25 是合唱
# (A② 4:26.3) 前的一刻。So the machine answers 「给我五分钟」 with 02:25: it shortens the
# promise to the distance that is actually left.
B1_T0, B1_T1 = 103.84, 136.6
B1_PEN = 0.28
B1_TYPE_WAIT = 0.32
B1_TICKS = (103.78, 106.15, 108.32, 110.64)
B1_CLOCK_T0 = 117.39
COUNTDOWN = 145.0            # 2:25 — from 2:00 to 4:25
B1_LAST_END = 112.89
B1_QUIET = 124.0
L1_T0, L1_T1 = 112.89, 115.18      # 「直到那一天我爱上她」
L2_T0, L2_T1 = 115.18, 117.39      # 「直到那一天我眼泪滑下」


def _demand_state(t):
    """The form's state at t, or None. Pure function of t."""
    if not (B1_T0 <= t < FORM_OUT1):
        return None
    stamped = 0
    for i, tt in enumerate(B1_TICKS):
        land = max(tt, B1_T0 + B1_TYPE_WAIT) if i == 0 else tt
        if t >= land:
            stamped = i + 1
    clock_on = t >= B1_CLOCK_T0
    a = 1.0
    if t >= B1_QUIET:
        a = 0.42
    if t > FORM_OUT0:
        a = min(a, max(0.0, 1.0 - (t - FORM_OUT0) / (FORM_OUT1 - FORM_OUT0)))
    hold = None
    if stamped and not clock_on:
        nxt = B1_TICKS[stamped] if stamped < len(B1_TICKS) else B1_CLOCK_T0
        hold = max(0.0, nxt - t)
    return {
        "pen": min(1.0, (t - B1_T0) / B1_PEN),
        "stamped": stamped,
        "hold": hold,
        "clock": "02:25" if clock_on else None,
        "phase": clock.beat_phase(t),
        "alpha": a,
        "line1": _smooth((t - L1_T0) / (L1_T1 - L1_T0)) if t >= L1_T0 else 0.0,
        "line2": _smooth((t - L2_T0) / (L2_T1 - L2_T0)) if t >= L2_T0 else 0.0,
        "shrink": _smooth((t - FORM_HOLD) / (FORM_ROLL - FORM_HOLD)) if t >= FORM_HOLD else 0.0,
    }


# the dial is born in the middle of the world, then takes its post at the bottom right
DIAL_T0 = 117.39
DIAL_CX, DIAL_CY = 642.0, 320.0      # centre of the 484 px world at 117.4–121.4
DIAL_TX, DIAL_TY = 1164.0, 656.0     # its post in the token band (tokens() draws there)
DIAL_MOVE = (120.20, 121.40)


def _countdown(t):
    """(text, alpha, done, outer, inner) for the token band's dial."""
    if t < 121.40:
        return None
    left = max(0.0, COUNTDOWN - (t - 120.0))
    a = 1.0
    if t > 264.0:
        a = max(0.0, 1.0 - (t - 264.0) / 4.0)
    if a <= 0.01:
        return None
    return ("%02d:%02d" % (int(left) // 60, int(left) % 60), a, left <= 0.0,
            min(1.0, (t - DIAL_T0) / 300.0), max(0.0, min(1.0, (t - 120.0) / COUNTDOWN)))


def _roll(text: str, age: float, *, step: float = 0.055, spin: float = 0.17,
          tick: float = 0.030) -> str:
    """A mechanical counter being set: each digit ticks up and lands on its own value.

    `tk.decode` was the first attempt and 导演 (04:54) called it 不规律 — it re-rolls each
    character on its own random clock, so nothing tells you the number is being SET.

    Here every digit starts at the value `n` ticks before its target and steps +1 on a
    fixed clock, so it lands EXACTLY on the target when it locks — a counter, not a
    scramble. Columns lock left to right, one every `step` seconds.
    """
    out = []
    n_ticks = max(1, int(round(spin / tick)))
    for i, ch in enumerate(text):
        if not ch.isdigit():
            out.append(ch)
            continue
        u = age - i * step
        tgt = int(ch)
        if u < 0:
            out.append("-")
        elif u < spin:
            start = (tgt - n_ticks) % 10
            out.append(str((start + int(u / tick)) % 10))
        else:
            out.append(ch)
    return "".join(out)


def _dial_state(t):
    """The dial while it is being assembled and moved. After DIAL_MOVE the band owns it."""
    if not (DIAL_T0 <= t < DIAL_MOVE[1]):
        return None
    left = max(0.0, COUNTDOWN - max(0.0, t - 120.0))
    txt = "%02d:%02d" % (int(left) // 60, int(left) % 60)
    seg = 1.0
    big = True
    if t < DIAL_T0 + 0.33:
        u = _smooth((t - DIAL_T0) / 0.33)
        r, seg, x, y, a = 46.0 * u, u, DIAL_CX, DIAL_CY, min(1.0, (t - DIAL_T0) / 0.10)
        txt = _roll(txt, t - DIAL_T0)
    elif t < DIAL_T0 + 0.71:
        u = _smooth((t - DIAL_T0 - 0.33) / 0.38)
        r, seg, x, y, a = 46.0 + 32.0 * u, 1.0, DIAL_CX, DIAL_CY, 1.0
        txt = _roll(txt, t - DIAL_T0)
    elif t < DIAL_MOVE[0]:
        r, seg, x, y, a = 78.0, 1.0, DIAL_CX, DIAL_CY, 1.0
    else:
        u = _smooth((t - DIAL_MOVE[0]) / (DIAL_MOVE[1] - DIAL_MOVE[0]))
        r = 78.0 + (15.0 - 78.0) * u
        x = DIAL_CX + (DIAL_TX - DIAL_CX) * u
        y = DIAL_CY + (DIAL_TY - DIAL_CY) * u
        big = u < 0.30
        a = 1.0
    return {"x": x, "y": y, "r": r, "outer": min(1.0, (t - DIAL_T0) / 300.0),
            "inner": max(0.0, min(1.0, (t - 120.0) / COUNTDOWN)),
            "text": txt, "alpha": a, "seg": seg, "big": big}


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
    if 103.84 <= t < scene.B1_END:
        amp_scale *= 1.0 + 0.22 * drive.drum_hit(t)
    # the emotional climb (导演: 画面要有提高和上升) — the world gains energy as 宝哥 does
    rise = _rise(t)
    if 87.0 <= t < scene.B1_END:
        amp_scale *= 0.88 + 0.24 * rise

    # the column: it exists only while someone is singing, and in A① it also waits for
    # the beam wave (plan/12 ②). The climb makes it taller — 宝哥的情绪在往上走.
    col = entity
    if in_a1:
        col = entity * w_beam
    if 87.0 <= t < scene.B1_END:
        col *= 1.0 + 0.40 * rise

    # the interlude: the machine steps out of the frame's contents, not only out of the
    # column. The SIGNAL plate is the machine's instrument and would sit exactly where the
    # keyboard stands, so it goes dark for the 121 s and comes back with B②.
    # 导演 (05:31): 2:15–2:25 是"抬起起伏起伏"——呐喊之后 137–145 还有第二个更大的峰，
    # 147 才落下来进钢琴。实测：drums/bass/other 在 137–145 全在 1.0，146 才掉。
    surge = None
    if scene.B1_END <= t < 152.0:
        surge = _ramp(t, [(136.6, 0.55), (137.6, 0.92), (143.0, 1.0), (146.2, 1.0),
                          (147.4, 0.12), (150.0, 0.18), (152.0, 0.22)])
        # 0.70 + 0.45*surge changed the ridge by 25 % — invisible. The fall has to be a
        # fall: 1.07 at the peak, 0.23 at the bottom.
        amp_scale *= 0.12 + 0.95 * surge
        rise = max(rise, 0.70 * surge)
    # 呐喊 (124–136.6): the demands' own blast. Rings on the beat.
    shock = 0.0
    if 124.0 <= t < scene.B1_END:
        shock = min(1.0, (t - 124.0) / 1.5) * min(1.0, (scene.B1_END - t) / 1.5)
    # 第二座峰 (137–146.6)：呐喊的余波。环继续从中心扩散，最后一圈正好和钢琴升起的
    # 时刻重叠——这是"衔接"的关键：旧动作还没走完，新东西已经在同一个中心长出来。
    if 137.0 <= t < 146.6:
        shock = max(shock, _ramp(t, [(137.0, 0.30), (139.0, 0.85), (144.0, 1.0),
                                     (146.0, 1.0), (146.6, 0.0)]))
    # 咆哮段 (212–230) 把冲击环请回来：这是全曲最满的地方，环踩在鼓上
    # 环留到 3:32 之后才真正出现：3:10–3:30 只有那条阶梯，否则后面的 solo 无处可去
    if 210.0 <= t < 242.0:
        shock = max(shock, _ramp(t, [(210, 0.0), (214, 0.55), (220, 1.0), (230, 1.0),
                                     (238, 0.55), (242, 0.0)]))
    in_break = scene.B1_END <= t < 245.79
    plate_a = 0.0 if in_break else (w_hud if t >= 358.92 else 1.0)
    # the pot keeps its place at the END of the band's row — the 兰花草 is the seventh chair
    px_ = 0.925 if in_break else fx

    # ---- 3:10–4:05 吉他 solo：一条连续的上升，不是三段拼起来 ----
    # 导演 (05:58): 3:10 音色更亮的吉他（几分钟后贝斯进来），3:10–3:30 没有感觉，和后面的
    # solo 对不上。实测 hi 频段（bands24 第 14 段以后）：190 之前 0.12，192 跳到 5.15，
    # 194 归 0，198/202/206 每两秒一记，212 起持续 6.16 —— 吉他是 PULSE，不是斜坡。
    # So brightness follows the hi band (spiky), the mountain follows `climb` (monotone),
    # and all three devices run from 190 to 245 instead of taking turns in separate windows.
    #   190–212  稀疏→爬升：低频在地面上推涟漪（ridge 不动，地动）
    #   212–230  顶格：螺旋从中心张开，冲击环回来，世界抖
    #   230–245  退：涟漪变稀、光衰，接 B②
    solo_kw = None
    if 188.0 <= t < 245.79:
        climb = _ramp(t, [(188, 0.05), (196, 0.24), (204, 0.46), (212, 0.95),
                          (222, 1.0), (232, 0.97), (245.79, 0.55)])
        hi = min(1.0, _hi_energy(t) / 5.5)
        # ---- 3:10–3:30 只做一件事：两件乐器对答（导演 06:18：这里要"明显"，但不能和
        # solo 用同一种语言，否则 3:32 无处可去）----
        # 吉他：从左打进一条细白轨；贝斯：从右答一条粗琥珀轨。
        rise_amt = _ramp(t, [(188.0, 0.0), (191.0, 0.75), (206.0, 1.0), (210.0, 1.0),
                             (213.0, 0.0)])
        ripple = 0.0 if t >= 210.0 else climb * (0.25 + 0.55 * drive.bass(t))
        spiral = 0.0 if t < 210.0 else _ramp(t, [(210.0, 0.0), (216.0, 0.55), (224.0, 1.0),
                                                 (236.0, 0.80), (244.0, 0.25)])
        solo_kw = {"rise": rise_amt, "rise_steps": RISE_STEPS,
                   "ripple": ripple, "spiral": spiral, "bright": hi}
        amp_scale *= 0.55 + 0.60 * climb          # 山脊跟着爬，顶点 1.12
        # 亮度：3:30 之前只允许"脉冲"（吉他每打一下一闪），过了 3:32 才允许"常亮"。
        # 这样 3:32 的满屏光是新的，不是 3:10 的延长。
        gate = _ramp(t, [(188.0, 0.0), (206.0, 0.06), (211.0, 0.30), (215.0, 0.95),
                         (228.0, 1.0), (245.79, 0.55)])
        rise = max(rise, 0.20 * hi if t < 210.0 else max(0.20 * hi, 0.95 * gate))

    return dict(
        solo=solo_kw,
        # the sky comes with the terrain: plan/12 ② says the WORLD arrives in waves, and
        # a sky that is already there while the mountain is not is a different film.
        sky_a=w_ter if in_a1 else 1.0,
        ridge_a=w_ter,
        star_a=max(0.0, 1.0 - 0.55 * mood) * (w_ter if in_a1 else 1.0),
        rain_a=rain,
        # the SIGNAL plate is the MACHINE's instrument, not the world — it powered on
        # during the prelude (`load wave`) and stays on. Only A④'s subtraction drains it.
        plate_a=plate_a,
        pot_a=pot,
        pot_count=1 if in_a1 else cnt,
        pot_x=0.845 if in_a1 else px_,
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
        # the interlude's wireframe band (导演拍板 7)
        stage=_stage_kw(t, sid),
        shock=shock,
        label=("WORLD // " + sid.upper()) if sid in scene.BREAK_CAMERA else "WORLD // VALLEY",
    )


# ---- the interlude's ensemble: who plays in which movement (plan/22 §4) -------------
# 导演拍板 7: 代码朋克线框器乐, 器乐团并排. The seven movements are not seven screens —
# they are ONE band, and each movement is the subset of chairs that is playing plus one
# chair pulled into the frame as the soloist. That is what makes the 121 s read as a
# performance rather than as a slideshow.
#
#   movement   chairs playing (base level)                    solo
#   boutro     鼓 .85 贝斯 .55 吉他 .80（呐喊的尾巴）            吉他
#   piano      钢琴 1.00                                       钢琴
#   duet       钢琴 .75 小提琴 .95                              钢琴
#   bass       贝斯 1.00 吉他 .65                               贝斯
#   roar       鼓 .85 吉他 1.00 贝斯 .75                        吉他
#   cool       鼓 .45 贝斯 .35 吉他 .35 钢琴 .20（逐个下线）      —
MOVE_LIVE = {
    "boutro": {"DRUM": 0.85, "BASS": 0.55, "GTR": 0.80, "PNO": 0.05, "VLN": 0.10, "VOX": 0.10},
    "piano":  {"DRUM": 0.0, "BASS": 0.0, "GTR": 0.0, "PNO": 1.00, "VLN": 0.0, "VOX": 0.0},
    "duet":   {"DRUM": 0.0, "BASS": 0.10, "GTR": 0.10, "PNO": 0.75, "VLN": 0.95, "VOX": 0.0},
    "bass":   {"DRUM": 0.30, "BASS": 1.00, "GTR": 0.65, "PNO": 0.10, "VLN": 0.15, "VOX": 0.0},
    "roar":   {"DRUM": 0.85, "BASS": 0.75, "GTR": 1.00, "PNO": 0.10, "VLN": 0.10, "VOX": 0.0},
    "cool":   {"DRUM": 0.45, "BASS": 0.35, "GTR": 0.35, "PNO": 0.20, "VLN": 0.0, "VOX": 0.0},
}
MOVE_SOLO = {"boutro": "GTR", "piano": "PNO", "duet": "PNO",
             "bass": "BASS", "roar": "GTR", "cool": None}
# which stem feeds which chair, so a lit slot is a measured level and not a decoration
STAGE_STEM = {"DRUM": "drums", "BASS": "bass", "GTR": "other", "PNO": "other",
              "VLN": "other", "VOX": "vocals"}

# the piano movement's canon, computed once (a strict canon is a delay line: honest)
_CANON = score3.canon(score3.window(147.0, 162.0))


def _stage_kw(t, sid):
    """The interlude's stage state at t (pure function of t). None outside the interlude."""
    if not (scene.B1_END <= t < 245.79):
        return None
    base = MOVE_LIVE.get(sid, {})
    live = {}
    for name, v in base.items():
        if v <= 0.0:
            live[name] = 0.0
            continue
        stem = STAGE_STEM[name]
        lv = {"drums": drive.drums, "bass": drive.bass,
              "other": drive.other, "vocals": drive.vocals}[stem](t)
        # the measured level breathes inside the movement's base: a chair that is playing
        # looks like it is playing NOW, not like a slot that was switched on
        live[name] = v * (0.42 + 0.58 * lv)
    mv = next(((s[1], s[2]) for s in scene.BREAK_SECTIONS if s[0] == sid), (t, t + 1.0))
    return {
        "kind": sid,
        "notes": score3.NOTES,
        "alt": _CANON if sid in ("piano", "duet") else None,
        "live": live,
        "solo": MOVE_SOLO.get(sid),
        "mv": mv,
    }


# ---- the cut: a CRT channel change, not a telegram from A to B ----------------------
# 导演 (2026-10-27): 第二篇章的切点"只有画面切换"，生硬。The four visible cuts in ch2 are
# geometry teleports — at 84.01 the entity column goes 512 -> 96 px and the world's left
# edge jumps 528 -> 112 in ONE frame. Half the picture is re-laid-out in 1/24 s and
# nothing happens in between, so it reads as a switch rather than as an edit.
#
# The film already owns the gesture that can carry a cut: the laser-disc player changing
# channel. A CRT collapse is that gesture applied to the whole raster — the picture
# squashes to a horizontal line, the line opens into the next picture. It hides the
# re-layout WITHOUT dissolving one image into another: 导演拍板 3 rules out the dissolve,
# and this is not one, it is a shutter. Nothing inside a shot changes.
#
# Only mode changes are listed: two neighbouring shots in the SAME layout are invisible
# anyway (the drawing is continuous in t), so a shutter there would invent a cut that the
# picture does not have. 103.84 (into B①) and 136.6 (into the interlude) are chapter
# boundaries: 103.84 gets one shutter, 136.6 stays naked (the machine simply withdraws) — the interlude entry is already a 1.2 s collapse ramp.
CUT_FRAMES = 3.0        # length of the whole gesture, in frames (0 disables it)
# 103.84 is a chapter boundary, so it is not a mode change — but it is the loudest cut in
# the film (quiet valley -> four demands over the whole world), and 导演 said the entry
# into B① is the most abrupt moment in it. One shutter there costs one frame.
_EXTRA_CUTS = (103.84,)
_CUTS = tuple(b[1] for a, b in zip(shots.SNAPPED, shots.SNAPPED[1:]) if a[3] != b[3]) \
    + _EXTRA_CUTS


def _squash(img: Image.Image, s: float) -> Image.Image:
    """Collapse the raster into a band around the middle, and leave the phosphor line.

    `s` is the surviving height (1 = untouched, 0 = a single line). The image is resized
    rather than clipped, because a CRT does not reveal a picture — it squeezes it, and the
    squeeze is what tells the eye "the machine changed something", not "the film lied".
    """
    if s >= 0.998:
        return img
    W, H = img.size
    band = max(1, int(round(H * max(0.0, s))))
    cy = H // 2
    out = Image.new("RGB", (W, H), (2, 3, 8))
    out.paste(img.resize((W, band), Image.BILINEAR), (0, cy - band // 2))
    d = ImageDraw.Draw(out)
    heat = 1.0 - min(1.0, s / 0.55)
    if band <= 6:
        d.rectangle([0, cy - band // 2, W, cy + band // 2],
                    fill=fade((255, 250, 236), 0.55 + 0.45 * heat))
    if heat > 0.01:
        d.line([(0, cy), (W, cy)], fill=fade((255, 246, 224), 0.90 * heat), width=2)
        for k in (1, 2, 3, 5):
            a = 0.14 * heat / (k * 0.9)
            d.line([(0, cy - k * 3), (W, cy - k * 3)], fill=fade(AMBER, a))
            d.line([(0, cy + k * 3), (W, cy + k * 3)], fill=fade(AMBER, a))
    return out


def _cut_shutter(t: float):
    """The squashed height at t, or None if t is not on a cut."""
    if CUT_FRAMES <= 0 or not _CUTS:
        return None
    h = (CUT_FRAMES / 2.0) / FPS
    for c in _CUTS:
        d = abs(t - c)
        if d < h:
            return (d / h) ** 0.85
    return None


# ---- the frame ----------------------------------------------------------------------
def frame(t: float) -> Image.Image:
    """One frame of the four-zone film. Pure function of t."""
    img = _plain_frame(t)
    s = _cut_shutter(t)
    return img if s is None else _squash(img, s)


def _plain_frame(t: float) -> Image.Image:
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
    collapse = _form_collapse(t)
    if scene.B1_END <= t < 245.79:
        u = min(1.0, (t - scene.B1_END) / 1.2) if t < 147.0 else \
            min(1.0, max(0.0, 1.0 - (t - 244.20) / 1.60))
        collapse = max(collapse, u)
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
    if 103.84 <= t < scene.B1_END:
        # the machine is blasted from the first demand all the way through the shout
        ov = min(1.0, max(0.0, (t - 103.84) / 1.6)) * min(1.0, max(0.0, (scene.B1_END - t) / 1.2))
    else:
        ov = 0.0
    ent = dict(tray=0.0, disc=True, rpm=8.3 if t >= 2.24 else 0.0,
               state=state, power="PLAY" if playing else "ON",
               nameplate=True, squeeze=ov)

    cs = _cell_state(t)
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
        demand=_demand_state(t),
        cell=(cs or {}).get("cell", 0.0), inst=cs,
        cell_px=(cs or {}).get("w", 0.0), status=_countdown(t), dial=_dial_state(t),
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


_BANDS = None


def _phrases(onsets, gap: float = 0.45):
    """Group onsets into phrases — a run of notes with no rest longer than `gap`.

    The unit that answers another phrase is the phrase, not the note (see tk.trade_rails).
    """
    out = []
    for ev in onsets:
        tn = ev[0]
        if out and tn - out[-1][1] <= gap:
            out[-1][1] = tn
        else:
            out.append([tn, tn])
    return [(a, b) for a, b in out]


PHR_GTR = _phrases(score3.GTR)
PHR_BASS = _phrases(score3.BASS)
# 3:10–3:30 的台阶：吉他每打一下抬一级（188–214 之间）
RISE_STEPS = [(e[0], 0.55 + 0.9 * e[2]) for e in score3.GTR if 188.0 <= e[0] <= 214.0]


def _hi_energy(t: float) -> float:
    """Energy in the top bands (14..22) at t — the guitar's brightness, not its loudness."""
    global _BANDS
    if _BANDS is None:
        import numpy as np
        fp = ROOT / "data" / "audio" / "bands24.npy"
        _BANDS = np.load(fp) if fp.exists() else False
    if _BANDS is False:
        return 0.0
    i = min(len(_BANDS) - 1, max(0, int(t * 24)))
    return float(_BANDS[i, 14:].sum())


def _undo_at(t):
    """The one character that goes back to its pre-rewrite version, for 0.6 s (plan/16 §2.3).

    Defined at the very bottom on purpose: earlier versions of this file kept losing it to
    wholesale section replacements. Order does not matter at call time.
    """
    return scene.undo_at(t)
