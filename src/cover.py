# -*- coding: utf-8 -*-
"""封面：用**原专辑封面**做主体，套上这部片子的 TUI 语言。

导演（01:1x）：「第一个是封面……封面可以不用纯代码，用原专辑封面制作」。
所以这张图不是"纯代码"的产物——它引用了 1994 年《卡拉OK·台北·我》的原版封面
（从 `input/song.flac` 里内嵌的那张 500×500 取出来，存成 `input/album-cover.jpg`）。
封面上的文字、边框、扫描线、角标仍然按片子的语法画（等宽字 + 琥珀 + 刻度）。

    python src/cover.py            # 写 assets/cover-16x9.png + assets/cover-1x1.png
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import tk
from tk import AMBER, BG, BLUE_HI, RED, fade, font, mix

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "input" / "album-cover.jpg"
OUT = ROOT / "assets"
CJK_B = "C:/Windows/Fonts/msyhbd.ttc"      # 中文粗体（msyh 只有常规体）

TITLE = "再见 兰花草"
SUB = "张雨生 ·《卡拉OK·台北·我》· 1994 · 6:35"
KIND = "同人作品 · 纯代码 MV"
EN = "EVERY FRAME IS CODE  ·  NO FOOTAGE  ·  1280×720  ·  24 FPS"


def _glow(img: Image.Image, amount: float = 0.30) -> Image.Image:
    """辉光：和 `tk.post` 同一个意思，但它写死了 1280×720 的扫描遮罩，方形封面用不了。"""
    blur = img.filter(ImageFilter.GaussianBlur(5))
    hot = blur.point(lambda v: int(v * 0.65))
    return Image.blend(img, ImageChops.screen(img, hot), amount)


def _envelope(n: int = 128):
    """这首歌**自己**的包络：ffmpeg 解成 4 kHz 单声道，按块算 RMS。

    封面上的那道波形不是装饰——它是这 6:35 的实际响度曲线，和片子里每条曲线一样是量出来的。
    """
    ff = ROOT / "tools" / "ffmpeg.exe"
    raw = subprocess.run([str(ff), "-v", "error", "-i", str(ROOT / "input" / "song.flac"),
                          "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    step = max(1, len(a) // n)
    env = np.array([float(np.sqrt((a[i * step:(i + 1) * step] ** 2).mean())) for i in range(n)])
    return env / max(1e-6, env.max())


def _bg(w: int, h: int) -> Image.Image:
    """片子的底色 + 一层极淡的网纹，让封面和成片是同一个世界。"""
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for y in range(0, h, 3):
        d.line([(0, y), (w, y)], fill=mix(BG, (10, 16, 26), 0.55))
    return img


def _scanlines(img: Image.Image, alpha: float = 0.10, step: int = 3) -> Image.Image:
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(0, img.height, step):
        d.line([(0, y), (img.width, y)], fill=(0, 0, 0, int(255 * alpha)))
    return img


def _ticks(d, x0, x1, y, n=24, a=0.30, col=AMBER):
    """一把刻度尺——片子里每个面板都有。"""
    w = (x1 - x0) / n
    for i in range(n + 1):
        hh = 7 if i % 6 else 11
        d.line([(x0 + i * w, y), (x0 + i * w, y + hh)], fill=fade(col, a))


def _corners(d, box, size=20, a=0.55, col=AMBER, w=2):
    x0, y0, x1, y1 = box
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx, cy), (cx + dx * size, cy)], fill=fade(col, a), width=w)
        d.line([(cx, cy), (cx, cy + dy * size)], fill=fade(col, a), width=w)


def _art(size: int) -> Image.Image:
    if not ART.exists():
        raise SystemExit(f"缺封面源图：{ART}（从 input/song.flac 里取出内嵌封面即可）")
    im = Image.open(ART).convert("RGB")
    return im.resize((size, size), Image.LANCZOS)


def _grain(img: Image.Image, amount: float = 5.0) -> Image.Image:
    """一点胶片颗粒，压掉原图与黑底之间的"贴上去"感。"""
    import random
    rnd = random.Random(1994)
    px = img.load()
    w, h = img.size
    for _ in range(int(w * h * 0.06)):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r, g, b = px[x, y]
        k = rnd.uniform(-amount, amount)
        px[x, y] = (max(0, min(255, int(r + k))),
                    max(0, min(255, int(g + k))),
                    max(0, min(255, int(b + k))))
    return img


def cover_16x9(w: int = 1280, h: int = 720) -> Image.Image:
    img = _bg(w, h)
    d = ImageDraw.Draw(img)

    # ---- 右边：原专辑封面，做成"唱片套" -------------------------------------
    art_s = 560
    ax0, ay0 = w - art_s - 64, (h - art_s) // 2
    art = _art(art_s)
    img.paste(art, (ax0, ay0))
    # 边缘一圈暗角，让它落在黑里而不是"贴"在黑上
    vig = Image.new("L", (art_s, art_s), 0)
    dv = ImageDraw.Draw(vig)
    for i in range(6):
        a = int(150 * (1 - i / 6.0))
        dv.rectangle([i, i, art_s - i, art_s - i], outline=a)
    img.paste(Image.new("RGB", (art_s, art_s), (0, 0, 0)), (ax0, ay0), vig)
    d.rectangle([ax0 - 1, ay0 - 1, ax0 + art_s, ay0 + art_s], outline=fade(AMBER, 0.35))
    _corners(d, (ax0 - 10, ay0 - 10, ax0 + art_s + 10, ay0 + art_s + 10), 22, 0.6)
    # 唱片套下方的"标签行"
    d.line([(ax0, ay0 + art_s + 18), (ax0 + art_s, ay0 + art_s + 18)], fill=fade(AMBER, 0.18))
    tk.text(d, (ax0, ay0 + art_s + 26), "LD-1994  ·  SIDE A  ·  TRACK 13",
            font(tk.MONO, 10), AMBER, 0.45)
    tk.text(d, (ax0, ay0 + art_s + 44), "© 1994 飛碟唱片 / 原版封面",
            font(tk.CJK, 9), AMBER, 0.30)

    # ---- 左边：机器的标签面板 -----------------------------------------------
    x = 64
    tk.text(d, (x, 92), "LASER KARAOKE  //  LD-1994", font(tk.MONO, 12), AMBER, 0.55)
    _ticks(d, x, x + 470, 116, 24, 0.26)

    tk.text(d, (x, 150), TITLE, font(CJK_B, 68), AMBER, 0.96)
    tk.text(d, (x, 240), SUB, font(tk.CJK, 15), AMBER, 0.62)

    d.line([(x, 286), (x + 470, 286)], fill=fade(AMBER, 0.22))
    tk.text(d, (x, 302), KIND, font(tk.CJK, 22), AMBER, 0.90)
    tk.text(d, (x, 340), EN, font(tk.MONO, 9), AMBER, 0.40)

    # ---- 中段：这首歌自己的包络（实测，不是装饰） ----------------------------
    env = _envelope(120)
    wx0, wx1 = x, x + 470
    base_y, max_h = 452, 64
    bw = (wx1 - wx0) / len(env)
    for i, v in enumerate(env):
        bh = 3 + v * max_h
        bx = wx0 + i * bw
        col = mix(AMBER, (255, 246, 224), 0.35 if v > 0.82 else 0.0)
        d.rectangle([bx, base_y - bh, bx + max(1.0, bw - 1.2), base_y], fill=fade(col, 0.55 + 0.35 * v))
    d.line([(wx0, base_y + 2), (wx1, base_y + 2)], fill=fade(AMBER, 0.22))
    _ticks(d, wx0, wx1, base_y + 4, 24, 0.22)
    tk.text(d, (x, 494), "SIGNAL  /  6:35  /  120 BANDS", font(tk.MONO, 8), AMBER, 0.32)

    # 底部：STAFF 行 + PLAY 芯片
    d.line([(x, 566), (x + 470, 566)], fill=fade(AMBER, 0.16))
    tk.text(d, (x, 580), "STAFF", font(tk.MONO_B, 10), AMBER, 0.50)
    tk.text(d, (x + 62, 580), "RedStar_ChinRinhan", font(tk.MONO_B, 13), AMBER, 0.85)
    tk.text(d, (x, 604), "CH 07/08/09  DeepSeek-V4.1-flash · MiniMax-M3.1-flash · Mimo-V2.6-Pro",
            font(tk.MONO, 8), AMBER, 0.34)

    # 右下：PLAY 芯片
    chip = "[ PLAY ]"
    cw = d.textlength(chip, font=font(tk.MONO_B, 11))
    d.rectangle([x + 470 - cw - 16, 578, x + 470 + 4, 600], outline=fade(AMBER, 0.45))
    tk.text(d, (x + 470 - cw - 8, 582), chip, font(tk.MONO_B, 11), AMBER, 0.80)

    img = _grain(img, 4.0)
    img = _scanlines(img, 0.08, 3)
    return _glow(img, 0.30)


def cover_1x1(size: int = 1000) -> Image.Image:
    """方形版：原封面满幅，下面压一条暗带放标题——像一张重新压过的唱片套。"""
    art = _art(size)
    img = art.copy()
    # 底部渐暗
    grad = Image.new("L", (1, size), 0)
    for y in range(size):
        u = max(0.0, (y - size * 0.52) / (size * 0.48))
        grad.putpixel((0, y), int(255 * min(1.0, u ** 1.25) * 0.92))
    grad = grad.resize((size, size))
    img.paste(Image.new("RGB", (size, size), (2, 3, 8)), (0, 0), grad)

    d = ImageDraw.Draw(img)
    # 底部一条实心暗带：原封面在那里的画面太满，小字压不住
    band_y = size - 210
    d.rectangle([0, band_y, size, size], fill=(3, 4, 9))
    d.line([(0, band_y), (size, band_y)], fill=fade(AMBER, 0.16))
    m = 56
    _corners(d, (m, m, size - m, size - m), 30, 0.55)
    tk.text(d, (m + 4, m + 2), "LASER KARAOKE  //  LD-1994", font(tk.MONO, 11), AMBER, 0.55)

    tk.text(d, (m + 4, size - 196), TITLE, font(CJK_B, 74), AMBER, 0.97)
    tk.text(d, (m + 4, size - 104), SUB, font(tk.CJK, 16), AMBER, 0.66)
    d.line([(m + 4, size - 74), (size - m, size - 74)], fill=fade(AMBER, 0.22))
    tk.text(d, (m + 4, size - 60), KIND, font(tk.CJK, 20), AMBER, 0.90)
    tk.text(d, (m + 4, size - 30), "EVERY FRAME IS CODE", font(tk.MONO, 10), AMBER, 0.42)
    tk.text(d, (m + 300, size - 30), "STAFF  RedStar_ChinRinhan", font(tk.MONO, 10), AMBER, 0.40)

    img = _grain(img, 4.0)
    img = _scanlines(img, 0.07, 3)
    return _glow(img, 0.26)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    a = cover_16x9()
    a.save(OUT / "cover-16x9.png")
    b = cover_1x1()
    b.save(OUT / "cover-1x1.png")
    print("wrote", OUT / "cover-16x9.png", a.size)
    print("wrote", OUT / "cover-1x1.png", b.size)


if __name__ == "__main__":
    main()
