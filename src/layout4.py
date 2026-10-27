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
import instruments
import tk
from tk import AMBER, BG, BLUE_HI, BLUE_MID, GREEN, RED, fade, font, mix

W, H = tk.W, tk.H
PANEL_BG = (8, 7, 5)

ENT_W = 512
ENT_W_CELL = 384        # when the instrument column is up the machine gives 128 px back
CELL_W = 292            # 器乐格：画面坐标里的固定第五区，见 zones()
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


def zones(collapse: float = 0.0, mode: str = "W", cell: float = 0.0,
          cell_px: float = 0.0, status=None, dial=None):
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
    c = max(0.0, min(1.0, cell))
    if mode == "P":
        return {
            "head": (0, 0, W, HEAD_H),
            "entity": (0, 0, 0, 0),
            "content": (0, 0, 0, 0),
            "ops": (0, 0, 0, 0),
            "paper": (8, BODY_Y0, W - 8, BODY_Y1),
            "tokens": (0, 0, 0, 0),
            "cell": (0, 0, 0, 0),
        }
    # The instrument column is a ZONE, not an overlay: it takes its width out of the
    # world and gives it back when it leaves, so nothing is ever covered. 导演 (03:17):
    # 「做的太大的话，30 秒转场的时候该怎么办」— at 99.30 the layout flips V→W, and an
    # overlay measured in world percentages would jump. In frame coordinates it cannot.
    base_w = ENT_W + (ENT_W_CELL - ENT_W) * c
    ew = int(round(base_w + (ENT_W_MIN - base_w) * u))
    cw = int(round(cell_px if cell_px > 0 else CELL_W * c))
    if cw < 3:
        cw = 0
    ex0 = 8
    ex1 = ex0 + ew
    cx0 = ex1 + GAP
    cx1 = W - 8 - OPS_W - GAP - (cw + GAP if cw else 0)
    cell_rect = (W - 8 - OPS_W - GAP - cw, BODY_Y0, W - 8 - OPS_W - GAP, BODY_Y1) if cw else (0, 0, 0, 0)
    return {
        "head": (0, 0, W, HEAD_H),
        "entity": (ex0, BODY_Y0, ex1, BODY_Y1),
        "content": (cx0, BODY_Y0, cx1, BODY_Y1),
        # ops is pinned to the right edge, NOT to the content's right edge: once the
        # instrument column sits between them, `cx1 + GAP` would stretch the meters across
        # everything the column took (SCORE became a 700 px bar). Caught at 110 s.
        "ops": (W - 8 - OPS_W, BODY_Y0, W - 8, BODY_Y1),
        "paper": (0, 0, 0, 0),
        "tokens": (8, H - TOK_H - 2, W - 8, H - 8),
        "cell": cell_rect,
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


# ---- 共享心跳（plan/24 §6-①）：整块界面跟着同一拍呼吸 -------------------------------
# 原案把 pulse 乘在每一个框上（engine.py:205 `0.45+0.3*pulse`、engine.py:265、stage.py:322）；
# 我们之前只有呐喊环和涟漪跟拍，框线是常数，所以「界面」本身是死的。这里只改亮度、不改几何：
# 每拍抬一点、0.14 s 内衰减回去，四个区同时亮——那是「一台机器」，不是「四个面板」。
BREATH = 0.18           # 框线在一拍上抬多少 alpha


def _breathe(t, base, depth=BREATH):
    """Frame alpha that rises on every beat — the whole chassis shares one pulse."""
    if not tk.FEEL:
        return base
    return min(1.0, base + depth * clock.pulse(t))


def _dim_zone(dst: Image.Image, rect, k: float) -> None:
    """把一个区压向纯黑（B②：机器往后退，抽空时全灭）。只动亮度，不动几何。"""
    if k <= 0.01:
        return
    x0, y0, x1, y1 = rect
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    lay = dst.crop((x0, y0, x1, y1))
    dst.paste(Image.blend(lay, Image.new("RGB", lay.size, (0, 0, 0)), min(0.985, k)),
              (x0, y0))


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
    d.line([(0, HEAD_H - 1), (W, HEAD_H - 1)], fill=fade(AMBER, _breathe(t, 0.22)))
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

    for gr, a in ((0, _breathe(t, 0.42)), (-4, 0.20), (-8, 0.10)):
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
    d.rectangle([bx0, by0, bx1, by1], outline=fade(AMBER, _breathe(t, 0.32)))
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
            boot=None, poem=None, rise=0.0, stage=None, shock=0.0, solo=None):
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
    # 呐喊: rings leave the centre on every beat (the shout's own punctuation)
    if shock > 0.01:
        tk.shock_ring(img, w * 0.44, h * 0.46, 1.0 - clock.pulse(t), shock,
                      color=AMBER, alpha=0.72, rings=4)
    # 3:10–4:05 吉他 solo：低频在地面上推涟漪，顶点时螺旋张开。三个动效各自绑定一件乐器，
    # 所以观众不用看标签也知道是谁在动。
    if solo:
        if solo.get("rise", 0) > 0.01:
            tk.rise_line(img, R, t, solo["rise_steps"], amount=solo["rise"])
        if solo.get("bass", 0) > 0.01:
            # 3:10–3:32：贝斯在吉他阶梯脚下的地面上横着走（音高 = 台阶高度）
            tk.bass_steps(img, R, t, solo["bass_notes"], amount=solo["bass"],
                          lo=38, hi=62)
        if solo.get("ripple", 0) > 0.01:
            # on the ridge line, not in the dark below it: 0.74 fell under the silhouette
            # and nobody saw it (checked at 190/196/204)
            tk.ground_ripple(img, R, h * 0.645, 1.0 - clock.pulse(t),
                             solo["ripple"], ripples=3, color=(210, 226, 255))
        if solo.get("spiral", 0) > 0.01:
            # drawn twice with a small offset: at the peak one pass reads as a hairline
            tk.spiral(img, w * 0.44, h * 0.46, t, solo["spiral"] * 0.9)
            tk.spiral(img, w * 0.44 + 2, h * 0.46 + 1, t, solo["spiral"] * 0.55)
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

    # the interlude's ensemble (instruments.py) — the band, the roll, the keyboard. Drawn
    # inside the world so it gets the film's scanlines and bloom like everything else.
    if stage is not None:
        st = dict(stage)
        instruments.stage(img, R, t, alpha=st.pop("alpha", 1.0), **st)
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
    tk.hud(d, R, t, label, BLUE_HI, _breathe(t, 0.40, 0.12), stamp="261026 0353")
    _frame(d, R, BLUE_MID, _breathe(t, 0.22))
    # the climb, last touch: the whole world gains light as the emotion rises
    if rise > 0.01:
        img = ImageEnhance.Brightness(img).enhance(1.0 + 0.16 * rise)
    return img


