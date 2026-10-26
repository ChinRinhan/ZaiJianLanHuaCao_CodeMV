# -*- coding: utf-8 -*-
"""build: the tower — render one chapter as a floor, then restack the master film.

    python build.py status     # which floors are up
    python build.py 1          # render floor 1 (ch1, 0-124s) and restack the master
    python build.py 2 3        # render floors 2 and 3, then restack
    python build.py all        # render every floor not yet on disk
    python build.py join       # restack only — no rendering

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
FF = ROOT / "tools" / "ffmpeg.exe"
FP = ROOT / "tools" / "ffprobe.exe"
SONG = ROOT / "input" / "song.flac"
PARTS = ROOT / "out" / "parts"
MASTER = ROOT / "out" / "film-v2.mp4"
PY = sys.executable

sys.path.insert(0, str(SRC))
from chapter import CHAPTERS  # noqa: E402  the floor table


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
    if cmd == "status":
        status()
        return
    if cmd == "join":
        join()
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
