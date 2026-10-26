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

# ---- the intro: four instruments light up one at a time ----------------------
# The analysis video's captions name the order (plan/18 §5.1) and the stems confirm the
# layer times: violin alone at 8-12 s (drums/bass are at -69 dB there), the band hits at
# 20-24 s, piano/violin/electric guitar stack from 36 s, the loudest stacking at 48-64 s,
# everything drops at 64 s to leave the voice alone.
# Our previous design ("one character grows into a mountain") had no support in the audio:
# the intro is not empty, it is four layers arriving. Each layer now has a visible event.
INTRO_LAYERS = [
    # t, label, which layer becomes visible
    (8.0, "VIOLIN", "entity"),    # a single high sustained line
    (20.0, "BAND", "rain"),       # drums + guitar: the first hit, rain starts
    (36.0, "PIANO", "flower"),    # piano enters: the first bloom appears
    (48.0, "GUITAR", "spiral"),   # electric guitar: the loudest stacking
    (64.0, "VOICE", None),        # everything drops; the machine waits for the voice
]


# ---- the intro: the machine powers up one module per lift --------------------
# The director's note: "这个开场不错，后续又这个CRT上电再衍生出其他的，比如09 10期间的小起伏，
# 20和40处同理，前奏每一个起伏就CRT上电出不同模块".
#
# So the CRT reveal is not a one-off for the opening: it is the film's grammar for bringing
# anything on line. Every lift in the intro boots another module of the same machine, each with
# its own aperture and its own read-outs. The lift times are measured, not guessed (see the
# dB table in plan/19): each row below is a real +3..+13 dB jump in the mix, and the stem
# columns say which instrument caused it.
#
#   t      dB    what actually happens (stems)                    module that powers on
#   8.0   +6.7   violin alone; drums/bass still -65/-58            LIGHT METER   (level starts moving)
#  15.0   +4.1   violin sustained, still no drums                 WAVEFORM      (a trace starts drawing)
#  20.0   +8.7   the band hits: drums -46->-34, bass -43->-30     SPECTRUM      (22 bands light up)
#  32.0   +8.7   piano/violin stack enters                       TRACK LIST    (the 13 tracks list)
#  38.0   +5.3   everything: drums -52->-35, bass -46->-33        SCORE + CH    (the scoring block)
#  42.0   +6.8   electric guitar enters                           TICKER        (the log line starts)
#  47.0   +7.6   drums -28, bass -25: the loudest stack           SLEEVE        (cover art block)
#  64.0  -10.8   everything drops; the machine waits for a voice  all modules idle, dim
INTRO_BOOTS = [
    # t, module id, the label printed in its title bar
    (8.0, "meter", "LEVEL METER"),
    (15.0, "wave", "WAVEFORM 100 Hz"),
    (20.0, "spectrum", "SPECTRUM  22 BAND"),
    (32.0, "playlist", "PLAYLIST  13 TRACKS"),
    (38.0, "score", "SCORE / CHANNELS"),
    (42.0, "ticker", "SYSLOG"),
    (47.0, "sleeve", "SLEEVE"),
]


def intro_boot_state(t: float):
    """How many modules are powered on, and how far the newest one is through its CRT reveal."""
    n = 0
    newest_u = 1.0
    for t_at, _mid, _lab in INTRO_BOOTS:
        if t >= t_at:
            n += 1
            newest_u = min(1.0, (t - t_at) / 0.55)
    return n, newest_u


def intro_layer(t: float) -> float:
    """How many of the four musical layers have arrived (0..4)."""
    return sum(1 for lt, _, _ in INTRO_LAYERS if t >= lt)