def ops(t, rect=None, *, score=0.0, level=0.0, boot=None, overload=0.0, ch=None):
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
    _frame(d, (0, 0, w - 1, h - 1), AMBER, _breathe(t, 0.32), title="meters")

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
    if ch is None:
        tk.text(d, (8, h - 34), "[ -- ]", font(tk.MONO, 10), RED, 0.60)
    # B② 的点名册不在这里画：它要画在压暗之后（见 frame() 的 _chorus_row），
    # 否则它会跟着仪表一起暗下去——而归零之后它是全画面唯一还亮着的机器部件。
    return img


def _chorus_row(img: Image.Image, rect, ch) -> None:
    """B② 的点名册：CH 1–6。四个是「给我…」的账，后两个是合唱最后加进来的人。

    唱片内页写着「六人齐唱」，这六格从 0:00 空到现在，就为了这一下。
    """
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    lit = max(int(ch.get("acct", 0)), int(ch.get("choir", 0)))
    call = int(ch.get("call", -1))
    flash = float(ch.get("flash", 0.0))
    for i in range(6):
        cx = x0 + 8 + i * 11
        on = i < lit
        hot = i == call                    # 正在被点到的那个：亮一格，让"点名"看得出来
        col = AMBER if on else RED
        a = (0.95 if on else 0.30) + 0.25 * flash + (0.35 if hot else 0.0)
        d.rectangle([cx, y1 - 37, cx + 9, y1 - 25], outline=fade(col, min(1.0, a)),
                    fill=fade(col, (0.55 if hot else 0.35) * a if on else 0.05))
        tk.text(d, (cx + 2, y1 - 36), str(i + 1), font(tk.MONO, 7), col, min(1.0, a + 0.05))


SCORE_LABELS = {"boutro": "OUT", "piano": "PNO", "duet": "DUET",
                "bass": "BAS", "roar": "ROAR", "last": "LAST"}


