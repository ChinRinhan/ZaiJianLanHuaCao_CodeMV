# -*- coding: utf-8 -*-
"""layout4: the four-zone frame (left 实体 / right 内容 / right-edge ops / bottom tokens).

    +---------------------------------------------------------------+
    | header: LASER KARAOKE  LD-1994  ...  01:08.2 / 06:35   PLAY   |  44 px
    +----------------------+--------------------------------------+
    |  ENTITY  512 px      |  CONTENT  752 px        | ops 80 px  |
    |  the machine itself  |  what gets loaded      | real steps |
    +----------------------+--------------------------------------+
    | stdout . tokens  -- the lyric as a token stream               |  90 px
    +---------------------------------------------------------------+

Rules that keep the halves from fighting:
  ENTITY  the machine's front panel: CD transport, nameplate, PLAYLIST, the progress bar.
  CONTENT the world only: sky, ridges, telemetry, rain, column, pot, SIGNAL plate. No chassis.
  OPS     the two meters: SCORE and LEVEL (plan/14 keeps them in the machine, and the
          narrow column is where ch1's left-panel meters end up once the panel is split).
  TOKENS  the lyric, typed with the pen (plan/10): whole glyphs, one underline, one nib.

The HEADER, TOKENS band and OPS column never move: that is what kills the seam between
chapters. Only the split between ENTITY and CONTENT moves, and only once -- during the
121-second interlude the machine physically withdraws (512 -> 96 px) and the world takes the
frame. `zones(collapse)` is the single place that split is decided.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

import clock
import crt
import drive
import tk
from tk import AMBER, BG, BLUE_HI, BLUE_MID, GREEN, RED, fade, font, mix

W, H = tk.W, tk.H
PANEL_BG = (8, 7, 5)

ENT_W = 512
ENT_W_MIN = 96
GAP = 8
OPS_W = 80
HEAD_H = 44
TOK_H = 90
BODY_Y0 = HEAD_H + 4
BODY_Y1 = H - TOK_H - 6

# 1921 胡适《希望》首句 — the world carries the original; the machine rewrites it (我→谁)
POEM_OLD = "我从山中来"

# the album, in order — track 13 is the one playing (same table as preview.PLAYLIST)
PLAYLIST = [
    ("01", "我是多么想"), ("02", "动物的悲歌"), ("03", "灵光"),
    ("04", "永公街的街长"), ("05", "子夜抒怀"), ("06", "兄弟呀"),
    ("07", "这一年这一夜"), ("08", "我的心在发烫"), ("09", "后知后觉"),
    ("10", "蝴蝶结"), ("11", "跟得上我吧"), ("12", "我期待"),
    ("13", "再见 兰花草"),
]


def zones(collapse: float = 0.0, mode: str = "W"):
    """The four zones, and the three shot modes that re-weight them.

    W  the full machine: entity left, world right, ops column, token band.
    V  the valley shot: the entity withdraws to a narrow lamp strip and the world takes
       the frame (this is `collapse=1`; the interlude lives here).
    P  the paper shot: the machine and the ops column are gone, the lyric is the subject,
       and the only trace of the world is one horizon line near the foot of the page.

    plan/14 §2.2: the three layouts are NOT three sets of drawing code — they are the same
    code with different rectangles and different type sizes.
    """
    u = max(0.0, min(1.0, collapse))
    if mode == "P":
        return {
            "head": (0, 0, W, HEAD_H),
            "entity": (0, 0, 0, 0),
            "content": (0, 0, 0, 0),
            "ops": (0, 0, 0, 0),
            "paper": (8, BODY_Y0, W - 8, BODY_Y1),
            "tokens": (0, 0, 0, 0),
        }
    ew = int(round(ENT_W + (ENT_W_MIN - ENT_W) * u))
    ex0 = 8
    ex1 = ex0 + ew
    cx0 = ex1 + GAP
    cx1 = W - 8 - OPS_W - GAP
    return {
        "head": (0, 0, W, HEAD_H),
        "entity": (ex0, BODY_Y0, ex1, BODY_Y1),
        "content": (cx0, BODY_Y0, cx1, BODY_Y1),
        "ops": (cx1 + GAP, BODY_Y0, W - 8, BODY_Y1),
        "paper": (0, 0, 0, 0),
        "tokens": (8, H - TOK_H - 2, W - 8, H - 8),
    }


def _frame(d, rect, color, alpha=0.35, title=None, right=None):
    x0, y0, x1, y1 = rect
    d.rectangle(rect, outline=fade(color, alpha))
    L = 8
    for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(px, py), (px + sx * L, py)], fill=fade(color, min(1.0, alpha + 0.35)))
        d.line([(px, py), (px, py + sy * L)], fill=fade(color, min(1.0, alpha + 0.35)))
    if title and (x1 - x0) > 2 * len(title) * 6:
        f = font(tk.MONO, 10)
        tw = d.textlength(f" {title} ", font=f)
        d.rectangle([x0 + 10, y0 - 6, x0 + 14 + tw, y0 + 8], fill=BG)
        d.text((x0 + 12, y0 - 5), f" {title} ", font=f, fill=fade(color, min(1.0, alpha + 0.45)))
    if right:
        f = font(tk.MONO, 9)
        tw = d.textlength(right, font=f)
        d.text((x1 - tw - 8, y0 + 3), right, font=f, fill=fade(color, min(1.0, alpha + 0.3)))


def _reveal(parent: Image.Image, rect, u: float, draw) -> None:
    """Legacy CRT-aperture reveal — kept for the `mount ui/` macro gesture only."""
    if u <= 0.0:
        return
    if u >= 1.0:
        draw(parent)
        return
    lay = parent.copy()
    draw(lay)
    ap, line = crt.aperture_rect(rect, u)
    mask = Image.new("L", parent.size, 0)
    md = ImageDraw.Draw(mask)
    if ap is not None:
        ax0, ay0, ax1, ay1 = (int(round(v)) for v in ap)
        md.rectangle([ax0, ay0, ax1, ay1], fill=255)
        cy = (ay0 + ay1) // 2
        md.line([(ax0, cy), (ax1, cy)], fill=255, width=2)
    if line is not None:
        x0, x1, cy = line
        md.line([(x0, cy), (x1, cy)], fill=255, width=2)
    parent.paste(lay, (0, 0), mask)
    if ap is not None:
        d = ImageDraw.Draw(parent)
        cy = (int(ap[1]) + int(ap[3])) // 2
        d.line([(int(ap[0]), cy), (int(ap[2]), cy)], fill=fade((255, 246, 224), 0.45))


# ---- the module boot grammar: 先画框，然后以代码输入的动效为填充 ---------------------
FRAME_U = 0.34          # the first third of a boot is spent drawing the box


def _pen_frame(d, rect, u: float, color=AMBER, alpha=0.35, flash: bool = False):
    """The border draws itself like one pen stroke, clockwise from the top-left corner.

    A hot nib rides the leading point; when the stroke closes, the corner brackets pop
    (brighter for a beat if `flash`). This is the film's pen (plan/10) applied to chrome.
    """
    x0, y0, x1, y1 = rect
    w, h = max(0.0, x1 - x0), max(0.0, y1 - y0)
    per = 2 * (w + h)
    if per <= 0:
        return
    want = per * max(0.0, min(1.0, u))
    segs = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
            ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    acc = 0.0
    tip = (x0, y0)
    c = fade(color, alpha)
    for (ax, ay), (bx, by) in segs:
        L = abs(bx - ax) + abs(by - ay)
        if acc + L <= want:
            d.line([(ax, ay), (bx, by)], fill=c, width=1)
            tip = (bx, by)
            acc += L
        else:
            if want > acc:
                t = (want - acc) / max(1.0, L)
                ex, ey = ax + (bx - ax) * t, ay + (by - ay) * t
                d.line([(ax, ay), (ex, ey)], fill=c, width=1)
                tip = (ex, ey)
            break
    # the nib: a hot dot at the leading point while the stroke is still moving
    if u < 1.0:
        d.ellipse([tip[0] - 2, tip[1] - 2, tip[0] + 2, tip[1] + 2], fill=(255, 246, 224))
    # corner brackets snap in as the stroke closes
    if u >= 0.98:
        ca = min(1.0, alpha + (0.45 if flash else 0.18))
        L = 8
        for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                                 (x0, y1, 1, -1), (x1, y1, -1, -1)):
            d.line([(px, py), (px + sx * L, py)], fill=fade(color, ca))
            d.line([(px, py), (px, py + sy * L)], fill=fade(color, ca))


def _type_in(d, xy, s, f, color, k: float, row: int, rows: int, t: float,
             alpha: float = 1.0, rate: float = 60.0):
    """One row of code-input: the text is typed, each fresh glyph flickers before it locks.

    k is the fill progress 0..1; row `row` of `rows` starts when k passes its slot.
    At k = 1 the string is drawn plain, so the steady state is byte-identical to before.
    """
    if rows <= 0:
        return
    start = row / rows
    if k < 1.0:
        if k <= start:
            return
        age = (k - start) * rows * 0.18
        s_ = tk.decode(s, age, seed=int(t * 24) + row * 37 + 7717, rate=rate, settle=0.10)
    else:
        s_ = s
    d.text(xy, s_, font=f, fill=fade(color, alpha))
    # a block cursor rides the row while it is still being born
    if k < 1.0 and len(s_) < len(s) and (t * 2.2) % 1.0 < 0.62:
        cw = d.textlength(s_, font=f)
        d.rectangle([xy[0] + cw + 2, xy[1] + 1,
                     xy[0] + cw + 10, xy[1] + f.size + 1], fill=fade(BLUE_HI, 0.85))


def _wipe_in(parent: Image.Image, box, k: float, draw, axis: str = "x"):
    """Run `draw`, then reveal it progressively along `axis` behind a hot scan line.

    axis="x" plots left→right (charts); axis="y" prints top→bottom (panels).
    """
    if k >= 1.0:
        draw(parent)
        return
    if k <= 0.0:
        return
    lay = parent.copy()
    draw(lay)
    x0, y0, x1, y1 = (int(v) for v in box)
    if axis == "x":
        cut = x0 + int((x1 - x0) * k)
        if cut > x0:
            parent.paste(lay.crop((x0, y0, cut, y1)), (x0, y0))
            ImageDraw.Draw(parent).line([(cut, y0), (cut, y1)],
                                        fill=fade((255, 246, 224), 0.30), width=1)
    else:
        cut = y0 + int((y1 - y0) * k)
        if cut > y0:
            parent.paste(lay.crop((x0, y0, x1, cut)), (x0, y0))
            ImageDraw.Draw(parent).line([(x0, cut), (x1, cut)],
                                        fill=fade((255, 246, 224), 0.22), width=1)


def _boot(parent: Image.Image, rect, u: float, body, *, t: float = 0.0,
          color=AMBER, alpha=0.32, frame: bool = True, scan: bool = True):
    """One module coming on line, in two beats (导演: 先画框，然后以代码输入的动效为填充).

      u <  FRAME_U   the border draws itself as a pen stroke, nib at the leading point
      u >= FRAME_U   the body fills in — rows typed as code, charts plotted behind a wipe

    `body(k)` receives the fill progress 0..1 and staggers its own rows. The frame is
    stroked ON TOP of the body so a panel's own background never swallows the pen line.
    Steady state (u >= 1) draws plain, so nothing looks "typed" once the module is up.
    """
    if u <= 0.0:
        return
    u = min(1.0, u)
    if frame and u < FRAME_U:
        _pen_frame(ImageDraw.Draw(parent), rect, u / FRAME_U, color, alpha)
        return
    k = (u - FRAME_U) / (1.0 - FRAME_U) if frame else u
    body(parent, min(1.0, k))
    d = ImageDraw.Draw(parent)
    if frame:
        _pen_frame(d, rect, 1.0, color, alpha, flash=(u < FRAME_U + 0.09))
    if scan and 0.0 < k < 1.0:
        x0, y0, x1, y1 = rect
        fy = y0 + (y1 - y0) * k
        d.line([(x0 + 1, fy), (x1 - 1, fy)], fill=fade((255, 246, 224), 0.18), width=1)


def _boot_u(boot, key: str) -> float:
    """Module reveal progress. `boot=None` means the intro is over: everything is up."""
    if boot is None:
        return 1.0
    return max(0.0, min(1.0, float(boot.get(key, 0.0))))


def _poem(img: Image.Image, rect, t: float, st: dict, *, seed: int = 11,
          amp_scale: float = 1.0, x_off: float = 0.0, floor: float = 0.70):
    """The poem's first line living in the world (导演三条 + plan/05 §3.2).

    「我从山中来」——1921 胡适的原句，静淡一行浮在地平线上。当机器的 REWRITE 01 落定，
    世界接受这次编辑：我 被红笔划掉，谁 以 decode 打上去（与机器层同一套语法）。山起来的
    时候，这一句落上山脊——全片只此一次。

    Two copies crossfade: the flat horizon copy (clear period) hands over to the ridge
    copy (mountain risen). The replacement animates on the horizon copy only, so the
    ridge simply receives the finished line.
    """
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    a = st["alpha"]
    if a <= 0.01:
        return
    f = font(tk.CJK, 17)
    d = ImageDraw.Draw(img)

    # ---- the horizon copy: flat, dim, static (静淡一行不闪) ----
    hz = st["horizon"]
    if hz > 0.01:
        ah = a * hz
        yh = y0 + h * 0.615
        chars = list(POEM_OLD)
        n = len(chars)
        cw = 19
        total = n * cw
        fx = x0 + (w - total) / 2
        ty = yh - 34
        col = mix((170, 196, 245), (255, 252, 244), 0.45)
        for i, ch in enumerate(chars):
            cx = fx + i * cw
            if i == 0 and st["strike"]:
                age = st["type_age"]
                sa = st.get("strike_a", 1.0)
                if age is None:
                    # the strike just landed: the old glyph, struck through
                    dead = min(1.0, st["strike_u"] * 1.3)
                    tk.text(d, (cx, ty), ch, f, col, ah * (1.0 - 0.45 * dead))
                    d.line([(cx, ty + 10), (cx + 16, ty + 10)],
                           fill=fade(RED, 0.85 * ah * min(1.0, st["strike_u"] * 2)), width=2)
                else:
                    # 谁 lands in place; the dead 我 and its scar fade out with strike_a
                    if sa > 0.01:
                        tk.text(d, (cx, ty), ch, f, col, ah * 0.30 * sa)
                        d.line([(cx, ty + 10), (cx + 16, ty + 10)],
                               fill=fade(RED, 0.85 * ah * sa), width=2)
                    s_ = tk.decode("谁", age, seed=int(t * 24) + 401, rate=6.0, settle=0.5)
                    if s_:
                        tk.text(d, (cx, ty), s_, f, col, ah)
                    # a block cursor rides the glyph while it is still being born
                    if age < 0.75 and (t * 2.2) % 1.0 < 0.62:
                        d.rectangle([cx + 19, ty + 2, cx + 27, ty + 20],
                                    fill=fade(BLUE_HI, 0.80 * ah))
            else:
                tk.text(d, (cx, ty), ch, f, col, ah * 0.62)
        # the red box parks on the replaced char (plan/05 §1.9)
        if st["box_a"] > 0.01:
            d.rectangle([fx - 3, ty - 2, fx + 18, ty + 22],
                        outline=fade(RED, 0.70 * ah * st["box_a"]))

    # ---- the ridge copy: the line lands on the mountain (plan/05 §3.2, once) ----
    rg = st["ridge"]
    if rg > 0.01:
        text = "谁从山中来" if st["strike"] else POEM_OLD
        tk.ridge_text(img, rect, text, seed=seed, warm=0.12, row=1, size=17,
                      alpha=0.88 * a * rg, t=t, x_off=x_off,
                      amp_scale=amp_scale, floor=floor)


def header(t, *, state="READY", playing=False):
    img = Image.new("RGB", (W, HEAD_H), BG)
    d = ImageDraw.Draw(img)
    y0 = 6
    d.line([(0, HEAD_H - 1), (W, HEAD_H - 1)], fill=fade(AMBER, 0.22))
    tk.text(d, (14, y0), "LASER KARAOKE", font(tk.MONO_B, 13), AMBER, 0.88)
    tk.text(d, (150, y0 + 2), "LD-1994", font(tk.MONO, 11), AMBER, 0.50)
    lv = min(1.0, drive.drums(t) * 0.8 + 0.1)
    for i in range(24):
        hh = int(2 + 10 * lv * (0.4 + 0.6 * abs(math.sin(t * 2.4 + i * 0.6))))
        d.rectangle([240 + i * 5, y0 + 14 - hh, 240 + i * 5 + 3, y0 + 14],
                    fill=fade(AMBER, 0.25 + 0.6 * lv))
    mm, ss = int(t // 60), t % 60
    tk.text(d, (W - 300, y0 + 2), "%02d:%05.2f / 06:35" % (mm, ss), font(tk.MONO, 11), AMBER, 0.62)
    tk.text(d, (W - 120, y0 + 2), "PLAY" if playing else state,
            font(tk.MONO_B, 11), GREEN if playing else AMBER, 0.92)
    return img


def entity(t, rect=None, *, tray=0.0, disc=True, rpm=8.3, state="PLAY", power="ON",
           nameplate=True, collapse=0.0, boot=None, squeeze=0.0):
    rect = rect or zones(collapse)["entity"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), PANEL_BG)
    d = ImageDraw.Draw(img)
    u = max(0.0, min(1.0, collapse))
    narrow = w < 220
    idle = float(boot.get("idle", 0.0)) if boot else 0.0
    dim = 1.0 - 0.5 * idle

    for gr, a in ((0, 0.42), (-4, 0.20), (-8, 0.10)):
        d.rectangle([gr, gr, w - 1 - gr, h - 1 - gr], outline=fade(AMBER, a * (1 - 0.4 * u)))

    hy = 30 if narrow else 36
    d.rectangle([10, hy - 12, w - 10, hy + 2], fill=(12, 10, 6))
    d.line([(10, hy), (w - 10, hy)], fill=fade((255, 246, 224), 0.52))
    if narrow:
        tk.text(d, (16, 8), "LD-1994", font(tk.MONO, 8), AMBER, 0.55)
        lamp = {"OFF": (70, 44, 20), "ON": AMBER, "PLAY": GREEN}[power]
        d.ellipse([w // 2 - 7, h // 2 - 7, w // 2 + 7, h // 2 + 7],
                  outline=fade(lamp, 0.9), fill=fade(lamp, 0.55))
        tk.text(d, (16, h - 40), "PWR", font(tk.MONO, 8), AMBER, 0.40)
        hit = drive.drum_hit(t)
        d.ellipse([16, h - 24, 26, h - 14], outline=fade(AMBER, 0.5),
                  fill=fade(AMBER, 0.2 + 0.6 * hit))
        return img

    bx0, bx1 = 16, w - 16

    by0, by1 = 14, 248
    d.rectangle([bx0, by0, bx1, by1], outline=fade(AMBER, 0.32))
    tk.text(d, (bx0 + 10, by0 + 2), " CD TRANSPORT ", font(tk.MONO, 9), AMBER, 0.60)

    if tray > 0.01:
        th, ty = 150, hy + 8
        d.rectangle([bx0 + 8 - 20 * tray, ty, bx1 - 8 + 20 * tray, ty + th],
                    fill=(16, 13, 7), outline=fade(AMBER, 0.28 + 0.22 * tray))
        tk.text(d, (bx0 + 18, ty + th - 18), "TRAY", font(tk.MONO, 8), AMBER, 0.36 * tray)

    if disc:
        r = 88
        cx, cy = bx0 + 22 + r, hy + 22 + r
        revs = 0.5 * 8.3 * 0.8 + rpm * max(0.0, t - 6.0) if rpm > 0 else 0.0
        blur = min(1.0, rpm / 8.3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(52, 44, 30), outline=fade(AMBER, 0.55))
        for k in range(1, 10):
            rr = r * k / 10
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      outline=fade(AMBER, 0.11 * (1 - 0.6 * blur)))
        for k in range(-r, r):
            if abs(k) < r * 0.97:
                ww = (r * r - k * k) ** 0.5
                aa = 0.38 * (1 - abs(k) / r) ** 1.4
                col = mix((255, 236, 190), (150, 210, 255), (k + r) / (2 * r))
                d.line([(cx - ww, cy + k), (cx + ww, cy + k)], fill=fade(col, aa))
        if rpm > 0:
            a0 = (revs * 360.0) % 360.0
            d.arc([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], start=a0,
                  end=a0 + 70 + 190 * blur,
                  fill=fade((255, 248, 225), 0.70 * (1 - 0.5 * blur)), width=2)
        d.ellipse([cx - r * 0.30, cy - r * 0.30, cx + r * 0.30, cy + r * 0.30],
                  fill=(30, 24, 14), outline=fade(AMBER, 0.4))
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=fade(AMBER, 0.6))

        # The nameplate sits to the RIGHT of the disc. While the column collapses (the
        # 121-second interlude) there is not enough room for it, and a rectangle whose
        # right edge is left of its left edge raises ValueError. So the plate is drawn
        # only when it fits, and the disc alone carries the column in between.
        px, py = cx + r + 18, cy - 74
        if nameplate and bx1 - 8 > px - 8:
            np_rect = (px - 8, py - 10, bx1 - 8, py + 108)

            def _draw_nameplate(im, k):
                dd = ImageDraw.Draw(im)
                dd.rectangle(list(np_rect), outline=fade(AMBER, 0.22), fill=(11, 9, 6))
                # each datum is typed in as code input (导演: 先画框，然后代码输入填充)
                _type_in(dd, (px, py - 2), "TRACK 013", font(tk.MONO, 9), AMBER,
                         k, 0, 6, t, alpha=0.44)
                _type_in(dd, (px, py + 14), "再见 兰花草", font(tk.CJK, 22), (238, 206, 148),
                         k, 1, 6, t, alpha=0.95, rate=30.0)
                if k >= 2 / 6:
                    dd.line([(px, py + 44), (px + 150, py + 44)], fill=fade(AMBER, 0.26))
                _type_in(dd, (px, py + 50), "张雨生", font(tk.CJK, 12), AMBER,
                         k, 3, 6, t, alpha=0.64, rate=30.0)
                _type_in(dd, (px, py + 68), "卡拉OK·台北·我", font(tk.CJK, 9), AMBER,
                         k, 4, 6, t, alpha=0.40, rate=30.0)
                _type_in(dd, (px, py + 82), "1994 飞碟唱片", font(tk.CJK, 9), AMBER,
                         k, 5, 6, t, alpha=0.34, rate=30.0)
                if k >= 0.98:
                    for sx in (px - 4, bx1 - 16):
                        dd.ellipse([sx, py - 6, sx + 5, py - 1], fill=fade(AMBER, 0.28))
                        dd.ellipse([sx, py + 100, sx + 5, py + 105], fill=fade(AMBER, 0.28))

            _boot(img, np_rect, _boot_u(boot, "sleeve"), _draw_nameplate, t=t)

    my0, my1 = 262, 500
    # B① 界面过载（plan/05 §4: 播放列表被挤）——the rows pack tighter as the machine
    # is squeezed by the volume; the block itself shrinks with them.
    row_h = 16 - 5 * max(0.0, min(1.0, squeeze))
    blk_h = 20 + 13 * row_h + 10
    my1 = my0 + blk_h

    def _draw_playlist(im, k):
        dd = ImageDraw.Draw(im)
        dd.rectangle([bx0, my0, bx1, my1], outline=fade(AMBER, 0.28))
        # the header is typed first, then the 13 tracks land one per row
        _type_in(dd, (bx0 + 10, my0 + 2), " PLAYLIST ", font(tk.MONO, 9), AMBER,
                 k, 0, 15, t, alpha=0.55)
        _type_in(dd, (bx1 - 78, my0 + 3), "13 TRACKS", font(tk.MONO, 8), AMBER,
                 k, 1, 15, t, alpha=0.28)
        n_rows = 15                      # 2 header rows + 13 tracks
        for i, (num, name) in enumerate(PLAYLIST):
            row = i + 2
            if k < 1.0 and k <= row / n_rows:
                break                    # this row has not been typed yet
            yy = my0 + 20 + i * row_h
            cur = num == "13"
            if cur:
                dd.rectangle([bx0 + 4, yy - 2, bx1 - 4, yy + 15], fill=(30, 21, 6))
                dd.rectangle([bx0 + 4, yy - 2, bx0 + 7, yy + 15], fill=fade(AMBER, 0.9))
            _type_in(dd, (bx0 + 14, yy), num, font(tk.MONO, 10), AMBER,
                     k, row, n_rows, t, alpha=(0.9 if cur else 0.28), rate=90.0)
            _type_in(dd, (bx0 + 46, yy - 1), name, font(tk.CJK, 11),
                     AMBER if cur else (150, 150, 150),
                     k, row, n_rows, t, alpha=(0.95 if cur else 0.33), rate=30.0)
            if cur and (k >= 1.0 or k > (row + 0.7) / n_rows):
                tk.text(dd, (bx1 - 48, yy), "NOW", font(tk.MONO_B, 9), GREEN, 0.85)

    _boot(img, (bx0, my0, bx1, my1), _boot_u(boot, "playlist"), _draw_playlist, t=t)

    # progress + transport: the machine's own clock, under the playlist (ch1 left panel)
    py = 516
    hr_y = py - 6
    d.line([(bx0 + 4, hr_y), (bx1 - 4, hr_y)], fill=fade(AMBER, 0.18))
    d.rectangle([bx0 + 4, py, bx1 - 4, py + 5], fill=(22, 16, 6))
    p = max(0.0, min(1.0, t / 395.667))
    if p > 0:
        d.rectangle([bx0 + 4, py, bx0 + 4 + int((bx1 - bx0 - 8) * p), py + 5],
                    fill=fade(AMBER, 0.80))
    mm, ss = int(t // 60), int(t % 60)
    tk.text(d, (bx0 + 4, py + 14), "%02d:%02d" % (mm, ss), font(tk.MONO, 12), AMBER, 0.65)
    tk.text(d, (bx1 - 130, py + 14), "/ 06:35  " + ("PLAY >" if state == "PLAY" else "PAUSE ||"),
            font(tk.MONO, 11), AMBER, 0.50)

    cy = 558
    lamp = {"OFF": (70, 44, 20), "ON": AMBER, "PLAY": GREEN}[power]
    d.ellipse([bx0 + 4, cy, bx0 + 18, cy + 14], outline=fade(lamp, 0.9), fill=fade(lamp, 0.55))
    tk.text(d, (bx0 + 26, cy + 1), "POWER", font(tk.MONO, 8), AMBER, 0.40)
    for i, (lab, on) in enumerate((("PLAY", state == "PLAY"), ("STOP", state == "STOP"))):
        kx = 128 + i * 74
        top = cy + (3 if on else 0)
        d.rectangle([kx, top, kx + 60, top + 22], fill=fade(AMBER, 0.20 if on else 0.07),
                    outline=fade(AMBER, 0.55 if on else 0.22))
        tk.text(d, (kx + 13, top + 5), lab, font(tk.MONO_B, 10),
                GREEN if on else AMBER, 0.95 if on else 0.40)
    hit = drive.drum_hit(t)
    d.ellipse([290, cy + 2, 300, cy + 12], outline=fade(AMBER, 0.55),
              fill=fade(AMBER, 0.25 + 0.6 * hit))
    tk.text(d, (306, cy + 1), "SPIN", font(tk.MONO, 8), AMBER, 0.40)

    for i in range(8):
        d.line([(24, h - 34 + i * 4), (w - 24, h - 34 + i * 4)], fill=fade(AMBER, 0.05))
    return img


def content(t, rect=None, *, sky_a=1.0, ridge_a=1.0, star_a=1.0, rain_a=0.0, plate_a=1.0,
            pot_a=1.0, column_a=1.0, floor=0.70, seed=11, label="WORLD // VALLEY",
            amp_scale=1.0, x_off=0.0, pot_h=235.0, pot_count=1, pot_x=0.845, horizon=0.0,
            boot=None, poem=None, rise=0.0):
    rect = rect or zones()["content"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    R = (0, 0, w, h)
    img = Image.new("RGB", (w, h), PANEL_BG)

    # the climb (导演: 画面要有提高和上升) — the world warms and gains light as the
    # emotion rises toward the demands
    warm = 0.40 * rise

    if sky_a > 0.01:
        lay = Image.new("RGB", (w, h), PANEL_BG)
        tk.sky(lay, R, warm, 0.0)
        img.paste(Image.blend(Image.new("RGB", (w, h), PANEL_BG), lay, sky_a), (0, 0))

    v_sig = drive.vocals_smooth(t)
    b_sig = drive.bass_smooth(t)
    o_sig = drive.other_smooth(t)

    if ridge_a > 0.01:
        lay = Image.new("RGB", (w, h), PANEL_BG)
        tk.terrain(lay, R, mood=warm, seed=seed, t=t, cold=0.0, x_off=x_off,
                   amp_scale=amp_scale * ridge_a * (0.74 + 0.55 * b_sig), floor=floor)
        img = Image.blend(img, lay, min(1.0, ridge_a * 1.15))
    if star_a > 0.01:
        tk.stars(img, R, t, seed, min(1.0, 0.95 * star_a * (0.85 + 0.55 * rise)))
    if rain_a > 0.01:
        tk.rain(img, R, t, rain_a * (0.25 + 1.15 * o_sig), seed)
    if column_a > 0.01:
        img = tk.entity(img, w * 0.40, h * 0.40, t, column_a * (0.18 + 0.82 * v_sig))

    tk.grass(img, R, t, ridge_a, seed)
    # ch1's floating read-outs (grad / rms / tok ...) — the pane reads as a TUI, not a
    # wallpaper. Gated on the HUD wave so A④ can still drain them away.
    if plate_a > 0.05:
        tk.reticle(img, w * 0.40, h * 0.40, 18)

        def _draw_telemetry(im, k):
            # the read-outs are already "code"; they just print in behind the wipe
            tk.telemetry(im, R, t, seed, (1.0 - 0.4 * 0.0) * plate_a)

        _boot(img, R, _boot_u(boot, "ticker"), _draw_telemetry, t=t,
              frame=False, scan=False)
    if pot_a > 0.01:
        # one pot is the poem's pot ("谁记得曾经有那一盆"); a hillside of them is A③
        if pot_count <= 1:
            tk.orchid(img, w * pot_x, h - 16, pot_h * pot_a, t, alpha=1.0, blooms=2)
        else:
            for k in range(pot_count):
                fx = pot_x + (k - (pot_count - 1) / 2) * 0.085
                hh = pot_h * pot_a * (0.72 + 0.28 * ((k * 37) % 7) / 6)
                tk.orchid(img, w * fx, h - 16 - (k % 3) * 6, hh, t + k * 0.7,
                          alpha=0.92, blooms=2)

    d = ImageDraw.Draw(img)
    if horizon > 0.005:
        # plan/12 ①: while the world is empty there is still a GROUND. Without this the
        # content pane reads as a render failure instead of "the machine is waiting".
        yh = h * 0.615
        d.line([(10, yh), (w - 10, yh)], fill=fade(BLUE_HI, 0.09 * horizon))

    # the poem's first line lives in the world (导演: 只放首句，静淡一行)
    if poem is not None:
        _poem(img, R, t, poem, seed=seed, amp_scale=amp_scale, x_off=x_off, floor=floor)
        d = ImageDraw.Draw(img)

    d = ImageDraw.Draw(img)
    if plate_a > 0.01:
        pw, ph = int(w * 0.50), 132
        plate = (16, h - ph - 16, 16 + pw, h - 16)
        spec_box = (plate[0] + 10, plate[1] + 20, plate[0] + int(pw * 0.42), plate[3] - 10)
        wave_box = (plate[0] + int(pw * 0.45), plate[1] + 20, plate[2] - 10, plate[3] - 10)

        def _draw_plate(im, k):
            dd = ImageDraw.Draw(im)
            tk.hud_plate(im, plate, "SIGNAL / 24.15N 120.68E", BLUE_HI, 0.30 * plate_a)
            dd = ImageDraw.Draw(im)
            # the two charts PLOT in left→right behind a hot edge — the machine drawing
            # its own read-outs, not a picture fading up
            wv = _boot_u(boot, "wave")
            if wv > 0.01:
                kw = k if wv < 1.0 else 1.0
                _wipe_in(im, wave_box, kw,
                         lambda dst: tk.line_chart(dst, wave_box, t, _series(), BLUE_HI,
                                                   0.75 * plate_a, mode="history"),
                         axis="x")
                dd = ImageDraw.Draw(im)
            sp = _boot_u(boot, "spectrum")
            if sp > 0.01:
                ks = k if sp < 1.0 else 1.0
                _wipe_in(im, spec_box, ks,
                         lambda dst: tk.spectrum(dst, spec_box, t, max(0.05, _level(t)),
                                                 dim=plate_a, **_bands(t)),
                         axis="x")
                dd = ImageDraw.Draw(im)
            # SPEC / RMS tags type in last
            _type_in(dd, (plate[0] + 8, plate[3] - 12), "SPEC", font(tk.MONO, 8), BLUE_HI,
                     k, 0, 2, t, alpha=0.35 * plate_a, rate=90.0)
            _type_in(dd, (plate[0] + 202, plate[3] - 12), "RMS / 100 Hz", font(tk.MONO, 8),
                     BLUE_HI, k, 1, 2, t, alpha=0.35 * plate_a, rate=90.0)

        _boot(img, plate, _boot_u(boot, "wave"), _draw_plate, t=t,
              color=BLUE_HI, alpha=0.26, scan=False)
        d = ImageDraw.Draw(img)
    tk.ticks(img, R)
    d = ImageDraw.Draw(img)
    tk.hud(d, R, t, label, BLUE_HI, 0.40, stamp="261026 0353")
    _frame(d, R, BLUE_MID, 0.22)
    # the climb, last touch: the whole world gains light as the emotion rises
    if rise > 0.01:
        img = ImageEnhance.Brightness(img).enhance(1.0 + 0.16 * rise)
    return img


def ops(t, rect=None, *, score=0.0, level=0.0, boot=None, overload=0.0):
    """The narrow right column: ch1's two meters, SCORE and LEVEL, stacked vertically.

    plan/14 keeps the meters "in the machine"; once the panel is split into four zones the
    80 px edge is where they fit — a big number over a bar over a bar meter. Replaces the
    ops task list, which read as a dashboard rather than as part of a karaoke machine.
    During B① the machine overloads (plan/05 §4) and a red PEAK lamp pins on, flashing
    with the drums.
    """
    rect = rect or zones()["ops"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), PANEL_BG)
    d = ImageDraw.Draw(img)
    _frame(d, (0, 0, w - 1, h - 1), AMBER, 0.32, title="meters")

    if overload > 0.01:
        # the overload lamp: red, pinned, twitching on every drum hit (plan/05 §4 口令闪)
        hit = drive.drum_hit(t)
        la = (0.55 + 0.45 * hit) * overload
        d.rectangle([6, h - 74, w - 8, h - 60], fill=fade(RED, 0.18 * la))
        tk.text(d, (10, h - 73), "PEAK", font(tk.MONO_B, 9), RED, la)

    # ---- SCORE: the number, then its bar (ch1 left panel rows 310-341) ----
    def _draw_score(im, k):
        dd = ImageDraw.Draw(im)
        _type_in(dd, (8, 18), "SCORE", font(tk.MONO, 9), AMBER, k, 0, 3, t,
                 alpha=0.50, rate=90.0)
        sc = min(score, 99.4)
        # the digits are typed one at a time, like a machine reading out its score
        _type_in(dd, (6, 32), f"{sc:4.1f}", font(tk.MONO_B, 22), AMBER, k, 1, 3, t,
                 alpha=0.92, rate=18.0)
        if k >= 2 / 3:
            dd.rectangle([6, 64, w - 8, 70], fill=(24, 17, 6))
            if sc > 0:
                bar = (k - 2 / 3) / (1 / 3) if k < 1.0 else 1.0
                dd.rectangle([6, 64, 6 + int((w - 14) * min(1.0, sc / 100) * min(1.0, bar)), 70],
                             fill=fade(AMBER, 0.85))

    _boot(img, (0, 8, w, 78), _boot_u(boot, "score"), _draw_score, t=t)

    # ---- LEVEL: ch1's 26-segment bar meter, rotated to fit the column ----
    def _draw_level(im, k):
        dd = ImageDraw.Draw(im)
        _type_in(dd, (8, 92), "LEVEL", font(tk.MONO, 9), AMBER, k, 0, 2, t,
                 alpha=0.50, rate=90.0)
        n = 22
        for i in range(n):
            # bars light one by one, top down, as the code fills the meter
            if k < 1.0 and k <= (i + 1) / (n + 1):
                break
            v = level * (0.35 + 0.65 * abs(math.sin(t * 2.7 + i * 0.55))) * (1 - 0.5 * i / n)
            hh = int(2 + v * 26)
            y = 118 + i * 11
            if y + 8 > h - 60:
                break
            dd.rectangle([8, y, 8 + hh, y + 7], fill=fade(AMBER, 0.22 + 0.7 * v))
            dd.rectangle([8 + hh + 2, y, w - 10, y + 7], outline=fade(AMBER, 0.10))

    _boot(img, (0, 84, w, h - 56), _boot_u(boot, "meter"), _draw_level, t=t)

    # ---- empty chorus channels: the meter jumps, the sources are blank (ch1) ----
    tk.text(d, (8, h - 48), "CH 1-6", font(tk.MONO, 9), AMBER, 0.45)
    tk.text(d, (8, h - 34), "[ -- ]", font(tk.MONO, 10), RED, 0.60)
    return img


def tokens(t, rect=None, *, chars, ids=None, typed=0, struck=None, cursor=False,
           label="LYRIC", log=None, old=None, times=None, sub=None):
    """The bottom band. Two roles, one place:

    log  -> boot lines, printed one by one with decoding glyphs (the opening)
    chars-> the lyric, TYPED with the pen (plan/10: whole glyphs, one underline, one nib)

    Keeping both in the same band is what lets the machine hand over to the song without the
    frame changing: the text simply stops being a boot log and starts being the lyric.

    `old` is the pre-rewrite line. It is shown struck through, on its own row above the
    line being written, so a rewrite reads as an edit of the same line rather than a new
    line (plan/11 §3: 纸不动，笔不停).
    """
    rect = rect or zones()["tokens"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    _frame(d, (0, 0, w - 1, h - 1), AMBER, 0.30)

    if log is not None:
        tk.text(d, (12, 6), "tty0 . boot", font(tk.MONO, 9), AMBER, 0.40)
        tk.text(d, (14, 24), "$", font(tk.MONO_B, 14), GREEN, 0.85)
        f = font(tk.MONO, 10)
        for i, (t_at, s_) in enumerate(log[-4:]):
            if t < t_at:
                break
            age = t - t_at
            txt = tk.decode(s_, age, seed=7717 + i * 31 + int(t * 24) // 24, rate=90.0, settle=0.10)
            d.text((34, 24 + i * 15), txt, font=f,
                   fill=fade(AMBER, 0.45 + 0.45 * min(1.0, age * 4)))
        return img

    tk.text(d, (12, 6), label, font(tk.MONO, 9), AMBER, 0.40)

    top = 26
    if old:
        # the dead version, struck through, above the line being written
        fo = font(tk.CJK, 13)
        d.text((14, 8), "REWRITTEN", font=tk.font(tk.MONO, 7), fill=fade(RED, 0.55))
        d.text((88, 6), old, font=fo, fill=fade((150, 150, 150), 0.50))
        ow = d.textlength(old, font=fo)
        d.line([(88, 6 + 15), (88 + ow, 6 + 15)], fill=fade(RED, 0.60), width=1)
        top = 34

    if not chars:
        if cursor:
            d.rectangle([16, top + 2, 28, top + 30], fill=fade(BLUE_HI, 0.85))
        return img

    # the lyric: typed with the pen — whole glyphs, one underline, one nib (plan/10)
    fc = font(tk.CJK, 21)
    disp = "".join(chars)
    if times is not None and len(times) == len(disp):
        tk.pen_typed(img, (16, top), disp, fc, (255, 252, 240), t, times=times,
                     alpha=0.95, underline=AMBER)
    else:
        # no measured times: fall back to the same even progress pen_typed uses
        prog = typed / max(1, len(disp))
        tk.pen_typed(img, (16, top), disp, fc, (255, 252, 240), prog, times=None,
                     alpha=0.95, underline=AMBER)

    # the one rewritten glyph, struck where it sits (plan/16 §2.3 UNDO marks the same way)
    if struck is not None and 0 <= struck < len(disp):
        cx = 16 + d.textlength(disp[:struck], font=fc)
        cw = d.textlength(disp[struck], font=fc)
        uy = top + int(fc.size * 1.06)
        d.line([(cx, uy), (cx + cw, uy)], fill=fade(RED, 0.95), width=2)

    if sub:
        tk.text(d, (16, top + 34), sub, font(tk.CJK, 11), AMBER, 0.34)
    return img


_SERIES = None
_BANDS = None


def _series():
    global _SERIES
    if _SERIES is None:
        import numpy as np
        p = Path(__file__).resolve().parents[1] / "data" / "audio" / "rms.npy"
        _SERIES = np.load(p).astype(float).tolist() if p.exists() else []
    return _SERIES


def _bands(t):
    global _BANDS
    if _BANDS is None:
        import numpy as np
        p = Path(__file__).resolve().parents[1] / "data" / "audio" / "bands24.npy"
        _BANDS = np.load(p) if p.exists() else None
    if _BANDS is None:
        return {}
    i0 = min(max(0, int(t * 24)), len(_BANDS) - 1)
    return {"cur": _BANDS[i0], "peak": _BANDS[max(0, i0 - 12):i0 + 1].max(axis=0)}


def _level(t):
    import numpy as np
    s = _series()[max(0, int(t * 100) - 12):int(t * 100) + 12]
    return float(np.sqrt(np.mean(np.array(s) ** 2))) if s else 0.0


def paper(t, rect=None, *, chars, typed=0, struck=None, cursor=False, label="LYRIC // page",
          ids=None, sub=None, horizon=0.10, alpha=1.0, old=None, times=None):
    """The P shot: the page, and nothing else.

    plan/14 §2.2 — "只留歌词区（放大到 720 宽，字号 34，居中）" and "只留一条地平线".
    The machine is not in this shot: the song is being written and the page IS the screen.
    The horizon is the last trace of the world, at the very foot of the page, so the shot
    still belongs to the same film.

    `old` is the pre-rewrite line: struck through, above the line being written, so the
    rewrite reads as "the same page, edited" (plan/11 §3: 纸不动，笔不停).
    """
    rect = rect or zones(mode="P")["paper"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # the page itself: a faint sheet of light, so the shot is not a black rectangle
    d.rectangle([0, 0, w - 1, h - 1], outline=fade(AMBER, 0.16 * alpha))
    d.rectangle([6, 6, w - 7, h - 7], outline=fade(AMBER, 0.07 * alpha))

    tk.text(d, (16, 10), label, font(tk.MONO, 9), AMBER, 0.38 * alpha)
    if sub:
        tk.text(d, (w - 12 - d.textlength(sub, font=tk.font(tk.MONO, 9)), 10), sub,
                font(tk.MONO, 9), AMBER, 0.32 * alpha)

    # ---- 点缀 (导演: 界面有点空) — the page is a manuscript inside a machine:
    # faint ruled lines, line numbers in the margin, and the machine's own stamps.
    f_no = font(tk.MONO, 8)
    d.line([(72, 34), (72, h - 58)], fill=fade(AMBER, 0.11 * alpha))
    yy = 58
    n_line = 1
    while yy < h - 72:
        tk.text(d, (22, yy - 5), "%02d" % n_line, f_no, AMBER, 0.16 * alpha)
        d.line([(84, yy), (w - 24, yy)], fill=fade(AMBER, 0.05 * alpha))
        yy += 46
        n_line += 1
    tk.text(d, (w - 158, h - 36), "24.15N 120.68E", font(tk.MONO, 8), BLUE_HI, 0.30 * alpha)
    tk.text(d, (22, h - 36), "TUI-1", font(tk.MONO, 8), BLUE_HI, 0.22 * alpha)

    # the horizon: one line, at the foot of the page (plan/12 ①: the world keeps a trace)
    if horizon > 0.005:
        yh = y0 + h - 42
        d.line([(x0 + 24, yh), (x1 - 24, yh)], fill=fade(BLUE_MID, 0.55 * horizon * alpha))

    # the lyric, centred, typed with the pen at 34 px — big enough to read the pen moving
    fc = font(tk.CJK, 34)
    disp = "".join(chars)
    widths = [d.textlength(c, font=fc) for c in chars]
    total = sum(widths) + 8 * max(0, len(chars) - 1)
    fx = x0 + (w - total) / 2
    fy = y0 + h * 0.42

    # the old version, struck through, sitting above the line being written
    if old:
        fo = font(tk.CJK, 15)
        ow = d.textlength(old, font=fo)
        ox = x0 + (w - ow) / 2
        oy = fy - 48
        d.text((ox, oy), old, font=fo, fill=fade((150, 150, 150), 0.50 * alpha))
        d.line([(ox, oy + 17), (ox + ow, oy + 17)], fill=fade(RED, 0.60 * alpha), width=1)
        d.text((ox, oy - 17), "REWRITTEN", font=tk.font(tk.MONO, 8), fill=fade(RED, 0.55 * alpha))

    if disp:
        if times is not None and len(times) == len(disp):
            tk.pen_typed(img, (fx, fy), disp, fc, (255, 252, 240), t, times=times,
                         alpha=0.96 * alpha, underline=AMBER)
        else:
            tk.pen_typed(img, (fx, fy), disp, fc, (255, 252, 240),
                         typed / max(1, len(disp)), times=None,
                         alpha=0.96 * alpha, underline=AMBER)

    # the one rewritten glyph, struck where it sits
    if struck is not None and 0 <= struck < len(chars):
        cx = fx + sum(widths[:struck]) + 8 * struck
        cw = widths[struck]
        uy = fy + int(fc.size * 1.06)
        d.line([(cx, uy), (cx + cw, uy)], fill=fade(RED, 0.95 * alpha), width=3)
    return img


def frame(t, *, collapse=0.0, mode="W", entity_kw=None, content_kw=None, score=0.0, level=0.0,
          chars=None, typed=0, struck=None, cursor=False, state="READY", playing=False,
          log=None, paper_kw=None, old=None, cue=None, big=None, undo=None, times=None,
          boot=None, overload=0.0, glow=0.34):
    z = zones(collapse, mode)
    img = Image.new("RGB", (W, H), BG)

    def _workbench(dst):
        dst.paste(header(t, state=state, playing=playing), (0, 0))
        if mode == "P":
            pkw = dict(paper_kw or {})
            if old:
                pkw["old"] = old
            dst.paste(paper(t, z["paper"], chars=chars or [], typed=typed, struck=struck,
                            cursor=cursor, times=times, **pkw), z["paper"][:2])
        else:
            dst.paste(entity(t, z["entity"], collapse=collapse, boot=boot,
                             **(entity_kw or {})), z["entity"][:2])
            dst.paste(content(t, z["content"], boot=boot, **(content_kw or {})), z["content"][:2])
            dst.paste(ops(t, z["ops"], score=score, level=level, boot=boot,
                          overload=overload), z["ops"][:2])

    # `mount ui/` opens the whole workbench through one CRT aperture. The console (token
    # band) is drawn AFTER, always lit — the command that caused the mount must stay
    # readable while the mount is happening. That is the command-line grammar.
    if mode == "P":
        _reveal(img, (0, 0, W, H), _boot_u(boot, "skeleton"), _workbench)
    else:
        _reveal(img, (0, 0, W, z["tokens"][1] - 2), _boot_u(boot, "skeleton"), _workbench)
        img.paste(tokens(t, z["tokens"], chars=chars or [], typed=typed, struck=struck,
                         cursor=cursor, log=log, old=old, times=times), z["tokens"][:2])

    # standby: the machine goes dark and waits for the voice (64 s)
    idle = float((boot or {}).get("idle", 0.0))
    if idle > 0.01:
        img = Image.blend(img, Image.new("RGB", (W, H), (2, 3, 8)), 0.40 * idle)

    # the demands land BEFORE post() so the film's scanlines, bloom and vignette treat
    # them like every other pixel — the type is in the picture, not on top of it
    if big:
        _big_line(img, big[0], big[1], age=big[2] if len(big) > 2 else 9.9)
    img = tk.post(img, glow)
    if cue:
        _cue_line(img, cue, t)
    return img


def _cue_line(img, cue, t):
    """The stage direction, in red, on its own line (plan/19 §2 row 3)."""
    d = ImageDraw.Draw(img)
    blink = 0.55 + 0.45 * math.sin(t * 7.0)
    tk.text(d, (16, H - TOK_H - 26), ">> " + cue, font(tk.MONO_B, 15), RED, 0.95 * blink)


def _big_line(img, word, alpha, age=9.9):
    """B①' demands — 雷霆大字 (plan/05 §3: 942 AD — the strongest moment is typography).

    Stamped over the WORLD half, sized to fit it (an overflowing line is not big, it is a
    bug), and NOT a sticker: a dark rim keeps the glyphs readable over any ridge, and the
    call is made BEFORE post() so the scanlines, bloom and vignette treat it like every
    other pixel in the film. The phrase LANDS — a scale punch that settles in 0.22 s —
    and hangs on a beam of light that runs the width of the world, the same horizontal
    language as the horizon and the ridge.
    """
    if alpha <= 0.01 or not word:
        return
    d = ImageDraw.Draw(img)
    x0 = ENT_W + GAP + 8
    x1 = W - 8 - OPS_W - GAP            # the content zone, not under the meters
    fs = max(36, min(88, int((x1 - x0 - 24) / max(1, len(word)))))
    punch = 0.0 if age >= 0.22 else (1.0 - age / 0.22)
    fs = int(fs * (1.0 + 0.07 * punch))
    f = font(tk.CJK, fs)
    tw = d.textlength(word, font=f)
    bx = x0 + ((x1 - x0) - tw) / 2
    by = H * 0.42 - fs * 0.5
    # the dark rim first, then the glyph — so the type reads against any ridge behind it
    d.text((bx, by), word, font=f, fill=fade((2, 3, 8), alpha),
           stroke_width=3, stroke_fill=fade((2, 3, 8), alpha))
    d.text((bx, by), word, font=f, fill=fade(AMBER, 0.92 * alpha))
    # the beam: a light bar the full width of the world, falling off at both ends
    yb = by + fs * 1.16
    span = x1 - x0
    for i in range(0, span, 6):
        u = (i + 3) / max(1, span)
        fall = min(1.0, 2.4 * min(u, 1.0 - u) + 0.10)
        d.rectangle([x0 + i, yb, x0 + i + 6, yb + 2],
                    fill=fade(AMBER, 0.52 * alpha * fall))