SECTIONS = [
    # Structure follows 再见兰花草-段落结构.md (v2) — the doc the director pointed at.
    # That doc's own table has ±1 s error, so exact sung times still come from the LRC and the
    # stem envelopes; what we take from it is the SHAPE: 8 sections, and the 23/23/23/23/23/13
    # half-block rhythm of the back half (its §2.1, "全曲唯一的节奏突变").
    # id, start, end, mood, cold, flower, entity, rain, spiral, amp, flower_x, count
    ("intro", 0.0, 67.85, 0.00, 0.00, 0.00, 0.00, 0.00, 0.0, 0.55, 0.72, 1),
    ("A1", 67.85, 103.84, 0.12, 0.00, 0.55, 0.55, 0.10, 0.0, 0.85, 0.72, 1),
    # B① ends at 124 s per the doc (2:04), not at the last sung syllable (121.9). The shout
    # (呐喊) sits at 124-136 and belongs to the interlude's opening blast, not to B①.
    ("B1", 103.84, 124.0, 0.35, 0.00, 0.65, 0.70, 0.15, 0.3, 1.00, 0.70, 1),
    ("B2", 245.79, 266.31, 0.10, 0.00, 0.60, 0.35, 0.00, 0.0, 0.80, 0.70, 1),
    # A②/A③ are each two 23 s half-blocks (doc §2.1); each half gets its own cue line.
    ("A2a", 266.31, 289.64, 0.00, 0.30, 0.80, 0.80, 0.10, 0.2, 1.00, 0.66, 3),
    ("A2b", 289.64, 312.45, 0.00, 0.40, 0.82, 0.82, 0.12, 0.3, 1.05, 0.66, 3),
    ("A3a", 312.45, 334.69, 0.00, 1.00, 1.00, 0.95, 0.25, 1.0, 1.20, 0.62, 5),
    ("A3b", 334.69, 358.92, 0.00, 1.00, 1.00, 0.95, 0.25, 1.0, 1.20, 0.62, 5),
    # A④ is subtraction, not a fourth build-up (plan/03 §4). Split at 380.99 = its own
    # half-block boundary, and the shot list has 22.1 s + 6 s of "最后只唱两句".
    ("A4a", 358.92, 380.99, 0.00, 0.10, 0.45, 0.00, 0.00, 0.0, 0.55, 0.50, 1),
    ("A4b", 380.99, 386.5, 0.00, 0.05, 0.42, 0.00, 0.00, 0.0, 0.48, 0.50, 1),
]


def rms_at(t: float) -> float:
    i = int(t * RMS_HZ)
    if i < 0 or i >= len(RMS):
        return 0.0
    seg = RMS[max(0, i - 12):i + 12]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def section_at(t: float):
    """The design section for t. The interlude resolves to its named movement, so the picture
    can follow the instrument that is playing rather than a single 121-second block."""
    if 124.0 <= t < 245.79:
        for s in BREAK_SECTIONS:
            if s[1] <= t < s[2]:
                return s
    for s in SECTIONS:
        if s[1] <= t < s[2]:
            return s
    return SECTIONS[-1]