def _score_strip(d, box, t, sections, alpha: float = 1.0):
    """间奏的总谱：一条横向时间轴，六段刻度，playhead 走。

    底部这条带在间奏里原本是空的——间奏没有歌词，109 秒只有一个表盘缩在右端。
    它不该是歌词栏的替补，是另一件事：右列的六轨回答「谁在弹」，这条带回答「走到哪了」。
    一张谱，一支笔，全曲长度一眼看完。
    """
    x0, y0, x1, y1 = box
    t0, t1 = sections[0][1], sections[-1][2]
    span = max(1e-6, t1 - t0)
    wdt = x1 - x0

    def X(tt):
        return x0 + (min(t1, max(t0, tt)) - t0) / span * wdt

    mid = (y0 + y1) * 0.5
    hh = 11
    d.line([(x0, mid), (x1, mid)], fill=fade(AMBER, 0.12 * alpha))

    # 每 4 拍一根刻度：谱要有网格，不能只有六个色块
    i = clock.beat_index(t0)
    while True:
        bt = clock.beat_t(i)
        if bt >= t1:
            break
        if i % 4 == 0:
            bx = X(bt)
            d.line([(bx, mid + hh + 2), (bx, mid + hh + 7)], fill=fade(AMBER, 0.16 * alpha))
        i += 1

    last_id = sections[-1][0]
    for sid, a, b, *_rest in sections:
        xa, xb = X(a), X(b)
        label = SCORE_LABELS.get(sid, sid.upper()[:4])
        if t >= b:                       # 已经走完的
            fill_a, edge_a, txt_a = 0.12, 0.26, 0.40
        elif t >= a:                     # 正在走的
            fill_a, edge_a, txt_a = 0.30, 0.90, 1.00
        else:                            # 还没到的
            fill_a, edge_a, txt_a = 0.02, 0.14, 0.26
        edge_col = AMBER
        if sid == last_id and a <= t < b:
            # 最后一格：结尾前 4 秒边框转红——谱先知道要结束了，画面才跟上（B② 全灭）
            heat = max(0.0, min(1.0, (t - (b - 4.0)) / 4.0))
            edge_col = mix(AMBER, RED, heat)
            edge_a = max(edge_a, 0.55 + 0.45 * heat)
        d.rectangle([xa + 1, mid - hh, xb - 1, mid + hh], fill=fade(AMBER, fill_a * alpha),
                    outline=fade(edge_col, edge_a * alpha))
        f = font(tk.MONO_B if (a <= t < b) else tk.MONO, 8)
        tw = d.textlength(label, font=f)
        if xb - xa > tw + 10:
            d.text(((xa + xb) / 2 - tw / 2, mid - 5), label, font=f,
                   fill=fade(edge_col if sid == last_id and a <= t < b else AMBER,
                             txt_a * alpha))

    # playhead：一根线加一个笔尖，和全片同一支笔
    px = X(t)
    d.line([(px, mid - hh - 5), (px, mid + hh + 5)], fill=fade((255, 246, 224), 0.90 * alpha),
           width=2)
    d.polygon([(px - 3, mid - hh - 10), (px + 3, mid - hh - 10), (px, mid - hh - 3)],
              fill=fade((255, 246, 224), 0.90 * alpha))
    d.text((x1 - 34, y0 + 2), "%d:%02d" % (int(t) // 60, int(t) % 60),
           font=font(tk.MONO, 8), fill=fade(AMBER, 0.45 * alpha))


def tokens(t, rect=None, *, chars, ids=None, typed=0, struck=None, cursor=False,
           label="LYRIC", log=None, old=None, times=None, sub=None, status=None,
           score=None, chip=None):
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
    _frame(d, (0, 0, w - 1, h - 1), AMBER, _breathe(t, 0.30))

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

    # 导演 (04:37): 倒计时先在中间以代码动效生成，再落到下面。It lives here for the rest
    # of the film: two rings (the 5:00 promise that never closes, the 2:25 that does) and
    # the number. `status` = (text, alpha, done, outer, inner).
    if status is not None:
        s_, a_, done, outer, inner = status
        # 归位之后：**和那个弹出的计时框长得一模一样**（同一个部件，只是不在动）。
        # 位置就是它最早那个表盘的老地方：底部栏右端。
        # 导演 08:5x：「可以再弹出一个计时框在右下角，就是原来的区域」
        # 底部带只有 90 px 高，上面还有 LYRIC 标签和歌词行 —— 计时框必须压进 34 px，
        # 否则上沿会顶出带子（实测 44 px 的框压住了带子外框）。
        pw, ph = 158, 30
        px1, py1 = w - 12, h - 16
        px0, py0 = px1 - pw, py1 - ph
        d.rectangle([px0, py0, px1, py1], fill=fade((6, 6, 10), 0.92 * a_),
                    outline=fade(AMBER, 0.50 * a_))
        rr = 6
        cx, cy = px0 + 6 + rr, (py0 + py1) // 2
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=fade(AMBER, 0.22 * a_))
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], -90,
              -90 + 359.9 * max(0.0, min(1.0, inner)),
              fill=fade((255, 246, 224), 0.95 * a_), width=3)
        col = RED if done else AMBER
        tk.text(d, (cx + rr + 6, py0 + 4), s_, font(tk.MONO_B, 13), col, 0.95 * a_)
        tk.text(d, (px1 - 40, py0 + 6), "NOW" if done else "CHORUS",
                font(tk.MONO, 7), col, 0.42 * a_)

    top = 26
    # 倒计时最小化之后落在左端（chip）；歌词必须给它让位，否则两个东西叠在一起
    LX = 16
    if score:
        # 总谱必须让开右端的计时框（pw=168 + 10 边距 + 12 间隙），否则 LAST 格会压在框上
        _score_strip(d, (12, 20, w - 186, 80), t, score)
    if old:
        # the dead version, struck through, above the line being written
        fo = font(tk.CJK, 13)
        d.text((14, 8), "REWRITTEN", font=tk.font(tk.MONO, 7), fill=fade(RED, 0.55))
        d.text((88, 6), old, font=fo, fill=fade((150, 150, 150), 0.50))
        ow = d.textlength(old, font=fo)
        d.line([(88, 6 + 15), (88 + ow, 6 + 15)], fill=fade(RED, 0.60), width=1)
        top = 34

    if not chars:
        # 间奏时这条带是总谱，不是等着下一句歌词的空行——光标不该出现
        if cursor and not score:
            d.rectangle([LX, top + 2, LX + 12, top + 30], fill=fade(BLUE_HI, 0.85))
        return img

    # the lyric: typed with the pen — whole glyphs, one underline, one nib (plan/10)
    fc = font(tk.CJK, 21)
    disp = "".join(chars)
    if times is not None and len(times) == len(disp):
        tk.pen_typed(img, (LX, top), disp, fc, (255, 252, 240), t, times=times,
                     alpha=0.95, underline=AMBER)
    else:
        # no measured times: fall back to the same even progress pen_typed uses
        prog = typed / max(1, len(disp))
        tk.pen_typed(img, (LX, top), disp, fc, (255, 252, 240), prog, times=None,
                     alpha=0.95, underline=AMBER)

    # the one rewritten glyph, struck where it sits (plan/16 §2.3 UNDO marks the same way)
    if struck is not None and 0 <= struck < len(disp):
        cx = LX + d.textlength(disp[:struck], font=fc)
        cw = d.textlength(disp[struck], font=fc)
        uy = top + int(fc.size * 1.06)
        d.line([(cx, uy), (cx + cw, uy)], fill=fade(RED, 0.95), width=2)

    if sub:
        tk.text(d, (LX, top + 34), sub, font(tk.CJK, 11), AMBER, 0.34)
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
          boot=None, overload=0.0, glow=0.34, demand=None, cell=0.0, inst=None,
          cell_px: float = 0.0, status=None, dial=None, dim=None, chorus=None,
          scoreline=None, chip_now=False, voices=None):
    z = zones(collapse, mode, cell, cell_px)
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
                          overload=overload, ch=chorus), z["ops"][:2])
            # B②：机器往后退（顶栏 + 实体列 + 仪表压暗），世界不动——"当着观众再说一遍"
            if dim:
                _dim_zone(dst, (0, 0, W, HEAD_H), dim.get("header", 0.0))
                _dim_zone(dst, z["entity"], dim.get("entity", 0.0))
                _dim_zone(dst, z["content"], dim.get("content", 0.0))
                _dim_zone(dst, z["ops"], dim.get("ops", 0.0))
            # 点名册画在压暗之后：归零那一刻，它是全画面唯一还亮着的机器部件
            if chorus:
                _chorus_row(dst, z["ops"], chorus)
            ch = z.get("cell") or (0, 0, 0, 0)
            if inst and ch[2] - ch[0] > 30:
                instruments.cellpanel(dst, ch, t, tracks=inst.get("tracks", []),
                                      alpha=inst.get("alpha", 1.0),
                                      sub=inst.get("sub", ""),
                                      strum=inst.get("strum", -1.0),
                                      solo=inst.get("solo"),
                                      weights=inst.get("weights"))

    # `mount ui/` opens the whole workbench through one CRT aperture. The console (token
    # band) is drawn AFTER, always lit — the command that caused the mount must stay
    # readable while the mount is happening. That is the command-line grammar.
    if mode == "P":
        _reveal(img, (0, 0, W, H), _boot_u(boot, "skeleton"), _workbench)
    else:
        _reveal(img, (0, 0, W, z["tokens"][1] - 2), _boot_u(boot, "skeleton"), _workbench)
        img.paste(tokens(t, z["tokens"], chars=chars or [], typed=typed, struck=struck,
                         cursor=cursor, log=log, old=old, times=times, status=status,
                         label=("SCORE // INTERLUDE" if scoreline else "LYRIC"),
                         score=scoreline, chip=bool(chip_now)),
                  z["tokens"][:2])

    # standby: the machine goes dark and waits for the voice (64 s)
    idle = float((boot or {}).get("idle", 0.0))
    if idle > 0.01:
        img = Image.blend(img, Image.new("RGB", (W, H), (2, 3, 8)), 0.40 * idle)

    # the demands land BEFORE post() so the film's scanlines, bloom and vignette treat
    # them like every other pixel — the type is in the picture, not on top of it
    if demand:
        _demand_slot(img, demand, z.get("cell") or None)
    if big:
        _big_line(img, big[0], big[1], age=big[2] if len(big) > 2 else 9.9,
                  box=z.get("cell") or None,
                  step=big[3] if len(big) > 3 else 1)
    if dial:
        rr = dial["rect"]
        if rr[2] >= rr[0] and rr[3] >= rr[1]:
            _dial(img, rr, stage=dial["stage"], inner=dial["inner"],
                  text=dial["text"], alpha=1.0)
    # B② 的复声叠影：画在世界（content）里，和 B① 的大字同一层，但在 post() 之前，
    # 所以扫描线/辉光/暗角把它当成画面的一部分。
    if voices:
        _b2_voices(img, z.get("content") or z.get("paper"), voices)
    img = tk.post(img, glow)
    if cue:
        _cue_line(img, cue, t)
    return img


