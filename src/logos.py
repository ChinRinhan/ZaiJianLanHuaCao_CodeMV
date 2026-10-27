# -*- coding: utf-8 -*-
"""三个模型的标志：官方 mark 的**字形化**版本。

导演（00:5x）：「用本项目风格化呈现出这几个模型的 logo」。

做法：把各自的官方标识降采样成 26×13 的字形矩阵，**以字符数据存进代码**——
不引用任何位图文件，所以片尾那句「每一帧由代码绘制」仍然成立。

- `deepseek`：官方鲸鱼（#5786FE），按灰度均值降采样，保留剪影
- `minimax`：官方波形 M（#E73562），按块取最大值降采样——它的笔画只有 1 个块宽，
  均值会把笔画抹掉，取最大值才留得住
- `mimo`：官方是**字标**（"Xiaomi MiMo"），不是图形，所以这里不画矩阵，画字

用法：
    logos.draw(img, (x, y), "deepseek", px=4, alpha=1.0)
"""
from __future__ import annotations

from PIL import Image, ImageDraw

import tk
from tk import fade, font, mix

LEVELS = " .:+*#@"          # 六级字形：' ' 是空，'@' 是实心

# 品牌色（取各自官方标识的主色）
COLOR = {
    "deepseek": (87, 134, 254),
    "minimax": (231, 53, 98),
    "mimo": (255, 105, 0),
}

# 26 × 13，字符 = 灰度级
MARKS = {
    "deepseek": (
        "        ...:*:  *         ",
        "      +@@@@@@   @#. .*    ",
        "     *@@@@@@@#. #@#@@#    ",
        "    :@@@@@@@@@#.:@@@@:    ",
        "    ##*#@@@@@@@#.*@+.     ",
        "    @.  .*@@@*+@@@@       ",
        "    @:    +@@#:+@@#       ",
        "    #*     +@@#+@@+       ",
        "    +@.     *@@@@#        ",
        "    .@#   + .@@@@.        ",
        "     :@#: ##..@@#.        ",
        "      :@@@@@@***##.       ",
        "        +#@@#*.           ",
    ),
    "minimax": (
        "         @@@@@ @@@@@      ",
        "         @@ @@ @@ @@      ",
        "         @@ @@ @@ @@      ",
        "   @@@@* @@ @@ @@ @@  @@@@",
        "   @@@@@ @@ @@ @@ @@ @@@@@",
        "@  @@ @@ @@ @@ @@ @@ @@ +@",
        "@@ @@ @@ @@ @@ @@ @@ @@ +@",
        "@@@@@ @@ @@ @@ @@ @@ @@ +@",
        "@@@@  @@ @@ @@ @@ @@ @@ +@",
        "      @@ @@ @@ @@ @@@@@ :@",
        "      @@:@@ @@ @@ :@@@@   ",
        "      @@@@@ @@ @@         ",
        "            @@@@@         ",
    ),
}

MARK_W = 26
MARK_H = 13

# 字标（mimo）：大行 + 小行，颜色分开给
WORDMARK = {"mimo": ("XIAOMI", "MiMo")}


def _level(ch: str) -> float:
    i = LEVELS.find(ch)
    return 0.0 if i <= 0 else i / (len(LEVELS) - 1)


def draw(img: Image.Image, xy, name: str, *, px: int = 4, alpha: float = 1.0,
         tint=None) -> None:
    """在 (x, y) 画一个模型的标志，占 26·px × 13·px。"""
    if alpha <= 0.01:
        return
    x0, y0 = xy
    col = tint or COLOR.get(name, tk.AMBER)
    if name in WORDMARK:
        small, big = WORDMARK[name]
        d = ImageDraw.Draw(img)
        fs = font(tk.MONO_B, max(7, int(px * 2.1)))
        fb = font(tk.MONO_B, max(10, int(px * 6.4)))
        tw = d.textlength(big, font=fb)
        th = px * MARK_H
        d.text((x0 + (MARK_W * px - tw) / 2, y0 + th * 0.30), big, font=fb,
               fill=fade((240, 244, 255), 0.95 * alpha))
        d.text((x0 + (MARK_W * px - tw) / 2, y0 + th * 0.10), small, font=fs,
               fill=fade(col, 0.80 * alpha))
        return
    rows = MARKS.get(name)
    if not rows:
        return
    d = ImageDraw.Draw(img)
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            v = _level(ch)
            if v <= 0.02:
                continue
            x = x0 + c * px
            y = y0 + r * px
            # 实心块，亮度按字形级；边缘那两级再压暗一点，读起来才不像马赛克
            a = alpha * (0.30 + 0.70 * v)
            # 只有最亮那级掺一点白（像灯管过曝），其余用品牌原色，否则鲸鱼会灰掉
            c = mix(col, (255, 255, 255), 0.22) if v > 0.9 else col
            d.rectangle([x, y, x + px - 0.5, y + px - 0.5], fill=fade(c, a))
