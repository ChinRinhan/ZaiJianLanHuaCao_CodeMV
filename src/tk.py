# -*- coding: utf-8 -*-
"""tk: drawing primitives for the Lanhuacao MV. Pure PIL, deterministic, 1280x720.

Terrain is drawn as shapes (clean silhouettes); characters are used for grain, particles and HUD.
Consolas has no block-element glyphs, so every non-ASCII glyph goes through msyh.
"""
from __future__ import annotations

import math
import os
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
BG = (4, 7, 15)

AMBER = (255, 176, 0)
AMBER_MID = (150, 100, 8)
AMBER_DIM = (70, 48, 6)
BLUE_LO = (10, 18, 44)
BLUE_MID = (77, 107, 254)
BLUE_HI = (196, 212, 255)
RED = (255, 58, 40)
GREEN = (70, 255, 140)

MONO = "C:/Windows/Fonts/consola.ttf"
MONO_B = "C:/Windows/Fonts/consolab.ttf"
CJK = "C:/Windows/Fonts/msyh.ttc"
KAI = "C:/Windows/Fonts/simkai.ttf"

# 手感开关（plan/24 §6-①）：TUI_FEEL=0 关掉「跟拍呼吸」与「字形乱跳」，回到 2026-10-27 之前的
# 观感，用来做 A/B 对比。默认开。它不是美术参数，是"有没有接上原案那两条手感"的开关。
FEEL = os.environ.get("TUI_FEEL", "1") != "0"

CW, CH = 9, 16