def _cue_line(img, cue, t):
    """The stage direction, in red, on its own line (plan/19 §2 row 3)."""
    d = ImageDraw.Draw(img)
    blink = 0.55 + 0.45 * math.sin(t * 7.0)
    tk.text(d, (16, H - TOK_H - 26), ">> " + cue, font(tk.MONO_B, 15), RED, 0.95 * blink)


BIG_CAP = 60            # 大字字号上限（原 88）。留出字位框的内边距，见 _demand_slot
DEMAND_ROWS = 5         # 01–04 = 四句「给我…」；05 = 一直没被要的那一件：时间


def _demand_geom(box=None, shrink: float = 0.0):
    """The form's rectangle, and the baseline the type sits on.

    `box` is the instrument column's rect: 导演 (04:12) 「慢慢把界面转化成器乐合奏」 — the
    form is not a fourth thing that appears, it is the column grown wide. So the form takes
    the column's horizontal extent and only decides its own height.
    """
    cy = H * 0.42
    by = cy - BIG_CAP * 0.5
    if box and box[2] - box[0] > 40:
        # the form IS the sheet: it takes the whole column, not a strip in the middle of
        # it. A 124 px form floating inside a 640x576 panel left two thirds of the panel
        # dead — seen at 110 s.
        # `shrink` rolls the sheet up from the top until only the five boxes are left, so
        # the column can go back to being the band without the sheet ever popping.
        y0 = (box[1] + 10) + ((box[3] - 96) - (box[1] + 10)) * max(0.0, min(1.0, shrink))
        return (box[0] + 8, y0, box[2] - 8, box[3] - 10), by
    x0 = ENT_W + GAP + 8
    x1 = W - 8 - OPS_W - GAP
    return (x0 + 8, by - 34, x1 - 8, by + BIG_CAP * 1.16 + 36), by


