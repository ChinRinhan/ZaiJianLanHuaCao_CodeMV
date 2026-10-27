# -*- coding: utf-8 -*-
"""The backing vocal, measured on the REAL separated stems — and the picture that follows.

导演（10:5x）：「第一次『宣言』的时候明显只有宝哥一个声音，到 4:05 的第二次的时候，就有宝哥
多音轨的和声或『合唱』，刚好预告最后的『齐唱』段」。

证据链（三步，每一步都留了探针）：

1. **Demucs 的四轨量不出来**（`probes/vocal_layers.py` / `vocal_harmony.py` /
   `vocal_pitches.py`）：它把原唱的所有人声压进 vocals 一轨，所以 1:43 与 4:05 的同时音高数
   分别是 2.57 / 2.79（差异在噪声内），而真正六人齐唱的 A② 只有 1.49。
2. **原曲分轨量得出来**（`probes/backing_vocal.py`）：导演放进仓库的 17 轨里有 `主唱人声`
   和 `背景和声` 两轨。第 4 句「给我一个空间让我转圈」的和声相对电平是
   **B① −9.7 dB → B② −5.0 dB**——合唱在第二次宣言时涌上来，主唱同时退了 2 dB。
3. **画面照这个画**（本模块）：B② 的四句各有多少层、和声有多亮，都由上面那份 JSON 决定。

所以 B② 的复声**不是编的**，是量出来的；B① 保持一个人的写法（那也是量出来的：B① 四句的
和声相对电平一直在 −8.6 ~ −9.8 dB，几乎听不见）。

层数与亮度是**连续**的，不是一刀切：相对电平每近 1 dB，和声层就更亮一点。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PATH = ROOT / "data" / "backing_vocal.json"
_PATH_FULL = ROOT / "data" / "backing_vocal_full.json"
_PATH_TAIL = ROOT / "data" / "backing_vocal_tail.json"
_PATH_WORDS = ROOT / "data" / "word_times_v2.json"

# 和声相对电平 → 画几层。分界是**量出来的**：B① 四句是 −8.6 ~ −9.8 dB（一个人），
# B② 是 −7.4 / −6.6 / −6.3 / −5.0 dB（合唱在涌上来）。所以 −8.5 以下 = 一个人，
# −8.5 ~ −6.0 = 两层，−6.0 以上 = 三层。
_LO = -8.5        # 低于这个 = 一个人（B① 全程在这一档）
_HI = -6.0         # 到这个 = 三层（B② 第 4 句 −5.0）


def _load():
    if not _PATH.exists():
        return None
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


_DATA = _load()


def _load_full():
    try:
        return json.loads(_PATH_FULL.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_tail():
    try:
        return json.loads(_PATH_TAIL.read_text(encoding="utf-8"))
    except Exception:
        return None


_FULL = _load_full()

# A③ / A④ (the last two thirds of the song) are measured separately, because they are
# the loudest chorus in the whole recording — see `src/probes/backing_vocal_tail.py`.
# They are concatenated onto the same list so every lookup sees one continuous timeline.
_TAIL = _load_tail()
if _TAIL:
    _FULL = (_FULL or []) + _TAIL


def _load_words():
    try:
        return json.loads(_PATH_WORDS.read_text(encoding="utf-8"))
    except Exception:
        return None


_WORDS = _load_words()


def char_onsets(t0: float):
    """The per-character onset times of the sung line that starts at `t0`.

    From `data/word_times_v2.json` — the measured onsets of every character (probe:
    `src/probes/align_chars.py`). The chorus uses them to make the light bands **sing**:
    without this the bands only have one dynamic (spread out / gather in), which reads as
    a diagram of the chorus rather than as six people singing it.

    Returns [] when the line is not in the table.
    """
    if not _WORDS:
        return []
    for row in _WORDS.get("lines", []):
        if abs(float(row.get("t0", -1)) - t0) < 0.02:
            return [float(x) for x in row.get("times", [])]
    return []


def line_at(t: float):
    """The sung line covering t, as (group, n, text, rel_db, voices) — or None.

    From `data/backing_vocal_full.json` (probe: src/probes/backing_vocal_full.py) plus
    `data/backing_vocal_tail.json` (probe: src/probes/backing_vocal_tail.py), which walk
    every sung line from 1:43 to the end on the director's 17-track separation.

    This is where "合唱逐渐增加" comes from as a fact rather than a wish: B① is 1 voice for
    all eight lines; B② climbs 2→2→2→3 and then drops back to 1 for its last two lines
    (the backing is -43 dB there — nobody is singing); A② moves 3,3,5,4,2,4,3,4,5,3; A③
    moves 4,4,5,3,5,5,5,5,4,4; and A④ — the end — is 6,5,5,4,4,4,6.

    So the chorus is not a fixed number of people, it is six people taking turns, and
    the *last* section is the fullest one: in A④ the backing voice sits 0.1 dB below the
    lead — the two are indistinguishable. That is what the picture has to show.
    """
    if not _FULL:
        return None
    for row in _FULL:
        if row["t0"] <= t < row["t1"]:
            return (row["group"], row["n"], row["text"],
                    float(row["rel_db"]), int(row["voices"]))
    return None


def voices_at(t: float) -> int:
    """How many voices are singing at t (1 = the lead alone)."""
    r = line_at(t)
    return r[4] if r else 1


def next_line_after(t: float):
    """The sung line that starts after t, or None.

    Used to carry the picture across the gaps *between* lines: during a gap nobody is
    singing, but the previous line's gathered chord should not blink out of existence.
    """
    if not _FULL:
        return None
    for row in _FULL:
        if row["t0"] > t:
            return row
    return None


def prev_line_before(t: float):
    """The sung line that was still sounding before t, or None.

    Note: the list has one big hole in it — B① ends at 2:02 and B② starts at 4:05 — so
    this must NOT stop at the first row that does not match; it has to keep scanning.
    (An earlier version broke out of the loop there, and then reported B②'s last line as
    the previous line for everything in A②.)
    """
    if not _FULL:
        return None
    last = None
    for row in _FULL:
        if row["t1"] <= t:
            last = row
    return last


def preceding_line(group: str, n: int):
    """The line immediately before (group, n) in the sung order, or None."""
    if not _FULL:
        return None
    idx = -1
    for i, r in enumerate(_FULL):
        if r["group"] == group and r["n"] == n:
            idx = i
            break
    if idx <= 0:
        return None
    return _FULL[idx - 1]


def layers(group: str, n: int) -> int:
    """How many voices the picture should show for sentence n (1-based) of group."""
    if not _DATA:
        return 1
    for row in _DATA.get(group, []):
        if row.get("n") == n:
            rel = float(row.get("rel_db", -12.0))
            if rel <= _LO:
                return 1
            if rel >= _HI:
                return 3
            return 2
    return 1


def rel_db(group: str, n: int) -> float:
    """The measured backing-vocal level relative to the lead (dB, negative = quieter)."""
    if not _DATA:
        return -12.0
    for row in _DATA.get(group, []):
        if row.get("n") == n:
            return float(row.get("rel_db", -12.0))
    return -12.0


def shadow_alpha(group: str, n: int) -> float:
    """How bright the backing voice is drawn (0 = invisible, 1 = as loud as the lead).

    The *order of magnitude* comes from the record: -9.7 dB (B①) is barely there,
    -5.0 dB (B②'s last line) is clearly there. The mapping to an opacity is a drawing
    decision — but it is monotonic in the measurement, and it is the same mapping for
    every line, so the picture cannot claim more choir than the record has.
    """
    rel = rel_db(group, n)
    u = max(0.0, min(1.0, (rel - _LO) / (_HI - _LO)))
    return round(0.16 + 0.40 * u, 3)


def source_note() -> str:
    return ("data/backing_vocal.json (measured on 再见 兰花草 - 张雨生_分轨: 主唱人声 vs "
            "背景和声; probe src/probes/backing_vocal.py)" if _DATA
            else "no measurement (data/backing_vocal.json missing) — drawing 1 voice")


if __name__ == "__main__":
    print(source_note())
    for g in ("B1", "B2"):
        for n in (1, 2, 3, 4):
            print("  %s #%d  rel %+6.1f dB  layers %d  shadow alpha %.3f"
                  % (g, n, rel_db(g, n), layers(g, n), shadow_alpha(g, n)))