@lru_cache(maxsize=None)
def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def mix(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def fade(c, t: float):
    return mix(BG, c, t)


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ---- the four easings the reference PV uses (plan/14 §4) ----------------------
# We only had smoothstep, which is exactly why every arrival felt stiff: it decelerates
# into the target and stops dead. ease_back overshoots and locks, which reads as "mechanical".
def ease_io(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def ease_out(u: float) -> float:
    return 1 - (1 - max(0.0, min(1.0, u))) ** 3


def ease_in(u: float) -> float:
    return max(0.0, min(1.0, u)) ** 3


def ease_back(u: float, s: float = 1.2) -> float:
    """Out-back: arrives, overshoots a little, then locks in (reference kit.py:257).

    Only use on moves of 0.4 s or longer — on fast elements the overshoot reads as jitter.
    """
    u = max(0.0, min(1.0, u)) - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


SCR = "!<>-_\\/[]{}=+*^?#%$&@01|~:;"


def decode(s: str, age: float, seed: int = 0, rate: float = 45.0, settle: float = 0.12) -> str:
    """Typewriter where each new character flickers through random glyphs before it locks.

    This is the reference PV's standard text birth (tuikit.decode). Deterministic: the seed is
    the frame number, so any frame can be re-rendered on its own.
    """
    import random as _random
    rng = _random.Random(seed)
    n = min(len(s), max(0, int(age * rate)))
    out = []
    for i in range(n):
        ch = s[i]
        a = age - i / rate
        if ch != " " and a < settle:
            ch = rng.choice(SCR)
        out.append(ch)
    return "".join(out)


def text(d: ImageDraw.ImageDraw, xy, s: str, f: ImageFont.FreeTypeFont, color, alpha: float = 1.0):
    d.text(xy, s, font=f, fill=fade(color, alpha))


# ---------------------------------------------------------------- noise
def _hash(x: int, y: int, seed: int) -> float:
    h = (x * 374761393 + y * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def noise2(x: float, y: float, seed: int = 0) -> float:
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b = _hash(xi, yi, seed), _hash(xi + 1, yi, seed)
    c, dd = _hash(xi, yi + 1, seed), _hash(xi + 1, yi + 1, seed)
    ab = a + (b - a) * u
    cd = c + (dd - c) * u
    return ab + (cd - ab) * v


def fbm(x: float, y: float, seed: int = 0, octaves: int = 3) -> float:
    v, amp, f = 0.0, 0.5, 1.0
    for i in range(octaves):
        v += amp * noise2(x * f, y * f, seed + i * 17)
        amp *= 0.5
        f *= 2.0
    return v / (1 - 0.5 ** octaves) * 0.5


# ---------------------------------------------------------------- grid (ASCII only)
class Grid:
    def __init__(self, cols: int, rows: int, x0: int, y0: int):
        self.cols, self.rows, self.x0, self.y0 = cols, rows, x0, y0
        self.cells: list[list[tuple[str, tuple] | None]] = [[None] * cols for _ in range(rows)]

    def put(self, c: int, r: int, ch: str, color):
        if 0 <= c < self.cols and 0 <= r < self.rows:
            self.cells[r][c] = (ch, color)

    def draw(self, img: Image.Image, fnt: ImageFont.FreeTypeFont):
        d = ImageDraw.Draw(img)
        for r in range(self.rows):
            y = self.y0 + r * CH
            for c in range(self.cols):
                cell = self.cells[r][c]
                if cell:
                    d.text((self.x0 + c * CW, y), cell[0], font=fnt, fill=cell[1])


# ---------------------------------------------------------------- post
def bloom(img: Image.Image, amount: float = 0.5, radius: int = 8) -> Image.Image:
    small = img.resize((W // 3, H // 3), Image.BILINEAR)
    bright = ImageChops.subtract(small, Image.new("RGB", small.size, (62, 62, 62)))
    glow = bright.filter(ImageFilter.GaussianBlur(radius)).resize((W, H), Image.BILINEAR)
    return ImageChops.add(img, glow.point(lambda v: min(255, int(v * amount))))


@lru_cache(maxsize=1)
def _scan_mask() -> Image.Image:
    m = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(m)
    for y in range(0, H, 3):
        d.line([(0, y), (W, y)], fill=234)
    return m


@lru_cache(maxsize=1)
def _vignette() -> Image.Image:
    m = Image.new("L", (64, 36), 0)
    px = m.load()
    for y in range(36):
        for x in range(64):
            dx = (x / 63 - 0.5) * 1.75
            dy = (y / 35 - 0.5) * 1.75
            px[x, y] = int(255 * max(0.0, 1.0 - 0.20 * (dx * dx + dy * dy)))
    return m.resize((W, H), Image.BICUBIC)


FLOOR, CEIL = 6, 246          # 2.4% .. 96.5%: the gauze, lifted so details stay readable.


def _gauze(v: int) -> int:
    """Linear gauze + a gentle midtone lift, so dark detail survives the codec."""
    x = v / 255.0
    y = (x ** 0.86) * 0.965 + 0.015
    return max(FLOOR, min(CEIL, int(round(y * 255))))


def post(img: Image.Image, glow: float = 0.5) -> Image.Image:
    if glow > 0:
        img = bloom(img, glow)
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), _scan_mask())
    img = ImageChops.multiply(img, Image.merge("RGB", (_vignette(),) * 3))
    return img.point(_gauze)


# ---------------------------------------------------------------- world: shapes
def sky(img: Image.Image, rect, warm: float = 0.0, cold: float = 0.0):
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    top = mix((2, 3, 9), (9, 7, 15), warm * 0.5)
    mid = mix((22, 30, 66), (72, 42, 40), warm * 0.65)
    bot = mix((8, 10, 22), (30, 18, 16), warm * 0.5)
    if cold > 0:
        top = mix(top, (10, 16, 30), cold)
        mid = mix(mid, (150, 210, 240), cold * 0.55)
        bot = mix(bot, (26, 40, 62), cold * 0.7)
    hh = y0 + (y1 - y0) * 0.58
    for y in range(y0, y1):
        if y < hh:
            u = (y - y0) / max(1, hh - y0)
            d.line([(x0, y), (x1, y)], fill=mix(top, mid, u ** 1.6))
        else:
            u = (y - hh) / max(1, y1 - hh)
            d.line([(x0, y), (x1, y)], fill=mix(mid, bot, u ** 2.2))


def _ridge_px(x0, x1, base: float, amp: float, scale: float, seed: int) -> list[tuple[int, int]]:
    pts = []
    for x in range(x0, x1 + 1, 2):
        v = fbm((x - x0) * scale, 0.0, seed, 3)
        y = int(base + amp * (v - 0.5) * 2)
        pts.append((x, y))
    return pts


def _poly_mask(size, pts):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def _vgrad(size, top, bot, y0, y1):
    g = Image.new("RGB", size, bot)
    d = ImageDraw.Draw(g)
    for y in range(max(0, y0), min(size[1], y1)):
        u = (y - y0) / max(1, y1 - y0)
        d.line([(0, y), (size[0], y)], fill=mix(top, bot, u))
    return g


def terrain(img, rect, *, mood=0.0, seed=3, t=0.0, cold=0.0, amp_scale=1.0,
            x_off=0.0, floor=0.70):
    """Three ridge layers, each a masked vertical gradient so the mass reads as a silhouette.

    `x_off` slides the ridge pattern horizontally and `floor` moves the lowest ridge line up or
    down, so a section can be framed differently without redrawing it: same world, different
    camera. (plan/03 §2.1: the complaint was that the right pane looked identical at 80 s and
    386 s. Changing only the seed gives "the same filter", not "a different shot".)
    """
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    h = y1 - y0
    size = img.size
    warm = mood
    rim = mix((150, 178, 235), (255, 190, 130), warm * 0.8)
    if cold > 0:
        rim = mix(rim, (210, 244, 255), cold)
    # the three ridge baselines shift together with `floor`
    f_shift = (floor - 0.70) * h
    layers = [
        (y0 + h * 0.34 + f_shift, h * 0.150, 0.0034, mix((26, 34, 74), (96, 60, 50), warm * 0.55), mix((18, 24, 52), (58, 34, 34), warm * 0.4), 0, 0.45),
        (y0 + h * 0.52 + f_shift, h * 0.185, 0.0050, mix((14, 19, 46), (60, 38, 38), warm * 0.45), mix((11, 15, 34), (34, 22, 24), warm * 0.35), 37, 0.75),
        (y0 + h * 0.70 + f_shift, h * 0.210, 0.0072, mix((7, 10, 22), (28, 19, 20), warm * 0.35), mix((6, 8, 16), (16, 11, 13), warm * 0.25), 71, 1.0),
    ]
    for base, amp, scale, top_col, bot_col, sd, lit in layers:
        pts = []
        for x in range(x0, x1 + 1, 2):
            v = fbm((x - x0 - x_off) * scale, t * 0.055, seed + sd, 4)
            v2 = noise2((x - x0 - x_off) * scale * 3.7, t * 0.140, seed + sd + 9)
            v = (v - 0.5) * 2 + (v2 - 0.5) * 0.55
            v = math.copysign(abs(v) ** 0.8, v)
            pts.append((x, int(base + amp * amp_scale * v)))
        poly = pts + [(x1, y1), (x0, y1)]
        mask = _poly_mask(size, poly)
        top_y = min(p[1] for p in pts)
        img.paste(_vgrad(size, top_col, bot_col, top_y, y1), (0, 0), mask)
        d.line(pts, fill=mix(rim, top_col, 0.16 + 0.16 * lit), width=1)
        for (px, py) in pts[::7]:
            if _hash(px, py, seed + sd) > 0.62:
                d.text((px, py + 3), "·", font=font(MONO, 12), fill=mix(rim, top_col, 0.62))


def fog(img, rect, y: float, color, alpha: float = 0.18):
    x0, y0, x1, y1 = rect
    lay = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i in range(90):
        yy = y - 60 + i * 1.6
        u = i / 90
        a = alpha * math.exp(-((u - 0.42) ** 2) / 0.02)
        d.line([(x0, yy), (x1, yy)], fill=mix((0, 0, 0), color, a))
    return ImageChops.add(img, lay)


def entity(img: Image.Image, cx: float, cy: float, t: float, amount: float, seed: int = 91):
    """The 'her' stand-in: vertical aurora bands with a few glyphs. Never a figure."""
    if amount <= 0:
        return img
    glow = Image.new("RGB", img.size, (0, 0, 0))
    dg = ImageDraw.Draw(glow)
    for i in range(52, 0, -1):
        a = (1 - i / 52) ** 2.6 * 0.30 * amount
        dg.ellipse([cx - i * 1.7, cy - i * 2.6, cx + i * 1.7, cy + i * 2.6],
                   fill=mix((0, 0, 0), BLUE_MID, a))
    img = ImageChops.add(img, glow)
    lay = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(lay)

    # aurora: vertical bands of light, width and brightness driven by noise + time
    bands = 11
    for b in range(bands):
        off = (b - bands / 2) * 9.0
        ph = t * 0.7 + b * 1.13
        h = 150 + 110 * (0.5 + 0.5 * math.sin(ph * 0.83))
        x = cx + off + math.sin(ph) * 7
        w = 1.4 + 1.6 * abs(math.sin(ph * 0.7))
        inten = (0.25 + 0.55 * abs(math.sin(ph * 1.1))) * amount
        for i in range(int(h)):
            u = 1 - i / h
            yy = cy + 60 - i
            a = inten * (u ** 2.0) * 0.85
            d.line([(x - w * u, yy), (x + w * u, yy)],
                   fill=mix((0, 0, 0), mix(BLUE_MID, (240, 246, 255), u * 0.7), a))

    img = ImageChops.add(img, lay)
    d = ImageDraw.Draw(img)

    # a few glyphs drifting through the column
    f = font(MONO, 13)
    for i in range(26):
        n1 = _hash(i, 71, seed)
        n2 = _hash(i, 72, seed)
        gx = cx + (n1 - 0.5) * 150
        gy = cy + (n2 - 0.5) * 210 + math.sin(t * 0.8 + i) * 6
        if abs(gx - cx) > 80 or abs(gy - cy) > 120:
            continue
        d.text((gx, gy), "·:+#"[i % 4], font=f, fill=fade(BLUE_HI, 0.25 + 0.35 * amount))
    return img


def stars(img: Image.Image, rect, t: float, seed: int, amount: float = 1.0):
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    f = font(MONO, 11)
    for i in range(int(70 * amount)):
        x = x0 + _hash(i, 2, seed) * (x1 - x0)
        y = y0 + _hash(i, 3, seed) * (y1 - y0) * 0.45
        tw = 0.45 + 0.55 * math.sin(t * 1.3 + i * 2.1)
        d.text((x, y), "·", font=f, fill=fade(BLUE_HI, 0.22 * tw))


def rain(img: Image.Image, rect, t: float, amount: float, seed: int):
    if amount <= 0:
        return
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    for i in range(int(amount * 90)):
        x = x0 + ((_hash(i, 21, seed) * (x1 - x0) + t * 130) % (x1 - x0))
        y = y0 + ((_hash(i, 22, seed) * (y1 - y0) + t * 340) % (y1 - y0))
        d.line([(x, y), (x - 3, y + 9)], fill=fade(BLUE_HI, 0.18 + 0.20 * amount))


def spiral(img: Image.Image, cx: float, cy: float, t: float, amount: float, warm: float = 1.0):
    if amount <= 0:
        return
    d = ImageDraw.Draw(img)
    f = font(MONO, 12)
    pts = []
    steps = int(300 * amount)
    for i in range(steps):
        a = i * 0.055 + t * 0.25
        r = 8 + i * 1.05
        pts.append((cx + math.cos(a) * r * 1.15, cy + math.sin(a) * r * 0.55))
    for i in range(0, len(pts) - 1):
        u = i / len(pts)
        col = mix(fade(BLUE_MID, 0.45), mix((255, 205, 150), (255, 246, 232), u), 0.25 + 0.55 * u)
        d.line([pts[i], pts[i + 1]], fill=col)
    for i in range(0, len(pts), 26):
        d.text((pts[i][0], pts[i][1]), "+", font=f, fill=mix(BG, (255, 240, 220), 0.42))


def hud(d: ImageDraw.ImageDraw, rect, t: float, label: str, color, alpha=0.42, stamp=None):
    x0, y0, x1, y1 = rect
    f = font(MONO, 11)
    text(d, (x0 + 8, y0 + 6), label, f, color, alpha)
    if stamp:
        text(d, (x1 - 96, y0 + 6), stamp, f, color, alpha * 0.75)
    else:
        text(d, (x1 - 130, y0 + 6), f"{t:07.3f}s  {int(t * 24):05d}f", f, color, alpha * 0.8)
    text(d, (x0 + 8, y1 - 16), "24.15N 120.68E", f, color, alpha * 0.55)
    text(d, (x1 - 58, y1 - 16), "TUI-1", f, color, alpha * 0.55)
    for cx, cy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(cx, cy), (cx + dx * 13, cy)], fill=fade(color, alpha * 0.45))
        d.line([(cx, cy), (cx, cy + dy * 13)], fill=fade(color, alpha * 0.45))


def grass(img: Image.Image, rect, t: float, amount: float = 1.0, seed: int = 5, color=(90, 140, 110)):
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    # alpha follows `amount` too, not just the count: half-translucent terrain must not
    # leave a bright fence of blades standing on its own (plan/12 §3.2).
    for i in range(int(90 * amount)):
        x = x0 + _hash(i, 41, seed) * (x1 - x0)
        h = 8 + _hash(i, 42, seed) * 34
        sway = math.sin(t * 1.2 + i * 0.7) * 3
        c = mix(BG, color, (0.10 + 0.16 * _hash(i, 43, seed)) * min(1.0, 0.25 + 0.75 * amount))
        d.line([(x, y1 - 2), (x + sway, y1 - 2 - h)], fill=c, width=1)


def sun(img: Image.Image, cx: float, cy: float, r: float, warm: float = 1.0):
    """Additive low sun with a wide halo."""
    lay = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(lay)
    core = mix((255, 176, 120), (255, 246, 224), warm)
    for i in range(int(r * 4), 0, -1):
        a = (1 - i / (r * 4)) ** 2.4
        d.ellipse([cx - i, cy - i * 0.86, cx + i, cy + i * 0.86], fill=mix((0, 0, 0), core, 0.55 * a))
    return ImageChops.add(img, lay)


def flower(img: Image.Image, x: float, base_y: float, height: float, t: float,
           warm: float = 0.3, alpha: float = 1.0):
    d = ImageDraw.Draw(img)
    if height < 8:
        return
    stem = mix(BG, (128, 176, 146), 0.60 * alpha)
    leaf = mix(BG, (112, 172, 122), 0.50 * alpha)
    bloom = mix(BG, (255, 240, 210), 0.95 * alpha)
    pts = []
    for i in range(int(height)):
        u = i / height
        sway = math.sin(u * 3.0 + t * 0.9) * (7 * u * u)
        pts.append((x + sway, base_y - i))
    d.line(pts, fill=stem, width=2)
    for u, side in ((0.30, -1), (0.52, 1), (0.72, -1), (0.86, 1)):
        i = int(height * u)
        px, py = pts[i]
        d.line([(px, py), (px + side * 15, py - 10)], fill=leaf, width=1)
        d.line([(px, py), (px + side * 8, py - 12)], fill=leaf, width=1)
    hx, hy = pts[-1]
    for k in range(6):
        a = k * (2 * math.pi / 6) + t * 0.12
        ex, ey = hx + math.cos(a) * 8.0, hy + math.sin(a) * 8.0
        d.ellipse([ex - 5.2, ey - 5.2, ex + 5.2, ey + 5.2], fill=bloom)
    d.ellipse([hx - 4.0, hy - 4.0, hx + 4.0, hy + 4.0], fill=(255, 252, 240))


def ridge_text(img: Image.Image, rect, text: str, *, seed: int = 3, warm: float = 0.0,
               row: int = 2, size: int = 17, alpha: float = 0.9,
               t: float = 0.0, x_off: float = 0.0, amp_scale: float = 1.0,
               floor: float = 0.70):
    """Write a line of text so that each glyph sits on the ridge line of layer `row`.

    The geometry mirrors `terrain()` exactly (same fbm clock, x_off, amp_scale, floor
    shift) so the glyphs ride the ridge that is actually drawn — not a stale copy of it.
    """
    x0, y0, x1, y1 = rect
    h = y1 - y0
    f_shift = (floor - 0.70) * h
    bases = [y0 + h * 0.34 + f_shift, y0 + h * 0.52 + f_shift, y0 + h * 0.70 + f_shift]
    amps = [h * 0.150, h * 0.185, h * 0.210]
    scales = [0.0034, 0.0050, 0.0072]
    sds = [0, 37, 71]
    base, amp, scale, sd = bases[row], amps[row], scales[row], sds[row]
    f = font(CJK, size)
    d = ImageDraw.Draw(img)
    n = len(text)
    span = min((x1 - x0) * 0.86, n * size * 1.45)
    x_start = x0 + ((x1 - x0) - span) / 2
    raw = []
    for i in range(n):
        x = x_start + span * (i + 0.5) / max(1, n)
        v = fbm((x - x0 - x_off) * scale, t * 0.055, seed + sd, 4)
        v2 = noise2((x - x0 - x_off) * scale * 3.7, t * 0.140, seed + sd + 9)
        v = (v - 0.5) * 2 + (v2 - 0.5) * 0.55
        v = math.copysign(abs(v) ** 0.8, v)
        raw.append(base + amp * amp_scale * v)
    ys = []
    for i in range(n):
        w = [raw[j] for j in range(max(0, i - 2), min(n, i + 3))]
        ys.append(sum(w) / len(w))
    for i, ch in enumerate(text):
        if ch.strip() == "":
            continue
        x = x_start + span * (i + 0.5) / max(1, n)
        y = ys[i]
        col = mix(mix((170, 196, 245), (255, 200, 145), warm * 0.8), (255, 252, 244), 0.45)
        px, py = x - size * 0.5, y - size - 6
        d.text((px + 1, py + 1), ch, font=f, fill=(2, 3, 8))
        d.text((px, py), ch, font=f, fill=fade(col, alpha))


def telemetry(img: Image.Image, rect, t: float, seed: int = 4, amount: float = 1.0, color=BLUE_HI):
    """Dim machine read-outs drifting in the sky: keeps the pane reading as a TUI, not a wallpaper."""
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    f = font(MONO, 10)
    frags = ["0x4d1f", "12.84", "kv=0.91", "attn", "tok", "3f9a", "0.0312", "sin", "grad",
             "e-4", "1024", "l2=0.88", "qkv", "emb", "07ff", "rms", "pos"]
    for i in range(int(46 * amount)):
        x = x0 + 8 + _hash(i, 51, seed) * (x1 - x0 - 60)
        y = y0 + 10 + _hash(i, 52, seed) * (y1 - y0) * 0.40
        s_ = frags[i % len(frags)]
        drift = math.sin(t * 0.25 + i) * 3
        d.text((x + drift, y), s_, font=f, fill=fade(color, 0.09 + 0.07 * _hash(i, 53, seed)))


def reticle(img: Image.Image, cx: float, cy: float, r: float = 16, color=BLUE_HI, alpha: float = 0.35):
    d = ImageDraw.Draw(img)
    c = fade(color, alpha)
    d.line([(cx - r, cy), (cx - 5, cy)], fill=c)
    d.line([(cx + 5, cy), (cx + r, cy)], fill=c)
    d.line([(cx, cy - r), (cx, cy - 5)], fill=c)
    d.line([(cx, cy + 5), (cx, cy + r)], fill=c)


def ticks(img: Image.Image, rect, color=BLUE_HI, alpha=0.18):
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    c = fade(color, alpha)
    for x in range(x0 + 20, x1 - 10, 40):
        d.line([(x, y0 + 1), (x, y0 + 5)], fill=c)
        d.line([(x, y1 - 5), (x, y1 - 1)], fill=c)


def rise_line(img: Image.Image, rect, t: float, steps, *, amount: float = 1.0,
              span=(188.0, 212.0), floor: float = 0.86, ceil: float = 0.20,
              color=None):
    """A staircase that climbs one step per note — 3:10–3:30's only device.

    `steps` is [(time, weight)] (the guitar's attacks). The line is DRAWN left to right
    across `span`, and every attack lifts it. By 3:32 it is high in the frame, then it is
    torn apart by the solo's rings: the rise is literal, so the solo does not have to
    compete with it, it has to break it.

    导演 (06:18): 3:10 要"明显"、还要凸显后面的 solo。A single climbing line is obvious at
    any size, needs no legend, and leaves the spiral/ring vocabulary untouched for 3:32.
    """
    if amount <= 0.01:
        return
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    w, h = x1 - x0, y1 - y0
    col = (255, 250, 240) if color is None else color
    t0, t1 = span
    if t <= t0:
        return
    total = max(1e-6, sum(w for _t, w in steps))     # weights, not a power of the count:
                                                      # count**0.62 hit the ceiling in the
                                                      # first second and the line ran flat
    u = min(1.0, (t - t0) / (t1 - t0))
    xe = x0 + w * u
    pts = [(x0 + 2, y0 + h * floor)]
    cnt = 0.0
    for (ts, wt) in steps:
        if ts > t:
            break
        cnt += wt
        xx = x0 + 2 + (xe - x0 - 2) * min(1.0, (ts - t0) / max(1e-3, (t - t0)))
        yy = y0 + h * (floor - (floor - ceil) * min(1.0, cnt / total))
        pts.append((xx, pts[-1][1]))
        pts.append((xx, yy))
    pts.append((xe, pts[-1][1]))
    d.line(pts, fill=fade(col, 0.90 * amount), width=2)
    # the head: where the climb has got to
    d.line([(xe, pts[-1][1] - 7), (xe, pts[-1][1] + 7)], fill=fade(col, amount), width=2)
    d.line([(x0 + 2, y0 + h * floor), (x1 - 4, y0 + h * floor)], fill=fade(col, 0.10 * amount))


def bass_steps(img: Image.Image, rect, t: float, notes, *, span=(190.0, 212.0),
               floor: float = 0.95, band: float = 0.17, lo: int = 28, hi: int = 48,
               amount: float = 1.0, color=None):
    """The bass as a step trace lying on the ground — 3:10–3:32's second device.

    吉他往上爬（`rise_line` 的阶梯），贝斯在它脚下横着走（台阶）。同一条时间轴，两个方向：
    一个纵向的爬升，一个横向的踱步。音高就是台阶的高度，所以它读起来像"走"，不像电平表。
    3:10–3:32 之前贝斯是六件乐器里唯一没有自己形状的一件。
    """
    if amount <= 0.01:
        return
    x0, y0, x1, y1 = rect
    d = ImageDraw.Draw(img)
    w, h = x1 - x0, y1 - y0
    col = (255, 196, 120) if color is None else color
    t0, t1 = span
    if t <= t0:
        return
    d.line([(x0 + 2, y0 + h * floor), (x1 - 4, y0 + h * floor)],
           fill=fade(col, 0.10 * amount))
    u = min(1.0, (t - t0) / (t1 - t0))
    xe = x0 + w * u

    def Y(midi):
        v = (midi - lo) / max(1, (hi - lo))
        return y0 + h * (floor - band * max(0.0, min(1.0, v)))

    pts = []
    prev_y = None
    for n in notes:
        tn, midi = float(n[0]), int(n[1])
        if tn < t0:
            continue
        if tn > t:
            break
        xx = x0 + 2 + (xe - x0 - 2) * min(1.0, (tn - t0) / max(1e-3, (t - t0)))
        yy = Y(midi)
        if prev_y is not None:
            pts.append((xx, prev_y))      # 横向走一步
        pts.append((xx, yy))              # 换台阶
        prev_y = yy
    if len(pts) < 2:
        return
    pts.append((xe, pts[-1][1]))
    d.line(pts, fill=fade(col, 0.78 * amount), width=2)
    d.ellipse([xe - 3, pts[-1][1] - 3, xe + 3, pts[-1][1] + 3], fill=fade(col, amount))


def shock_ring(img: Image.Image, cx: float, cy: float, phase: float, amount: float = 1.0,
               rings: int = 3, rmax: float | None = None, color=AMBER, alpha: float = 0.5):
    """Concentric rings leaving the centre — the shout's punctuation.

    `phase` is 0 on the beat and 1 just before the next one (i.e. `1 - clock.pulse(t)`), so
    a ring is BORN exactly when the drums hit: the punctuation is locked to the grid by
    construction instead of being another free-running animation. Rings are ellipses
    squashed 0.62 vertically, the same flattening the terrain uses, so they lie in the
    world rather than on top of it.
    """
    if amount <= 0.01:
        return img
    d = ImageDraw.Draw(img)
    W, H = img.size
    rmax = rmax or (min(W, H) * 0.62)
    for i in range(rings):
        u = (phase + i / rings) % 1.0
        r = 14 + rmax * u ** 0.72
        a = alpha * amount * (1.0 - u) ** 1.1
        if a <= 0.01:
            continue
        d.ellipse([cx - r, cy - r * 0.62, cx + r, cy + r * 0.62],
                  outline=fade(color, a))
    core = max(0.0, 1.0 - phase / 0.16)
    if core > 0.01:
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4],
                  fill=fade((255, 246, 224), core * amount))
    return img