def _demand_slot(img, st, box=None):
    """B① 字位：一张五格的表，四格有章，第五格空着。

    The type used to appear out of nothing at full width — no cause, no place
    (导演: 1:43 太突兀). A frame alone is not enough either: the four demands are the
    premonition of two later moments, and a premonition needs an UNFILLED SLOT.

      bottom strip 01–04   four boxes, one per 「给我…」, each stamped when its phrase
                           lands. They stay stamped.
      bottom strip 05      empty from the first frame — a dashed `--:--`. It lights at
                           117.39 「你只要给我五分钟」 with 05:00 and runs down for real.
                           Four things were asked for; the fifth was never asked for, and
                           it is the one the song needs.
      dotted rule below    one tick per stamped phrase, and every tick flares on the
                           OFF-BEAT — the smallest cell of the syncopation the record
                           ends on (measured: A① puts its weight on the beat, A④ moves it
                           to 0.25/0.58 inside the beat). The ending is already ticking
                           here, at 1:43.

    Horizontal, not a left column: at 1280 px a vertical index of five 7 px rows is
    unreadable, while five boxes in a row read as a form at a glance.

    Drawn BEFORE _big_line so the glyphs sit inside the frame, never under it.
    """
    if not st:
        return
    a = st.get("alpha", 1.0)
    if a <= 0.01:
        return
    d = ImageDraw.Draw(img)
    rect, by = _demand_geom(box, float(st.get("shrink", 0.0)))
    x0, y0, x1, y1 = rect
    u = st.get("pen", 1.0)
    n_st = int(st.get("stamped", 0))
    clock_on = bool(st.get("clock"))

    # the frame has to read over a shaking, bright ridge
    if u >= 0.98:
        d.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], outline=fade((2, 3, 8), 0.55 * a))
    _pen_frame(d, rect, u, AMBER, 0.34 * a)
    if u < 0.98:
        return

    # ---- the five boxes, along the bottom edge, inside the frame ----
    fb = font(tk.MONO, 9)
    ys = y1 - 17
    xs = x0 + 12
    for i in range(DEMAND_ROWS):
        last = (i == DEMAND_ROWS - 1)
        done = i < n_st
        cur = (i == n_st and not clock_on) or (last and clock_on)
        ca = 0.70 if cur else (0.46 if done else 0.20)
        tk.text(d, (xs, ys - 1), "%02d" % (i + 1), fb, AMBER, ca * a)
        bx = xs + 18
        if done:
            d.rectangle([bx, ys, bx + 6, ys + 6], fill=fade(AMBER, 0.85 * a))
        elif last:
            # the empty slot: a dashed outline, and the time it will hold
            for k in range(3):
                d.line([(bx, ys + 3), (bx + 2, ys + 3)], fill=fade(AMBER, 0.35 * a))
                d.line([(bx, ys + 6), (bx + 2, ys + 6)], fill=fade(AMBER, 0.35 * a))
                d.line([(bx + 4, ys + 3), (bx + 6, ys + 3)], fill=fade(AMBER, 0.35 * a))
                d.line([(bx + 4, ys + 6), (bx + 6, ys + 6)], fill=fade(AMBER, 0.35 * a))
            tk.text(d, (bx + 12, ys - 1), st.get("clock") or "--:--", fb, AMBER,
                    (0.72 if clock_on else 0.28) * a)
        else:
            d.rectangle([bx, ys, bx + 6, ys + 6], outline=fade(AMBER, 0.20 * a))
        xs += 62 if last else 54

    # ---- header chips ride ON the top edge (never over the type) ----
    # The chips sit on an opaque BG patch, and an opaque patch cannot fade — at 0.1 alpha
    # they used to leave two black bars lying on the ridge. Below half light they are
    # skipped; what is left then is the clock, which is exactly what should be left.
    if a >= 0.55:
        f = font(tk.MONO, 9)
        lab = " DEMAND %02d/04 " % min(n_st, 4) if n_st else " DEMAND --/04 "
        tw = d.textlength(lab, font=f)
        d.rectangle([x0 + 10, y0 - 6, x0 + 14 + tw, y0 + 8], fill=BG)
        tk.text(d, (x0 + 12, y0 - 5), lab, f, AMBER, 0.55 * a)
        r = " CLOCK %s " % st.get("clock") if clock_on else (
            " HOLD %.2fs " % st["hold"] if st.get("hold") else None)
        if r:
            rw = d.textlength(r, font=f)
            d.rectangle([x1 - 14 - rw, y0 - 6, x1 - 10, y0 + 8], fill=BG)
            tk.text(d, (x1 - 12 - rw, y0 - 5), r, f, AMBER, 0.40 * a)

    # ---- 两句「直到那天」接住「五分钟」----
    # 导演 (04:12): 1:53 那两句加一个连续的效果，接住「五分钟」。So each line draws one
    # unbroken stroke across the world at the 05 row's height, and the second one lands in
    # the empty slot — the frame the line arrives is the frame the clock is assigned.
    xs_from = float(st.get("x_from", rect[0] - 300))
    ys5 = y1 - 17 + 3
    for k, key in enumerate(("line1", "line2")):
        u = float(st.get(key, 0.0))
        if u <= 0.0:
            continue
        yy = ys5 - k * 7
        xe = xs_from + (rect[0] + 12 - xs_from) * min(1.0, u)
        d.line([(xs_from, yy), (xe, yy)], fill=fade(AMBER, (0.55 - 0.12 * k) * a))
        if u < 1.0:
            d.ellipse([xe - 2, yy - 2, xe + 2, yy + 2], fill=fade((255, 246, 224), 0.9 * a))

    # ---- the off-beat rule: the cell the record ends on, planted here ----
    if n_st:
        ph = float(st.get("phase", 0.0))
        off = max(0.0, 1.0 - abs(ph - 0.5) / 0.14) ** 1.5
        yt = y1 + 8
        xx = x0 + 4
        for g in range(n_st):
            for _k in range(g + 1):
                d.line([(xx, yt), (xx, yt + 6)], fill=fade(AMBER, (0.26 + 0.74 * off) * a))
                xx += 5
            xx += 8
        d.line([(xx - 4, yt + 2), (x1, yt + 2)],
               fill=fade(AMBER, (0.16 + 0.42 * off) * a))




