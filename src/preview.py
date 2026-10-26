# -*- coding: utf-8 -*-
"""Render review stills for the Lanhuacao MV concept (1280x720, 24 fps)."""
from __future__ import annotations
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

import clock
import drive
import tk
from tk import (AMBER, BG, BLUE_HI, BLUE_MID, GREEN, RED, fade, font, mix, post)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "preview"
OUT.mkdir(parents=True, exist_ok=True)

LEFT = (8, 8, 392, 712)
RIGHT = (400, 8, 1272, 712)

_RMS_PATH = Path(__file__).resolve().parents[1] / "data" / "audio" / "rms.npy"
if _RMS_PATH.exists():
    import numpy as _np
    SERIES = _np.load(_RMS_PATH).astype(float).tolist()
else:
    SERIES = []

_BANDS_PATH = Path(__file__).resolve().parents[1] / "data" / "audio" / "bands24.npy"
if _BANDS_PATH.exists():
    import numpy as _npb
    BANDS = _npb.load(_BANDS_PATH)
else:
    BANDS = None


def _band_at(t: float):
    """Current 22 bands plus a half-second trailing max, so the plate has peak-hold like a real analyser."""
    if BANDS is None:
        return {}
    i0 = min(max(0, int(t * 24)), len(BANDS) - 1)
    return {"cur": BANDS[i0], "peak": BANDS[max(0, i0 - 12):i0 + 1].max(axis=0)}

PLAYLIST = [
    ("01", "我是多么想"), ("02", "动物的悲歌"), ("03", "灵光"),
    ("04", "永公街的街长"), ("05", "子夜抒怀"), ("06", "兄弟呀"),
    ("07", "这一年这一夜"), ("08", "我的心在发烫"), ("09", "后知后觉"),
    ("10", "蝴蝶结"), ("11", "跟得上我吧"), ("12", "我期待"),
    ("13", "再见 兰花草"),
]

# v3 动效：连续 → 量化，滚动 → 追加。翻成 False 可以逐帧对比新旧两版。
MOTION_V2 = True

_TICK_POOL = [
    "attn 0x4d1f", "tok 3f9a", "kv=0.91", "rms 0.88", "qkv 07ff", "emb 12c4",
    "loss 0.0312", "step 4481", "lr 1e-4", "grad 2.7e-3", "tmp 0.62", "seq 512",
    "w 0.4412", "b -0.031", "norm 1.07", "ctx 8192", "flop 3.1e12", "eta 00:41",
]


def _tick_line(i: int) -> str:
    """Deterministic log line: same i always yields the same text, so any frame re-renders identically."""
    a = _TICK_POOL[(i * 7) % len(_TICK_POOL)]
    b = _TICK_POOL[(i * 13 + 3) % len(_TICK_POOL)]
    c = _TICK_POOL[(i * 29 + 5) % len(_TICK_POOL)]
    return f"{i:04d}  {a}  {b}  {c}"


# One shared breathing value for the whole interface (plan/14 §1.3): every element multiplies
# by THIS, so they all brighten on the same beat and dim together. Per-element coefficients are
# exactly what made the old version read as "seven unrelated ramps".
def beat_breath(t: float) -> float:
    return 0.74 + 0.36 * clock.pulse(t)


def pane_border(d, rect, color, alpha=0.35):
    d.rectangle(rect, outline=fade(color, alpha))
    x0, y0, x1, y1 = rect
    for cx, cy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(cx, cy), (cx + dx * 14, cy)], fill=fade(color, alpha * 1.7))
        d.line([(cx, cy), (cx, cy + dy * 14)], fill=fade(color, alpha * 1.7))


def hr(d, x0, x1, y, color, alpha=0.2):
    d.line([(x0, y), (x1, y)], fill=fade(color, alpha))