def ground_ripple(img: Image.Image, rect, y: float, phase: float, amount: float = 1.0,
                  ripples: int = 3, color=None):
    """Rings lying ON the horizon, widening as they travel — the bass made visible.

    A bass note is felt in the floor before it is heard. `shock_ring` is a circle in the
    air; this is the same idea flattened onto the ground line (ry = rx * 0.10), so the two
    never read as the same effect: one is an impact, the other is a tremor.
    """
    if amount <= 0.01:
        return
    x0, _y0, x1, _y1 = rect
    d = ImageDraw.Draw(img)
    col = AMBER if color is None else color
    span = (x1 - x0) * 0.30
    for i in range(ripples):
        u = (phase + i / ripples) % 1.0
        rx = 30 + span * u ** 0.8
        a = 0.42 * amount * (1.0 - u) ** 1.5
        if a <= 0.01:
            continue
        d.ellipse([x0 + (x1 - x0) / 2 - rx, y - rx * 0.10,
                   x0 + (x1 - x0) / 2 + rx, y + rx * 0.10],
                  outline=fade(col, a), width=1)


def burst(img: Image.Image, cx: float, cy: float, t: float, amount: float, warm: float = 1.0):
    """Radial light rays: the 'key change' surge. Additive, so it never darkens the sky."""
    if amount <= 0:
        return img
    lay = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(lay)
    rays = 26
    for i in range(rays):
        a = i * (2 * math.pi / rays) + math.sin(t * 0.4 + i) * 0.06
        length = (70 + 150 * _hash(i, 61, 7)) * (0.6 + 0.4 * amount)
        wob = 0.6 + 0.4 * math.sin(t * 0.9 + i * 1.7)
        x2 = cx + math.cos(a) * length * wob
        y2 = cy + math.sin(a) * length * wob * 0.75
        c = mix((40, 60, 140), mix((255, 200, 150), (255, 246, 230), warm), 0.35 + 0.4 * wob)
        d.line([(cx, cy), (x2, y2)], fill=mix((0, 0, 0), c, 0.06 * amount * wob), width=1)
    return ImageChops.add(img, lay)