def _b2_voices(img: Image.Image, rect, st) -> None:
    """B② 的复声：同一句话，几个声部分着唱。

    导演（10:5x）：「第一次『宣言』的时候明显只有宝哥一个声音，到 4:05 的第二次的时候，就有
    宝哥多音轨的和声或『合唱』，刚好预告最后的『齐唱』段」。

    **这是量出来的，不是画的**：导演放进仓库的原曲 17 轨分轨里有 `主唱人声` 与 `背景和声`
    两轨。探针 `src/probes/backing_vocal.py` 量到第 4 句的和声相对电平是
    **B① −9.7 dB → B② −5.0 dB**（B② 四句逐句逼近：−7.4 / −6.6 / −6.3 / −5.0），
    而 B① 全程 −8.6 ~ −9.8 dB 不动。层数与和声的亮度都来自这份数据（`src/voices.py`）。

    为什么早先的三次探针量不出来：Demucs 把原唱所有人声压进 vocals 一轨，1:43 与 4:05 的
    同时音高数是 2.57 / 2.79（噪声内），而真正六人齐唱的 A② 只有 1.49。

    画法（第一版三层同尺寸叠印在一处，字糊成一团——重影不是合唱；改成 32/24/18 + 22 px
    行距也还是压在一起；最后统一 22 px + 34 px 行距 + 只做横向错开才读得出三层）：
      **三条谱行，一行一个声部**，同一句话写三遍，每行左端一个声部标（V1 / V2 / V3），
      行下一条随唱进度的亮条。这是合唱谱的读法：**同一句话，三个声部**。
    """
    if not st:
        return
    a = float(st.get("alpha", 0.0))
    if a <= 0.01:
        return
    word = st.get("word") or ""
    layers = int(st.get("layers", 1))
    shadow = float(st.get("shadow", 0.2))     # 实测的和声相对电平换算来的亮度
    if not word:
        return
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    cx = (x0 + x1) / 2
    prog = min(1.0, max(0.0, float(st.get("age", 0.0)) / 0.9))

    # 几条谱行 = 几个人在唱。层数是**量出来的**（`voices.layers`），所以这里只能画这么多行，
    # 不能"画三行再把多余的调暗"——那等于编一个合唱出来。
    FS = 22
    LEAD = 34
    f = font(tk.CJK, FS)
    tw = d.textlength(word, font=f)
    top = y0 + (y1 - y0) * 0.18
    for v in range(layers):
        off = (0, 44, 88)[v]                     # 逐行右移：错开才看得出是几个人在唱
        bx = cx - tw / 2 + off
        yy = top + v * LEAD
        # 主唱最亮；和声那几层按实测的相对电平给亮度（shadow 越大 = 和声越近 = 越亮）
        va = a * (0.95 if v == 0 else shadow * (1.0 - 0.18 * (v - 1)))
        # 每行左端：声部标 + 一小段谱线（标要亮，否则在山脊上看不见）
        lx = cx - tw / 2 - 46
        d.text((lx, yy + 2), "V%d" % (v + 1), font=font(tk.MONO_B, 9),
               fill=fade(AMBER, 0.85 * va))
        d.line([(lx + 22, yy + FS * 0.95), (lx + 32, yy + FS * 0.95)],
               fill=fade(AMBER, 0.55 * va), width=2)
        # the voice's own progress: a bright bar under the row
        bw = tw * prog
        d.rectangle([bx, yy + FS * 1.02, bx + bw, yy + FS * 1.02 + 3],
                    fill=fade(AMBER, 0.75 * va))
        d.text((bx, yy), word, font=f, fill=fade((2, 3, 8), 0.85 * va),
               stroke_width=3, stroke_fill=fade((2, 3, 8), 0.85 * va))
        d.text((bx, yy), word, font=f, fill=fade(AMBER, 0.95 * va))



    # the label: this is a staged choir, and the audience should know it.
    # 层数是实测的（`voices.layers`），所以这里写的就是量出来的几个人，不是"最多 3"。
    fsm = font(tk.MONO, 9)
    lab = " VOICES %02d " % layers
    tw2 = d.textlength(lab, font=fsm)
    ly = top - 20
    d.rectangle([cx - tw2 / 2 - 6, ly, cx + tw2 / 2 + 6, ly + 14], fill=fade(BG, 0.85 * a))
    tk.text(d, (cx - tw2 / 2, ly + 2), lab, fsm, AMBER, 0.60 * a)
    # 六个人还没进来——名单在 4:25 的点名册上（`VOICES 06 PENDING` 也在回执的抬头）
    r = " 06 PENDING "
    tw3 = d.textlength(r, font=fsm)
    d.rectangle([cx + tw2 / 2 + 12, ly, cx + tw2 / 2 + 12 + tw3 + 6, ly + 14],
                fill=fade(BG, 0.85 * a))
    tk.text(d, (cx + tw2 / 2 + 16, ly + 2), r, fsm, RED, 0.55 * a)




