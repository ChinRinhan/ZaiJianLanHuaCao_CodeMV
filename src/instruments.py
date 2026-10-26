# -*- coding: utf-8 -*-
"""instruments: the wireframe ensemble that plays the 121-second interlude.

导演拍板 7: 间奏器乐 = 代码朋克线框器乐, 器乐团并排 ("宝哥合唱团"梗的器乐版).
导演拍板 6: 不打字. 导演拍板 5: 不求真音高.

So the interlude is not a lyric sequence any more — it is a BAND, and the band is drawn
the way the rest of the film draws its machines: pure line, no photograph, no chroma
beyond the two colours the film already owns (amber = the machine, blue = the world).
Nothing here moves by itself; every mark is a function of t and of a note table, so
`frame(t)` stays reproducible.

    RACK      six chairs side by side on the ground line   <- 器乐团并排, always present
    ROLL      time falls, pitch runs sideways              <- who plays, and when
    KEYBOARD  wireframe keys, lit by the note that lands   <- the instrument itself

WHY PITCH RUNS SIDEWAYS IN THE ROLL: a falling-note field has TIME on the vertical and
PITCH on the horizontal, so every bar falls straight down onto the key it belongs to.
Drawing pitch vertically (a "piano roll" in the DAW sense) puts the notes in a column that
has no relation to the keyboard underneath — the first attempt did exactly that and read
as noise.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

import clock
import tk
from tk import AMBER, BLUE_HI, fade, font, mix

WHITE_PC = (0, 2, 4, 5, 7, 9, 11)

# the six chairs of the band. The stem each one is fed from is in scene4.STAGE_STEM, so a
# lit slot is a measured level and not a decoration.
SLOTS = ("DRUM", "BASS", "GTR", "PNO", "VLN", "VOX")


# ---------------------------------------------------------------- geometry helpers
def keymap(lo: int, hi: int, x0: float, w: float):
    """midi -> (centre x, key width, is_black) for a keyboard spanning [lo, hi).

    `lo` and `hi` must be octave boundaries (36 = C2). White keys share the width evenly,
    black keys sit on the seams and are 0.62 as wide, as on a real instrument.
    """
    whites = [m for m in range(lo, hi) if m % 12 in WHITE_PC]
    kw = w / max(1, len(whites))
    pos = {}
    for i, m in enumerate(whites):
        pos[m] = (x0 + (i + 0.5) * kw, kw, False)
    for m in range(lo, hi):
        pc = m % 12
        if pc in WHITE_PC:
            continue
        below = sum(1 for k in WHITE_PC if k < pc)
        i = (m // 12 - lo // 12) * 7 + below
        pos[m] = (x0 + i * kw, kw * 0.62, True)
    return kw, pos


def _persp(x: float, cx: float, k: float) -> float:
    return cx + (x - cx) * k


def _quad(d, xa: float, xb: float, y0: float, y1: float, cx: float, k: float,
          col, a: float, fill=0, rows: int = 0):
    """A key: a trapezoid whose top edge is squeezed toward the centre (a fallboard seen
    slightly from above). `fill` hatches horizontal strokes inside it — the film never
    fills a shape flat, a plotter fills it with lines."""
    tl = (round(_persp(xa, cx, k), 1), y0)
    tr = (round(_persp(xb, cx, k), 1), y0)
    br = (round(xb, 1), y1)
    bl = (round(xa, 1), y1)
    if fill > 0.01 and rows > 0:
        for i in range(rows + 1):
            u = i / rows
            y = y0 + (y1 - y0) * u
            xl = tl[0] + (bl[0] - tl[0]) * u
            xr = tr[0] + (br[0] - tr[0]) * u
            d.line([(xl, y), (xr, y)], fill=fade(col, a * fill * (1 - 0.55 * u)))
    d.line([tl, tr, br, bl, tl], fill=fade(col, a))


def _ticks(d, x0, x1, y, col, a, step=8.0, h=3):
    x = x0
    while x < x1:
        d.line([(round(x, 1), y), (round(x, 1), y + h)], fill=fade(col, a))
        x += step


# ---------------------------------------------------------------- the wire glyphs
def glyph(d, name: str, cx: float, cy: float, s: float, col, a: float):
    """One instrument, in the fewest lines that still read at 30 px.

    All six are 1 px wireframes on the same optical weight, so the rack reads as one set
    (a band standing in a row) rather than six unrelated icons.
    """
    c = fade(col, a)
    if name == "DRUM":
        d.ellipse([cx - s * 0.62, cy - s * 0.10, cx + s * 0.02, cy + s * 0.46], outline=c)
        d.ellipse([cx - s * 0.20, cy - s * 0.34, cx + s * 0.34, cy + s * 0.06], outline=c)
        d.line([(cx + s * 0.40, cy - s * 0.46), (cx + s * 0.62, cy + s * 0.06)], fill=c)
        d.line([(cx + s * 0.62, cy + s * 0.06), (cx + s * 0.52, cy + s * 0.44)], fill=c)
        d.ellipse([cx + s * 0.30, cy - s * 0.62, cx + s * 0.52, cy - s * 0.52], outline=c)
        d.line([(cx - s * 0.30, cy - s * 0.58), (cx + s * 0.10, cy - s * 0.44)], fill=c)
    elif name == "BASS":
        d.ellipse([cx - s * 0.66, cy - s * 0.06, cx - s * 0.14, cy + s * 0.40], outline=c)
        d.line([(cx - s * 0.16, cy + s * 0.14), (cx + s * 0.56, cy - s * 0.50)], fill=c, width=2)
        d.line([(cx + s * 0.56, cy - s * 0.50), (cx + s * 0.72, cy - s * 0.60)], fill=c)
        for i in range(4):
            d.line([(cx + s * (0.50 + i * 0.05), cy - s * (0.44 + i * 0.05)),
                    (cx + s * (0.58 + i * 0.05), cy - s * (0.54 + i * 0.05))], fill=c)
        d.line([(cx - s * 0.52, cy + s * 0.40), (cx - s * 0.28, cy + s * 0.40)], fill=c)
    elif name == "GTR":
        d.ellipse([cx - s * 0.50, cy - s * 0.02, cx + s * 0.06, cy + s * 0.44], outline=c)
        d.ellipse([cx - s * 0.36, cy + s * 0.10, cx + s * 0.02, cy + s * 0.32], outline=c)
        d.line([(cx + s * 0.02, cy + s * 0.22), (cx + s * 0.74, cy - s * 0.48)], fill=c, width=2)
        d.line([(cx + s * 0.74, cy - s * 0.48), (cx + s * 0.86, cy - s * 0.56)], fill=c)
        d.line([(cx - s * 0.20, cy + s * 0.16), (cx - s * 0.06, cy + s * 0.26)], fill=c)
    elif name == "PNO":
        d.line([(cx - s * 0.78, cy - s * 0.36), (cx + s * 0.30, cy - s * 0.36)], fill=c)
        d.line([(cx + s * 0.30, cy - s * 0.36), (cx + s * 0.44, cy - s * 0.06)], fill=c)
        d.line([(cx - s * 0.78, cy - s * 0.36), (cx - s * 0.78, cy + s * 0.10)], fill=c)
        d.rectangle([cx - s * 0.70, cy - s * 0.02, cx + s * 0.40, cy + s * 0.20], outline=c)
        for i in range(5):
            xx = cx - s * 0.70 + (i + 0.5) * s * 1.10 / 5
            d.line([(xx, cy - s * 0.02), (xx, cy + s * 0.20)], fill=c)
        d.line([(cx - s * 0.70, cy + s * 0.42), (cx + s * 0.40, cy + s * 0.42)], fill=c)
        d.line([(cx - s * 0.62, cy + s * 0.20), (cx - s * 0.62, cy + s * 0.42)], fill=c)
        d.line([(cx + s * 0.32, cy + s * 0.20), (cx + s * 0.32, cy + s * 0.42)], fill=c)
    elif name == "VLN":
        d.ellipse([cx - s * 0.52, cy - s * 0.06, cx - s * 0.06, cy + s * 0.42], outline=c)
        d.ellipse([cx - s * 0.44, cy + s * 0.06, cx - s * 0.16, cy + s * 0.24], outline=c)
        d.line([(cx - s * 0.10, cy + s * 0.20), (cx + s * 0.54, cy - s * 0.50)], fill=c, width=2)
        d.line([(cx + s * 0.54, cy - s * 0.50), (cx + s * 0.66, cy - s * 0.58)], fill=c)
        # the bow: the only line in the rack that is not the instrument
        d.line([(cx - s * 0.30, cy - s * 0.64), (cx + s * 0.30, cy + s * 0.46)],
               fill=fade(col, a * 0.5))
    elif name == "VOX":
        d.ellipse([cx - s * 0.16, cy - s * 0.56, cx + s * 0.16, cy - s * 0.24], outline=c)
        d.line([(cx, cy - s * 0.24), (cx, cy + s * 0.26)], fill=c)
        d.line([(cx - s * 0.34, cy + s * 0.30), (cx + s * 0.34, cy + s * 0.30)], fill=c)
        d.line([(cx - s * 0.30, cy + s * 0.44), (cx + s * 0.30, cy + s * 0.44)], fill=c)
        for k in (-1, 1):
            d.arc([cx - s * 0.34, cy - s * 0.60, cx + s * 0.34, cy - s * 0.20],
                  start=-60 if k > 0 else 120, end=60 if k > 0 else 240,
                  fill=fade(col, a * 0.5))


# ---------------------------------------------------------------- the instrument cell
# 导演 (2026-10-27 03:10): 「你这吉他画的不行。可以再多分割出线框来装器乐，不一定
# 是吉他形状的，可以是代码状的。」
#
# He is right, and the reason is structural: a wireframe guitar is still a drawing of an
# OBJECT, competing with the world it stands in. What an instrument actually is, in this
# film, is a set of rules and numbers — so the picture should show the RULE, not the body:
#
#     guitar  six horizontal lines + the tuning letters, notes as fret numbers  = TAB
#     bass    the same, four lines, EADG
#     violin  one line and a pitch curve                                       = staff
#     drums   a 6x16 step grid, cells lit by the hits                          = sequencer
#     piano   keys + falling notes (already built)                             = roll
#
# A TAB staff is the guitar's CODE. It needs no silhouette, it is readable at 500 px or
# 50 px, and it is a real notation — the fret numbers come from the measured onsets, so
# the chart is not decoration.

TUNING6 = (("e", 64), ("B", 59), ("G", 55), ("D", 50), ("A", 45), ("E", 40))   # high -> low
TUNING4 = (("G", 43), ("D", 38), ("A", 33), ("E", 28))                        # bass


def _panel(img, rect, col, a, title=None, right=None):
    """A carved cell: floor, border, corner brackets, title riding ON the top edge.

    The floor is BLENDED into what is underneath rather than painted over it: an opaque
    patch cannot fade, so a cell opening from 0 to 1 would pop into existence at full
    darkness and then merely brighten. Blending keeps the whole gesture continuous.
    """
    x0, y0, x1, y1 = rect
    crop = img.crop([x0 - 1, y0 - 1, x1 + 1, y1 + 1])
    img.paste(Image.blend(crop, Image.new("RGB", crop.size, (7, 6, 4)), min(1.0, a)),
              (x0 - 1, y0 - 1))
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], outline=fade((2, 3, 8), 0.5 * a))
    d.rectangle([x0, y0, x1, y1], outline=fade(col, 0.34 * a))
    L = 7
    for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(px, py), (px + sx * L, py)], fill=fade(col, 0.55 * a))
        d.line([(px, py), (px, py + sy * L)], fill=fade(col, 0.55 * a))
    f = font(tk.MONO, 9)
    if title:
        tw = d.textlength(" %s " % title, font=f)
        d.rectangle([x0 + 10, y0 - 6, x0 + 14 + tw, y0 + 8], fill=(7, 6, 4))
        tk.text(d, (x0 + 12, y0 - 5), " %s " % title, f, col, 0.58 * a)
    if right:
        tw = d.textlength(right, font=f)
        tk.text(d, (x1 - tw - 8, y0 + 4), right, f, col, 0.34 * a)


def _tab_track(d, box, t, onsets, tuning, span, alpha, marks=()):
    """Six (or four) lines, a TAB clef, string numbers and fret numbers — a real chart.

    导演 (05:10)「做①」: 谱号 / 行号 / 反复记号. In printed TAB those are:
      clef      the word TAB written down the head of the staff
      row no.   1-6 down the left, one per string (the thinnest string is 1)
      repeat    a thick-thin double bar with two dots where a figure comes round again
    The repeats here sit on the three 「给我…」 lines: they ARE the same figure three times,
    so the mark is a fact about the song, not decoration.
    """
    x0, y0, x1, y1 = box
    n = len(tuning)
    gx0 = x0 + 32
    gx1 = x1 - 6
    top = y0 + 4
    bot = y1 - 4
    step = (bot - top) / max(1, n - 1)
    now_x = gx1 - 4
    v = (gx1 - gx0) / span
    f_t = font(tk.MONO_B, 8)
    f_n6 = font(tk.MONO, 7)
    # 谱号：竖排 TAB
    for k, ch in enumerate("TAB"):
        tk.text(d, (x0 + 2, top - 2 + k * 7), ch, font(tk.MONO, 7), AMBER, 0.55 * alpha)
    for i, (name, _m) in enumerate(tuning):
        yy = top + i * step
        d.line([(gx0, yy), (gx1, yy)], fill=fade(AMBER, 0.20 * alpha))
        # 行号（弦号 1 = 最细）+ 调弦字母
        tk.text(d, (x0 + 12, yy - 5), "%d" % (i + 1), f_n6, AMBER, 0.30 * alpha)
        tk.text(d, (x0 + 19, yy - 5), name, f_t, AMBER, 0.45 * alpha)
    # the chart's own grid: faint 1/4-beat rules, bright bar lines with bar numbers.
    # 导演 (04:12) ①「把真实曲谱给加上」—— 版式先做实：小节线 + 小节号，音符仍来自实测。
    f_b = font(tk.MONO, 7)
    i = clock.beat_index(t - span)
    while True:
        bt = clock.beat_t(i)
        if bt > t + 0.05:
            break
        xx = now_x - (t - bt) * v
        if gx0 <= xx <= gx1:
            bar = (i % 4 == 0)
            d.line([(xx, top - 2), (xx, bot + 2)],
                   fill=fade(AMBER, (0.30 if bar else 0.06) * alpha))
            if bar:
                d.text((xx + 2, top - 9), "%d" % (i // 4 + 1), font=f_b,
                       fill=fade(AMBER, 0.34 * alpha))
        i += 1
    # 反复记号：同一个句式的三句，画在它们各自的起句小节线上
    for tm in marks:
        age = t - tm
        if age < -0.04 or age > span:
            continue
        xx = now_x - age * v
        if not (gx0 <= xx <= gx1):
            continue
        d.line([(xx - 4, top - 2), (xx - 4, bot + 2)], fill=fade(AMBER, 0.55 * alpha))
        d.line([(xx - 1, top - 2), (xx - 1, bot + 2)], fill=fade(AMBER, 0.85 * alpha), width=2)
        for yy in (top + (bot - top) * 0.3, top + (bot - top) * 0.7):
            d.ellipse([xx + 2, yy - 1.5, xx + 5, yy + 1.5], fill=fade(AMBER, 0.75 * alpha))
    # the notes
    f_n = font(tk.MONO, 9)
    for ev in onsets:
        tn, m = ev[0], ev[1]
        age = t - tn
        if age < 0 or age > span:
            continue
        best, best_fret = 0, 99
        for k, (_nm, open_m) in enumerate(tuning):
            fr = m - open_m
            if 0 <= fr < best_fret:
                best, best_fret = k, fr
        if best_fret > 12:
            continue
        xx = now_x - age * v
        yy = top + best * step
        a_ = alpha * (0.95 if age < 0.4 else max(0.25, 1.0 - age / span))
        tk.text(d, (xx - 3, yy - 5), "%d" % best_fret, f_n, (255, 246, 224), a_)
    d.line([(now_x, top - 3), (now_x, bot + 3)], fill=fade((255, 246, 224), 0.5 * alpha))


def _roll_track(d, box, t, onsets, alpha, span: float = 3.0):
    """钢琴：竖键柱。一层细窄的竖条，按时间从左往右，条高＝音高。

    Every instrument needs a silhouette you can name at 40 px. Piano is the only one drawn
    as VERTICAL strokes, so "which lane is the piano" needs no label.
    """
    x0, y0, x1, y1 = box
    now_x = x1 - 4
    v = (x1 - x0) / span
    d.line([(x0, y1), (x1, y1)], fill=fade(AMBER, 0.30 * alpha))
    lo, hi = 40, 84
    for ev in onsets:
        tn, m = ev[0], ev[1]          # (t, midi, strength[, dur]) — the piano table has 4
        age = t - tn
        if age < 0 or age > span:
            continue
        xx = now_x - age * v
        u = (m - lo) / (hi - lo)
        hh = 4 + (y1 - y0 - 6) * max(0.0, min(1.0, u))
        a_ = alpha * (0.85 if age < 0.4 else max(0.22, 1.0 - age / span))
        d.line([(xx, y1), (xx, y1 - hh)], fill=fade((255, 246, 224), a_), width=2)


def _curve_track(d, box, t, onsets, alpha, span: float = 3.0):
    """小提琴：一条不断的曲线。全片唯一的曲线，别的轨都是直的。

    A violin line is legato — drawing it as a polyline through the recent pitches says
    "one bow, one line" without any icon.
    """
    x0, y0, x1, y1 = box
    now_x = x1 - 4
    v = (x1 - x0) / span
    win = [ev for ev in onsets if 0.0 <= t - ev[0] <= span]
    lo = min((ev[1] for ev in win), default=52)
    hi = max((ev[1] for ev in win), default=76)
    rg = max(6, hi - lo)                 # normalise to what is actually being played
    pts = []
    for ev in win:
        tn, m = ev[0], ev[1]
        xx = now_x - (t - tn) * v
        u = (m - lo) / rg
        pts.append((xx, y1 - 4 - (y1 - y0 - 8) * u))
    if len(pts) > 1:
        pts.sort()
        d.line(pts, fill=fade((255, 246, 224), 0.85 * alpha), width=2)
    d.line([(x0, y1), (x1, y1)], fill=fade(AMBER, 0.22 * alpha))


def _col_track(d, box, t, level, alpha, seg: int = 10):
    """人声：一根竖柱。没有谱，只有"现在有多响"——人声是唯一不画音符的乐器。"""
    x0, y0, x1, y1 = box
    h = (y1 - y0) * max(0.0, min(1.0, level))
    cx = (x0 + x1) / 2
    for k in range(seg):
        yy = y1 - (y1 - y0) * (k + 1) / seg
        on = y1 - h <= yy
        d.line([(cx - 9, yy), (cx + 9, yy)],
               fill=fade(AMBER if on else BLUE_HI, (0.85 if on else 0.14) * alpha), width=2)


def _grid_track(d, box, t, onsets, alpha, steps: int = 16):
    """A step sequencer: one column per 1/4 beat of the last bar, lit where a hit landed."""
    x0, y0, x1, y1 = box
    cw = (x1 - x0) / steps
    bl = clock.beat_len(t)
    cur = clock.beat_pos(t)
    base = math.floor(cur / 4.0) * 4.0                 # the bar we are in
    for k in range(steps):
        cx0 = x0 + k * cw
        cx1 = cx0 + cw - 1.5
        # step_t0 is a BEAT index, the onset times are SECONDS — the first version compared
        # the two directly and no cell ever lit. Convert through the local beat length.
        step_t0 = base + k * 0.25
        t0s = t + (step_t0 - cur) * bl
        t1s = t0s + 0.25 * bl
        # the bar's height is the STRONGEST hit in the step, not how many there were:
        # counting gave 16 identical full bars (a wall, not a pattern)
        strs = [st for (tn, _m, st) in onsets if t0s <= tn < t1s and st > 0.12]
        on = max(strs) if strs else 0.0
        yy = y1 - (y1 - y0) * (0.25 + 0.60 * on)      # a cap: full height read as a wall
        d.rectangle([cx0, yy, cx1, y1 - 2],
                    outline=fade(AMBER, 0.30 * alpha),
                    fill=fade(AMBER, 0.75 * alpha) if on > 0.05 else None)
    d.rectangle([x0, y0, x1, y1], outline=fade(AMBER, 0.12 * alpha))
    # the playhead: one line, not a column — a 16 px outlined box read as a bug
    k = int(((cur % 4.0) / 4.0) * steps)
    px = x0 + k * cw
    d.line([(px, y0 - 2), (px, y1 + 1)], fill=fade((255, 246, 224), 0.65 * alpha), width=2)


def cellpanel(img: Image.Image, box, t: float, *, tracks, alpha: float = 1.0, sub: str = "",
              strum: float = -1.0, solo: str | None = None):
    """The carved instrument column — 器乐格.

    导演 (2026-10-27 03:10): 不画乐器，画它的代码形态。03:17: 格子太大在 99.30 转场时会
    打架，所以它必须是画面坐标里的固定第五区（见 layout4.zones 的 cell 参数），并且
    随着别的乐器加进来要能多轨分格。

    Each track is one instrument and one notation; a new chair opens a new track, the way a
    mixer grows a channel when a player sits down. `tracks` is [(name, kind, payload)].
    """
    if alpha <= 0.01 or not tracks:
        return
    x0, y0, x1, y1 = box
    if x1 - x0 < 24:
        return
    d = ImageDraw.Draw(img)
    _panel(img, (x0, y0, x1, y1), AMBER, alpha,
           title="INST // %02d" % len(tracks), right=sub)

    n = len(tracks)
    ttop = y0 + 10
    tbot = y1 - 8
    gap = 7
    th = (tbot - ttop - gap * (n - 1)) / n
    f = font(tk.MONO_B, 9)
    for i, (name, kind, payload) in enumerate(tracks):
        ty0 = ttop + i * (th + gap)
        ty1 = ty0 + th
        # the chair's name and its level, on the track's own line
        d.line([(x0 + 4, ty0 - 3), (x1 - 4, ty0 - 3)], fill=fade(AMBER, 0.16 * alpha))
        tk.text(d, (x0 + 5, ty0 + 1), name, f, AMBER,
                (0.95 if name == solo else 0.60) * alpha)
        if name == solo:
            d.line([(x0 + 4, ty0 - 2), (x0 + 30, ty0 - 2)], fill=fade(AMBER, 0.75 * alpha))
        lv = float(payload.get("level", 0.0)) if isinstance(payload, dict) else 0.0
        bx = x1 - 42
        d.line([(bx, ty0 + 5), (x1 - 6, ty0 + 5)], fill=fade(AMBER, 0.18 * alpha))
        if lv > 0.02:
            d.line([(bx, ty0 + 5), (bx + 36 * min(1.0, lv), ty0 + 5)],
                   fill=fade(AMBER, 0.8 * alpha), width=2)
        body = (x0 + 4, ty0 + 13, x1 - 4, ty1)
        if kind == "TAB":
            _tab_track(d, body, t, payload["onsets"], payload["tuning"], 3.2, alpha)
        elif kind == "GRID":
            _grid_track(d, body, t, payload["onsets"], alpha)
        elif kind == "ROLL":
            _roll_track(d, body, t, payload["onsets"], alpha)
        elif kind == "CURVE":
            _curve_track(d, body, t, payload["onsets"], alpha)
        elif kind == "COL":
            _col_track(d, body, t, payload["level"], alpha)
    if 0.0 <= strum <= 1.0:
        xx = x0 + 4 + (x1 - x0 - 8) * strum
        d.line([(xx, ttop), (xx, tbot)], fill=fade((255, 246, 224), 0.9 * alpha), width=2)


# ---------------------------------------------------------------- the rack
def rack(img: Image.Image, box, t: float, *, live: dict, solo: str | None = None,
         alpha: float = 1.0, mutes: tuple = ()):
    """Six chairs on the ground line. `live[name]` is 0..1: how much that chair is playing.

    A silent chair is not hidden — it stays as a dim outline, because the point of the shot
    is that the band is STANDING there and only one of them is playing. That is what makes
    the seven movements read as one ensemble instead of seven unrelated screens.
    """
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    n = len(SLOTS)
    sw = (x1 - x0) / n
    hh = y1 - y0
    # the stage floor: one line the whole band stands on
    d.line([(x0, y1 - 4), (x1, y1 - 4)], fill=fade(AMBER, 0.18 * alpha))
    _ticks(d, x0, x1, y1 - 4, AMBER, 0.11 * alpha, step=6, h=5)

    for i, name in enumerate(SLOTS):
        cx = x0 + (i + 0.5) * sw
        lv = max(0.0, min(1.0, float(live.get(name, 0.0)))) * alpha
        on = lv > 0.02
        col = AMBER if on else BLUE_HI
        a = (0.30 + 0.68 * lv) if on else 0.16
        if name in mutes:
            a *= 0.35
        glyph(d, name, cx, y0 + hh * 0.38, min(34.0, sw * 0.40), col, a)

        f = font(tk.MONO, 8)
        lab = "%02d %s" % (i + 1, name)
        tw = d.textlength(lab, font=f)
        d.text((cx - tw / 2, y0 + hh * 0.66), lab, font=f,
               fill=fade(col, (0.60 if on else 0.28) * alpha))
        # level: four segments, so a silent chair still shows its rails
        bx0, bx1 = cx - sw * 0.30, cx + sw * 0.30
        by = y1 - 12
        d.line([(bx0, by), (bx1, by)], fill=fade(col, 0.22 * alpha))
        seg = 4
        for k in range(seg):
            u = (k + 1) / seg
            if lv >= u - 0.24:
                xa = bx0 + (bx1 - bx0) * (k / seg) + 1
                xb = bx0 + (bx1 - bx0) * ((k + 1) / seg) - 1
                d.rectangle([xa, by - 3, xb, by - 1], fill=fade(col, 0.80 * alpha))
        if solo == name:
            f2 = font(tk.MONO, 7)
            d.line([(cx - 30, y0 + 2), (cx + 30, y0 + 2)], fill=fade(AMBER, 0.60 * alpha))
            for sx in (cx - 30, cx + 30):
                d.line([(sx, y0 + 2), (sx, y0 + 7)], fill=fade(AMBER, 0.60 * alpha))
            tw2 = d.textlength("SOLO", font=f2)
            d.text((cx - tw2 / 2, y0 - 10), "SOLO", font=f2, fill=fade(AMBER, 0.90 * alpha))


# ---------------------------------------------------------------- the keyboard
def keyboard(img: Image.Image, box, t: float, *, lo: int, hi: int, presses: dict,
             trail=None, alt_presses=None, alpha: float = 1.0, label_oct=True):
    """A wireframe keyboard, lit by whatever landed on it.

    `presses` maps midi -> intensity 0..1 (already decayed by the caller); `trail` is the
    last few notes in order, drawn as one continuous pen line across the key bed — the
    melody written on the instrument, which is where the counterpoint reads.
    """
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    k = 1.0                          # orthographic: this film has no vanishing point
    kw, pos = keymap(lo, hi, x0, x1 - x0)
    d = ImageDraw.Draw(img)

    depth = (y1 - y0) - 34           # the keys themselves
    yb = y0 + 4                      # back edge
    yf = yb + depth                  # front edge

    # the bed: an opaque slab, so the ridge behind does not show THROUGH the keys. Without
    # it the instrument reads as a fence hanging in the valley instead of a thing standing
    # in it — the same reason every panel zone has its own background.
    d.rectangle([x0 - 9, yb - 12, x1 + 9, yf + 22], fill=(7, 6, 4))

    # the case: back rail, cheeks, front lip
    d.line([(x0 - 9, yb - 12), (x1 + 9, yb - 12)], fill=fade(AMBER, 0.34 * alpha))
    d.line([(x0 - 9, yb - 12), (x0 - 9, yf + 9)], fill=fade(AMBER, 0.26 * alpha))
    d.line([(x1 + 9, yb - 12), (x1 + 9, yf + 9)], fill=fade(AMBER, 0.26 * alpha))
    # the front board: the instrument's body, and the reason the keys read as a bed
    # lying flat rather than as a fence standing up
    d.rectangle([x0 - 9, yf + 1, x1 + 9, yf + 22], outline=fade(AMBER, 0.34 * alpha),
                fill=(9, 8, 5))
    d.line([(x0 - 9, yf + 1), (x1 + 9, yf + 1)], fill=fade((255, 246, 224), 0.30 * alpha))
    fn = font(tk.MONO, 8)
    d.text((x0 + 6, yf + 8), "PNO-01  /  LANHUACAO", font=fn, fill=fade(AMBER, 0.42 * alpha))
    d.text((x1 - 52, yf + 8), "88/61", font=fn, fill=fade(AMBER, 0.22 * alpha))
    # the landing rail: every note arrives here, and the roll sits directly above it
    _ticks(d, x0, x1, yb - 12, AMBER, 0.16 * alpha, step=5, h=5)

    # white keys
    for m in range(lo, hi):
        if m % 12 not in WHITE_PC:
            continue
        kx, kwid, _ = pos[m]
        p = max(0.0, min(1.0, presses.get(m, 0.0))) * alpha
        a = 0.34 + 0.62 * p
        _quad(d, kx - kwid / 2 + 1, kx + kwid / 2 - 1, yb, yf, cx, k,
              AMBER, a, fill=(0.30 + 0.60 * p), rows=5)
        # every key has a 4 px front lip: thickness, without a vanishing point
        d.rectangle([kx - kwid / 2 + 1, yf - 4, kx + kwid / 2 - 1, yf],
                    fill=(13, 11, 7),
                    outline=fade(AMBER, min(1.0, a + 0.10)))
        if p > 0.02:
            # the pressed key's lip goes solid: the one bright mark on the instrument
            d.line([(kx - kwid / 2 + 1, yb), (kx + kwid / 2 - 1, yb)],
                   fill=fade((255, 246, 224), 0.9 * p))
            d.line([(kx - kwid / 2 + 5, yf - 2), (kx + kwid / 2 - 5, yf - 2)],
                   fill=fade((255, 246, 224), 0.85 * p), width=2)

    # black keys on top: opaque, so they cut the white key strokes like real raised keys
    for m in range(lo, hi):
        if m % 12 in WHITE_PC:
            continue
        kx, kwid, _ = pos[m]
        p = max(0.0, min(1.0, presses.get(m, 0.0))) * alpha
        kb = yb + depth * 0.60
        d.rectangle([kx - kwid / 2, yb, kx + kwid / 2, kb], fill=(13, 11, 7))
        _quad(d, kx - kwid / 2, kx + kwid / 2, yb, kb, cx, k,
              mix(BLUE_HI, AMBER, p), 0.30 + 0.55 * p,
              fill=(0.20 + 0.55 * p), rows=4)
        d.line([(kx - kwid / 2, kb), (kx + kwid / 2, kb)],
               fill=fade(mix(BLUE_HI, AMBER, p), 0.34 + 0.5 * p))

    # the second voice: a bracket on the key, never a fill, so the two voices stay legible
    if alt_presses:
        for m, p in alt_presses.items():
            if m not in pos or p <= 0.02:
                continue
            kx, kwid, black = pos[m]
            y2 = yb + (depth * 0.62 if black else depth * 0.74)
            d.line([(kx - kwid * 0.34, y2), (kx + kwid * 0.34, y2)],
                   fill=fade(BLUE_HI, 0.60 * p * alpha))
            for sx in (kx - kwid * 0.34, kx + kwid * 0.34):
                d.line([(sx, y2 - 3), (sx, y2)], fill=fade(BLUE_HI, 0.60 * p * alpha))

    # octave marks under the front lip
    if label_oct:
        f = font(tk.MONO, 8)
        for m in range(lo, hi, 12):
            if m not in pos:
                continue
            d.text((pos[m][0] + 4, yf + 26), "C%d" % (m // 12 - 1), font=f,
                   fill=fade(BLUE_HI, 0.34 * alpha))

    # the pen trail: one line through the key bed of the last few notes
    if trail:
        pts = []
        for (m, _age, _inten) in trail:
            if m not in pos:
                continue
            black = (m % 12 not in WHITE_PC)
            pts.append((pos[m][0], yb + depth * (0.42 if black else 0.56)))
        if len(pts) > 1:
            d.line(pts, fill=fade(AMBER, 0.45 * alpha))
        for (px, py) in pts:
            d.ellipse([px - 2, py - 2, px + 2, py + 2], outline=fade(AMBER, 0.70 * alpha))


# ---------------------------------------------------------------- the roll
def roll(img: Image.Image, box, t: float, *, lo: int, hi: int, notes, lead: float = 3.0,
         alt=None, alpha: float = 1.0, alt_alpha: float = 0.55, title: str | None = None):
    """Notes fall. Time is vertical, pitch is horizontal, so a bar lands on its own key.

    Not a scrolling history (that reads as a recorder) and not a bar graph (that reads as a
    level meter): the note is a BODY with a head and a tail, so the eye can predict the next
    attack from the picture — which is what makes an instrumental passage feel played rather
    than accompanied.
    """
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    h = y1 - y0
    v = h / lead                      # pixels per second of lead time
    kw, pos = keymap(lo, hi, x0, x1 - x0)

    # the pitch rules are VERTICAL here: they are the same seams as the keyboard's keys
    for m in range(lo, hi):
        if m % 12 == 0 and m in pos:
            xx = pos[m][0] - kw / 2
            d.line([(xx, y0), (xx, y1 + 10)], fill=fade(BLUE_HI, 0.15 * alpha))
            d.text((xx + 3, y0 - 11), "C%d" % (m // 12 - 1), font=font(tk.MONO, 7),
                   fill=fade(BLUE_HI, 0.28 * alpha))
        if m in pos:
            xx = pos[m][0] + kw / 2
            d.line([(xx, y0), (xx, y1)], fill=fade(BLUE_HI, 0.045 * alpha))

    # beat rules fall with the music; bars are brighter and numbered
    i = clock.beat_index(t)
    while True:
        bt = clock.beat_t(i)
        yy = y1 - (bt - t) * v
        if yy > y1 + 2:
            break
        if y0 - 2 < yy < y1:
            bar = (i % 4 == 0)
            d.line([(x0, yy), (x1, yy)],
                   fill=fade(AMBER if bar else BLUE_HI, (0.17 if bar else 0.07) * alpha))
            if bar:
                d.text((x1 + 4, yy - 4), "%d" % (i // 4 + 1), font=font(tk.MONO, 7),
                       fill=fade(AMBER, 0.34 * alpha))
        i += 1
        if bt > t + lead + 1:
            break

    def _draw(seq, col, base_a, scale_w):
        for (tn, m, s, dur) in seq:
            if m not in pos:
                continue
            kx, kwid, black = pos[m]
            if tn < t - 0.10 or tn > t + lead:
                continue
            ybot = min(y1, y1 - (tn - t) * v)
            ytop = y1 - (tn + dur - t) * v
            if ybot - ytop < 2.0:
                ytop = ybot - 2.0
            bw = max(3.0, kwid * scale_w)
            a = base_a * (0.55 + 0.45 * s)
            d.rectangle([kx - bw / 2, ytop, kx + bw / 2, ybot], outline=fade(col, a))
            # the head (the attack) is the bright end; the body is the tail
            d.line([(kx - bw / 2, ybot - 1), (kx + bw / 2, ybot - 1)],
                   fill=fade(col, min(1.0, a * 1.6)), width=2)
            if ybot - ytop > 7:
                d.line([(kx - bw / 2 + 1, ytop + 4), (kx + bw / 2 - 1, ytop + 4)],
                       fill=fade(col, a * 0.40))

    if alt:
        _draw(alt, BLUE_HI, 0.40 * alt_alpha * alpha, 0.46)
    _draw(notes, AMBER, 0.85 * alpha, 0.60)

    # the playhead: a fixed line at the foot of the roll, where a note becomes sound
    pr = 0.35 + 0.65 * clock.pulse(t)
    d.line([(x0, y1), (x1, y1)], fill=fade((255, 246, 224), 0.55 * pr * alpha), width=2)
    for xx in (x0, x1):
        d.line([(xx, y1 - 7), (xx, y1)], fill=fade(AMBER, 0.55 * alpha))

    # frame + corner brackets, the film's chrome grammar
    d.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], outline=fade(AMBER, 0.15 * alpha))
    for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(px, py), (px + sx * 7, py)], fill=fade(AMBER, 0.48 * alpha))
        d.line([(px, py), (px, py + sy * 7)], fill=fade(AMBER, 0.48 * alpha))
    if title:
        f = font(tk.MONO, 8)
        tw = d.textlength(title, font=f)
        d.rectangle([x0 + 5, y0 - 5, x0 + 13 + tw, y0 + 7], fill=(7, 6, 4))
        d.text((x0 + 8, y0 - 4), title, font=f, fill=fade(AMBER, 0.45 * alpha))


# ---------------------------------------------------------------- presses from notes
def presses_at(notes, t: float, *, fade_t: float = 0.42, pre: float = 0.10) -> dict:
    """midi -> how lit the key is at t. Attack is instant, release is a rounded decay."""
    out = {}
    for (tn, m, s, _dur) in notes:
        age = t - tn
        if -pre <= age <= 0.0:
            p = 0.26
        elif 0.0 < age < fade_t:
            p = (1.0 - age / fade_t) ** 1.4
        else:
            continue
        out[m] = max(out.get(m, 0.0), p * (0.55 + 0.45 * s))
    return out


def trail_at(notes, t: float, *, span: float = 2.6, limit: int = 9) -> list:
    """The last few attacks, oldest first — the pen line drawn across the keys."""
    out = []
    for (tn, m, s, _dur) in notes:
        age = t - tn
        if 0.0 <= age <= span:
            out.append((m, round(age, 3), 1.0 - age / span))
    return out[-limit:]


# ---------------------------------------------------------------- the whole stage
def stage(img: Image.Image, rect, t: float, *, kind: str, notes, live: dict,
          alt=None, alpha: float = 1.0, solo: str | None = None, mv=(0.0, 0.0)):
    """The enlarged view in the world. The roster is NOT here — it is the six lanes."""
    """The interlude's picture: rack + roll + keyboard, in the content zone.

    `kind` selects which of the three belong to this movement. The rack is always there
    (that is the ensemble); the roll and the keyboard belong to the played movements.
    """
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    KX0, KX1 = x0 + 56, x0 + w - 56          # roll and keyboard share these, so notes land
    rack_box = (x0 + 26, y0 + h - 116, x0 + w - 168, y0 + h - 8)
    kb_box = (KX0, y0 + 296, KX1, y0 + 452)
    roll_box = (KX0, y0 + 66, KX1, y0 + 286)

    d = ImageDraw.Draw(img)
    lo, hi = 36, 72

    if kind in ("piano", "duet"):
        # 导演 (05:39): 2:15→2:25 到钢琴没有衔接；钢琴结束也没有收。
        # 进 146.4–148.0 从地面升上来，出 188.8–190.2 沉回地面——同一个动作的两端。
        def _ease(u):
            u = max(0.0, min(1.0, u))
            return u * u * (3 - 2 * u)
        a_in = _ease((t - 146.4) / 1.6) if t < 148.0 else 1.0
        a_out = 1.0 - _ease((t - 188.6) / 1.6) if t > 188.6 else 1.0
        a_kb = alpha * a_in * a_out
        dy = (1.0 - a_in) * 130.0 + (1.0 - a_out) * 190.0     # + = 向下
        near = [n for n in notes if t - 0.6 <= n[0] <= t + 3.4]
        alt_near = [n for n in (alt or []) if t - 0.6 <= n[0] <= t + 3.4]
        roll(img, roll_box, t, lo=lo, hi=hi, notes=near, alt=alt_near,
             title="NOTE ROLL // %d onsets" % len(notes), alpha=a_kb)
        keyboard(img, (kb_box[0], kb_box[1] + dy, kb_box[2], kb_box[3] + dy), t, lo=lo, hi=hi,
                 presses=presses_at(notes, t),
                 alt_presses=presses_at(alt_near, t) if alt_near else None,
                 trail=trail_at(notes, t), alpha=a_kb)
        # the movement read-out, in the top strip: where we are, in machine words. The
        # note counter is the machine keeping score of what the band has played so far —
        # the only number in this shot that is allowed to climb.
        f = font(tk.MONO, 9)
        bi = clock.beat_index(t)
        done = sum(1 for n in notes if mv[0] <= n[0] <= t)
        tot = sum(1 for n in notes if mv[0] <= n[0] < mv[1])
        line = ("%s  ·  BAR %d.%d  ·  NOTES %03d/%03d  ·  112.35 BPM"
                % (kind.upper(), bi // 4 + 1, bi % 4 + 1, done, tot))
        d.text((KX0, y0 + 12), line, font=f, fill=fade(AMBER, 0.42 * alpha))
        if alt:
            d.text((KX0, y0 + 26), "CANON +7 st / 1 beat  ·  d = 0.534 s", font=f,
                   fill=fade(BLUE_HI, 0.30 * alpha))

    # The rack used to stand on the ground line with six icons. ⑤-A moved the roster into
    # the instrument column as six lanes, so keeping both would be two lists of the same
    # six people. The lane that is soloing is marked in the column instead.
    return img
