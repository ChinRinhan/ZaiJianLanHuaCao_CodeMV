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
    # 导演（09:0x）①：「四句「给我…」现在四遍一模一样，观众第三句就麻了」。
    # 音乐上它们是递进的（B① 是全曲最响的 18 s），所以画面也逐句升级：
    # 不换动作，只让同一个动作更重——第 1 句只有字，第 4 句连世界都在晃。
    step = 0
    for i, tt in enumerate(B1_TICKS):
        if t >= max(tt, B1_T0 + B1_TYPE_WAIT):
            step = i + 1
    return w, a * a_out, t - lt, min(4, step)


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
FORM_OUT0, FORM_OUT1 = 119.46, 120.60   # 表退得比"钟"晚：问句还没说完，容器不能先收走
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
        # 导演（09:0x）③：「3:10 之后都是双吉他专场，把小提琴隐藏了，换成第二把吉他」。
        # 这不是审美问题，是**事实错误**：Demucs 把电吉他塞进了 other 轨，190 之后
        # other 主要是吉他（解析视频：「贝斯与电吉他的对话」「电吉他尽情咆哮」），
        # 我们却一直画着一条标着 VLN 的曲线。所以：
        #   162–190 对话段   保留 VLN（这一段 other 里确实是小提琴 + 钢琴，原话）
        #   其它所有时候     第四件乐器是 GTR2（第二把吉他），数据仍取 other 轨
        _vln_win = (162.0 <= t < 190.0)
        fourth = ("VLN", "CURVE", dict(onsets=score3.GTR)) if _vln_win else                  ("GTR2", "TAB", dict(onsets=score3.GTR, tuning=instruments.TUNING6,
                                      marks=()))
        lanes = [("GTR", "TAB", dict(onsets=score3.GTR, tuning=instruments.TUNING6,
                                     marks=())),
                 ("BAS", "TAB", dict(onsets=score3.BASS, tuning=instruments.TUNING4,
                                     marks=())),
                 ("DRM", "GRID", dict(onsets=score3.DRUM)),
                 ("PNO", "ROLL", dict(onsets=score3.NOTES)),
                 fourth,
                 ("VOX", "COL", dict())]
        for name, kind, pay in lanes:
            # GTR2 与 VLN 是同一个声部在不同段落的名字，电平跟着 other 轨走
            lv = live.get(name, live.get("VLN", 0.0) if name == "GTR2" else 0.0)
            if name == "GTR2":
                lv = max(lv, live.get("GTR", 0.0) * 0.85)
            pay["level"] = lv
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


# ---- the dial: 系统开了一个窗口，然后把它最小化 -------------------------------------
# 导演（08:3x）：「切割出一个提示框，里面放入倒计时，随后线框收缩，左下角再展开，
# 这样更有代码朋克感」。
#
# 这比"在世界中间长出一个环"高一档：环是一个图形，窗口是**系统的一个部件**。
# 弹出 → 折进角落 → 常驻，这是桌面语言，正好是这台机器的世界观（一台 1994 年的机器
# 跑着 2023 年的界面）。而且它天然解决"生硬"：有框、有标题栏、有打开和关闭的动作。
#
# 六拍：
#   POP    117.45-119.40  从世界正中切出一个框（四边同时向外切，不是淡入），框里没有数
#   SET    119.40         「钟」落 → 框里落数 05:00（他要的数）
#   CUT    119.44-120.12  05:00 → 02:25（当着观众的面把许诺数短）
#   FOLD   120.20-121.30  **原地**塌成一条横线（不移动）
#   HOP    121.30-121.76  那条线先横后竖扫到右下角（让"搬到那儿了"看得见）
#   OPEN   121.76-123.10  在右下角填充式弹出一个计时框（原来表盘的老地方）
DIAL_POP = 117.45        # 「你只要给我…」的第一个字
DIAL_SET = 119.40        # 「钟」落 = 他要的数说完了
DIAL_CUT = (119.44, 120.12)
DIAL_FOLD = (120.20, 121.30)
DIAL_HOP = (121.30, 121.76)      # 收线之后：一条细线从画面中心扫到右下角（它搬过去了）
DIAL_OPEN = (121.76, 123.10)     # 再在右下角填充式弹出计时框
DIAL_MOVE = (DIAL_FOLD[0], DIAL_OPEN[1])   # 窗口动作的完整区间：收线开始 → 展开结束   # (收线开始, 展开结束) —— 整个窗口动作的区间