def spectrum(img: Image.Image, box, t: float, level: float, bars: int = 22,
             cur=None, peak=None, dim: float = 1.0):
    """Bar spectrum. With `cur`/`peak` it shows the actual song; without, it falls back to a
    travelling sine (kept only so older stills stay reproducible)."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    w = (x1 - x0) / bars
    hgt = y1 - y0
    for i in range(bars):
        if cur is not None:
            v = float(cur[i % len(cur)])
        else:
            v = (0.25 + 0.75 * abs(math.sin(t * 2.1 + i * 0.55))) * level
            v *= 0.5 + 0.5 * math.exp(-i / bars * 2.2)
        h = max(1, int(hgt * min(1.0, v * 1.15)))
        col = mix((60, 120, 200), (210, 235, 255), min(1.0, v * 1.1))
        xa, xb = x0 + i * w + 1, x0 + i * w + w - 2
        d.rectangle([xa, y1 - h, xb, y1], fill=mix(BG, col, dim))
        if peak is not None:
            ph = max(1, int(hgt * min(1.0, float(peak[i % len(peak)]) * 1.15)))
            d.rectangle([xa, y1 - ph - 2, xb, y1 - ph], fill=fade((255, 246, 225), 0.55 * dim))


def line_chart(img: Image.Image, box, t: float, series, color=BLUE_HI, alpha: float = 0.8,
               span: int = 180, mode: str = "scroll"):
    """Energy trace. "scroll" = a window sliding under a fixed pen; "history" = everything so far."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    n = len(series)
    if n < 2:
        return
    if mode == "history":
        # memory behind, present in front. The trace is binned to one value per pixel, so
        # 266 s of signal never turns into a fuzz band; the last two seconds stay raw and bright.
        m = max(2, min(n, int(t * 100)))
        width = max(2, int(x1 - x0))
        bins = min(width, m)
        binpts = []
        for b in range(bins):
            s = m * b // bins
            e = max(s + 1, m * (b + 1) // bins)
            seg = series[s:e]
            v = sum(seg) / len(seg)
            binpts.append((x0 + (x1 - x0) * b / max(1, bins - 1),
                           y1 - (y1 - y0) * min(1.0, float(v) / 0.32)))
        if len(binpts) > 1:
            d.line(binpts, fill=fade(color, alpha * 0.55), width=1)
        recent = max(0, m - 200)
        pts2 = [(x0 + (x1 - x0) * i / (m - 1),
                 y1 - (y1 - y0) * min(1.0, float(series[i]) / 0.32))
                for i in range(recent, m)]
        if len(pts2) > 1:
            d.line(pts2, fill=fade(color, alpha * 0.95), width=1)
        d.line([(x0, y0), (x0, y1)], fill=fade(color, 0.25))
        px, py = binpts[-1]
        d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=fade((255, 246, 225), 0.95))
        return
    i1 = int(t * 100) % n
    pts = []
    for k in range(span):
        v = series[(i1 - span + k) % n]
        pts.append((x0 + (x1 - x0) * k / (span - 1), y1 - (y1 - y0) * min(1.0, v / 0.32)))
    d.line(pts, fill=fade(color, alpha), width=1)
    d.line([(x1 - 1, y0), (x1 - 1, y1)], fill=fade(color, 0.25))
    px, py = pts[-1]
    d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=fade((255, 246, 225), 0.95))