def _film_frame(w: int, h: int, seed: int):
    """One grainy frame of the strip: a soft portrait-shaped blob, dithered to 1 bit."""
    import numpy as _np
    yy, xx = _np.mgrid[0:h, 0:w]
    rnd = (seed * 37) % 11
    cx, cy = w * (0.40 + 0.06 * (rnd % 3)), h * (0.40 + 0.05 * ((rnd // 3) % 3))
    head = _np.exp(-(((xx - cx) / (w * 0.17)) ** 2 + ((yy - cy) / (h * 0.20)) ** 2))
    body = _np.exp(-(((xx - cx) / (w * 0.34)) ** 2 + ((yy - h * 0.95) / (h * 0.45)) ** 2))
    n = _np.vectorize(lambda a, b: tk.fbm(a * 0.06, b * 0.06, seed, 3))(xx.astype(float), yy.astype(float))
    floor = _np.clip((yy - h * (0.78 + 0.04 * (rnd % 4))) / (h * 0.05), 0, 1)
    v = _np.clip(head * (0.55 + 0.12 * (rnd % 4)) + body * 0.45 + n * 0.55 - 0.16 + floor * 0.25, 0, 1)
    bayer = _np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
    bits = (v > bayer[yy % 4, xx % 4] * 0.85).astype(_np.uint8) * 255
    return Image.fromarray(bits, mode="L").convert("RGB")


def cover(img, box, t: float, big: bool = False):
    """Code-drawn sleeve: vertical film strips with sprocket holes + red brush type."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    d = ImageDraw.Draw(img)
    d.rectangle(box, fill=(12, 11, 10))

    strips = 4 if w > 200 else 3
    sw = w * (0.235 if strips == 4 else 0.30)
    gap = (w - sw * strips) / (strips + 1)
    hole_w, hole_h = max(2, int(sw * 0.055)), max(2, int(sw * 0.045))
    fh = h * (0.175 if strips == 4 else 0.19)
    for k in range(strips):
        sx = x0 + gap + k * (sw + gap)
        d.rectangle([sx, y0, sx + sw, y1], fill=(44, 41, 37))
        # sprocket holes
        for yy in range(int(y0 + 4), int(y1 - 4), int(hole_h * 2.4)):
            for hx in (sx + 2, sx + sw - hole_w - 2):
                d.rectangle([hx, yy, hx + hole_w, yy + hole_h], fill=(8, 8, 8))
        # frames
        n_frames = max(3, int(h / (fh + 6)))
        for i in range(n_frames):
            fy = y0 + 4 + i * (fh + 6)
            if fy + fh > y1 - 4:
                break
            fr = _film_frame(int(sw - 10), int(fh), seed=k * 17 + i)
            img.paste(fr, (int(sx + 5), int(fy)))
            if big:
                tk.text(d, (sx + sw * 0.42, fy + fh * 0.78), f"{k+1}{i}", font(tk.MONO, 6), (150, 150, 150), 0.6)
        if big:
            lab = "KODAK 5040 EPH"
            f_lab = font(tk.MONO, max(5, int(sw * 0.10)))
            for i, ch in enumerate(lab):
                d.text((sx + sw * 0.5, y0 + 8 + i * max(6, int(sw * 0.12))), ch, font=f_lab, fill=(120, 120, 120))

    # dark plates so type sits on darkness (as on the real sleeve)
    d.rectangle([x0, y0 + h * 0.38, x1, y0 + h * 0.56], fill=(10, 9, 8))
    if big:
        d.rectangle([x0 + w * 0.60, y0 + h * 0.575, x1, y0 + h * 0.73], fill=(10, 9, 8))

    # red brush title across the middle
    ts = max(11, int(w * 0.135))
    f = font(tk.CJK, ts) if not big else font(tk.CJK, ts)
    title = "卡拉OK·台北·我"
    tw = d.textlength(title, font=f)
    ty = y0 + h * 0.405
    for dx, dy, col in ((3, 4, (30, 6, 4)), (1, 1, (150, 22, 14)), (0, 0, (226, 42, 30))):
        d.text((x0 + (w - tw) / 2 + dx, ty + dy), title, font=f, fill=col)
    # small credit block
    if big:
        tk.text(d, (x0 + w * 0.66, y0 + h * 0.60), "張雨生", font(tk.CJK, max(9, int(w * 0.080))), (245, 245, 245), 0.96)
        tk.text(d, (x0 + w * 0.66, y0 + h * 0.68), "創作輯", font(tk.CJK, max(8, int(w * 0.058))), (245, 245, 245), 0.85)
        tk.text(d, (x0 + 6, y1 - 16), "1994 飛碟唱片  UFO-9405", font(tk.CJK, max(7, int(w * 0.032))), (210, 210, 210), 0.75)
    d.rectangle(box, outline=fade((210, 210, 210), 0.22))



def cd_player(img, box, t: float, *, disc_pos=None, track="013", title="再见 兰花草", artist="张雨生",
              album="卡拉OK·台北·我", year="1994 飞碟唱片", big=False, playing=True, boot=1.0,
              text_alpha=None):
    """One prop instead of two: a top-loading CD transport with the disc turning inside it."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    d = ImageDraw.Draw(img)
    a = 0.2 + 0.8 * boot
    ta = a if text_alpha is None else text_alpha

    d.rectangle(box, fill=(10, 8, 5), outline=fade(AMBER, 0.30 * a))
    # slot / tray line along the top
    d.line([(x0 + 6, y0 + 11), (x1 - 6, y0 + 11)], fill=fade(AMBER, 0.16 * a))
    tk.text(d, (x0 + 8, y0 + 1), "CD TRANSPORT", font(tk.MONO, max(6, int(h * 0.05))), AMBER, 0.45 * ta)
    tk.text(d, (x1 - 44, y0 + 1), "TOC OK", font(tk.MONO, max(6, int(h * 0.05))), GREEN, 0.55 * ta)

    # the disc, turning
    r = min(h * 0.36, w * 0.15)
    cx, cy = x0 + r + 14, y0 + h * 0.60
    sq = 1.0
    if disc_pos is not None:
        if len(disc_pos) == 4:
            cx, cy, r, sq = disc_pos
        else:
            cx, cy, r = disc_pos
    ry = max(1.0, r * sq)
    d.ellipse([cx - r, cy - ry, cx + r, cy + ry], fill=(52, 44, 30), outline=fade(AMBER, 0.55 * a))
    for k in range(1, 8):
        rr = r * k / 8
        d.ellipse([cx - rr, cy - rr * sq, cx + rr, cy + rr * sq], outline=fade(AMBER, 0.13 * a))
    # iridescent sweep, so it reads as a disc and not a coin
    for k in range(-int(r), int(r)):
        if abs(k) < r * 0.97:
            w_ = (r * r - k * k) ** 0.5
            a_ = 0.42 * (1 - abs(k) / r) ** 1.4
            col = mix((255, 236, 190), (150, 210, 255), (k + r) / (2 * r))
            d.line([(cx - w_, cy + k * sq), (cx + w_, cy + k * sq)], fill=fade(col, a_ * a))
    spin = (math.floor(t * 2.0) * 12) % 360 if MOTION_V2 else (t * 40) % 360
    d.arc([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], start=spin,
          end=spin + 70, fill=fade((255, 248, 225), 0.75 * a), width=2)
    d.ellipse([cx - r * 0.30, cy - r * 0.30, cx + r * 0.30, cy + r * 0.30],
              fill=(30, 24, 14), outline=fade(AMBER, 0.4 * a))
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=fade(AMBER, 0.6 * a))
    if playing:
        for k in range(3):
            a0 = ((math.floor(t * 2.0) * 24) + k * 120) % 360 if MOTION_V2 else (t * 70 + k * 120) % 360
            d.arc([cx - r * 0.82, cy - r * 0.82, cx + r * 0.82, cy + r * 0.82], start=a0, end=a0 + 30,
                  fill=fade(AMBER, 0.6 * a))

    # song information, made prominent
    tx = x0 + r * 2 + 26
    tk.text(d, (tx, y0 + h * 0.16), f"TRACK {track}", font(tk.MONO, max(7, int(h * 0.06))), AMBER, 0.45 * ta)
    tk.text(d, (tx, y0 + h * 0.26), title, font(tk.CJK, max(14, int(h * 0.17))), AMBER, 0.98 * ta)
    tk.text(d, (tx, y0 + h * 0.50), artist, font(tk.CJK, max(9, int(h * 0.09))), AMBER, 0.72 * ta)
    tk.text(d, (tx, y0 + h * 0.65), album, font(tk.CJK, max(8, int(h * 0.08))), AMBER, 0.52 * ta)
    tk.text(d, (tx, y0 + h * 0.80), year, font(tk.CJK, max(7, int(h * 0.055))), AMBER, 0.42 * ta)


def karaoke(img, d, t, *, boot=1.0, lyric=("", ""), cue=None, score=0.0, level=0.4,
            progress=None, playing=True, rewrite=None, collapsed=False, channels=True,
            game_set=False, rewrite05=False, pen=None, pen_times=None):
    x0, y0, x1, y1 = LEFT
    breath = beat_breath(t)
    d.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], fill=(8, 6, 4))
    pane_border(d, LEFT, AMBER, (0.30 + 0.25 * boot) * breath)
    a = 0.22 + 0.78 * boot
    fm = font(tk.MONO, 12)

    tk.text(d, (x0 + 10, y0 + 10), "LASER KARAOKE", fm, AMBER, 0.85 * a * breath)
    tk.text(d, (x1 - 62, y0 + 10), "LD-1994", fm, AMBER, 0.55 * a * breath)
    hr(d, x0 + 10, x1 - 10, y0 + 28, AMBER, 0.22 * a)

    # one prop: the CD transport carries both the disc and the song information
    cd_player(img, (x0 + 8, y0 + 34, x1 - 8, y0 + 172), t, boot=boot, playing=playing)
    hr(d, x0 + 10, x1 - 10, y0 + 180, AMBER, 0.22 * a)

    # lyric LCD
    d.rectangle([x0 + 8, y0 + 186, x1 - 8, y0 + 268], fill=(11, 9, 5),
                outline=fade(AMBER, 0.18 * a * breath))
    if rewrite05 and not lyric[0]:
        # The lyric band is free, so the fifth rewrite gets the whole block: header, prompt,
        # rule, and a cursor blinking on an empty line. Nothing ever gets typed.
        tk.text(d, (x0 + 14, y0 + 190), "REWRITE 05", font(tk.MONO, 10), RED, 0.85)
        tk.text(d, (x0 + 16, y0 + 220), ">", font(tk.MONO, 14), AMBER, 0.45)
        d.line([(x0 + 16, y0 + 250), (x1 - 24, y0 + 250)], fill=fade(AMBER, 0.2))
        if (t * 1.7) % 1.0 < 0.55:
            d.rectangle([x0 + 34, y0 + 216, x0 + 48, y0 + 244], fill=fade(BLUE_HI, 0.88))
    elif rewrite05:
        # Someone is still singing, so the band keeps doing its only job — showing the line —
        # and the rewrite gets its own small slot underneath. plan/03 §2.4: "LYRIC 区永远
        # 显示当前唱句，不承担改写；改写单独给一块". Suppressing the vocal line for 3.5 s
        # to show an empty rewrite was the bug this fixes.
        tk.text(d, (x0 + 14, y0 + 190), "LYRIC", font(tk.MONO, 10), AMBER, 0.4 * a)
    else:
        tk.text(d, (x0 + 14, y0 + 190), "LYRIC", font(tk.MONO, 10), AMBER, 0.4 * a)
    if rewrite:
        old, new, idx, label = rewrite
        tk.text(d, (x1 - 96, y0 + 190), label, font(tk.MONO, 9), RED, 0.75)
        if idx >= 0:
            # single glyph replaced: everything stays, one character changes
            tk.text(d, (x0 + 16, y0 + 216), new, font(tk.KAI, 25), (232, 226, 206), 0.96)
            cx = x0 + 16 + idx * 21
            d.rectangle([cx - 2, y0 + 214, cx + 23, y0 + 248], outline=fade(RED, 0.95))
            tk.text(d, (cx + 1, y0 + 192), old[idx], font(tk.KAI, 17), (150, 150, 150), 0.55)
            d.line([(cx, y0 + 206), (cx + 21, y0 + 206)], fill=fade(RED, 0.6))
            tk.text(d, (x0 + 16, y0 + 250), f"{old[idx]} → {new[idx]}", font(tk.CJK, 10), RED, 0.45)
        else:
            # whole line rewritten: the old version is struck above, the new one typed below
            tk.text(d, (x0 + 16, y0 + 194), old, font(tk.KAI, 13), (150, 150, 150), 0.5)
            d.line([(x0 + 16, y0 + 206), (x0 + 16 + len(old) * 12, y0 + 206)], fill=fade(RED, 0.5))
            tk.text(d, (x0 + 16, y0 + 218), new, font(tk.KAI, 21), (232, 226, 206), 0.96)
            d.rectangle([x0 + 16, y0 + 244, x0 + 16 + len(new) * 19, y0 + 246], outline=fade(RED, 0.5))
    # `rewrite05` used to swallow the band unconditionally — but when someone is still
    # singing (up to 386.8 s), suppressing the line to show an empty rewrite is a fact
    # error. The band keeps its one job; the rewrite is drawn in its own slot below.
    if (rewrite or rewrite05) and not lyric[0]:
        pass
    elif boot > 0.4 and lyric[0]:
        if pen is not None or pen_times:
            # with per-character times the function needs the clock; without them it falls back to 0..1 progress
            tk.pen_typed(img, (x0 + 18, y0 + 198), lyric[0], font(tk.CJK, 20), BLUE_HI,
                         t if pen_times else (pen or 0.0), times=pen_times,
                         alpha=0.95 * a, underline=AMBER)
        else:
            tk.text(d, (x0 + 16, y0 + 190), lyric[0], font(tk.CJK, 21), BLUE_HI, 0.95 * a)
        if lyric[1]:
            tk.text(d, (x0 + 18, y0 + 234), lyric[1], font(tk.CJK, 11), AMBER, 0.34 * a)
    elif not rewrite05:
        tk.text(d, (x0 + 16, y0 + 200), "· · ·", font(tk.CJK, 21), AMBER, 0.22 * a)

    # the fifth rewrite: full block when the band is free, a small slot while someone sings.
    # The slot lives INSIDE the LCD band (y+246..y+264), under the lyric line, so it never
    # covers >> READY (y+278) or the SCORE row (y+302).
    if rewrite05 and lyric[0]:
        bx0, by0, bx1 = x0 + 12, y0 + 244, x1 - 12
        d.rectangle([bx0, by0, bx1, by0 + 20], fill=(9, 7, 4), outline=fade(RED, 0.32))
        tk.text(d, (bx0 + 5, by0 + 3), "REWRITE 05", font(tk.MONO, 7), RED, 0.85)
        tk.text(d, (bx0 + 58, by0 + 4), ">", font(tk.MONO, 8), AMBER, 0.55)
        d.line([(bx0 + 66, by0 + 16), (bx1 - 6, by0 + 16)], fill=fade(AMBER, 0.18))
        if (t * 1.7) % 1.0 < 0.55:
            d.rectangle([bx0 + 70, by0 + 5, bx0 + 77, by0 + 17], fill=fade(BLUE_HI, 0.80))

    # cue
    if cue:
        blink = 0.55 + 0.45 * math.sin(t * 7.0)
        tk.text(d, (x0 + 14, y0 + 278), f">> {cue}", font(tk.MONO_B, 15), RED, 0.95 * blink)
    else:
        tk.text(d, (x0 + 14, y0 + 278), ">> READY", font(tk.MONO, 14), AMBER, 0.25 * a)

    # score
    tk.text(d, (x0 + 12, y0 + 310), "SCORE", font(tk.MONO, 11), AMBER, 0.5 * a)
    tk.text(d, (x0 + 66, y0 + 302), f"{min(score, 99.4):5.1f}", font(tk.MONO_B, 24), AMBER, 0.9 * a)
    d.rectangle([x0 + 12, y0 + 336, x1 - 12, y0 + 341], fill=(24, 17, 6))
    if score > 0:
        d.rectangle([x0 + 12, y0 + 336, x0 + 12 + int((x1 - 24) * min(1, score / 100)), y0 + 341],
                    fill=fade(AMBER, 0.85))

    # level meter
    tk.text(d, (x0 + 12, y0 + 354), "LEVEL", font(tk.MONO, 11), AMBER, 0.5 * a)
    n = 26
    for i in range(n):
        v = level * (0.35 + 0.65 * abs(math.sin(t * 2.7 + i * 0.55))) * (1 - 0.5 * i / n)
        h = int(2 + v * 16)
        x = x0 + 62 + i * 9
        d.rectangle([x, y0 + 368 - h, x + 5, y0 + 368], fill=fade(AMBER, 0.22 + 0.7 * v))

    # empty chorus channels: the level meter jumps, the sources are blank
    if channels:
        tk.text(d, (x0 + 300, y0 + 354), "CH 1-6", font(tk.MONO, 9), AMBER, 0.45 * a)
        tk.text(d, (x0 + 300, y0 + 366), "[ -- ]", font(tk.MONO, 9), RED, 0.55 * a)

    # playlist: all 13 tracks, in album order (collapses to one line after A2)
    hr(d, x0 + 10, x1 - 10, y0 + 380, AMBER, 0.18 * a)
    if collapsed:
        tk.text(d, (x0 + 12, y0 + 388), "13/13", font(tk.MONO, 10), AMBER, 0.5 * a)
        tk.text(d, (x0 + 52, y0 + 387), "再见 兰花草", font(tk.CJK, 11), AMBER, 0.8 * a)
        tk.text(d, (x1 - 52, y0 + 388), "NOW", font(tk.MONO_B, 9), GREEN, 0.85 * a)
    if not collapsed:
        tk.text(d, (x0 + 12, y0 + 386), "PLAYLIST", font(tk.MONO, 10), AMBER, 0.35 * a)
        tk.text(d, (x1 - 66, y0 + 386), "13 TRACKS", font(tk.MONO, 9), AMBER, 0.25 * a)
    window = [] if collapsed else PLAYLIST
    for i, (num, name) in enumerate(window):
        yy = y0 + 404 + i * 16
        cur = num == "13"
        if cur:
            d.rectangle([x0 + 8, yy - 2, x1 - 8, yy + 15], fill=(30, 21, 6))
            d.rectangle([x0 + 8, yy - 2, x0 + 11, yy + 15], fill=fade(AMBER, 0.9))
        tk.text(d, (x0 + 16, yy), num, font(tk.MONO, 10), AMBER, (0.9 if cur else 0.28) * a)
        tk.text(d, (x0 + 44, yy - 1), name, font(tk.CJK, 11), AMBER if cur else (150, 150, 150),
                (0.95 if cur else 0.33) * a)
        if cur:
            tk.text(d, (x1 - 52, yy), "NOW", font(tk.MONO_B, 9), GREEN, 0.85 * a)

    # progress
    p = progress if progress is not None else 0.0
    hr(d, x0 + 10, x1 - 10, y0 + 630, AMBER, 0.18 * a)
    d.rectangle([x0 + 10, y0 + 640, x1 - 10, y0 + 644], fill=(22, 16, 6))
    d.rectangle([x0 + 10, y0 + 640, x0 + 10 + int((x1 - 20) * min(1, max(0, p))), y0 + 644],
                fill=fade(AMBER, 0.8))
    mm, ss = int(t // 60), int(t % 60)
    tk.text(d, (x0 + 10, y0 + 656), f"{mm:02d}:{ss:02d}", font(tk.MONO, 12), AMBER, 0.65 * a)
    tk.text(d, (x1 - 122, y0 + 656), f"/ 06:35  {'PLAY >' if playing else 'PAUSE ||'}",
            font(tk.MONO, 12), AMBER, 0.5 * a)


def compose(t, *, boot=1.0, lyric=("", ""), cue=None, score=0.0, level=0.4,
            mood=0.0, sun=0.0, flower=0.0, entity=0.0, rain=0.0, spiral=0.0,
            seed=3, glow=0.5, label="WORLD // VALLEY", progress=None, playing=True,
            blank=False, center=None, cursor=None, big_glyph=None, ridge_lyric=None,
            ridge_row=2, rewrite=None, streak=0.0, machine_note=None, cold=0.0,
            collapsed=False, game_set=False, rewrite05=False, amp_scale=1.0, flower_x=0.72,
            flower_count=1, world_fade=1.0, pen=None, pen_times=None,
            w_terrain=1.0, w_beam=None, w_hud=1.0, big_b1=None, camera=None):
    if w_beam is None:
        w_beam = w_terrain
    img = Image.new("RGB", (tk.W, tk.H), BG)
    d = ImageDraw.Draw(img)

    if not blank:
        x0, y0, x1, y1 = RIGHT
        # ---- the four stems, read as control signals (plan/17 §7) ------------------
        # vocals -> the beam only exists while someone is singing
        # bass   -> the mountain breathes with the low end (smoothed: a peak-hold jitters)
        # other  -> rain / character noise density, never a translation
        # drums  -> a threshold flash, not a slider
        v_sig = drive.vocals_smooth(t)
        b_sig = drive.bass_smooth(t)
        o_sig = drive.other_smooth(t)
        d_hit = drive.drum_hit(t)
        breath = beat_breath(t)

        # layer 1: the mountain, composited alone so it can arrive before the machine does
        wimg = Image.new("RGB", (tk.W, tk.H), BG)
        tk.sky(wimg, RIGHT, mood, cold)
        # `camera` = (ridge offset px, ridge scale, floor). Every section gets its own framing
        # instead of the same mountain with a different filter — that was plan/03 §2.1, "the
        # right pane does not move for six minutes".
        _cam_off, _cam_scale, _cam_floor = camera if camera else (0.0, 1.0, 0.70)
        tk.terrain(wimg, RIGHT, mood=mood, seed=seed, t=t, cold=cold,
                   amp_scale=amp_scale * (0.74 + 0.55 * b_sig) * _cam_scale,
                   x_off=_cam_off, floor=_cam_floor)
        if sun > 0:
            wimg = tk.sun(wimg, x0 + (x1 - x0) * 0.70, y0 + (y1 - y0) * 0.44, 30, warm=mood)
        tk.stars(wimg, RIGHT, t, seed, 1.0 - 0.55 * mood)
        tk.rain(wimg, RIGHT, t, rain * (0.25 + 1.15 * o_sig), seed)
        img.paste(Image.blend(Image.new("RGB", (x1 - x0, y1 - y0), BG),
                              wimg.crop((x0, y0, x1, y1)), w_terrain), (x0, y0))

        # layer 2: the beam and everything that breathes with the sound
        if w_beam > 0.01:
            if spiral > 0:
                img = tk.burst(img, x0 + (x1 - x0) * 0.40, y0 + (y1 - y0) * 0.40, t,
                               spiral * w_beam, mood)
            if entity > 0.01:
                # the column's height and brightness are the vocal envelope, so it is dark
                # through the whole 124-second interlude and full while he sings
                img = tk.entity(img, x0 + (x1 - x0) * 0.40, y0 + (y1 - y0) * 0.40, t,
                                entity * w_beam * (0.18 + 0.82 * v_sig))
            img = tk.fog(img, RIGHT, y0 + (y1 - y0) * 0.575,
                         mix(BLUE_HI, (255, 200, 150), mood * 0.8),
                         (0.05 + 0.06 * v_sig) * w_beam)
            # grass belongs to the ground, not to the beam: following w_beam made it float
            # like a fence whenever the mountain was half transparent (plan/15 §3.2 #7)
            tk.grass(img, RIGHT, t, w_terrain, seed)
        d = ImageDraw.Draw(img)
        if flower > 0:
            n = max(1, flower_count)
            for k in range(n):
                fx = flower_x + (k - (n - 1) / 2) * 0.085
                hh = flower * 235 * (0.72 + 0.28 * ((k * 37) % 7) / 6)
                if n == 1:
                    # one potted plant, as the poem describes it (胡适: "种在小园中") —
                    # a pot is what makes the last line ("谁记得曾经有那一盆") mean anything
                    tk.orchid(img, x0 + (x1 - x0) * fx, y1 - 14, hh, t, alpha=1.0, blooms=2)
                else:
                    # a hillside of them: still 兰 (five narrow tepals + a lip), never the
                    # six-petal daisy the old tk.flower drew — the song is called 兰花草
                    tk.orchid(img, x0 + (x1 - x0) * fx, y1 - 14 - (k % 3) * 6,
                              hh * 0.78, t + k * 0.7, alpha=0.92, blooms=2)
        if big_glyph:
            f = font(tk.CJK, 130)
            tw = d.textlength(big_glyph, font=f)
            tk.text(d, ((x0 + x1 - tw) / 2, (y0 + y1) / 2 - 80), big_glyph, f, BLUE_HI, 0.85)

        if ridge_lyric and w_terrain > 0.25:
            tk.ridge_text(img, RIGHT, ridge_lyric, seed=seed, warm=mood, row=ridge_row,
                          alpha=0.92 * w_terrain)
            d = ImageDraw.Draw(img)
        if w_hud > 0.05:
            tk.reticle(img, x0 + (x1 - x0) * 0.40, y0 + (y1 - y0) * 0.40, 18)
            tk.ticks(img, RIGHT)
            tk.telemetry(img, RIGHT, t, seed, (1.0 - 0.4 * mood) * world_fade * w_hud)
        d = ImageDraw.Draw(img)
        pane_border(d, RIGHT, BLUE_MID, 0.28)
        tk.hud(d, RIGHT, t, label, BLUE_HI, 0.40, stamp="261026 0353")

        # layer 3: the machine finally starts measuring what it was watching
        if w_hud > 0.02:
            plate = (x0 + 16, y1 - 150, x0 + 470, y1 - 44)
            plt = breath + 0.10 * d_hit
            tk.hud_plate(img, plate, "SIGNAL / 24.15N 120.68E", BLUE_HI, 0.28 * w_hud * plt)
            d = ImageDraw.Draw(img)
            tk.spectrum(img, (plate[0] + 8, plate[1] + 18, plate[0] + 188, plate[3] - 8), t,
                        max(0.05, level), dim=w_hud, **_band_at(t))
            tk.line_chart(img, (plate[0] + 202, plate[1] + 18, plate[2] - 8, plate[3] - 8), t,
                          SERIES, BLUE_HI, 0.75 * w_hud,
                          mode=("history" if MOTION_V2 else "scroll"))
            f_lab = font(tk.MONO, 8)
            d.text((plate[0] + 8, plate[3] - 12), "SPEC", font=f_lab,
                   fill=fade(BLUE_HI, 0.35 * w_hud))
            d.text((plate[0] + 202, plate[3] - 12), "RMS / 100 Hz", font=f_lab,
                   fill=fade(BLUE_HI, 0.35 * w_hud))
            if MOTION_V2:
                f_t = font(tk.MONO, 10)
                step = 0.42
                kk = int(t / step)
                for jj in range(2):
                    idx = kk - 1 + jj
                    if idx < 0:
                        continue
                    age = (1 - jj) / 2.0
                    d.text((x0 + 10, y1 - 26 - (1 - jj) * 14), _tick_line(idx), font=f_t,
                           fill=fade(BLUE_HI, (0.24 * (1 - age) + 0.05) * w_hud))
            else:
                tick = "0x4d1f  12.84  kv=0.91  attn  tok 3f9a  0.0312  rms 0.88  qkv  emb 07ff  "
                f_t = font(tk.MONO, 10)
                tw = d.textlength(tick, font=f_t)
                off = (t * 46) % tw
                x = x0 + 8 - off
                while x < x1 - 8:
                    d.text((x, y1 - 26), tick, font=f_t, fill=fade(BLUE_HI, 0.16 * w_hud))
                    x += tw
        if streak > 0:
            lay = Image.new("RGB", img.size, (0, 0, 0))
            dl = ImageDraw.Draw(lay)
            sy = y0 + (y1 - y0) * (0.42 + 0.03 * math.sin(t * 0.35))
            for k in range(-7, 8):
                aa = (1 - abs(k) / 8) ** 2 * 0.16 * streak
                dl.line([(x0 + 24, sy + k), (x1 - 24, sy + k)], fill=mix((0, 0, 0), (255, 226, 190), aa))
            img = ImageChops.add(img, lay)
            d = ImageDraw.Draw(img)
        karaoke(img, d, t, boot=boot, lyric=lyric, cue=cue, score=score,
                level=level, progress=progress, playing=playing, rewrite=rewrite,
                collapsed=collapsed, game_set=game_set, rewrite05=rewrite05, pen=pen,
                pen_times=pen_times)
        if cursor:
            d.rectangle([cursor[0], cursor[1], cursor[0] + 8, cursor[1] + 15], fill=BLUE_HI)

    if center:
        f = font(tk.CJK, 22)
        tw = d.textlength(center, font=f)
        d.text(((tk.W - tw) / 2, tk.H / 2 - 14), center, font=f, fill=BLUE_HI)

    # B①: the four demands stamped across the whole frame (plan/05 §4). This is the only
    # place in the film where type covers both panes — the loudest 18 s of the song get the
    # whole screen, not a 384 px box. It stays clear of the left pane's chrome so the machine
    # remains readable underneath: the words are stamped OVER the world, not over the machine.
    if big_b1:
        word, alpha = big_b1
        if alpha > 0.01:
            fs = 88 if len(word) <= 10 else 70
            f_big = font(tk.CJK, fs)
            tw = d.textlength(word, font=f_big)
            bx = RIGHT[0] + ((RIGHT[2] - RIGHT[0]) - tw) / 2
            by = tk.H * 0.44 - fs * 0.5
            d.text((bx + 2, by + 3), word, font=f_big, fill=fade((0, 0, 0), alpha))
            d.text((bx, by), word, font=f_big, fill=fade(tk.AMBER, 0.93 * alpha))
            # a hairline under it, so it reads as a stamped line and not as a title card
            d.rectangle([bx, by + fs * 1.18, bx + tw, by + fs * 1.18 + 2],
                        fill=fade(tk.AMBER, 0.5 * alpha))

    return post(img, glow * 0.6)




def cover_card(t: float, title: str = "再见 兰花草", cursor: bool = False):
    """Opening card (0-3 s): the code-drawn cover, big, while the credits are read out.

    `title` is passed in already-typed, so the caller owns the 0.6 s breath after 再见.
    """
    img = Image.new("RGB", (tk.W, tk.H), BG)
    d = ImageDraw.Draw(img)
    cover(img, (110, 120, 590, 600), t, big=True)

    x = 640
    tk.text(d, (x, 150), "作词  张雨生", font(tk.CJK, 15), AMBER, 0.8)
    tk.text(d, (x, 182), "作曲  张雨生", font(tk.CJK, 15), AMBER, 0.8)
    tk.text(d, (x, 214), "编曲  The Band", font(tk.CJK, 15), AMBER, 0.8)
    tk.text(d, (x, 246), "制作人 张雨生", font(tk.CJK, 15), AMBER, 0.8)

    f_title = font(tk.CJK, 34)
    if title:
        tk.text(d, (x, 300), title, f_title, BLUE_HI, 0.95)
    if cursor:
        tw_c = d.textlength(title, font=f_title) if title else 0
        d.rectangle([x + tw_c + 12, 308, x + tw_c + 30, 340], fill=fade(BLUE_HI, 0.85))
    tk.text(d, (x, 348), "张雨生 · 卡拉OK·台北·我 · 1994", font(tk.CJK, 13), AMBER, 0.55)
    tk.text(d, (x, 372), "飞碟唱片 · 第 13 轨 · 6:35", font(tk.CJK, 11), AMBER, 0.35)

    # loading bar
    p_ = min(1.0, max(0.0, (t - 0.4) / 2.4))
    tk.text(d, (x, 430), "LOADING DISC", font(tk.MONO, 11), AMBER, 0.4)
    n = 26
    filled = int(n * p_)
    d.rectangle([x, 452, x + n * 9, 462], outline=fade(AMBER, 0.25))
    d.rectangle([x + 1, 453, x + 1 + int((n * 9 - 2) * p_), 461], fill=fade(AMBER, 0.7))
    tk.text(d, (x, 470), f"{int(p_ * 100):3d}%   LD-1994   SIDE A", font(tk.MONO, 10), AMBER, 0.4)

    d.rectangle([x, 520, x + 420, 522], fill=fade(AMBER, 0.12))
    tk.text(d, (x, 534), "LASER KARAOKE SYSTEM   /   MODEL LD-1994", font(tk.MONO, 10), AMBER, 0.3)
    return post(img, 0.35)



def ending_frame(t: float, *, cursor_on: bool = True):
    """386.5 s: GAME SET and an empty REWRITE 05 line. 387 s: cut to 3% black.

    The cursor has to sit ON the empty rewrite line — that is what makes the dot in the
    3% black read as "still waiting" instead of a dead pixel.
    """
    img = Image.new("RGB", (tk.W, tk.H), BG)
    d = ImageDraw.Draw(img)
    tk.text(d, (64, 40), "LASER KARAOKE  //  LD-1994", font(tk.MONO, 12), AMBER, 0.45)
    tk.text(d, (64, 286), "GAME SET", font(tk.MONO_B, 54), AMBER, 0.92)
    tk.text(d, (64, 372), "REWRITE 05", font(tk.MONO, 14), RED, 0.72)
    d.line([(64, 428), (300, 428)], fill=fade(AMBER, 0.22))
    if cursor_on:
        d.rectangle([64, 400, 78, 426], fill=fade(AMBER, 0.9))
    tk.text(d, (64, 596), "再见 兰花草", font(tk.CJK, 13), AMBER, 0.28)
    tk.text(d, (64, 640), "261026 0353", font(tk.MONO, 10), AMBER, 0.3)
    return post(img, 0.25)


def black_frame(t: float, cursor_on: bool = True, thanks: bool = False, thanks_alpha: float = 1.0):
    """3% black. The cursor is the only thing left — same spot as on the GAME SET card.

    391 s the machine says the 1994 phrase, 393 s it fades and only the cursor is left
    (plan/05 §7). `[ 谢谢收听 ]` is the karaoke machine's own sign-off, not a 2026 eulogy
    (plan/04 §6) — which is why it is allowed and "宝哥我们想你" is not.
    """
    img = Image.new("RGB", (tk.W, tk.H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    if cursor_on:
        d.rectangle([64, 400, 78, 426], fill=(255, 176, 0))
    if thanks and thanks_alpha > 0.01:
        f = font(tk.MONO, 15)
        txt = "[ 谢谢收听 ]"
        tw = d.textlength(txt, font=f)
        d.text(((tk.W - tw) / 2, tk.H / 2 + 60), txt, font=f,
               fill=fade(AMBER, 0.62 * thanks_alpha))
    return img.point(tk._gauze)



def _lerp_box(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def intro_scene(t: float):
    """0-6 s: a CD is pushed into the transport, the deck reads the TOC, then it flies into the corner."""
    img = Image.new("RGB", (tk.W, tk.H), BG)
    d = ImageDraw.Draw(img)

    big = (tk.W * 0.5 - 300, tk.H * 0.5 - 150, tk.W * 0.5 + 300, tk.H * 0.5 + 60)
    small = (LEFT[0] + 8, LEFT[1] + 34, LEFT[2] - 8, LEFT[1] + 172)
    u = tk.ease((t - 3.4) / 2.4)
    box = _lerp_box(big, small, u)

    disc = None
    if 0.35 <= t < 2.55:
        target_x = box[0] + (box[2] - box[0]) * 0.19
        target_y = box[1] + (box[3] - box[1]) * 0.60
        k = tk.ease((t - 0.35) / 1.55)
        sx0, sy0 = tk.W * 0.5 + 330, tk.H * 0.5 + 250
        dx = sx0 + (target_x - sx0) * k
        dy = sy0 + ((target_y - 120) - sy0) * k
        r_ = 64 - 20 * k
        drop = tk.ease((t - 1.95) / 0.5)
        sq = 1.0 - 0.94 * drop
        disc = (dx, dy + 150 * drop, r_, sq)
    if 2.45 <= t < 2.95:                      # the tray swallows it
        fl = 1 - abs((t - 2.7) / 0.25)
        d.line([(box[0] + 4, box[1] + 11), (box[2] - 4, box[1] + 11)],
               fill=fade((255, 240, 210), 0.45 * max(0.0, fl)))
    boot_info = 0.0 if t < 2.45 else tk.ease((t - 2.45) / 0.9)
    cd_player(img, box, t, disc_pos=disc, playing=t > 2.6, boot=boot_info, text_alpha=boot_info)

    lines = [("作词", "张雨生"), ("作曲", "张雨生"), ("编曲", "The Band"), ("制作人", "张雨生")]
    for i, (k, v) in enumerate(lines):
        a = tk.ease((t - (2.9 + i * 0.35)) / 0.5)
        if a <= 0:
            continue
        y = 190 + i * 34
        tk.text(d, (700, y), k, font(tk.CJK, 13), AMBER, 0.55 * a)
        tk.text(d, (760, y), v, font(tk.CJK, 15), AMBER, 0.9 * a)

    if t > 2.6:
        p_ = max(0.0, min(1.0, (t - 2.6) / 2.6))
        tk.text(d, (700, 360), "TOC READ", font(tk.MONO, 11), AMBER, 0.4)
        d.rectangle([700, 380, 940, 386], outline=fade(AMBER, 0.25))
        d.rectangle([701, 381, 701 + int(238 * p_), 385], fill=fade(AMBER, 0.7))
        tk.text(d, (700, 396), f"{int(p_ * 100):3d}%   LD-1994   SIDE A", font(tk.MONO, 10), AMBER, 0.4)

    if t < 3.0:
        a = 1 - tk.ease((t - 2.2) / 0.8)
        tk.text(d, (64, 600), "INSERT DISC", font(tk.MONO, 13), AMBER, 0.6 * a)
    return post(img, 0.35)


def main():
    shots = [
        ("00-cover-002s.png", cover_card(2.0)),
        ("01-intro-012s.png", compose(
            12.0, boot=0.12, score=0.0, level=0.05, mood=0.0, flower=0.03, seed=11,
            glow=0.30, label="WORLD // IDLE", progress=12.0 / 395.667, big_glyph="兰")),
        ("07-rewrite-070s.png", compose(
            69.4, boot=1.0, score=61.2, level=0.42, mood=0.10, flower=0.50, entity=0.55,
            seed=23, glow=0.45, progress=69.4 / 395.667, amp_scale=0.85,
            rewrite=("我从山中来 带着兰花草", "谁从山中来 带着兰花草", 0, "REWRITE 01"))),
        ("02-A1-080s.png", compose(
            80.0, boot=1.0, lyric=("其人其事渐湮灭", "我就是不能忘掉那盆兰花草"),
            score=78.4, level=0.55, mood=0.15, flower=0.55, entity=0.55, rain=0.12,
            seed=5, progress=80.0 / 395.667, ridge_lyric="其人其事渐湮灭", ridge_row=1)),
        ("08-break-solo-176s.png", compose(
            176.0, boot=0.75, score=0.0, level=0.14, mood=0.18, flower=0.55, entity=0.0,
            seed=29, glow=0.30, label="WORLD // SOLO", progress=176.0 / 395.667,
            playing=False, streak=1.0, amp_scale=0.55)),
        ("03-break-180s.png", compose(
            180.0, boot=1.0, score=0.0, level=0.10, mood=0.62, sun=1.0, flower=0.72,
            seed=9, label="WORLD // BREAK", playing=False, progress=180.0 / 395.667,
            amp_scale=0.7)),
        ("04-A3-320s.png", compose(
            320.0, boot=1.0, lyric=("也曾勤灌溉长得一园好", "虽然经过许多年"),
            cue="KEY  +2", score=99.1, level=0.95, mood=0.0, cold=1.0, flower=1.0,
            entity=0.95, rain=0.25, spiral=1.0, seed=13, glow=0.8,
            progress=320.0 / 395.667, amp_scale=1.2, flower_x=0.62,
            flower_count=5, collapsed=True)),
        ("05-A4b-386s.png", compose(
            386.0, boot=0.55, lyric=("梵音在弦外醉翁意韵妙", ""), score=0.0, level=0.16,
            mood=0.0, flower=0.34, entity=0.0, seed=17, glow=0.28,
            progress=386.0 / 395.667, collapsed=True, amp_scale=0.8, flower_x=0.5)),
        ("09-game-set-386s.png", ending_frame(386.5, cursor_on=True)),
        ("10-black-389s.png", black_frame(389.0, cursor_on=True)),
        ("06-outro-393s.png", compose(393.0, blank=True, glow=0.0, center="[ 谢谢收听 ]")),
    ]
    for name, im in shots:
        p = OUT / name
        im.save(p)
        print("wrote", p)


if __name__ == "__main__":
    main()
