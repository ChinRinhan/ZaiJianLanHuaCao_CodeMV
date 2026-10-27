# -*- coding: utf-8 -*-
"""封面：用**原专辑封面**做主体，套上这部片子的 TUI 语言。

导演（01:1x）：「第一个是封面……封面可以不用纯代码，用原专辑封面制作」。
导演（01:5x）：「封面你给一版 4:3 的，有些字符太小了没有辨识」——所以这一版把所有小字
从 8–10 px 抬到 11–15 px，并补一张 4:3。

产出三张（`assets/`）：

| 文件 | 尺寸 | 用在哪 |
|---|---|---|
| `cover-16x9.png` | 1280×720 | 视频缩略图 / 仓库头图 |
| `cover-4x3.png`  | 1440×1080 | 4:3 平台、演示页、封面合集 |
| `cover-1x1.png`  | 1000×1000 | 音频平台、社交卡 |

原版封面从 `input/song.flac` 内嵌的那张 500×500 取出来（`input/album-cover.jpg`），
版权归原权利人，只作为非官方同人作品的标识。

    python src/cover.py
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import tk
from tk import AMBER, BG, fade, font, mix

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "input" / "album-cover.jpg"
OUT = ROOT / "assets"
CJK_B = "C:/Windows/Fonts/msyhbd.ttc"      # 中文粗体（msyh 只有常规体）

TITLE = "再见 兰花草"
SUB = "张雨生 ·《卡拉OK·台北·我》· 1994 · 6:35"
# 导演定的标题：张雨生《再见 兰花草》| AI 程序所描绘的未播放完毕的卡拉OK
TAGLINE = "AI 程序所描绘的未播放完毕的卡拉OK"
KIND = "同人作品 · 纯代码 MV"
EN = "EVERY FRAME IS CODE  ·  NO FOOTAGE  ·  24 FPS"
MODELS = "CH 07/08/09  DeepSeek-V4.1-flash · MiniMax-M3.1-flash · Mimo-V2.6-Pro"


# ---------------------------------------------------------------- 素材
def _art(size: int) -> Image.Image:
    if not ART.exists():
        raise SystemExit(f"缺封面源图：{ART}（从 input/song.flac 里取出内嵌封面即可）")
    return Image.open(ART).convert("RGB").resize((size, size), Image.LANCZOS)


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


# ---------------------------------------------------------------- 画法
def _bg(w: int, h: int) -> Image.Image:
    """片子的底色 + 一层极淡的网纹，让封面和成片是同一个世界。"""
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for y in range(0, h, 3):
        d.line([(0, y), (w, y)], fill=mix(BG, (10, 16, 26), 0.55))
    return img


def _glow(img: Image.Image, amount: float = 0.30) -> Image.Image:
    """辉光：和 `tk.post` 同一个意思，但它写死了 1280×720 的扫描遮罩，别的尺寸用不了。"""
    blur = img.filter(ImageFilter.GaussianBlur(5))
    hot = blur.point(lambda v: int(v * 0.65))
    return Image.blend(img, ImageChops.screen(img, hot), amount)


def _scanlines(img: Image.Image, alpha: float = 0.10, step: int = 3) -> Image.Image:
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(0, img.height, step):
        d.line([(0, y), (img.width, y)], fill=(0, 0, 0, int(255 * alpha)))
    return img


def _ticks(d, x0, x1, y, n=24, a=0.30, col=AMBER, hh=11):
    """一把刻度尺——片子里每个面板都有。"""
    w = (x1 - x0) / n
    for i in range(n + 1):
        h = hh if i % 6 == 0 else int(hh * 0.62)
        d.line([(x0 + i * w, y), (x0 + i * w, y + h)], fill=fade(col, a))


def _corners(d, box, size=20, a=0.55, col=AMBER, w=2):
    x0, y0, x1, y1 = box
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx, cy), (cx + dx * size, cy)], fill=fade(col, a), width=w)
        d.line([(cx, cy), (cx, cy + dy * size)], fill=fade(col, a), width=w)


def _wave(d, x0, x1, base_y, max_h, env):
    bw = (x1 - x0) / len(env)
    for i, v in enumerate(env):
        bh = 3 + v * max_h
        bx = x0 + i * bw
        col = mix(AMBER, (255, 246, 224), 0.35 if v > 0.82 else 0.0)
        d.rectangle([bx, base_y - bh, bx + max(1.0, bw - 1.2), base_y],
                    fill=fade(col, 0.55 + 0.35 * v))
    d.line([(x0, base_y + 2), (x1, base_y + 2)], fill=fade(AMBER, 0.22))


def _grain(img: Image.Image, amount: float = 4.0) -> Image.Image:
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


def _sleeve(img, ax0, ay0, art_s, label_dy=26, big=False):
    """把专辑封面做成"唱片套"：角标 + 细边 + 边缘暗角 + 标签行。"""
    art = _art(art_s)
    img.paste(art, (ax0, ay0))
    vig = Image.new("L", (art_s, art_s), 0)
    dv = ImageDraw.Draw(vig)
    for i in range(6):
        dv.rectangle([i, i, art_s - i, art_s - i], outline=int(150 * (1 - i / 6.0)))
    img.paste(Image.new("RGB", (art_s, art_s), (0, 0, 0)), (ax0, ay0), vig)
    d = ImageDraw.Draw(img)
    d.rectangle([ax0 - 1, ay0 - 1, ax0 + art_s, ay0 + art_s], outline=fade(AMBER, 0.35))
    _corners(d, (ax0 - 10, ay0 - 10, ax0 + art_s + 10, ay0 + art_s + 10),
             26 if big else 22, 0.6, w=2)
    ly = ay0 + art_s + label_dy
    d.line([(ax0, ly - 8), (ax0 + art_s, ly - 8)], fill=fade(AMBER, 0.18))
    tk.text(d, (ax0, ly), "LD-1994  ·  SIDE A  ·  TRACK 13",
            font(tk.MONO, 14 if big else 11), AMBER, 0.50)
    tk.text(d, (ax0, ly + (30 if big else 22)), "© 1994 飛碟唱片 / 原版封面",
            font(tk.CJK, 13 if big else 11), AMBER, 0.34)


# ---------------------------------------------------------------- 三种画幅
def cover_wide(w: int = 1280, h: int = 720) -> Image.Image:
    """16:9：左边标签面板，右边唱片套。"""
    img = _bg(w, h)
    d = ImageDraw.Draw(img)
    art_s = 560
    ax0, ay0 = w - art_s - 64, (h - art_s) // 2 - 8
    _sleeve(img, ax0, ay0, art_s)

    x = 64
    tk.text(d, (x, 92), "LASER KARAOKE  //  LD-1994", font(tk.MONO, 13), AMBER, 0.58)
    _ticks(d, x, x + 470, 118, 24, 0.26)

    tk.text(d, (x, 148), TITLE, font(CJK_B, 68), AMBER, 0.96)
    tk.text(d, (x, 240), SUB, font(tk.CJK, 17), AMBER, 0.64)

    d.line([(x, 286), (x + 470, 286)], fill=fade(AMBER, 0.22))
    tk.text(d, (x, 300), TAGLINE, font(tk.CJK, 22), AMBER, 0.92)
    tk.text(d, (x, 342), KIND, font(tk.CJK, 13), AMBER, 0.55)
    tk.text(d, (x, 366), EN, font(tk.MONO, 11), AMBER, 0.40)

    env = _envelope(120)
    _wave(d, x, x + 470, 492, 66, env)
    _ticks(d, x, x + 470, 496, 24, 0.22, hh=9)
    tk.text(d, (x, 520), "SIGNAL  /  6:35  /  120 BANDS", font(tk.MONO, 11), AMBER, 0.38)

    d.line([(x, 578), (x + 470, 578)], fill=fade(AMBER, 0.16))
    tk.text(d, (x, 592), "STAFF", font(tk.MONO_B, 12), AMBER, 0.55)
    tk.text(d, (x + 74, 588), "RedStar_ChinRinhan", font(tk.MONO_B, 17), AMBER, 0.88)
    tk.text(d, (x, 626), MODELS, font(tk.MONO, 11), AMBER, 0.40)

    chip = "[ PLAY ]"
    cw = d.textlength(chip, font=font(tk.MONO_B, 12))
    d.rectangle([x + 470 - cw - 16, 588, x + 470 + 4, 614], outline=fade(AMBER, 0.45))
    tk.text(d, (x + 470 - cw - 8, 592), chip, font(tk.MONO_B, 12), AMBER, 0.80)

    img = _grain(img, 4.0)
    img = _scanlines(img, 0.08, 3)
    return _glow(img, 0.30)


def cover_4x3(w: int = 1440, h: int = 1080) -> Image.Image:
    """4:3：字号整体抬一档（导演：8–10 px 的小字没有辨识），整幅上下居中。"""
    img = _bg(w, h)
    d = ImageDraw.Draw(img)
    art_s = 640
    ax0, ay0 = w - art_s - 84, 210
    _sleeve(img, ax0, ay0, art_s, label_dy=34, big=True)

    x = 84
    col = ax0 - 60 - x          # 左栏宽度
    tk.text(d, (x, 140), "LASER KARAOKE  //  LD-1994", font(tk.MONO, 16), AMBER, 0.58)
    _ticks(d, x, x + col, 172, 24, 0.26, hh=13)

    tk.text(d, (x, 216), TITLE, font(CJK_B, 92), AMBER, 0.96)
    tk.text(d, (x, 336), SUB, font(tk.CJK, 21), AMBER, 0.64)

    d.line([(x, 388), (x + col, 388)], fill=fade(AMBER, 0.22))
    tk.text(d, (x, 406), TAGLINE, font(tk.CJK, 29), AMBER, 0.92)
    tk.text(d, (x, 458), KIND, font(tk.CJK, 16), AMBER, 0.55)
    tk.text(d, (x, 486), EN, font(tk.MONO, 13), AMBER, 0.40)

    env = _envelope(96)
    _wave(d, x, x + col, 664, 92, env)
    _ticks(d, x, x + col, 670, 24, 0.22, hh=11)
    tk.text(d, (x, 700), "SIGNAL  /  6:35  /  96 BANDS", font(tk.MONO, 13), AMBER, 0.38)

    d.line([(x, 774), (x + col, 774)], fill=fade(AMBER, 0.16))
    tk.text(d, (x, 792), "STAFF", font(tk.MONO_B, 15), AMBER, 0.55)
    tk.text(d, (x + 96, 786), "RedStar_ChinRinhan", font(tk.MONO_B, 22), AMBER, 0.88)
    tk.text(d, (x, 834), MODELS, font(tk.MONO, 13), AMBER, 0.40)

    chip = "[ PLAY ]"
    cw = d.textlength(chip, font=font(tk.MONO_B, 15))
    d.rectangle([x + col - cw - 18, 788, x + col + 4, 820], outline=fade(AMBER, 0.45))
    tk.text(d, (x + col - cw - 9, 793), chip, font(tk.MONO_B, 15), AMBER, 0.80)

    img = _grain(img, 4.0)
    img = _scanlines(img, 0.08, 3)
    return _glow(img, 0.30)


def cover_1x1(size: int = 1000) -> Image.Image:
    """1:1：原封面满幅，底部压一条实心暗带放标题。"""
    img = _art(size).copy()
    grad = Image.new("L", (1, size), 0)
    for y in range(size):
        u = max(0.0, (y - size * 0.48) / (size * 0.52))
        grad.putpixel((0, y), int(255 * min(1.0, u ** 1.2) * 0.94))
    img.paste(Image.new("RGB", (size, size), (2, 3, 8)), (0, 0), grad.resize((size, size)))

    d = ImageDraw.Draw(img)
    band_y = size - 250
    d.rectangle([0, band_y, size, size], fill=(3, 4, 9))
    d.line([(0, band_y), (size, band_y)], fill=fade(AMBER, 0.16))
    m = 56
    _corners(d, (m, m, size - m, size - m), 30, 0.55)
    tk.text(d, (m + 4, m + 2), "LASER KARAOKE  //  LD-1994", font(tk.MONO, 13), AMBER, 0.58)

    tk.text(d, (m + 4, size - 234), TITLE, font(CJK_B, 76), AMBER, 0.97)
    tk.text(d, (m + 4, size - 138), SUB, font(tk.CJK, 19), AMBER, 0.66)
    d.line([(m + 4, size - 104), (size - m, size - 104)], fill=fade(AMBER, 0.22))
    tk.text(d, (m + 4, size - 92), TAGLINE, font(tk.CJK, 23), AMBER, 0.92)
    tk.text(d, (m + 4, size - 48), KIND, font(tk.CJK, 14), AMBER, 0.55)
    tk.text(d, (m + 4, size - 24), "EVERY FRAME IS CODE", font(tk.MONO, 12), AMBER, 0.40)
    tk.text(d, (m + 330, size - 24), "STAFF  RedStar_ChinRinhan", font(tk.MONO, 12), AMBER, 0.40)

    img = _grain(img, 4.0)
    img = _scanlines(img, 0.07, 3)
    return _glow(img, 0.26)


# ---------------------------------------------------------------- 落盘
def _save(img: Image.Image, path: Path) -> None:
    """先写临时文件再 os.replace：Windows 上目标文件偶尔被别的进程占着，
    直接 save 会抛 OSError [Errno 22]（今天踩过一次）。"""
    tmp = path.with_suffix(".tmp.png")
    img.save(tmp)
    os.replace(tmp, path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, im in (("cover-16x9.png", cover_wide()),
                     ("cover-4x3.png", cover_4x3()),
                     ("cover-1x1.png", cover_1x1())):
        _save(im, OUT / name)
        print("wrote", OUT / name, im.size)


if __name__ == "__main__":
    main()