def hud_plate(img: Image.Image, box, label: str, color=BLUE_HI, alpha: float = 0.35):
    d = ImageDraw.Draw(img)
    d.rectangle(box, fill=(4, 6, 12), outline=fade(color, alpha * 0.8))
    f = font(MONO, 9)
    text(d, (box[0] + 5, box[1] + 3), label, f, color, alpha + 0.15)


# ---------------------------------------------------------------- orchid (盆栽兰花草)
def _bez(p0, p1, p2, p3, n=30):
    out = []
    for i in range(n):
        u = i / (n - 1)
        v = 1 - u
        out.append((v**3 * p0[0] + 3 * v * v * u * p1[0] + 3 * v * u * u * p2[0] + u**3 * p3[0],
                    v**3 * p0[1] + 3 * v * v * u * p1[1] + 3 * v * u * u * p2[1] + u**3 * p3[1]))
    return out


def _blade(d, pts, w0, color):
    """A leaf is a tapered ribbon, not a line: wide at the base, needle at the tip."""
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        u = i / (n - 1)
        w = w0 * (1 - u) ** 0.65 + 0.35
        if i < n - 1:
            dx, dy = pts[i + 1][0] - x, pts[i + 1][1] - y
        else:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    d.polygon(left + right[::-1], fill=color)