def _dial(img, rect, *, stage: int, inner: float, text: str, alpha: float = 1.0,
          label: str = "TILL CHORUS"):
    """The countdown as a WINDOW, not a circle.

    导演（08:3x）：「切割出一个提示框，里面放入倒计时，随后线框收缩，左下角再展开，
    这样更有代码朋克感」。

    窗口语言比环形语言高一档：环是一个图形，窗口是**系统的一个部件**。
    弹出 → 收成一条底边 → 在左下角展开成常驻芯片——这是桌面动作，正好是这台机器的
    世界观（一台 1994 年的机器跑着后来的界面）。而且它天生解决"生硬"：有框、有标题栏、
    有打开和关闭。

    窗口里仍然是那对环，因为那是"五分钟 vs 2:25"的算术：
        outer, thin, 300 s   许诺——永远不闭合，因为歌先结束了
        inner, thick, 145 s  实际给的——正好在 4:25 闭合
    """
    if alpha <= 0.01:
        return
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w < 2 and h < 2:
        return
    if h < 4 and w >= 2:
        # 收线：只剩一条底边。这条线是唯一还在的东西——所以要亮、要有余晖，
        # 否则"窗口塌成一条线"这个动作根本看不见（实测在暗山脊上几乎消失）。
        d0 = ImageDraw.Draw(img)
        d0.line([(x0, y1), (x1, y1)], fill=fade((255, 246, 224), 1.0 * alpha), width=3)
        for k in (2, 5, 9):
            d0.line([(x0, y1 - k), (x1, y1 - k)],
                    fill=fade(AMBER, 0.42 * alpha / k), width=1)
            d0.line([(x0, y1 + k), (x1, y1 + k)],
                    fill=fade(AMBER, 0.42 * alpha / k), width=1)
        return
    d = ImageDraw.Draw(img)
    chip = h <= 46 and w >= 30
    a = alpha

    if chip:
        # ---- 归位的计时框（右下角）：一个框 + 一个环 + 一个数，就是最小化之后的样子 ----
        d.rectangle([x0, y0, x1, y1], fill=fade((6, 6, 10), 0.88 * a),
                    outline=fade(AMBER, 0.55 * a))
        # 环的半径同时受高度和宽度约束——刚弹出来时框只有几十 px，硬给 9 会溢出
        r = max(3, min(9, (h - 10) // 2, (w - 40) // 2))
        ccx, ccy = x0 + 6 + r, (y0 + y1) // 2
        if r >= 3:
            d.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], outline=fade(AMBER, 0.22 * a))
            d.arc([ccx - r, ccy - r, ccx + r, ccy + r], -90,
                  -90 + 359.9 * max(0.0, min(1.0, inner)),
                  fill=fade((255, 246, 224), 0.95 * a), width=2)
        if text and w >= 78:
            fsz = 13 if h >= 24 else 10
            tk.text(d, (ccx + r + 6, y0 + (h - fsz) // 2 - 2), text,
                    font(tk.MONO_B, fsz), RED if inner <= 0.005 else AMBER, 0.95 * a)
        if w >= 130:
            tk.text(d, (x1 - 44, y0 + 6), "CHORUS", font(tk.MONO, 7), AMBER, 0.40 * a)
        return

    # ---- 窗口本体 ----
    d.rectangle([x0, y0, x1, y1], fill=fade((5, 6, 11), 0.72 * a),
                outline=fade(AMBER, 0.70 * a), width=2)
    # 标题栏：一条横线 + 一个标签，和 TUI 的其它框同一套语法（框太小就不画）
    if h >= 56 and w >= 120:
        ty = y0 + 17
        d.line([(x0 + 2, ty), (x1 - 2, ty)], fill=fade(AMBER, 0.40 * a))
        tk.text(d, (x0 + 7, y0 + 4), " TIMER // 05:00 ", font(tk.MONO, 9), AMBER, 0.75 * a)
        tk.text(d, (x1 - 15, y0 + 4), "x", font(tk.MONO, 9), AMBER, 0.35 * a)

    # 里面的环：外环许诺（永不闭合），内环是实际给的。
    # 半径必须由框的高度决定，而且圆心要在**标题栏以下的可用区**里居中——
    # 原来 cy 取 y0+30、rr 有 10 px 下限，框一小（切框那 0.4 s 里 59×27）就整圈跑出框外。
    tbh = 19 if h >= 56 else 0            # 标题栏占掉的高度；框太小就不画标题栏
    avail = h - tbh - 6
    if avail < 8 or w < 16:
        return                            # 收线到最后几帧：框太扁，环画不下，交给外面的横线
    rr = max(3.0, min(avail, w * 0.34) / 2)
    cx = x0 + 8 + rr
    cy = y0 + tbh + avail / 2
    ring = fade(AMBER, 0.80 * a)
    hot = fade((255, 246, 224), 1.0 * a)
    n = 30
    for i in range(n):
        a0 = -90 + 360 * i / n
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], a0, a0 + 360 / n - 1.2,
              fill=ring, width=2)
    r2 = rr * 0.70
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=fade(AMBER, 0.16 * a))
    if inner > 0.002:
        d.arc([cx - r2, cy - r2, cx + r2, cy + r2], -90,
              -90 + 359.9 * min(1.0, inner), fill=hot, width=3)
    if rr >= 18:                       # 小框不画刻度：刻度一定会顶出边
        for k in range(12):
            a0 = math.radians(-90 + k * 30)
            d.line([(cx + math.cos(a0) * (rr + 3), cy + math.sin(a0) * (rr + 3)),
                    (cx + math.cos(a0) * (rr + 6), cy + math.sin(a0) * (rr + 6))],
                   fill=fade(AMBER, 0.30 * a))

    # 数：大字在环的右边（窗口里是"图表 + 读数"，不是"图表当背景"）。
    # 字号跟框高走，框一小就缩——否则数字会从框右边溢出去。
    tx0 = cx + rr + 6
    room = x1 - tx0 - 6
    if text and room >= 36:
        fs = int(max(12, min(38, avail * 0.62)))
        f = font(tk.MONO_B, fs)
        d.text((tx0, cy - fs * 0.58), text, font=f, fill=fade((2, 3, 8), a),
               stroke_width=2, stroke_fill=fade((2, 3, 8), a))
        d.text((tx0, cy - fs * 0.58), text, font=f, fill=fade((255, 246, 224), 0.98 * a))
        if room >= 90:
            tk.text(d, (tx0, cy + fs * 0.46), label, font(tk.MONO, 8), AMBER, 0.48 * a)
    if stage == 2:
        # 打折中：框的右下角闪一个小方块，提示"系统正在改这个数"
        if int(inner * 40) % 2 == 0:
            d.rectangle([x1 - 14, y1 - 13, x1 - 7, y1 - 6], fill=fade(RED, 0.85 * a))