# ---- the 121-second interlude, in seven movements ----------------------------
# The doc puts the interlude at 2:04-4:05 (124-245). The analysis video's captions then name
# the instruments movement by movement, and the stem table (plan/18 §6) matches it window for
# window, so each movement can be designed around an instrument instead of an energy level.
#
#   window     OCR caption (B站解析)                  stems (dBFS)            design
#   124-138    "随着鼓的重击，宝哥发出高亢响亮的呐喊"   vocals -28~-33          the shout: full blast
#   138-146.5  "呐喊结束，电吉他与鼓收尾"               drums -29 bass -31      the tail, thinning
#   147-162    "细小的钢琴声…像巴赫的巴洛克"            only other -39.3        almost dark: one thin line
#   162-190    "小提琴与钢琴交互进行"                   only other -30.8        two lines trading
#   190-212    "贝斯清晰可闻，电吉他以不同方式咆哮"     bass -31.7 drums -34.2  bass visible again
#   212-230    "电吉他尽情咆哮"                         drums -25.3 (loudest)   full-on, beat drives it
#   230-245.79 同上（人声轨空）                         drums -25.5             thinning into B②
BREAK_SECTIONS = [
    # id, start, end, mood, cold, flower, entity, rain, spiral, amp, flower_x, count
    ("shout", 124.00, 138.0, 0.40, 0.00, 0.60, 0.70, 0.05, 0.5, 1.10, 0.72, 1),
    ("boutro", 138.0, 147.0, 0.30, 0.00, 0.52, 0.35, 0.00, 0.2, 0.75, 0.72, 1),
    ("piano", 147.0, 162.0, 0.20, 0.10, 0.30, 0.00, 0.00, 0.0, 0.28, 0.72, 1),
    ("duet", 162.0, 190.0, 0.25, 0.05, 0.40, 0.00, 0.00, 0.0, 0.40, 0.60, 1),
    ("bass", 190.0, 212.0, 0.30, 0.00, 0.45, 0.00, 0.00, 0.0, 0.55, 0.78, 1),
    ("roar", 212.0, 230.0, 0.35, 0.00, 0.55, 0.45, 0.00, 0.4, 1.00, 0.72, 1),
    ("cool", 230.0, 245.79, 0.30, 0.00, 0.50, 0.35, 0.00, 0.2, 0.90, 0.72, 1),
]

# the framing of each movement: a different camera, not a different filter (plan/03 §2.1)
# (ridge offset px, ridge scale multiplier, floor line: 0=high horizon, 1=low)
BREAK_CAMERA = {
    "shout": (0.0, 1.15, 0.70),    # full blast: widest, tallest
    "boutro": (-20.0, 0.95, 0.66),
    "piano": (0.0, 0.55, 0.42),    # almost empty: a single thin line, high in the frame
    "duet": (-60.0, 0.70, 0.52),   # pans left, two lines trading
    "bass": (40.0, 0.85, 0.66),    # comes back right, bass visible: low horizon
    "roar": (0.0, 1.20, 0.72),     # the loudest movement
    "cool": (-20.0, 0.95, 0.64),
}


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
    if t < 124.0:
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


# ---- UNDO: the one capability an editing program cannot reproduce -----------------
# plan/16 §2.3, the third of the five difference points: "A④ 给一次 0.6 秒的 undo——字从新
# 变回旧，再变回新。" In A④ the first line is "谁从山中来带着兰花草" (REWRITE 01's new
# version). For 0.6 s the machine puts the 1921 character back: "我". Then it returns to "谁".
# This is pure-function rendering's own gesture — no NLE can "调回某一帧的某个字".
# Exactly once in the film. Twice would turn the thesis into a trick.
UNDO_AT = 359.90
UNDO_HOLD = 0.60
UNDO_CHAR = (0, "我")      # index into the line, the pre-rewrite glyph


