# -*- coding: utf-8 -*-
"""scene: map song time -> one frame of the film.

Frame = f(t). No cross-frame state. Video time = LRC time + OFFSET (the LRC runs 0.90 s early,
measured by cross-correlating 53 lyric lines against the vocal-band onset envelope).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

import preview
import tk
import clock

ROOT = Path(__file__).resolve().parents[1]
TL = json.loads((ROOT / "data" / "timeline.json").read_text(encoding="utf-8"))
OFFSET = 0.0          # LRC is the reference; +0.90 was a bad estimate (locked onto sustained vocal energy)
LEAD = 0.06           # lyrics appear a hair before the attack, like a real karaoke machine
FPS = 24
DUR = 395.667
END_CUT = 387.0       # audio is dead from here; the picture is cut, not faded (plan/03 §3.5)

_CUE_RE = re.compile(r"[（(]([^）)]*)[）)]")


def _split_cue(text: str):
    """The LRC stores the four sing-along instructions inline, e.g.
    '（啊预备唱）谁从山中来带着兰花草'. They are stage directions, not lyrics, and must not be
    typed into the lyric band (plan/15 §3.2 #4). Returns (cue, lyric)."""
    cues = _CUE_RE.findall(text)
    body = _CUE_RE.sub("", text).strip()
    cue = cues[0].strip() if cues else None
    return cue, body


_TLL = [l for l in TL["lines"] if l["t"] >= 5]
LINES = []
for _l in _TLL:
    _cue, _body = _split_cue(_l["text"])
    LINES.append({"t": _l["t"] + OFFSET - LEAD, "text": _body, "cue": _cue,
                  "cue_at": _l["t"] + OFFSET})

# per-character sung times, snapped to the beat grid (see clock.py / word_times.json)
_WT_PATH = ROOT / "data" / "word_times.json"
if _WT_PATH.exists():
    _WT = json.loads(_WT_PATH.read_text(encoding="utf-8"))["lines"]
    for _ln, _w in zip(LINES, _WT):
        if _split_cue(_w["text"])[1] == _ln["text"]:
            # the word table still carries the leading instruction; drop those characters so
            # index i lines up with the cleaned lyric
            _times = [x + OFFSET - LEAD for x in _w["times"]]
            _cut = len(_split_cue(_w["text"])[0]) + 2 if _split_cue(_w["text"])[0] else 0
            _ln["times"] = _times[_cut:][:len(_ln["text"])] if _cut else _times[:len(_ln["text"])]
RMS = np.load(ROOT / "data" / "audio" / "rms.npy")
RMS_HZ = 100.0

# the four displacements of A①, on video time
REWRITES = [
    {"at": LINES[0]["t"], "old": "我从山中来 带着兰花草", "new": "谁从山中来 带着兰花草", "idx": 0, "label": "REWRITE 01"},
    {"at": LINES[1]["t"], "old": "种在小园中 希望花开好", "new": "也曾勤灌溉 长得一园好", "idx": -1, "label": "REWRITE 02"},
    {"at": LINES[7]["t"], "old": "一日望三回", "new": "茶花樱花满山开 杜鹃木棉沿街栽", "idx": -1, "label": "REWRITE 03"},
    {"at": LINES[9]["t"], "old": "祝汝满盆花", "new": "谁记得曾经有那一盆兰花草", "idx": -1, "label": "REWRITE 04"},
]
REWRITE_HOLD = 2.6          # seconds a diff stays on screen when its line starts
BREAK = 2.0                 # a gap longer than this means the line must clear (reference words.py)

SECTIONS = [
    # id, start, end, mood, cold, flower, entity, rain, spiral, amp, flower_x, count
    ("intro", 0.0, 67.85, 0.00, 0.00, 0.00, 0.00, 0.00, 0.0, 0.55, 0.72, 1),
    ("A1", 67.85, 103.84, 0.12, 0.00, 0.55, 0.55, 0.10, 0.0, 0.85, 0.72, 1),
    ("B1", 103.84, 122.0, 0.35, 0.00, 0.65, 0.70, 0.15, 0.3, 1.00, 0.70, 1),
    ("break", 122.0, 245.79, 0.25, 0.00, 0.55, 0.60, 0.00, 0.0, 0.55, 0.72, 1),
    ("B2", 245.79, 266.31, 0.10, 0.00, 0.60, 0.35, 0.00, 0.0, 0.80, 0.70, 1),
    ("A2", 266.31, 312.45, 0.00, 0.35, 0.80, 0.80, 0.10, 0.2, 1.00, 0.66, 3),
    ("A3", 312.45, 358.92, 0.00, 1.00, 1.00, 0.95, 0.25, 1.0, 1.20, 0.62, 5),
    # A④ is subtraction, not a fourth build-up (plan/03 §4): no beam, no rain, no spiral,
    # one potted plant. Leaving entity=0.25 here lit a stray column over the empty mountain.
    ("A4", 358.92, 380.99, 0.00, 0.10, 0.45, 0.00, 0.00, 0.0, 0.55, 0.50, 1),
]


def rms_at(t: float) -> float:
    i = int(t * RMS_HZ)
    if i < 0 or i >= len(RMS):
        return 0.0
    seg = RMS[max(0, i - 12):i + 12]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def section_at(t: float):
    for s in SECTIONS:
        if s[1] <= t < s[2]:
            return s
    return SECTIONS[-1]


def _line_end(line: dict) -> float:
    """When the line itself stops being sung — NOT when the next line starts.

    This distinction is the whole bug. The reference words.py:57 compares the *gap after the
    line's own end*. Using the next line's start as "end" means a line followed by a 124-second
    interlude is treated as lasting 124 seconds, so it never clears.
    """
    times = line.get("times")
    if times:
        last = times[-1]
        n = max(1, len(times))
        step = (times[-1] - times[0]) / (n - 1) if n > 1 else 0.4
        return last + max(0.25, step * 1.6)
    return line["t"] + 2.6


def line_at(t: float):
    """The lyric being sung, or None.

    A line lives from its own start until one beat after its own end (that extra beat is the
    "尾音"), then fades over another beat — but only when the gap to the next line is longer
    than BREAK. Inside a continuous run of lines there is no tail, the next line starts immediately.
    """
    cur = None
    nxt = None
    for i, l in enumerate(LINES):
        if l["t"] <= t:
            cur = l
            nxt = LINES[i + 1] if i + 1 < len(LINES) else None
        else:
            break
    if cur is None:
        return None, None
    end = _line_end(cur)
    nxt_t = nxt["t"] if nxt else DUR
    if nxt_t - end > BREAK:
        beat = clock.beat_len(end)
        if t > end + 2 * beat:
            return None, nxt
    return cur, nxt


def line_alpha(t: float) -> float:
    """1.0 while the line is live, ramping to 0 across the fade beat after a long tail."""
    cur, nxt = line_at(t)
    if cur is None:
        return 0.0
    end = _line_end(cur)
    nxt_t = nxt["t"] if nxt else DUR
    if nxt_t - end <= BREAK:
        return 1.0
    beat = clock.beat_len(end)
    fade_start = end + beat
    fade_end = end + 2 * beat
    if t <= fade_start:
        return 1.0
    if t >= fade_end:
        return 0.0
    return 1.0 - (t - fade_start) / max(1e-6, fade_end - fade_start)


def rewrite_at(t: float):
    for r in REWRITES:
        if r["at"] <= t < r["at"] + REWRITE_HOLD:
            return (r["old"], r["new"], r["idx"], r["label"])
    return None


def score_at(t: float) -> float:
    if t < 67.85:
        return 0.0
    if t < 103.84:
        return 61.0 + 17.0 * (t - 67.85) / 36.0
    if t < 122.0:
        return 99.4
    if t < 245.79:
        return 0.0
    if t < 266.31:
        return 0.0
    if t < 312.45:
        return 70.0 + 20.0 * (t - 266.31) / 46.14
    if t < 358.92:
        return 99.1
    return max(0.0, 99.1 * (1 - (t - 358.92) / 22.0))


def level_at(t: float) -> float:
    r = rms_at(t)
    return max(0.02, min(1.0, (r / 0.16) ** 0.6))


def amp_at(t: float, base: float) -> float:
    """Ridge amplitude follows the low-frequency energy: quiet passages flatten the mountains."""
    return base * (0.55 + 1.05 * level_at(t))


def _b1_word(t: float):
    """B① is the loudest 18 seconds of the song (-15 to -17 dB, vocal stem at -18),
    yet it was being delivered inside a 384 px lyric LCD. The reference PV proves that the
    strongest moment in a TUI piece is typography, not drawing (plan/05 §3: `942 AD`).
    So the four demands get the whole screen, one per phrase.

    只给四条「给我…」。后面「直到那一天…」「你只要给我五分钟」是释放段，不是索取，
    它们回到 LCD 里，一行一行唱完——大字用四次就够，用七次就成了字幕墙。
    """
    for i, l in enumerate(LINES):
        if l["t"] <= t and l["text"].startswith("给我"):
            nxt = LINES[i + 1]["t"] if i + 1 < len(LINES) else l["t"] + 2.2
            if l["t"] <= t < nxt:
                a_in = min(1.0, (t - l["t"]) / 0.28)
                a_out = min(1.0, max(0.0, (nxt - t) / 0.26))
                return l["text"], a_in, a_out
    return None, 0.0, 0.0


def _normal(t: float):
    s = section_at(t)
    _id, _s, _e, mood, cold, flower, entity, rain, spiral, amp, fx, cnt = s
    cur, nxt = line_at(t)
    rw = rewrite_at(t)
    la = line_alpha(t)
    lyric = ("", "")
    if cur and not rw and la > 0.01:
        lyric = (cur["text"], nxt["text"] if nxt else "")
    progress = t / DUR
    pen = None
    if cur and not rw and lyric[0]:
        span = min(_line_end(cur), nxt["t"] if nxt else _line_end(cur)) - cur["t"]
        pen = min(1.0, max(0.0, (t - cur["t"]) / max(0.5, span * 0.86)))

    # the four stage directions are shown as cues, in their own red line, never as lyric text
    cue = None
    if cur and cur.get("cue") and t >= cur["cue_at"] - LEAD:
        cue = cur["cue"].upper() if cur["cue"].isascii() else cur["cue"]

    # B①: the demands are stamped across the whole screen, not typed into the LCD
    b1_big = None
    b1_alpha = 0.0
    if 103.84 <= t < 122.0:
        w, a_in, a_out = _b1_word(t)
        if w:
            b1_big = w
            b1_alpha = a_in * a_out
            # the same words must not also crawl through the LCD: one text, one place
            lyric = ("", "")
            pen = None

    return preview.compose(
        t,
        boot=1.0 if t >= 8.0 else max(0.12, t / 8.0),
        lyric=lyric,
        cue=cue,
        score=score_at(t),
        level=level_at(t),
        mood=mood, cold=cold, flower=flower, entity=entity, rain=rain, spiral=spiral,
        seed=11,
        glow=0.55 if cold < 0.5 else 0.75,
        progress=progress,
        amp_scale=amp_at(t, amp),
        flower_x=fx,
        flower_count=cnt,
        rewrite=rw,
        collapsed=t >= 266.31,
        pen=pen,
        pen_times=(cur.get("times") if (cur and not rw and lyric[0]) else None),
        big_b1=(b1_big, b1_alpha) if b1_big else None,
    )


def frame(t: float):
    """One frame of the film. Pure function of t.

    0-5.6 s   the disc goes in
    5.6-6.4 s crossfade into the running machine
    6.4-386.5 the song
    383.0-    REWRITE 05 opens on the LCD (empty line, cursor) while GAME SET appears
    386.5-387 GAME SET card, then a hard cut — the audio is dead from 387.0 (plan/03 §3.5)
    387.0-395 3% black with the cursor still on the empty rewrite line
    391.0-    [谢谢收听]
    393.0-    it fades; only the cursor is left
    """
    if t >= END_CUT:
        return preview.black_frame(t, cursor_on=t < DUR - 0.35, thanks=t >= 391.0, thanks_alpha=
                                   1.0 if t < 393.0 else max(0.0, 1.0 - (t - 393.0) / 1.6))
    if t >= 386.5:
        return preview.ending_frame(t, cursor_on=True)
    if t < 5.6:
        return preview.intro_scene(t)
    if t < 6.4:
        u = (t - 5.6) / 0.8
        return Image.blend(preview.intro_scene(t), _normal(t), u)
    if t >= REWRITE05_AT:
        return _ending_run(t)
    return _normal(t)


REWRITE05_AT = 383.0


def _ending_run(t: float):
    """383.0-386.5: everything retreats, then the machine opens a fifth rewrite.

    The A④ contract (plan/03 §4, plan/05 §7): no additions, only subtraction. The flower
    field goes back to one pot, the list is one line, the score is zero, and from 383.0 the
    lyric band yields to `REWRITE 05` with nothing under it.

    The three layer weights are driven to zero here — that is what "减法" means mechanically:
    the mountain thins out, the beam goes, and the instrument plate (the machine's own
    measuring) is the last thing to leave, because the machine is still there and the world is not.
    """
    u = min(1.0, max(0.0, (t - 380.99) / (386.5 - 380.99)))   # 0 at A④ start, 1 at GAME SET
    return preview.compose(
        t,
        boot=0.55,
        lyric=("", ""),
        cue=None,
        score=0.0,
        level=level_at(t),
        mood=0.0, cold=0.0,
        flower=max(0.0, 0.42 - u * 0.42),
        entity=0.0, rain=0.0, spiral=0.0,
        seed=11, glow=0.26, progress=t / DUR,
        amp_scale=amp_at(t, 0.55) * (1.0 - 0.55 * u),
        flower_x=0.50, flower_count=1,
        collapsed=True, rewrite05=True,
        w_terrain=1.0 - 0.82 * u,          # the mountain thins to a horizon line
        w_beam=1.0 - u,                    # no more light column
        w_hud=1.0 - 0.35 * u,              # the machine keeps measuring longest
    )