def _big_line(img, word, alpha, age=9.9, box=None, step=1):
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
    if box and box[2] - box[0] > 40:
        tx0, tx1 = box[0] + 10, box[2] - 10
    else:
        tx0 = x0 + 8
        tx1 = x1 - 8
    fs = max(36, min(BIG_CAP, int((tx1 - tx0 - 24) / max(1, len(word)))))
    # 落定手感（plan/24 §6-①）：冲进去 → 过冲一点 → 锁死。原案 kit.py:257 的 ease_back；
    # 线性收敛只有"到位"，多了这一下"弹"才像机器把字盖上去。0.22 s 内完成。
    _u = 0.0 if age >= 0.22 else (age / 0.22)
    punch = 1.0 - (tk.ease_back(_u, s=2.2) if tk.FEEL else _u)
    # 递进：第 1 句 0.09 的冲拳，第 4 句 0.15——同一动作，越砸越重
    _amp = 0.09 + 0.020 * (max(1, min(4, step)) - 1)
    fs = int(fs * (1.0 + (_amp if tk.FEEL else 0.07) * punch))
    f = font(tk.CJK, fs)
    tw = d.textlength(word, font=f)
    bx = tx0 + ((tx1 - tx0) - tw) / 2
    by = H * 0.42 - fs * 0.5
    # the dark rim first, then the glyph — so the type reads against any ridge behind it
    d.text((bx, by), word, font=f, fill=fade((2, 3, 8), alpha),
           stroke_width=3, stroke_fill=fade((2, 3, 8), alpha))
    d.text((bx, by), word, font=f, fill=fade(AMBER, 0.92 * alpha))
    # the beam: a light bar the full width of the world, falling off at both ends.
    # 递进：第 2 句起光带变粗，第 4 句最粗——观众不看字也能数出打到第几下。
    yb = by + fs * 1.16
    span = x1 - x0
    bh = 3 + max(0, min(4, step) - 1)
    ba = 0.62 + 0.07 * (max(1, min(4, step)) - 1)
    for i in range(0, span, 6):
        u = (i + 3) / max(1, span)
        fall = min(1.0, 2.4 * min(u, 1.0 - u) + 0.10)
        d.rectangle([x0 + i, yb, x0 + i + 6, yb + bh],
                    fill=fade(AMBER, min(1.0, ba) * alpha * fall))