def _bloom(d, x, y, r, petal, lip, tilt=0.0):
    """Five narrow tepals in a fan plus a lip — reads as 兰, not as 菊."""
    for k in range(5):
        a = math.radians(-168 + k * 34 + tilt)
        ex, ey = x + math.cos(a) * r * 1.65, y + math.sin(a) * r * 1.65
        d.line([(x, y), (ex, ey)], fill=petal, width=max(1, int(r * 0.40)))
        d.ellipse([ex - r * 0.30, ey - r * 0.30, ex + r * 0.30, ey + r * 0.30], fill=petal)
    d.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=lip)


def orchid(img: Image.Image, cx: float, base_y: float, h: float, t: float = 0.0,
           alpha: float = 1.0, blooms: int = 3):
    """A potted 国兰: pot, 7 ribbon leaves, 2 scapes, small blooms along the upper third."""
    if h < 40:
        return
    d = ImageDraw.Draw(img)
    pot_h = h * 0.19
    pot_w = h * 0.44
    top = base_y - pot_h
    leaf_c = mix(BG, (104, 176, 138), 0.58 * alpha)
    deep_c = mix(BG, (74, 138, 108), 0.45 * alpha)
    petal_c = mix(BG, (255, 246, 228), 0.96 * alpha)
    lip_c = mix(BG, (232, 198, 146), 0.92 * alpha)

    # 小尺寸减叶（plan/12 §3.3）：108–160 px 时 9 片挤成一丛草，<150 px 用 5 片
    n_leaves = 5 if h < 150 else 9
    for k in range(n_leaves):
        u = (k + 0.5) / n_leaves
        spread = (u - 0.5) * 2.0
        droop = max(0.0, abs(spread) - 0.42) / 0.58
        x0 = cx + spread * pot_w * 0.24
        y0 = top + 1
        sway = math.sin(t * 0.45 + k * 1.7) * h * 0.010
        tipx = x0 + spread * h * (0.52 + 0.30 * droop) + sway
        tipy = top - h * (0.58 + 0.34 * abs(spread)) + h * 1.15 * droop * droop
        c1 = (x0 + spread * h * 0.22, top - h * 0.40)
        c2 = (tipx - spread * h * 0.16, tipy + h * 0.26)
        _blade(d, _bez((x0, y0), c1, c2, (tipx, tipy), 34), 1.9,
               leaf_c if k % 3 else deep_c)

    for s in range(2):
        sgn = -1 if s else 1
        sx = cx + sgn * pot_w * 0.10
        tipx = sx + sgn * h * 0.10 + math.sin(t * 0.4 + s) * h * 0.01
        tipy = top - h * (0.98 + 0.04 * s)
        stem = _bez((sx, top), (sx + sgn * h * 0.05, top - h * 0.44),
                    (tipx + sgn * h * 0.07, top - h * 0.78), (tipx, tipy), 30)
        d.line(stem, fill=deep_c, width=1)
        for b in range(blooms):
            uu = 0.46 + 0.20 * b
            i = int(uu * (len(stem) - 1))
            px, py = stem[i]
            _bloom(d, px + sgn * h * 0.018, py, h * 0.021, petal_c, lip_c, tilt=sgn * 12)

    d.polygon([(cx - pot_w * 0.50, top), (cx + pot_w * 0.50, top),
               (cx + pot_w * 0.40, base_y), (cx - pot_w * 0.40, base_y)],
              fill=mix(BG, (118, 84, 60), 0.32 * alpha))
    d.line([(cx - pot_w * 0.58, top), (cx + pot_w * 0.58, top)],
           fill=mix(BG, (168, 128, 92), 0.52 * alpha), width=2)
    d.line([(cx - pot_w * 0.40, base_y - 1), (cx + pot_w * 0.40, base_y - 1)],
           fill=mix(BG, (52, 38, 30), 0.40 * alpha), width=2)