def undo_at(t: float):
    """(char_index, old_char) during the 0.6 s undo window, else None."""
    if not (UNDO_AT <= t < UNDO_AT + UNDO_HOLD):
        return None
    cur, _ = line_at(t)
    if not cur or not cur["text"].startswith("谁"):
        return None
    return UNDO_CHAR


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
    if 103.84 <= t < 124.0:
        w, a_in, a_out = _b1_word(t)
        if w:
            b1_big = w
            b1_alpha = a_in * a_out
            # the same words must not also crawl through the LCD: one text, one place
            lyric = ("", "")
            pen = None

    # ---- the intro: four instruments light up one at a time --------------------
    # 0-8 s nothing but the machine and a dark world (the disc has just gone in)
    # 8 s   violin alone          -> the light column appears
    # 20 s  drums + guitar hit    -> rain begins
    # 36 s  piano enters          -> the pot appears
    # 48 s  electric guitar       -> the rays; the loudest stacking of the intro
    # 64 s  everything drops      -> all four go quiet, the machine waits for the voice
    intro_extra = {}
    if t < 67.85:
        n = intro_layer(t)
        ramp = lambda k: min(1.0, max(0.0, (t - (INTRO_LAYERS[k][0] - 0.6)) / 1.2))
        # The right pane stays DARK for the whole intro. The intro is the machine getting
        # itself ready; the world has not been put on yet. It arrives with the first sung line
        # at 67.85, which is also when the mountain is supposed to exist (plan/09 §4: "A① 是
        # 全片唯一人还在的时刻，此时世界应该是空的").
        idle = 1.0 if t < 64.0 else max(0.0, 1 - (t - 64) / 3.0)
        intro_extra = {
            "entity": 0.30 * ramp(0) * idle * 0.35,
            "rain": 0.0,
            "flower": 0.0,
            "spiral": 0.0,
            "w_terrain": 0.06 + 0.10 * ramp(3),
        }
        entity = intro_extra["entity"]
        rain = intro_extra["rain"]
        flower = intro_extra["flower"]
        spiral = intro_extra["spiral"]
    w_terrain = intro_extra.get("w_terrain", 1.0)

    # ---- the interlude: each movement gets its own framing ----------------------
    cam = BREAK_CAMERA.get(_id)
    if cam:
        w_terrain = min(w_terrain, 0.92)

    # ---- A④ is subtraction from its first frame ----
    # plan/03 §4: "把 A④ 拍成减法——花田退回一株、网格退回基准、颜色褪成单色、评分归零、
    # 播放列表缩成一行". The retreat is one continuous curve across the whole 27.6 s
    # (358.92-386.5), not a switch that only starts when REWRITE 05 opens.
    a4_w = None
    if 358.92 <= t < 386.5:
        u4 = (t - 358.92) / (386.5 - 358.92)
        a4_w = {
            "w_terrain": 1.0 - 0.90 * u4,
            "w_beam": 1.0 - 1.00 * u4,
            "w_hud": 1.0 - 0.62 * u4,
        }
    if a4_w:
        w_terrain = a4_w["w_terrain"]

    # the instrument plate: absent through the intro (nothing has been wired up yet), then it
    # fades in as the world does at 64-68 s, then A④ drains it.
    if t < 67.85:
        w_hud = 0.0 if t < 64.0 else min(1.0, (t - 64.0) / 3.85)
    elif a4_w:
        w_hud = a4_w["w_hud"]
    else:
        w_hud = 1.0

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
        w_terrain=w_terrain,
        w_beam=a4_w["w_beam"] if a4_w else None,
        w_hud=a4_w["w_hud"] if a4_w else 1.0,
        camera=cam,
        undo=undo_at(t),
        intro_mode=(t < 67.85),
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


REWRITE05_AT = 386.1


def _ending_run(t: float):
    """386.1-386.5: the last line finishes, the machine opens a fifth rewrite.

    The A④ contract (plan/03 §4, plan/05 §7): no additions, only subtraction. The flower
    field is back to one pot, the list is one line, the score is zero.

    NOTE ON TIMING. This used to start at 383.0, which suppressed the lyric band while the
    voice was still singing (the vocal stem does not go quiet until 386.8 s, and the last
    line "梵音在弦外醉翁意韵妙" is sung across 385.94-386.78). Showing an empty REWRITE 05 over
    a line that is audibly being sung is a fact error, not a style choice. So REWRITE 05 now
    opens at 386.1 — after the last glyph — and the lyric band keeps its only job until then.
    """
    u = min(1.0, max(0.0, (t - 380.99) / (386.5 - 380.99)))   # 0 at A④ start, 1 at GAME SET
    cur, nxt = line_at(t)
    still_singing = cur is not None and _line_end(cur) > t
    return preview.compose(
        t,
        boot=0.55,
        lyric=(cur["text"], "") if still_singing else ("", ""),
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
        pen_times=(cur.get("times") if still_singing else None),
        w_terrain=1.0 - 0.82 * u,          # the mountain thins to a horizon line
        w_beam=1.0 - u,                    # no more light column
        w_hud=1.0 - 0.35 * u,              # the machine keeps measuring longest
    )
