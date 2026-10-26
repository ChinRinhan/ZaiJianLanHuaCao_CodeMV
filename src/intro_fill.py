# -*- coding: utf-8 -*-
"""intro_fill: fill the frame cell by cell, on the music.

The director's note after approving the opening:
"05之后不要渐变然后转到弹方框，要和你05的动效方案一样，慢慢按节奏填充到整个画面，引入1:08前的所有内容"

Two things were rejected:
  - the 0.8 s cross-fade that widened the aperture to a full-width frame (it read as a
    dissolve into a different shot), and
  - boxes popping into place one after another.

What is wanted instead is the SAME gesture as the CRT power-on in the first five seconds,
continued: the picture grows by cells, each cell arriving on a musical attack, until the
whole frame is lit and everything that exists before 1:08 is on screen.

So this module gives every region of the frame a reveal time taken from a measured onset,
and `fill()` composites the finished frame into the area that has already arrived.

The grid is coarse on purpose (16 x 9 px cells at 1280x720 = 80 x 80). A finer grid reads as
noise; a coarser one reads as a wipe. 80 x 80 with a 3-cell soft front holds both.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

import tk

W, H = tk.W, tk.H
CELL = 16                      # px; 80 x 80 cells over the frame
# the transport panel: the fill's origin, and the one block that never goes dark
SEED_RECT = (8, 42, 392, 180)
COLS, ROWS = W // CELL, H // CELL


def _front(t: float, times: list[float], soft: float = 0.34) -> float:
    """Fraction of the intro that has arrived, given the measured onset list.

    Returns a value in 0..n where n is how many onsets have passed, plus the fraction of the
    way to the next one — so the fill advances in steps that land on the music.
    """
    n = 0
    for x in times:
        if t >= x:
            n += 1
        else:
            break
    if n == 0:
        return 0.0
    if n >= len(times):
        return float(len(times))
    prev_t = times[n - 1]
    next_t = times[n]
    span = max(1e-3, next_t - prev_t)
    return (n - 1) + min(1.0, (t - prev_t) / span) ** 1.0


def cell_time(cx: float, cy: float, times: list[float], mode: str = "radial") -> float:
    """The moment a cell at (cx, cy) arrives.

    Every mode spreads the same measured onsets over the frame differently, so the fill has a
    direction the eye can follow. `radial` from the machine, `sweep` left to right, `inward`
    from the edges toward the centre.
    """
    n = len(times)
    if n == 0:
        return 0.0
    if mode == "radial":
        # The fill starts at the transport panel and spreads OUT IN ALL DIRECTIONS from it.
        # Normalising by the distance to the frame's farthest corner (not its diagonal) keeps the
        # front round instead of stretching it into a wedge that sweeps up from the bottom.
        sx, sy = 200.0, 120.0                                  # the transport panel
        far = max(math.hypot(sx - 0, sy - 0), math.hypot(sx - W, sy - 0),
                  math.hypot(sx - 0, sy - H), math.hypot(sx - W, sy - H))
        k = min(0.999, math.hypot(cx - sx, cy - sy) / far)
    elif mode == "sweep":
        k = min(0.999, cx / W)
    elif mode == "inward":
        d = min(cx, W - cx, cy, H - cy) / (min(W, H) / 2)
        k = 1.0 - min(0.999, d)
    else:
        k = 0.5
    return times[min(n - 1, int(k * n))]


def fill(finished: Image.Image, t: float, times: list[float], mode: str = "radial",
         started: float = 0.0, order: str = "music") -> Image.Image:
    """Composite `finished` into the cells that have arrived, over a black glass background.

    `started` is when the fill begins; before it, the caller's own aperture picture is kept by
    returning `finished` unchanged (the intro's first five seconds are drawn by intro_scene).
    """
    if t < started or not times:
        return finished
    front = _front(t, times)
    if front <= 0:
        return finished

    # build a per-cell alpha mask: 255 where the cell has arrived, with a soft leading edge
    m = Image.new("L", (COLS, ROWS), 0)
    mp = m.load()
    for r in range(ROWS):
        cy = r * CELL + CELL / 2
        for q in range(COLS):
            cx = q * CELL + CELL / 2
            ct = cell_time(cx, cy, times, mode)
            idx = times.index(ct) if ct in times else 0
            age = t - ct
            if age <= 0:
                mp[q, r] = 0
            elif age < 0.16:
                # decoding: partial, with a flicker so the front is visible as activity
                mp[q, r] = int(255 * (0.35 + 0.5 * age / 0.16))
            else:
                mp[q, r] = 255

    mask = m.resize((COLS * CELL, ROWS * CELL), Image.NEAREST)
    # Start from black glass and paste the finished frame through the mask. Pasting onto a copy
    # of `finished` is a no-op — the same image in the same place — which is why an early
    # version showed the whole frame from the first filled cell.
    out = Image.new("RGB", finished.size, (2, 3, 8))
    out.paste(finished, (0, 0), mask)
    # The machine is always there. The fill is what the machine's picture spreads into, so the
    # machine itself must never be switched off while the front is still travelling — otherwise
    # the first second of the fill is a black screen with one bright corner.
    keep = Image.new("L", finished.size, 0)
    ImageDraw.Draw(keep).rectangle(SEED_RECT, fill=255)
    out.paste(finished, (0, 0), keep)
    return out


def front_cells(t: float, times: list[float], mode: str = "radial"):
    """(cells_arrived, cells_total) — for the read-out that reports how much of the frame is in."""
    if not times or t < times[0]:
        return 0, COLS * ROWS
    n = 0
    for r in range(ROWS):
        cy = r * CELL + CELL / 2
        for q in range(COLS):
            cx = q * CELL + CELL / 2
            ct = cell_time(cx, cy, times, mode)
            if t >= ct:
                n += 1
    return n, COLS * ROWS