# ---------------------------------------------------------------- pen (钢笔)
def pen_typed(img: Image.Image, xy, s: str, f, color, t: float, times=None,
              alpha: float = 0.95, nib: bool = True, underline=None, settle: float = 0.08):
    """Type a line on the music clock.

    `times` is when each character was sung. A character lands on its own grid point, flickers for
    `settle` seconds (drawn dim and 1 px off), then locks. The underline only ever grows in whole
    characters, and the nib jumps with it — nothing here moves at a private constant speed.
    """
    x, y = xy
    if not s:
        return
    d = ImageDraw.Draw(img)
    if times is None:
        k = max(0.0, min(1.0, t))
        n = min(len(s), int(k * len(s)))
    else:
        n = 0
        while n < len(s) and times[n] <= t + 1e-6:
            n += 1
    for i in range(n):
        ci = x + d.textlength(s[:i], font=f)
        fresh = times is not None and (t - times[i]) < settle
        ch = s[i]
        if fresh and FEEL:
            # 字还没解析完：`settle` 秒内它在字形集里乱跳，然后锁死（原案 words.py:96-99）。
            # 种子取帧号，所以任何一帧仍可单独复现。宽度用真字算（ci），画面不会抖位。
            ch = SCR[random.Random(int(t * 24) * 131 + i).randrange(len(SCR))]
        # FEEL=0 时亮度也回到旧值（0.55），保证开关能一比一复现 2026-10-27 之前的画面
        dim = (0.82 if FEEL else 0.55) if fresh else 1.0
        d.text((ci + (1 if fresh else 0), y + (1 if fresh else 0)), ch, font=f,
               fill=fade(color, alpha * dim))
    cut = x + d.textlength(s[:n], font=f)
    ucol = underline if underline is not None else color
    uy = y + f.size * 1.06
    d.line([(x, uy), (cut, uy)], fill=fade(ucol, alpha * 0.40), width=1)
    if n:
        d.line([(max(x, cut - 26), uy), (cut, uy)], fill=fade(ucol, alpha * 0.80), width=2)
    if nib and n < len(s):
        d.ellipse([cut - 2.8, uy - 2.8, cut + 2.8, uy + 2.8], fill=(255, 250, 236))
        d.polygon([(cut - 2.4, uy + 1.6), (cut + 5.8, uy - 24.0), (cut + 7.8, uy + 0.5)],
                  fill=mix(BG, (214, 220, 234), 0.96))
        d.line([(cut + 3.2, uy - 1.4), (cut + 6.2, uy - 19.0)],
               fill=mix(BG, (94, 102, 118), 0.85), width=1)
