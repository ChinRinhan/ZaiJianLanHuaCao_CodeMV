# -*- coding: utf-8 -*-
"""crt: the film's one gesture for bringing a module on line.

The director approved the opening and asked for it to become grammar rather than a one-off:
"后续又这个CRT上电再衍生出其他的，比如09 10期间的小起伏，20和40处同理，前奏每一个起伏就
CRT上电出不同模块".

So this module holds the aperture reveal in a reusable form. `boot_panel()` draws a module
inside a rect, clipped by its own CRT aperture, with:

  - the picture opening out of a hot horizontal line, then out of that line vertically
  - a title bar that decodes its label (glyphs flicker, then lock)
  - a state word that changes as the module comes up (SEEK -> LOCK -> LIVE)
  - an "idle" state after the intro drops out at 64 s: dim, but still powered

Everything is a pure function of t and of a 0..1 progress value, so the same helper serves the
opening (one big panel) and the intro lifts (many small ones).
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

import tk

HOT = (255, 246, 224)


def aperture_rect(rect, u: float):
    """The visible sub-rectangle of `rect` at reveal progress u (0 = a line, 1 = the whole rect).

    First the line grows horizontally to full width, then it opens vertically. Two stages, so
    you can see the line before there is any picture — that is what makes it read as a tube.
    """
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if u <= 0:
        return None, (cx, cx, cy)
    if u < 0.42:
        k = tk.ease_out(u / 0.42)
        hw = max(1.0, (x1 - x0) / 2 * k)
        return None, (cx - hw, cx + hw, cy)
    k = tk.ease_out((u - 0.42) / 0.58)
    hh = max(1.0, (y1 - y0) / 2 * k)
    return (x0, cy - hh, x1, cy + hh), None


def boot_panel(img: Image.Image, rect, t: float, u: float, title: str,
               rows=None, live: bool = True, dim: float = 1.0, seed: int = 0,
               state: str = "LOCK") -> Image.Image:
    """Draw one module powering on, clipped to its CRT aperture.

    rows: list of (label, value, colour_or_None) lines; values are strings that already hold
    their live numbers, so the caller decides what changes.
    """
    ap, line = aperture_rect(rect, u)
    if ap is None and line is None:
        return img
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect
    if ap is None:
        # only the hot line exists
        d.line([(line[0], line[2]), (line[1], line[2])],
               fill=tk.fade(HOT, 0.85 * dim), width=2)
        return img

    ax0, ay0, ax1, ay1 = (int(round(v)) for v in ap)
    lay = img.crop((ax0, ay0, ax1, ay1))
    dl = ImageDraw.Draw(lay)
    lw, lh = lay.size

    def tx(x, y, s, f, c, a):
        dl.text((x - ax0, y - ay0), s, font=f, fill=tk.fade(c, a))

    # The frame goes 1 px INSIDE the crop. Drawing it at the crop's own right/bottom edge put
    # those two sides outside the image, so every module looked like it had only a top-left
    # corner — the "线框没有画完" the director caught.
    dl.rectangle([0, 0, lw - 1, lh - 1], outline=tk.fade(tk.AMBER, 0.42 * dim))
    if lh > 22:
        txt = tk.decode(title, max(0.0, (t - 0.0)) if u < 1.0 else 9.0,
                        seed=seed * 7919 + int(t * 24), rate=90.0, settle=0.08)
        tx(x0 + 7, y0 + 4, txt, tk.font(tk.MONO, 9), tk.AMBER, 0.80 * dim)
        if state:
            tx(x1 - 42, y0 + 4, state, tk.font(tk.MONO, 8),
               tk.GREEN if state == "LIVE" else tk.AMBER, 0.72 * dim)
        dl.line([(5, 17), (lw - 6, 17)], fill=tk.fade(tk.AMBER, 0.20 * dim))

    # the module's own read-outs
    if rows:
        for i, (label, value, col) in enumerate(rows):
            yy = y0 + 23 + i * 14
            if yy > ay1 - 6:
                break
            tx(x0 + 8, yy, label, tk.font(tk.MONO, 8), tk.AMBER, 0.52 * dim)
            tx(x0 + 82, yy, value, tk.font(tk.MONO_B, 9), col or tk.AMBER, 0.92 * dim)

    if 0.0 < u < 1.0:
        # the hot scan line marks the front of the reveal
        mid = lh // 2
        dl.line([(0, mid), (lw, mid)], fill=tk.fade(HOT, 0.5 * dim), width=1)

    img.paste(lay, (ax0, ay0))
    return img
