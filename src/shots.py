# -*- coding: utf-8 -*-
"""shots: the A① shot table and the three layout modes it uses.

plan/14 §2.3 — the director agreed to cut A① into 10 shots. The table below is that plan,
verbatim in its timings and its intent:

    #  起      止       时长  版式  做什么 / 为什么
    1  67.85   70.55    2.7  W    建立：机器、空山、盆花
    2  70.55   76.67    6.1  P    「谁从山中来」被写出来。推近到纸面
    3  76.67   81.19    4.5  P    保持。L3/L4 慢（0.60 秒/字），不切
    4  81.19   84.00    2.8  W    L5 是全段最急（0.19 秒/字）。退回全景
    5  84.00   90.58    6.6  V    「我往山中行」——视线第一次转到山上
    6  90.58   94.83    4.3  V    不动，让花长高
    7  94.83   97.11    2.3  W    山浮现的那一下
    8  97.11   99.30    2.2  V    「杜鹃木棉沿街栽」。推回山，花最大
    9  99.30  101.90    2.6  W    「谁记得曾经有那一盆」。山满、花缩
    10 101.90  103.84    1.9  W    收束：接 B①

The three layouts (plan/14 §2.2) are the same drawing code with different rectangles:

    W 全景   entity 512 px | world | ops 80 px | token band
    P 纸面   the page only: the lyric at 34 px, centred, one horizon at the foot
    V 山景   entity collapses to a 96 px lamp strip, the world takes the frame

The cut points are on the beat grid. The grid is the measured one (data/beat_times.json,
731 beats, mean 111.29 BPM) and the sub-beat grid is 1/6 of a beat, which puts every cut
within 1.1 frames of a grid point (plan/14 §6: "每个切点与网格偏差 < 1 帧").
"""
from __future__ import annotations

import clock

# ---------------------------------------------------------------- the shot table
# name, t0, t1, mode
SHOTS = [
    ("01-establish", 67.85, 70.55, "W"),
    ("02-paper-who", 70.55, 76.67, "P"),
    ("03-paper-slow", 76.67, 81.19, "P"),
    ("04-wide-urgent", 81.19, 84.00, "W"),
    ("05-valley-turn", 84.00, 90.58, "V"),
    ("06-valley-grow", 90.58, 94.83, "V"),
    ("07-mountain", 94.83, 97.11, "W"),
    ("08-valley-full", 97.11, 99.30, "V"),
    ("09-wide-contrast", 99.30, 101.90, "W"),
    ("10-close-out", 101.90, 103.84, "W"),
]

A1_T0 = SHOTS[0][1]
A1_T1 = SHOTS[-1][2]

# The cut points are snapped to the 1/6-beat grid. The raw plan times come from the LRC,
# which is itself quantised to the beat — but the measured grid drifts, so the plan's
# round numbers can sit up to 5 frames off a real grid point. Snapping is a pure function
# of the measured beat table, so the shot list stays reproducible.
GRID_DIV = 6
GRID_TOL = 0.030          # seconds; a grid point this close wins


def _snap(t: float) -> float:
    g = clock.grid(GRID_DIV)
    best = min(g, key=lambda x: abs(x - t))
    return best if abs(best - t) <= GRID_TOL else t


def _build():
    """Snap the INTERIOR cuts to the grid, but keep the section's own boundaries exact.

    67.85 and 103.84 are the LRC's own line times — the moment the first word of A① is
    sung and the moment the last word of A① is done. Those are facts about the recording,
    not shot decisions, so they must not move. Only the cuts *between* the shots are
    staging, and those are free to land on the grid.
    """
    out = []
    for i, (name, t0, t1, mode) in enumerate(SHOTS):
        a = t0 if i == 0 else _snap(t0)
        b = t1 if i == len(SHOTS) - 1 else _snap(t1)
        out.append((name, a, b, mode))
    return out


SNAPPED = _build()


def shot_at(t: float):
    """(name, t0, t1, mode) for the shot containing t, or None outside A①."""
    for s in SNAPPED:
        if s[1] <= t < s[2]:
            return s
    return None


def mode_at(t: float) -> str:
    s = shot_at(t)
    return s[3] if s else "W"


def shot_list():
    """The table with its grid deviation, for the report."""
    rows = []
    for name, t0, t1, mode in SNAPPED:
        g = clock.grid(GRID_DIV)
        d0 = min(abs(t0 - x) for x in g)
        d1 = min(abs(t1 - x) for x in g)
        rows.append({
            "name": name, "t0": t0, "t1": t1, "mode": mode,
            "dur": t1 - t0,
            "dev0": d0, "dev1": d1,
            "dev0_frames": d0 * 24, "dev1_frames": d1 * 24,
        })
    return rows


def check_coverage():
    """plan/14 §6: the shots must tile 67.85-103.84 with no gap and no overlap."""
    problems = []
    if abs(SNAPPED[0][1] - A1_T0) > 1e-6:
        problems.append(f"first shot starts at {SNAPPED[0][1]}, expected {A1_T0}")
    if abs(SNAPPED[-1][2] - A1_T1) > 1e-6:
        problems.append(f"last shot ends at {SNAPPED[-1][2]}, expected {A1_T1}")
    for a, b in zip(SNAPPED, SNAPPED[1:]):
        if abs(a[2] - b[1]) > 1e-6:
            problems.append(f"{a[0]} ends {a[2]}, {b[0]} starts {b[1]}")
    for name, t0, t1, mode in SNAPPED:
        if t1 <= t0:
            problems.append(f"{name} has non-positive duration")
    return problems


if __name__ == "__main__":
    print("A① shot table (grid div %d)" % GRID_DIV)
    print("%-16s %8s %8s %6s %6s %s" % ("shot", "t0", "t1", "dur", "mode", "grid dev (frames)"))
    for r in shot_list():
        print("%-16s %8.3f %8.3f %6.2f %6s  %.2f / %.2f" % (
            r["name"], r["t0"], r["t1"], r["dur"], r["mode"], r["dev0_frames"], r["dev1_frames"]))
    probs = check_coverage()
    print()
    if probs:
        print("COVERAGE PROBLEMS:")
        for p in probs:
            print("  -", p)
    else:
        print("coverage OK: tiles %.2f .. %.2f with no gap" % (A1_T0, A1_T1))
    worst = max(max(r["dev0_frames"], r["dev1_frames"]) for r in shot_list())
    print("worst grid deviation: %.2f frames" % worst)
