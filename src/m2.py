# -*- coding: utf-8 -*-
"""M2 stills: the three lines from plan/04 (veil / fifth rewrite / machine death).

Renders into out/m2/ so the M1 stills in out/preview/ stay untouched.
"""
from __future__ import annotations
from pathlib import Path

from PIL import Image, ImageDraw

import tk
import preview

OUT = Path(__file__).resolve().parents[1] / "out" / "m2"
OUT.mkdir(parents=True, exist_ok=True)


def typed_title(t: float) -> str:
    """0.55 再 / 0.75 见 / ——— 0.6 s 空 ——— / 1.35 兰 / 1.55 花 / 1.75 草

    The space before 兰花草 only appears once typing resumes — that gap IS the breath.
    """
    sched = [(0.55, "再"), (0.75, "见"), (1.35, "兰"), (1.55, "花"), (1.75, "草")]
    s = "".join(ch for tt, ch in sched if t >= tt)
    if len(s) >= 3:
        s = s[:2] + " " + s[2:]
    return s


def title_still(t: float, cursor: bool) -> Image.Image:
    return preview.cover_card(t, title=typed_title(t), cursor=cursor)


def main():
    shots = [
        ("t1-title-1000ms-gap.png", title_still(1.00, True)),
        ("t2-title-1900ms-full.png", title_still(1.90, False)),
        ("e1-3830-rewrite05.png", preview.compose(
            383.0, boot=0.55, score=0.0, level=0.12, mood=0.0, flower=0.30,
            entity=0.0, seed=17, glow=0.18, progress=383.0 / 395.667,
            collapsed=True, amp_scale=0.45, flower_x=0.5, rewrite05=True,
            world_fade=0.3)),
        ("e2-3865-gameset.png", preview.ending_frame(386.5, cursor_on=True)),
        ("e3-3890-black3.png", preview.black_frame(389.0, cursor_on=True)),
    ]
    for name, im in shots:
        p = OUT / name
        im.save(p)
        print("wrote", p)


if __name__ == "__main__":
    main()
