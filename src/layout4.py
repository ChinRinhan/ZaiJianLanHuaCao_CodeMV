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
  ENTITY  physical only: hatch, tray, disc, nameplate, VU meter, lamps, keys. No read-outs.
  CONTENT the world only: sky, ridges, stars, rain, column, pot, SIGNAL plate. No chassis.
  OPS     names of operations the machine is actually performing. One per beat.
  TOKENS  the lyric, one character per chip, with an id. This is where rewriting happens.

The HEADER, TOKENS band and OPS column never move: that is what kills the seam between
chapters. Only the split between ENTITY and CONTENT moves, and only once -- during the
121-second interlude the machine physically withdraws (512 -> 96 px) and the world takes the
frame. `zones(collapse)` is the single place that split is decided.
"""
from __future__ import annotations

import math
import zlib
from pathlib import Path

from PIL import Image, ImageDraw

import clock
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
           nameplate=True, collapse=0.0):
    rect = rect or zones(collapse)["entity"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), PANEL_BG)
    d = ImageDraw.Draw(img)
    u = max(0.0, min(1.0, collapse))
    narrow = w < 220

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

        if nameplate:
            px, py = cx + r + 18, cy - 74
            d.rectangle([px - 8, py - 10, bx1 - 8, py + 108], outline=fade(AMBER, 0.22), fill=(11, 9, 6))
            tk.text(d, (px, py - 2), "TRACK 013", font(tk.MONO, 9), AMBER, 0.44)
            tk.text(d, (px, py + 14), "再见 兰花草", font(tk.CJK, 22), (238, 206, 148), 0.95)
            d.line([(px, py + 44), (px + 150, py + 44)], fill=fade(AMBER, 0.26))
            tk.text(d, (px, py + 50), "张雨生", font(tk.CJK, 12), AMBER, 0.64)
            tk.text(d, (px, py + 68), "卡拉OK·台北·我", font(tk.CJK, 9), AMBER, 0.40)
            tk.text(d, (px, py + 82), "1994 飞碟唱片", font(tk.CJK, 9), AMBER, 0.34)
            for sx in (px - 4, bx1 - 16):
                d.ellipse([sx, py - 6, sx + 5, py - 1], fill=fade(AMBER, 0.28))
                d.ellipse([sx, py + 100, sx + 5, py + 105], fill=fade(AMBER, 0.28))

    my0, my1 = 262, 430
    d.rectangle([bx0, my0, bx1, my1], outline=fade(AMBER, 0.28))
    tk.text(d, (bx0 + 10, my0 + 2), " ANALOG LEVEL ", font(tk.MONO, 9), AMBER, 0.55)
    mx, myy = (bx0 + bx1) / 2, my1 - 20
    R, A0, A1 = 104.0, 210.0, 330.0
    for i in range(41):
        a = math.radians(A0 + (A1 - A0) * i / 40)
        ex, ey = mx + math.cos(a) * R, myy + math.sin(a) * R
        ir = R - (11 if i % 5 == 0 else 5)
        d.line([(mx + math.cos(a) * ir, myy + math.sin(a) * ir), (ex, ey)],
               fill=fade(RED if i >= 34 else AMBER, 0.58 if i % 5 == 0 else 0.24))
    d.arc([mx - R, myy - R, mx + R, myy + R], start=A0 + (A1 - A0) * 34 / 40, end=A1,
          fill=fade(RED, 0.34), width=2)
    lv = 0.55 * drive.vocals_smooth(t) + 0.25 * drive.drums(t) + 0.20 * drive.bass_smooth(t)
    lv = max(0.0, min(1.0, lv))
    na = math.radians(A0 + (A1 - A0) * lv)
    d.line([(mx, myy), (mx + math.cos(na) * (R - 14), myy + math.sin(na) * (R - 14))],
           fill=fade((255, 240, 210), 0.94), width=2)
    d.ellipse([mx - 6, myy - 6, mx + 6, myy + 6], fill=(30, 24, 14), outline=fade(AMBER, 0.5))
    d.ellipse([bx1 - 38, my0 + 6, bx1 - 26, my0 + 18], outline=fade(RED, 0.6),
              fill=fade(RED, 0.85 if lv > 0.86 else 0.10))
    tk.text(d, (bx0 + 10, my0 + 18), "VU", font(tk.MONO, 8), AMBER, 0.30)
    tk.text(d, (bx1 - 34, my0 + 22), "PEAK", font(tk.MONO, 7), RED, 0.35)

    cy = 496
    lamp = {"OFF": (70, 44, 20), "ON": AMBER, "PLAY": GREEN}[power]
    d.ellipse([24, cy, 38, cy + 14], outline=fade(lamp, 0.9), fill=fade(lamp, 0.55))
    tk.text(d, (46, cy + 1), "POWER", font(tk.MONO, 8), AMBER, 0.40)
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

    wx, wy = 128, 448
    d.rectangle([wx, wy, wx + 100, wy + 26], outline=fade(AMBER, 0.28), fill=(10, 8, 5))
    for i, ch in enumerate("013"):
        d.rectangle([wx + 8 + i * 30, wy + 3, wx + 8 + i * 30 + 24, wy + 23],
                    outline=fade(AMBER, 0.20))
        tk.text(d, (wx + 15 + i * 30, wy + 6), ch, font(tk.MONO_B, 13), AMBER, 0.76)
    tk.text(d, (wx + 108, wy + 8), "TOC", font(tk.MONO, 8), AMBER, 0.36)

    for i in range(8):
        d.line([(24, h - 34 + i * 4), (w - 24, h - 34 + i * 4)], fill=fade(AMBER, 0.05))
    return img


def content(t, rect=None, *, sky_a=1.0, ridge_a=1.0, star_a=1.0, rain_a=0.0, plate_a=1.0,
            pot_a=1.0, column_a=1.0, floor=0.70, seed=11, label="WORLD // VALLEY",
            amp_scale=1.0, x_off=0.0, pot_h=235.0, pot_count=1, pot_x=0.845, horizon=0.0):
    rect = rect or zones()["content"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    R = (0, 0, w, h)
    img = Image.new("RGB", (w, h), PANEL_BG)

    if sky_a > 0.01:
        lay = Image.new("RGB", (w, h), PANEL_BG)
        tk.sky(lay, R, 0.0, 0.0)
        img.paste(Image.blend(Image.new("RGB", (w, h), PANEL_BG), lay, sky_a), (0, 0))

    v_sig = drive.vocals_smooth(t)
    b_sig = drive.bass_smooth(t)
    o_sig = drive.other_smooth(t)

    if ridge_a > 0.01:
        lay = Image.new("RGB", (w, h), PANEL_BG)
        tk.terrain(lay, R, mood=0.0, seed=seed, t=t, cold=0.0, x_off=x_off,
                   amp_scale=amp_scale * ridge_a * (0.74 + 0.55 * b_sig), floor=floor)
        img = Image.blend(img, lay, min(1.0, ridge_a * 1.15))
    if star_a > 0.01:
        tk.stars(img, R, t, seed, 0.95 * star_a)
    if rain_a > 0.01:
        tk.rain(img, R, t, rain_a * (0.25 + 1.15 * o_sig), seed)
    if column_a > 0.01:
        img = tk.entity(img, w * 0.40, h * 0.40, t, column_a * (0.18 + 0.82 * v_sig))

    tk.grass(img, R, t, ridge_a, seed)
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

    d = ImageDraw.Draw(img)
    if plate_a > 0.01:
        pw, ph = int(w * 0.50), 132
        plate = (16, h - ph - 16, 16 + pw, h - 16)
        tk.hud_plate(img, plate, "SIGNAL / 24.15N 120.68E", BLUE_HI, 0.30 * plate_a)
        d = ImageDraw.Draw(img)
        tk.spectrum(img, (plate[0] + 10, plate[1] + 20, plate[0] + int(pw * 0.42), plate[3] - 10),
                    t, max(0.05, _level(t)), dim=plate_a, **_bands(t))
        tk.line_chart(img, (plate[0] + int(pw * 0.45), plate[1] + 20, plate[2] - 10, plate[3] - 10),
                      t, _series(), BLUE_HI, 0.75 * plate_a, mode="history")
        d = ImageDraw.Draw(img)
    tk.ticks(img, R)
    d = ImageDraw.Draw(img)
    tk.hud(d, R, t, label, BLUE_HI, 0.40, stamp="261026 0353")
    _frame(d, R, BLUE_MID, 0.22)
    return img


def ops(t, rect=None, *, names, highlight=0):
    rect = rect or zones()["ops"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), PANEL_BG)
    d = ImageDraw.Draw(img)
    _frame(d, (0, 0, w - 1, h - 1), BLUE_MID, 0.28, title="ops")
    f = font(tk.MONO, 8)
    rows = max(1, (h - 30) // 13)
    shown = names[-rows:]
    # `highlight` is the index into `names` of the operation that is happening now. The
    # column shows the tail of the list, so the live row is the one at the same offset
    # from the end — otherwise the box sits on the OLDEST row, which reads as "stuck".
    live = names.index(names[highlight]) if 0 <= highlight < len(names) else -1
    yy = 22
    for i, nm in enumerate(shown):
        gi = len(names) - len(shown) + i
        lit = gi == live
        d.text((7, yy + i * 13), nm[:9], font=f, fill=fade(BLUE_HI, 0.88 if lit else 0.28))
        if lit:
            d.rectangle([3, yy + i * 13 - 1, w - 4, yy + i * 13 + 10], outline=fade(BLUE_HI, 0.45))
    return img


def tokens(t, rect=None, *, chars, ids=None, typed=0, struck=None, cursor=False,
           label="stdout . tokens", log=None, old=None):
    """The bottom band. Two roles, one place:

    log  -> boot lines, printed one by one with decoding glyphs (the opening)
    chars-> the lyric as token chips with ids (the song)

    Keeping both in the same band is what lets the machine hand over to the song without the
    frame changing: the text simply stops being a boot log and starts being the lyric.

    `old` is the pre-rewrite line. It is shown struck through, on its own row above the
    chips, so a rewrite reads as an edit of the same line rather than a new line (plan/11 §3).
    """
    rect = rect or zones()["tokens"]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    _frame(d, (0, 0, w - 1, h - 1), AMBER, 0.30)

    if log is not None:
        tk.text(d, (12, 6), "stdout . boot", font(tk.MONO, 9), AMBER, 0.40)
        tk.text(d, (14, 24), ">", font(tk.MONO_B, 14), GREEN, 0.85)
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
    tk.text(d, (w - 110, 6), "%02d/%02d" % (typed, len(chars)), font(tk.MONO, 9), AMBER, 0.40)
    tk.text(d, (14, 30), ">", font(tk.MONO_B, 16), GREEN, 0.85)

    top = 26
    if old:
        # the dead version, struck through, above the line being written
        fo = font(tk.CJK, 13)
        d.text((36, 8), "REWRITTEN", font=tk.font(tk.MONO, 7), fill=fade(RED, 0.55))
        d.text((100, 6), old, font=fo, fill=fade((150, 150, 150), 0.50))
        ow = d.textlength(old, font=fo)
        d.line([(100, 6 + 15), (100 + ow, 6 + 15)], fill=fade(RED, 0.60), width=1)
        top = 34

    fx = 36
    fc = font(tk.CJK, 19)
    fi = font(tk.MONO, 7)
    ids = ids or [zlib.crc32(c.encode()) % 100000 for c in chars]
    for i, ch in enumerate(chars):
        cw = d.textlength(ch, font=fc) + 12
        if fx + cw > w - 20:
            break
        live = i < typed
        if live:
            d.rectangle([fx, top, fx + cw, top + 30], fill=fade(AMBER, 0.18), outline=fade(AMBER, 0.62))
            d.text((fx + 6, top + 3), ch, font=fc, fill=(255, 252, 240))
        else:
            d.rectangle([fx, top, fx + cw, top + 30], outline=fade(AMBER, 0.14))
            d.text((fx + 6, top + 3), ch, font=fc, fill=fade(AMBER, 0.16))
        if struck is not None and i == struck:
            d.line([(fx + 2, top + 15), (fx + cw - 2, top + 15)], fill=fade(RED, 0.95), width=2)
        d.text((fx + 4, top + 34), str(ids[i]), font=fi, fill=fade(AMBER, 0.30 if live else 0.12))
        fx += cw + 5
    if cursor:
        d.rectangle([fx + 2, top + 2, fx + 12, top + 28], fill=fade(BLUE_HI, 0.85))
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
          ids=None, sub=None, horizon=0.10, alpha=1.0, old=None):
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

    # the horizon: one line, at the foot of the page (plan/12 ①: the world keeps a trace)
    if horizon > 0.005:
        yh = y0 + h - 42
        d.line([(x0 + 24, yh), (x1 - 24, yh)], fill=fade(BLUE_MID, 0.55 * horizon * alpha))

    # the lyric, centred, at 34 px — big enough to read the pen moving
    fc = font(tk.CJK, 34)
    fi = font(tk.MONO, 8)
    ids = ids or [zlib.crc32(c.encode()) % 100000 for c in chars]
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

    for i, ch in enumerate(chars):
        cw = widths[i]
        live = i < typed
        if live:
            d.rectangle([fx - 3, fy - 6, fx + cw + 3, fy + 46],
                        fill=fade(AMBER, 0.13 * alpha), outline=fade(AMBER, 0.50 * alpha))
            d.text((fx, fy), ch, font=fc, fill=fade((255, 252, 240), 0.96 * alpha))
        else:
            d.text((fx, fy), ch, font=fc, fill=fade(AMBER, 0.13 * alpha))
        if struck is not None and i == struck:
            d.line([(fx - 1, fy + 20), (fx + cw + 1, fy + 20)], fill=fade(RED, 0.95 * alpha), width=3)
        d.text((fx + 1, fy + 50), str(ids[i]), font=fi,
               fill=fade(AMBER, (0.28 if live else 0.10) * alpha))
        fx += cw + 8
    if cursor:
        d.rectangle([fx + 2, fy - 2, fx + 14, fy + 44], fill=fade(BLUE_HI, 0.85 * alpha))

    # the pen: the same pen as the token band, so the writing is one continuous act
    if typed < len(chars):
        nx = fx
        d.ellipse([nx - 2.8, fy + 39.2, nx + 2.8, fy + 44.8], fill=(255, 250, 236))
        d.polygon([(nx - 2.4, fy + 46.2), (nx + 5.8, fy + 20.0), (nx + 7.8, fy + 45.0)],
                  fill=mix(BG, (214, 220, 234), 0.96))
        d.line([(nx + 3.2, fy + 45.2), (nx + 6.2, fy + 27.4)],
               fill=mix(BG, (94, 102, 118), 0.85), width=1)
    return img


def frame(t, *, collapse=0.0, mode="W", entity_kw=None, content_kw=None, ops_names=None, ops_hi=0,
          chars=None, typed=0, struck=None, cursor=False, state="READY", playing=False,
          log=None, paper_kw=None, old=None):
    z = zones(collapse, mode)
    img = Image.new("RGB", (W, H), BG)
    img.paste(header(t, state=state, playing=playing), (0, 0))
    if mode == "P":
        pkw = dict(paper_kw or {})
        if old:
            pkw["old"] = old
        img.paste(paper(t, z["paper"], chars=chars or [], typed=typed, struck=struck,
                        cursor=cursor, **pkw), z["paper"][:2])
        return tk.post(img, 0.34)
    img.paste(entity(t, z["entity"], collapse=collapse, **(entity_kw or {})), z["entity"][:2])
    img.paste(content(t, z["content"], **(content_kw or {})), z["content"][:2])
    img.paste(ops(t, z["ops"], names=ops_names or [], highlight=ops_hi), z["ops"][:2])
    img.paste(tokens(t, z["tokens"], chars=chars or [], typed=typed, struck=struck,
                     cursor=cursor, log=log, old=old), z["tokens"][:2])
    return tk.post(img, 0.34)
