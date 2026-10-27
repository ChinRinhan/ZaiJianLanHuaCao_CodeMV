# -*- coding: utf-8 -*-
"""build: the tower — render one chapter as a floor, then restack the master film.

    python build.py status     # which floors are up
    python build.py 1          # render floor 1 (ch1, 0-124s) and restack the master
    python build.py 2 3        # render floors 2 and 3, then restack
    python build.py all        # render every floor not yet on disk
    python build.py join       # restack only — no rendering
    python build.py 4k         # out/film_4k.mp4: 3x nearest-neighbour (3840x2160)

THE ONE FILE: `out/film-v2.mp4`. Every `build.py N` leaves that file holding every floor
finished so far, in order. Floors themselves are `out/parts/NN-<name>.mp4` and can be
watched alone (each carries its own audio slice).

Like a building: you only ever look at the tower. The floors are how it got there.
Re-running a number re-renders that floor alone; `join` always rebuilds the master from
the floors on disk, so the tower never depends on how it was built.

Chapters are the 段落结构 split (`chapter.py` CHAPTERS). Frames come from the `scene4`
path — the four-zone layout with the ch1 element set (disc / playlist / meters / pen).

Join is audio-exact by construction: the video streams are copied end to end and the
audio is the original FLAC from t=0, so chapter seams cannot drift.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parent
from media import FFMPEG as FF, FFPROBE as FP  # noqa: E402  tools/ 里没有就用 PATH
SONG = ROOT / "input" / "song.flac"
PARTS = ROOT / "out" / "parts"
MASTER = ROOT / "out" / "film-v2.mp4"
PY = sys.executable

sys.path.insert(0, str(SRC))
from chapter import CHAPTERS, assert_floors  # noqa: E402  the floor table


def floor_no(cid: str) -> int:
    return int(cid)


def part_path(cid: str, name: str) -> Path:
    return PARTS / f"{int(cid):02d}-{name}.mp4"


def floors_on_disk() -> dict[int, Path]:
    out = {}
    for cid, name, _t0, _t1, _d in CHAPTERS:
        p = part_path(cid, name)
        if p.exists():
            out[floor_no(cid)] = p
    return out


def render_floor(cid: str, name: str, t0: float, t1: float) -> Path:
    dst = part_path(cid, name)
    rel = dst.relative_to(ROOT / "out").as_posix()
    cmd = [PY, str(SRC / "render.py"), f"{t0:.3f}", f"{t1:.3f}", rel,
           "--workers", "8", "--scene", "scene4"]
    print(f"floor {int(cid):02d}  {t0:.2f}..{t1:.2f}s  ({t1 - t0:.1f}s, {int((t1 - t0) * 24)} frames)")
    subprocess.run(cmd, check=True)
    return dst


def join() -> None:
    """Restack the master from the floors on disk (contiguous from floor 1)."""
    have = floors_on_disk()
    if not have:
        raise SystemExit("no floors on disk — run `build.py 1` first")
    n = 1
    while n in have:
        n += 1
    used = [have[i] for i in range(1, n)]
    gap = [i for i in range(1, max(have) + 1) if i not in have]
    if gap:
        print(f"note: gap at floor(s) {gap} — they are NOT in the tower yet")

    lst = PARTS / "_concat.txt"
    PARTS.mkdir(parents=True, exist_ok=True)
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in used),
                   encoding="utf-8")
    cmd = [str(FF), "-v", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", str(lst),
           "-i", str(SONG),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
           "-shortest", "-movflags", "+faststart", str(MASTER)]
    subprocess.run(cmd, check=True)
    sz = MASTER.stat().st_size / 1048576
    print(f"tower -> {MASTER}  ({len(used)} floor(s), {sz:.1f} MB)")


def upscale(k: int = 3) -> None:
    """3840×2160：**整数倍最近邻放大**，不是重渲。

    和原案仓库（`world.execute(me);` 的 PV）同一手法——它的 `--4k` 也是
    `scale=3840:2160:flags=neighbor`。理由：这部片子的画面是"一块 1994 年的屏幕"，
    像素网格是设计的一部分；最近邻放大保住网格，读起来是"更大的屏"，不是"更糊的图"。
    真要重渲到 2160p 得把 layout4 里所有绝对坐标和字号都乘一个比例——不值得，
    而且 720p 的字体度量是逐帧调过的。

    1080p（1.5×）**故意不做**：非整数倍最近邻会让像素大小不均匀（有的 1 px、有的 2 px），
    平台需要 1080p 时从这份 4K 用 lanczos 缩下去即可。
    """
    if not MASTER.exists():
        raise SystemExit("no master — run `build.py join` first")
    w, h = 1280 * k, 720 * k
    out = ROOT / "out" / "film_4k.mp4"
    cmd = [str(FF), "-v", "error", "-y", "-i", str(MASTER),
           "-vf", f"scale={w}:{h}:flags=neighbor,format=yuv420p",
           "-c:v", "libx264", "-crf", "18", "-preset", "medium",
           "-c:a", "copy", "-movflags", "+faststart", str(out)]
    print(f"upscale {MASTER.name} -> {out.name} ({w}x{h}, x{k} neighbour)")
    subprocess.run(cmd, check=True)
    print(f"wrote {out}  ({out.stat().st_size / 1048576:.1f} MB)")


def status() -> None:
    have = floors_on_disk()
    print("floors:")
    for cid, name, t0, t1, desc in CHAPTERS:
        n = floor_no(cid)
        p = have.get(n)
        mark = "UP  " if p else "    "
        size = f"{p.stat().st_size / 1048576:5.1f} MB" if p else " " * 8
        print(f"  {mark}{n}  {t0:6.2f}-{t1:6.2f}  ({t1 - t0:5.1f}s)  {size}  {name}")
        print(f"        {desc}")
    if MASTER.exists():
        sz = MASTER.stat().st_size / 1048576
        print(f"master: {MASTER}  ({sz:.1f} MB)")
    else:
        print(f"master: {MASTER}  (not built yet)")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = args[0]
    assert_floors()          # 楼层表必须盖满 0..395.667，否则立刻停（plan/16 §0）
    if cmd == "status":
        status()
        return
    if cmd == "join":
        join()
        return
    if cmd == "4k":
        upscale(3)
        return
    if cmd == "all":
        have = floors_on_disk()
        todo = [c for c in CHAPTERS if floor_no(c[0]) not in have]
        if not todo:
            print("all floors already up")
        for cid, name, t0, t1, _d in todo:
            render_floor(cid, name, t0, t1)
        join()
        return
    want = set()
    for a in args:
        if not a.isdigit():
            raise SystemExit(f"unknown argument {a!r}; try: status | N | all | join")
        want.add(int(a))
    table = {floor_no(c[0]): c for c in CHAPTERS}
    for n in sorted(want):
        if n not in table:
            raise SystemExit(f"no floor {n}; the tower has {min(table)}..{max(table)}")
        cid, name, t0, t1, _d = table[n]
        render_floor(cid, name, t0, t1)
    join()


if __name__ == "__main__":
    main()
