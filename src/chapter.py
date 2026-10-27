# -*- coding: utf-8 -*-
"""chapter: render one 篇章 (chapter) of the film, plus its key frames.

The film is a pure function of time, so any range renders on its own — a chapter can be
re-rendered without touching the rest, which is the whole point of working in chapters:
the director reviews ~2 minutes, points at a second, and only that chapter is rebuilt.

Chapter boundaries follow 再见兰花草-段落结构.md (v2), which splits the song the way the
record itself does — not into equal pieces. 1 → 2:08 is 前奏 + A① + B①, i.e. everything
before the interlude.

    python chapter.py 1                 # render chapter 1
    python chapter.py 1 --stills-only   # just the key frames, faster for a look
    python chapter.py --list
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FPS = 24

# (id, name, start, end, what it is)
CHAPTERS = [
    ("1", "ch1-before-interlude", 0.0, 136.6,
     "前奏四层乐器 → A① 四次改写 → B① 整屏大字 → 呐喊（2:16 人声落尽）"),
    ("2", "ch2-interlude", 136.6, 245.79,
     "间奏：收尾 → 钢琴 → 小提琴×钢琴 → 贝斯 → 吉他咆哮 → 收冷"),
    # 2026-10-27 07:3x：ch3 拆成两篇。B② 是独立的一篇（它有自己的起承转合：后退→抽空→
    # 归零→点名），A② 是另一篇。这样"一篇一篇"的纪律才落得到楼层上，而不是一章 66 秒。
    ("3", "ch3-b2", 245.79, 266.31,
     "B② 第二次要五分钟：机器后退 → 抽空 → 表盘归零 → CH 1–6 点名（六人齐唱）"),
    ("4", "ch4-a2", 266.31, 312.45,
     "A② 带唱第一轮，两个半块（啊预备唱 / 第二步）"),
    ("5", "ch5-a3-peak", 312.45, 358.92,
     "A③ 顶点：全片最亮、兰丛、两个半块（升key / 再升）"),
    ("6", "ch6-a4-rewrite", 358.92, 387.0,
     "A④ 减法 → REWRITE 05 → GAME SET → 硬切"),
    ("7", "ch7-outro", 387.0, 395.667,
     "3% 黑 + 光标 + [谢谢收听]"),
]

SONG_END = 395.667


def check_floors() -> list[str]:
    """The six floors must tile 0..395.667 with no gap and no overlap.

    plan/16 §0「断言式时间轴」的第二半：原案在 engine.py:355-362 断言整首歌被镜头盖满，
    我们之前只对 A① 有 check_coverage()，楼层之间没有任何校验——段落漏了、叠了，只能靠
    人眼在成片里发现。这里补上。
    """
    problems = []
    prev = None
    for cid, name, t0, t1, _desc in CHAPTERS:
        if prev is not None and abs(t0 - prev) > 1e-6:
            problems.append(f"floor {cid} ({name}) starts {t0}, previous floor ended {prev}")
        if t1 <= t0:
            problems.append(f"floor {cid} ({name}) has non-positive length {t1 - t0}")
        prev = t1
    if abs(CHAPTERS[0][2] - 0.0) > 1e-6:
        problems.append(f"first floor starts {CHAPTERS[0][2]}, expected 0")
    if abs(prev - SONG_END) > 1e-6:
        problems.append(f"last floor ends {prev}, expected {SONG_END}")
    return problems


def assert_floors() -> None:
    probs = check_floors()
    if probs:
        raise ValueError("floor table does not tile 0..%.3f: %s"
                         % (SONG_END, "; ".join(probs)))


# one key frame every ~7 s, plus every chapter boundary and every named moment
STILLS = {
    "1": [1.0, 3.0, 6.0, 9.0, 12.5, 21.0, 30.0, 40.0, 50.0, 58.0, 66.0,
          68.5, 72.0, 76.0, 80.0, 86.0, 92.0, 96.0, 100.0, 103.0,
          105.0, 107.0, 110.0, 113.0, 116.0, 119.0, 122.0, 126.0, 130.0, 134.0, 136.0],
    "2": [138.0, 142.0, 145.0, 150.0, 156.0, 162.0, 170.0, 180.0,
          190.0, 196.0, 205.0, 212.0, 220.0, 228.0, 236.0, 243.0],
    "3": [246.0, 248.5, 250.2, 252.3, 256.0, 260.9, 263.0, 264.5, 265.1, 265.6, 266.2],
    "4": [267.0, 272.0, 280.0, 288.0, 291.0, 297.0, 305.0, 311.0],
    "5": [314.0, 320.0, 327.0, 333.0, 337.0, 342.0, 350.0, 356.0],
    "6": [360.0, 366.0, 372.0, 378.0, 382.0, 384.0, 386.0, 386.6],
    "7": [387.5, 389.0, 391.5, 393.0, 394.5],
}


def chapter_by_id(cid: str):
    for c in CHAPTERS:
        if c[0] == cid:
            return c
    raise SystemExit(f"unknown chapter {cid!r}; try --list")


def render_stills(cid: str, t0: float, t1: float) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import scene4                      # 2026-10-27: 审片入口之前还指着旧 scene（plan/24 §5-1）

    d = OUT / f"stills-ch{cid}"
    d.mkdir(parents=True, exist_ok=True)
    for t in STILLS.get(cid, []):
        if not (t0 <= t <= t1):
            continue
        scene4.frame(t).save(d / f"{t:07.2f}.png")
    print(f"stills -> {d}  ({len(list(d.glob('*.png')))} frames)")


def render_video(cid: str, name: str, t0: float, t1: float, workers: int) -> None:
    cmd = [sys.executable, str(Path(__file__).resolve().parent / "render.py"),
           f"{t0}", f"{t1}", f"{name}.mp4", "--workers", str(workers), "--scene", "scene4"]
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter", nargs="?", help="chapter id, e.g. 1")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--stills-only", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if args.list or not args.chapter:
        for cid, name, t0, t1, desc in CHAPTERS:
            print(f"  {cid}  {t0:6.2f}-{t1:6.2f}  ({t1 - t0:5.1f}s)  {name}\n     {desc}")
        return

    cid, name, t0, t1, desc = chapter_by_id(args.chapter)
    print(f"chapter {cid}: {t0:.2f}..{t1:.2f}  ({t1 - t0:.1f}s, {int((t1 - t0) * FPS)} frames)")
    print(f"  {desc}")
    render_stills(cid, t0, t1)
    if not args.stills_only:
        render_video(cid, name, t0, t1, args.workers)


if __name__ == "__main__":
    main()
