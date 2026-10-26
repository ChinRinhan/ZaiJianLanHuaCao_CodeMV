# -*- coding: utf-8 -*-
"""views: the review sheet — the film at the moments that matter, in the four-zone layout.

    python views.py                # writes out/views/*.png
    python views.py --a1           # only the 10 A① shots
    python views.py --contact      # also a contact sheet

The sheet is the same list of moments the old sheet used (the boot, the four intro
layers, the handover, A①, the rewrite, the interlude, A③), PLUS one frame per A① shot
from the shot table — because the ten cuts are the thing that has to be judged as a
sequence, and a single still cannot show whether the rhythm of the cuts works.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

import scene4
import shots

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "views"
OUT.mkdir(parents=True, exist_ok=True)

# name, t — the moments that decide whether the film works
MOMENTS = [
    ("01-t02-dark", 2.0),
    ("02-t04-tray", 4.0),
    ("03-t08-sky", 8.5),
    ("04-t22-terrain", 22.0),
    ("05-t40-full", 40.0),
    ("06-t65-ready", 65.5),
    ("07-t80-A1", 80.0),
    ("08-t95-rewrite", 95.5),
    ("09-t150-interlude", 150.0),
    ("10-t320-A3", 320.0),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a1", action="store_true", help="only the A① shot sheet")
    ap.add_argument("--contact", action="store_true", help="also write a contact sheet")
    args = ap.parse_args()

    made = []
    if not args.a1:
        for name, t in MOMENTS:
            p = OUT / f"{name}.png"
            scene4.frame(t).save(p)
            made.append(p)
            print("wrote", p.name)

    # the A① shot sheet: one frame per shot, at the middle of the shot
    for name, t0, t1, mode in shots.SNAPPED:
        t = t0 + (t1 - t0) * 0.5
        p = OUT / f"a1-{name}.png"
        scene4.frame(t).save(p)
        made.append(p)
        print("wrote", p.name)

    if args.contact:
        _contact(made)
    print(f"\n{len(made)} views -> {OUT}")


def _contact(paths):
    """A contact sheet, so a whole sequence can be judged in one look."""
    cols = 3
    tw = 420
    th = int(tw * 720 / 1280)
    lh = 16
    rows = (len(paths) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tw, rows * (th + lh)), (18, 18, 18))
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 12)
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        x = (i % cols) * tw
        y = (i // cols) * (th + lh)
        canvas.paste(im, (x, y))
        d.text((x + 4, y + th + 2), p.stem, font=f, fill=(220, 220, 90))
    out = ROOT / ".scratch" / "views-v4.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print("wrote", out, canvas.size)


if __name__ == "__main__":
    main()
