# -*- coding: utf-8 -*-
"""从官方标识的矢量/位图源生成 `src/logos.py` 的多边形数据（构建期工具，渲染时不跑）。

来源（2026-10-28 拉取，均不在仓库里）：
  - DeepSeek : https://cdn.simpleicons.org/deepseek   （官方鲸鱼，#5786FE）
  - MiniMax  : https://cdn.simpleicons.org/minimax    （官方波形 M，#E73562）
  - MiMo     : https://github.com/XiaomiMiMo.png?size=240 （官方字标 "Xiaomi MIMO"）

做法：把源栅格化到 1024 px，用 OpenCV 的 RETR_CCOMP 抽轮廓（外轮廓 + 洞），
Douglas-Peucker 简化，再**归一化到 0..1000 的整数坐标**写进 `src/logos.py`。
渲染时用 `ImageDraw.polygon` 画这些点——所以画面里是**准确的官方形状**，
仓库里仍然没有一个图片文件。

    python src/probes/make_logos.py <deepseek.svg> <minimax.svg> <mimo.png>
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import resvg_py
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "logos.py"
RES = 1024
EPS = 1.6          # 简化容差（1024 px 空间里 1.6 px，肉眼看不出来）
Q = 1000           # 归一化到 0..1000


def svg_mask(svg_path: Path) -> np.ndarray:
    svg = svg_path.read_text(encoding="utf-8")
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=RES, height=RES))
    tmp = Path("/tmp/_logo.png")
    tmp.write_bytes(png)
    a = np.asarray(Image.open(tmp).convert("RGBA"))[:, :, 3]
    return (a > 110).astype(np.uint8) * 255


def img_mask(png_path: Path) -> np.ndarray:
    im = Image.open(png_path).convert("L")
    im = im.resize((RES, RES), Image.LANCZOS)
    a = np.asarray(im)
    return (a > 110).astype(np.uint8) * 255


def trace(mask: np.ndarray):
    """→ (outer, hole) 两组归一化多边形（0..1000，按 bbox 归一）。"""
    ys, xs = np.where(mask > 0)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return [], [], (w / h)
    hier = hier[0]
    outer, hole = [], []
    for i, c in enumerate(cnts):
        if cv2.contourArea(c) < 40:
            continue
        ap = cv2.approxPolyDP(c, EPS, True).reshape(-1, 2)
        if len(ap) < 3:
            continue
        pts = [((int(round((x - x0) / w * Q)), int(round((y - y0) / h * Q)))) for x, y in ap]
        (outer if hier[i][3] == -1 else hole).append(pts)
    return outer, hole, (w / h)


def fmt(polys) -> str:
    return " | ".join(" ".join("%d,%d" % p for p in poly) for poly in polys)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    ds, mm, mi = (Path(a) for a in sys.argv[1:])
    data = {
        "deepseek": trace(svg_mask(ds)),
        "minimax": trace(svg_mask(mm)),
        "mimo": trace(img_mask(mi)),
    }
    lines = []
    for name, (outer, hole, aspect) in data.items():
        npts = sum(len(p) for p in outer) + sum(len(p) for p in hole)
        print("%-9s contours %d/%d  points %d  aspect %.3f"
              % (name, len(outer), len(hole), npts, aspect))
        lines.append('    "%s": (' % name)
        lines.append("        %.4f," % aspect)
        lines.append('        "%s",' % fmt(outer))
        lines.append('        "%s",' % fmt(hole))
        lines.append("    ),")
    OUT.write_text(
        HEAD + "\n".join(lines) + "\n" + TAIL, encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")


HEAD = '''# -*- coding: utf-8 -*-
"""三个模型的官方标识，以**多边形数据**存进代码（构建期由 `src/probes/make_logos.py` 生成）。

导演（01:0x）：「这个程序化生成还是不太行，毕竟厂商 logo 是准确信息，这个太抽象了」。

所以不再用 26×13 的字形矩阵去"抽象"它们——改成从**官方标识的矢量/位图**抽出轮廓，
归一化成 0..1000 的整数点集，渲染时用 `ImageDraw.polygon` 画出来。
形状是准确的（鲸鱼就是那条鲸鱼），而仓库里仍然没有一个图片文件：画面上每一块颜色
都是代码按点集填的。

- `deepseek`：官方鲸鱼（#5786FE）
- `minimax` ：官方波形 M（#E73562）
- `mimo`    ：官方字标 "Xiaomi MIMO"（小米橙）

每个条目的结构：(宽高比, 外轮廓, 洞) —— 多边形之间用 " | " 分隔，点用 "x,y"。
"""
from __future__ import annotations

from PIL import Image, ImageDraw

import tk
from tk import fade, mix

Q = 1000.0

COLOR = {
    "deepseek": (87, 134, 254),
    "minimax": (231, 53, 98),
    "mimo": (255, 105, 0),
}

MARKS = {
'''

TAIL = '''}

_CACHE: dict = {}


def _polys(s: str):
    out = []
    if not s:
        return out
    for chunk in s.split("|"):
        pts = [tuple(float(v) for v in p.split(",")) for p in chunk.split()]
        if len(pts) >= 3:
            out.append(pts)
    return out


def mask(name: str, w: int, h: int) -> Image.Image:
    """把标志画成 w×h 的灰度遮罩（超采样 3× 再缩，边缘才不毛）。"""
    key = (name, w, h)
    if key in _CACHE:
        return _CACHE[key]
    aspect, outer, hole = MARKS[name]
    # 在 w×h 里按比例居中：多边形归一化到 0..1000，y 方向按 aspect 还原
    mw = w
    mh = max(1.0, w / aspect)
    if mh > h:
        mh = h
        mw = h * aspect
    ox, oy = (w - mw) / 2.0, (h - mh) / 2.0
    ss = 3
    im = Image.new("L", (int(w * ss), int(h * ss)), 0)
    d = ImageDraw.Draw(im)

    def scale(pts):
        return [((ox + x / Q * mw) * ss, (oy + y / Q * mh) * ss) for x, y in pts]

    for p in _polys(outer):
        d.polygon(scale(p), fill=255)
    for p in _polys(hole):
        d.polygon(scale(p), fill=0)
    im = im.resize((w, h), Image.LANCZOS)
    _CACHE[key] = im
    return im


def draw(img: Image.Image, xy, name: str, *, w: int, h: int, alpha: float = 1.0,
         tint=None) -> None:
    """在 (x, y) 画一个模型的官方标识，占 w×h（宽高比按官方形状内嵌居中）。"""
    if alpha <= 0.01:
        return
    m = mask(name, w, h)
    col = tint or COLOR.get(name, tk.AMBER)
    # 用遮罩当 alpha 贴一层纯色，再做一点过曝（灯管感）
    layer = Image.new("RGB", (w, h), col)
    a = m.point(lambda v: int(v * alpha))
    img.paste(layer, (int(xy[0]), int(xy[1])), a)
'''


if __name__ == "__main__":
    main()