# the box, in frame coordinates
BOX_W, BOX_H = 300, 138
BOX_CX, BOX_CY = 706.0, 330.0          # centre of the 356 px world at 117.4–120.2
# 计时框归位的地方 = 底部栏右端，也就是它最早那个表盘的老位置（导演：「就是原来的区域」）
PILL_X1, PILL_Y1 = 1264.0, 706.0
PILL_W, PILL_H = 176, 44


def _dial_stage(t):
    """(stage, u) — 0 切框 / 1 落数 / 2 打折 / 3 收线 / 4 搬家 / 5 弹出计时框."""
    if t < DIAL_SET:
        return 0, _smooth((t - DIAL_POP) / (DIAL_SET - DIAL_POP))
    if t < DIAL_CUT[0]:
        return 1, 1.0
    if t < DIAL_CUT[1]:
        return 2, (t - DIAL_CUT[0]) / (DIAL_CUT[1] - DIAL_CUT[0])
    if t < DIAL_HOP[0]:
        return 3, _smooth((t - DIAL_FOLD[0]) / (DIAL_FOLD[1] - DIAL_FOLD[0]))
    if t < DIAL_OPEN[0]:
        return 4, _smooth((t - DIAL_HOP[0]) / (DIAL_HOP[1] - DIAL_HOP[0]))
    return 5, _smooth((t - DIAL_OPEN[0]) / (DIAL_OPEN[1] - DIAL_OPEN[0]))


# the dial is born in the middle of the world, then takes its post at the bottom right
DIAL_T0 = DIAL_POP


def _countdown(t):
    """(text, alpha, done, outer, inner) for the token band's dial."""
    if t < DIAL_OPEN[1]:
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
    """The window's geometry at t: (rect, stage, text, inner, cut) or None.

    `rect` is the box the frame is drawn on. In stage 3 it collapses to a BOTTOM EDGE
    (height → 0 at the bottom), which is the line that then opens into the chip.
    """
    if not (DIAL_T0 <= t < DIAL_MOVE[1]):
        return None
    stage, u = _dial_stage(t)

    bx0 = int(round(BOX_CX - BOX_W / 2))
    by0 = int(round(BOX_CY - BOX_H / 2))
    bx1 = bx0 + BOX_W
    by1 = by0 + BOX_H

    # 数：他要 5:00，机器给 2:25；stage 2 是当着面数短
    if stage <= 1:
        txt = "05:00"
        inner = 1.0
    elif stage == 2:
        cur = 300.0 + (COUNTDOWN - 300.0) * _smooth(u)
        txt = "%02d:%02d" % (int(cur) // 60, int(cur) % 60)
        inner = cur / 300.0
    else:
        txt = "%02d:%02d" % (int(COUNTDOWN) // 60, int(COUNTDOWN) % 60)
        inner = min(1.0, COUNTDOWN / 300.0)

    if stage == 0:
        # 切框：四边同时向外切出去（不是淡入）。u=0 时是一个点，u=1 时是整框。
        half_w = max(1.0, BOX_W / 2 * u)
        half_h = max(1.0, BOX_H / 2 * u)
        r = (int(BOX_CX - half_w), int(BOX_CY - half_h),
             int(BOX_CX + half_w), int(BOX_CY + half_h))
        txt = ""                                  # 空框：还没有数
    elif stage <= 2:
        r = (bx0, by0, bx1, by1)
    elif stage == 4:
        # 搬家：那条横线扫到右下角去。它必须先走一趟，观众才知道"东西搬到那儿了"，
        # 否则中间那 60 px 的空档只能靠脑补。
        # 右端沿着一条折线走：先向右，再向下——像一个窗口被拖到角落。
        ex = BOX_CX + (PILL_X1 - 90 - BOX_CX) * u
        ey = BOX_CY + (PILL_Y1 - 20 - BOX_CY) * (u * u)      # 先横后竖
        r = (int(ex - 60), int(ey), int(ex + 60), int(ey))
        txt = ""
    elif stage == 3:
        # 折：高度先收到底，宽度再收窄 —— 就在世界原处塌成一条**横线**，不往上也不往下。
        # （导演 08:5x：「收缩成线之后不要平移向下」）
        cx = (bx0 + bx1) / 2
        cy = (by0 + by1) / 2
        hh = (BOX_H / 2) * max(0.0, 1.0 - u * 2.2)
        w2 = (BOX_W / 2) * max(0.0, 1.0 - max(0.0, u - 0.45) / 0.55)
        r = (int(cx - w2), int(cy - hh), int(cx + w2), int(cy + hh))
        txt = "" if u > 0.30 else txt
    else:
        # 归位：右下角（原来那个表盘的地方）**重新弹出一个计时框**，像填充一样长起来：
        # 先长宽（从右边缘往左填），再长高。导演 08:5x：「就像填充一样」
        e = u
        cw = max(26.0, PILL_W * min(1.0, e / 0.62))
        ch = max(20.0, PILL_H * min(1.0, max(0.0, (e - 0.08) / 0.62)))
        r = (int(PILL_X1 - cw), int(PILL_Y1 - ch), int(PILL_X1), int(PILL_Y1))
        txt = "" if e < 0.55 else txt

    return {"rect": r, "stage": stage, "text": txt, "inner": inner,
            "u": u, "cx": BOX_CX, "cy": BOX_CY}


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

    # the interlude's six movements each get their own framing (plan/19 §3.1).
    # 导演（09:1x）：「3:08 到 3:09 进入 solo 的衔接不够，中途有跳帧」。
    # 实测 189.96 → 190.00 这一帧：x_off −60→+40、floor 0.52→0.66、amp 0.167→0.279，
    # 帧差 9.06（平时 1.25，7.3 倍）。BREAK_CAMERA 是硬切表，但我们的段落之间**没有切点**，
    # 所以镜头参数必须在边界上过渡——否则每一段开头都是一次跳帧。
    x_off, scale, floor = _cam_at(t, sid)
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
        # 返工（08:1x）：230–245.79 是全间奏最响的一段，原来这三条斜坡都在往 245.79 掉
        # （climb 0.55 / spiral 0.25 / gate 0.55）——那是"收冷"的残留。现在改成顶住不落：
        # 先顶满，再由 B② 一刀关掉。落差是 B② 的，不是间奏自己泄的。
        climb = _ramp(t, [(188, 0.05), (196, 0.24), (204, 0.46), (212, 0.95),
                          (222, 1.0), (232, 1.0), (245.79, 1.0)])
        hi = min(1.0, _hi_energy(t) / 5.5)
        # ---- 3:10–3:30 只做一件事：两件乐器对答（导演 06:18：这里要"明显"，但不能和
        # solo 用同一种语言，否则 3:32 无处可去）----
        # 吉他：从左打进一条细白轨；贝斯：从右答一条粗琥珀轨。
        rise_amt = _ramp(t, [(188.0, 0.0), (191.0, 0.75), (206.0, 1.0), (210.0, 1.0),
                             (213.0, 0.0)])
        ripple = 0.0 if t >= 210.0 else climb * (0.25 + 0.55 * drive.bass(t))
        # 3:50 之后这一段有自己的语言（钉墙），螺旋要退到背景里去：
        # 两套形状同时占着世界中心，谁也不是主角，观众只会看到"东西很多"。
        spiral = 0.0 if t < 210.0 else _ramp(t, [(210.0, 0.0), (216.0, 0.55), (224.0, 1.0),
                                                 (229.0, 1.0), (231.6, 0.18), (245.79, 0.14)])
        solo_kw = {"rise": rise_amt, "rise_steps": RISE_STEPS,
                   "ripple": ripple, "spiral": spiral, "bright": hi,
                   # 3:10–3:32：贝斯已经升格成 stage 里的"走格"（instruments._walk_grid），
                   # 地面上那条小台阶就不画了——同一件乐器画两遍，观众只会看到两次抖动。
                   "bass": 0.0,
                   "bass_notes": score3.BASS}
        amp_scale *= 0.55 + 0.60 * climb          # 山脊跟着爬，顶点 1.12
        # 亮度：3:30 之前只允许"脉冲"（吉他每打一下一闪），过了 3:32 才允许"常亮"。
        # 这样 3:32 的满屏光是新的，不是 3:10 的延长。
        gate = _ramp(t, [(188.0, 0.0), (206.0, 0.06), (211.0, 0.30), (215.0, 0.95),
                         (228.0, 1.0), (245.79, 1.0)])
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


CAM_BLEND = 0.85       # 段落边界前后各 0.85 s 用来插值镜头


def _cam_at(t, sid):
    """Framing at t, interpolated across movement boundaries.

    每段有自己的 (x_off, scale, floor)。直接切会让每段的**第一帧**变成一次没有剪辑点的跳切
    ——190.00 就是这样：x_off −60→+40、floor 0.52→0.66、amp +67%，帧差 9.06（平时 1.25）。
    所以边界前后各 CAM_BLEND 秒做一次 smooth 过渡：**上一段的参数淡出，下一段的淡入**。
    """
    secs = scene.BREAK_SECTIONS
    cur = scene.BREAK_CAMERA.get(sid, (0.0, 1.0, 0.70))
    for i, (mid, t0, t1, *_r) in enumerate(secs):
        if not (t0 <= t < t1):
            continue
        # 只在**段尾**做过渡：把这一段的镜头提前挪到下一段去。
        # 段头不能再插一次——两段过渡会在边界上重叠，190.00 会从 39 跳回 −60。
        # （一开始写了两头插值，就是这个结果：189.96 已是 39.36，190.00 又跳回 −60。）
        if i + 1 < len(secs) and t1 - t < CAM_BLEND:
            nxt = scene.BREAK_CAMERA.get(secs[i + 1][0], (0.0, 1.0, 0.70))
            u = _smooth((t - (t1 - CAM_BLEND)) / CAM_BLEND)   # 0 → 1（离开 cur，走向 nxt）
            return tuple(c + (n - c) * u for c, n in zip(cur, nxt))
        return cur
    return cur


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
#   last       鼓 .95 贝斯 .70 吉他 1.00（最后一波，不是收冷）   吉他
MOVE_LIVE = {
    "boutro": {"DRUM": 0.85, "BASS": 0.55, "GTR": 0.80, "PNO": 0.05, "VLN": 0.10, "VOX": 0.10},
    "piano":  {"DRUM": 0.0, "BASS": 0.0, "GTR": 0.0, "PNO": 1.00, "VLN": 0.0, "VOX": 0.0},
    "duet":   {"DRUM": 0.0, "BASS": 0.10, "GTR": 0.10, "PNO": 0.75, "VLN": 0.95, "VOX": 0.0},
    "bass":   {"DRUM": 0.30, "BASS": 1.00, "GTR": 0.65, "PNO": 0.10, "VLN": 0.15, "VOX": 0.0},
    "roar":   {"DRUM": 0.85, "BASS": 0.75, "GTR": 1.00, "PNO": 0.10, "VLN": 0.10, "VOX": 0.0},
    # 返工：原来这里是"逐个下线"的 .45/.35/.35/.20。实测 230–245.79 是全间奏最响的一段
    # （drums −22.7 / other −23.6），画面却在关灯——声音和画面对着干。改成满编。
    "last":   {"DRUM": 0.95, "BASS": 0.70, "GTR": 1.00, "PNO": 0.12, "VLN": 0.10, "VOX": 0.0},
}
MOVE_SOLO = {"boutro": "GTR", "piano": "PNO", "duet": "PNO",
             "bass": "BASS", "roar": "GTR", "last": "GTR"}
# which stem feeds which chair, so a lit slot is a measured level and not a decoration
STAGE_STEM = {"DRUM": "drums", "BASS": "bass", "GTR": "other", "PNO": "other",
              "VLN": "other", "VOX": "vocals"}

# the piano movement's canon, computed once (a strict canon is a delay line: honest)
_CANON = score3.canon(score3.window(147.0, 162.0))
# 对话段自己的卡农：162–190 是另一条线。之前两段共用一个 147–162 的卡农，
# 所以对话段里根本没有音符落进画面——小提琴的弓是空的。
_CANON_DUET = score3.canon(score3.window(162.0, 190.0))


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
        "alt": (_CANON_DUET if sid == "duet" else _CANON) if sid in ("piano", "duet") else None,
        # 贝斯段 / 最后一波各自的主角：实测 onset 表直接交给 stage，
        # 不在这里算任何形状——放大视图只负责"把这一段画成它的乐器"。
        "bass": score3.BASS,
        "drum": score3.DRUM,
        "live": live,
        "solo": MOVE_SOLO.get(sid),
        "mv": mv,
    }


# ---- B②：第二次要五分钟，然后是合唱 ------------------------------------------------
# 导演（07:1x）：「这一段，这是第二次宝哥让观众相信他，给他五分钟，随后就是令人惊喜的
# 宝哥『合唱』」。所以 B② 不做第二次"砸"——B① 已经砸过一次，再砸一次就把 A②/A③ 的路
# 堵死。它做三拍：
#   1) 245.79–260.9  机器往后退（实体列 + 仪表压暗），世界让出来；四句「给我…」各落一次账
#   2) 260.9–265.0   鼓与贝斯退场（实测 drums −65、bass −70 dB），画面同步抽空：世界冻结，
#                    只剩歌词和右下角那个走了两分半的表盘
#   3) 265.0–266.31  表盘归零（内环 = 4:25 闭合），CH 1–6 逐个点名——六个人进来，
#                    266.31 接 A②「啊预备唱」。点名册就是唱片内页上的「六人齐唱」。
B2_T0, B2_T1 = 245.79, 266.31
B2_ACCT = (245.84, 248.51, 250.12, 252.26)   # 四句「给我…」的实测起音（word_times_v2）
B2_DRAIN = 260.9                              # 鼓贝斯退场
B2_ZERO = 265.0                               # 内环闭合 = 4:25
B2_CHOIR_T0, B2_CHOIR_DT = 265.10, 0.17       # 六格点名，一格 0.17 s


def _b2_state(t):
    """B② 的状态；不在 B② 返回 None。"""
    if not (B2_T0 <= t < B2_T1):
        return None
    acct = sum(1 for x in B2_ACCT if t >= x)
    enter = _smooth((t - B2_T0) / 1.2)            # 机器是"先长回来，再退后"，不是一进来就暗
    drain = _smooth((t - B2_DRAIN) / 1.6)
    choir = 0 if t < B2_CHOIR_T0 else min(6, 1 + int((t - B2_CHOIR_T0) / B2_CHOIR_DT))
    flash = max(0.0, 1.0 - abs(t - B2_ZERO) / 0.35)
    return {"acct": acct, "enter": enter, "drain": drain, "choir": choir,
            "call": (choir - 1) if choir else -1,
            "flash": flash, "zero": t >= B2_ZERO}


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
_EXTRA_CUTS = (103.84, 265.0)
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
    # B②：机器往后退，世界让出来；抽空时世界冻结，只剩歌词与表盘
    b2 = _b2_state(t)
    dim = None
    if b2:
        # 导演 07:2x：「一起都灭掉，像是进入了新的阶段」。所以抽空不是"调暗"，是"关灯"：
        # 顶栏、实体列、仪表、世界全灭；留在画面上的只有歌词、表盘和那张点名册。
        dim = {"header": 0.88 * b2["drain"],
               "entity": 0.30 * b2["enter"] + 0.62 * b2["drain"],
               "content": 0.88 * b2["drain"],
               "ops": 0.12 * b2["enter"] + 0.82 * b2["drain"]}
        k = b2["drain"]
        if k > 0.01:
            kw.update(
                sky_a=kw["sky_a"] * (1.0 - 0.92 * k),
                ridge_a=kw["ridge_a"] * (1.0 - 0.95 * k),
                star_a=kw["star_a"] * (1.0 - 0.95 * k),
                rain_a=kw["rain_a"] * (1.0 - k),
                plate_a=kw["plate_a"] * (1.0 - 0.97 * k),
                pot_a=kw["pot_a"] * (1.0 - 0.85 * k),
                column_a=kw["column_a"] * (1.0 - 0.95 * k),
                rise=kw["rise"] * (1.0 - k))
    # B① 界面过载（plan/05 §4: 评分冲顶、播放列表被挤、口令闪）— the machine is being
    # blasted; the interface visibly suffers for it.
    if 103.84 <= t < scene.B1_END:
        # the machine is blasted from the first demand all the way through the shout
        ov = min(1.0, max(0.0, (t - 103.84) / 1.6)) * min(1.0, max(0.0, (scene.B1_END - t) / 1.2))
        # 导演（09:0x）①：四句「给我…」现在是四遍一模一样，观众第三句就麻了。
        # 只让光带变粗不够——真正该变的是**世界**：每落一句，山脊多晃一点，机器多过载一点。
        _st = 0
        for _i, _tt in enumerate(B1_TICKS):
            if t >= max(_tt, 103.84 + 0.32):
                _st = _i + 1
        _k = max(0, _st - 1) / 3.0
        ov = min(1.0, ov * (1.0 + 1.60 * _k))
        kw["amp_scale"] = kw.get("amp_scale", 1.0) * (1.0 + 0.75 * _k)
        kw["rise"] = min(1.4, kw.get("rise", 0.0) + 0.45 * _k)
        # 每落一句，世界正中砸一个冲击环——同一记鼓，越到后面越大
        kw["shock"] = max(kw.get("shock", 0.0), 0.45 + 0.30 * _k)
    else:
        ov = 0.0
    # 最后一波：机器第二次过载（B① 之后第二次），一路顶到 4:05.8，然后 B② 把它关掉。
    # 这一下不是为了热闹，是为了让 B② 的"全灭"有一个可以掉下来的高度。
    if 230.0 <= t < 245.79:
        ov = max(ov, 0.80 * _smooth((t - 230.0) / 9.0))
    ent = dict(tray=0.0, disc=True, rpm=8.3 if t >= 2.24 else 0.0,
               state=state, power="PLAY" if playing else "ON",
               nameplate=True, squeeze=ov)

    cs = _cell_state(t)
    boot = _boot_state(t)
    # 间奏：底部那条带变成总谱（谁在弹由右列回答，走到哪了由这条带回答）
    sc = list(scene.BREAK_SECTIONS) if scene.B1_END <= t < 245.79 else None
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
        chip_now=_countdown(t) is not None,
        glow=0.30 + 0.16 * _rise(t),
        dim=dim, chorus=b2, scoreline=sc,
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
