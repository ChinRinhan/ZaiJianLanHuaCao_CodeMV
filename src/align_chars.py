# -*- coding: utf-8 -*-
"""align_chars: per-character sung times, measured instead of spread.

plan/17 §7 offered three tiers of accuracy for the karaoke typing (档 A 词块 / 档 B 半自动 /
档 C 强制对齐). This is 档 B, done properly:

    人声轨谱通量 (spectral flux on the vocals stem)  +  网格 Viterbi (grid-constrained DP)

Why not 档 C: MMS_FA is ~1 GB of model, needs a download, and the plan's own wording says
"我们不是做卡拉OK". Why not 档 A: block-of-2-3-characters only fixes "the line starts on the
beat"; inside a block the characters are still spread evenly, which is the visible error when
one line runs 0.18 s/char and the next runs 0.61 s/char.

Why flux and not RMS: a sustained vowel keeps the RMS high, so RMS cannot see where a
syllable starts. The positive difference of the magnitude spectrum does: it spikes at the
attack and decays through the vowel. That is exactly the "onset" we want.

The DP is the same idea as the reference PV's grid Viterbi (kit.py): the cost of placing a
character is the flux at that instant, but the search is restricted to a window around the
expected time, and the path is penalised for changing pace, so a burst of onsets cannot pull
all the characters to the front of the line.

Outputs:
  data/word_times_v2.json   {bpm, phase, beat, lines: [{t0, text, times}], source, ...}
  out/align-report.md       per-line: measured vs spread, so the change can be audited

Deterministic and pure: the flux file is the only input; no randomness anywhere.

Run:
  python src/align_chars.py            # writes data/word_times_v2.json + report
  python src/align_chars.py --preview  # also draws the flux curve with the picked onsets
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "data" / "audio"
FLUX_NPY = AUD / "vocals_flux.npy"
FLUX_JSON = AUD / "vocals_flux.json"
WT_OLD = ROOT / "data" / "word_times.json"
OUT_JSON = ROOT / "data" / "word_times_v2.json"
OUT_REPORT = ROOT / "out" / "align-report.md"

# how much the search may wander from the spread-out guess, in seconds
SLACK = 0.42
# the cost of moving a character to a different instant than its neighbour's pace suggests
PACE_PENALTY = 0.55


def _load_flux():
    flux = np.load(FLUX_NPY).astype(np.float64)
    meta = json.loads(FLUX_JSON.read_text(encoding="utf-8"))
    rate = float(meta["rate"])
    # normalise to 0..1 so the DP costs are scale-free
    hi = np.percentile(flux, 99.0)
    if hi <= 0:
        hi = flux.max() or 1.0
    flux = flux / hi
    # Smooth before peak picking. The raw curve is a sum over 513 frequency bins, so at
    # 172 Hz it jitters by a few percent from frame to frame and a raw local maximum is
    # often just the noisiest bin of a syllable rather than its attack. A 40 ms moving
    # average is the standard onset-detector front end (librosa's onset_strength does the
    # same with a lag/aggregate). The attack stays where it is; the jitter goes away.
    win = max(1, int(round(0.040 * rate)))
    kernel = np.ones(win) / win
    smooth = np.convolve(flux, kernel, mode="same")
    return flux, smooth, rate


def _onset_times(flux: np.ndarray, rate: float, t0: float, t1: float):
    """Candidate syllable onsets inside [t0, t1): local maxima of the smoothed flux curve."""
    i0 = max(0, int(t0 * rate))
    i1 = min(len(flux), int(t1 * rate))
    if i1 - i0 < 3:
        return []
    seg = flux[i0:i1]
    out = []
    # a local maximum, and clearly above the local floor, and 0.09 s from the last one
    thresh = max(0.10, float(np.percentile(seg, 55)))
    last = -1e9
    for k in range(1, len(seg) - 1):
        v = seg[k]
        if v < seg[k - 1] or v < seg[k + 1] or v < thresh:
            continue
        t = (i0 + k) / rate
        if t - last < 0.09:
            continue
        out.append((t, float(v)))
        last = t
    return out


def _pick(onsets, n, span, t_start, t_end):
    """Choose n onset times for n characters.

    The spread-out guess says character i should be at
    `t_start + (i + 0.5) * span / n`. Each candidate onset is allowed to take the place of
    the character it is closest to, but no two characters may take the same onset, and a
    character may only move by SLACK seconds. That is the grid constraint: the search cannot
    reorder the line, it can only tighten the spacing.

    The DP state is (character, onset index) and the cost has three parts:
      - how far the onset sits from that character's ideal slot,
      - how weak the onset is (a soft onset is a worse anchor than a sharp one),
      - a pace term: how much the gap to the previous character deviates from the ideal gap.
    The pace term is a soft cost, not a filter — a line whose real singing is uneven must be
    allowed to be uneven, or the DP would rather fail than report the truth.
    """
    if n <= 0:
        return []
    ideal = [t_start + (i + 0.5) * span / n for i in range(n)]
    if not onsets:
        return ideal

    # candidate assignment: for each character, the onsets within SLACK of its ideal
    cands = []
    for i, want in enumerate(ideal):
        near = [j for j, (t, _v) in enumerate(onsets)
                if abs(t - want) <= SLACK and t_start - 0.20 <= t <= t_end + 0.20]
        cands.append(near)

    NEG = float("inf")
    dp = [{} for _ in range(n)]
    back = [{} for _ in range(n)]
    for j in cands[0]:
        t, v = onsets[j]
        dp[0][j] = 0.25 * abs(t - ideal[0]) + 1.0 * (1.0 - v)
    for i in range(1, n):
        want_step = ideal[i] - ideal[i - 1]
        for j in cands[i]:
            t, v = onsets[j]
            best = NEG
            bestk = None
            for k, c in dp[i - 1].items():
                if k >= j:
                    continue
                step = t - onsets[k][0]
                if step <= 0.05:
                    continue
                pace = abs(step - want_step) / max(0.08, want_step)
                cc = (c + 0.25 * abs(t - ideal[i]) + 1.0 * (1.0 - v)
                      + PACE_PENALTY * min(pace, 3.0))
                if cc < best:
                    best = cc
                    bestk = k
            if bestk is not None:
                dp[i][j] = best
                back[i][j] = bestk

    if not dp[n - 1]:
        return _greedy(onsets, n, ideal, t_start, t_end)

    # backtrack the cheapest path
    j = min(dp[n - 1], key=lambda k: dp[n - 1][k])
    picks = [j]
    for i in range(n - 1, 0, -1):
        j = back[i][j]
        picks.append(j)
    picks.reverse()
    return _clean([onsets[j][0] for j in picks], t_start, t_end)


def _greedy(onsets, n, ideal, t_start, t_end):
    """Fallback: walk the characters left to right, each taking the strongest unused onset
    that is closest to its ideal slot. Monotone by construction."""
    out = []
    used = set()
    last = t_start - 1.0
    for i in range(n):
        want = ideal[i]
        best = None
        for j, (t, v) in enumerate(onsets):
            if j in used or t <= last:
                continue
            score = abs(t - want) - 0.6 * v
            if best is None or score < best[0]:
                best = (score, j, t)
        if best is None:
            out.append(max(want, last + 0.05))
        else:
            used.add(best[1])
            out.append(best[2])
            last = best[2]
    return _clean(out, t_start, t_end)


def _clean(times, t_start, t_end):
    """Monotone, with a minimum spacing, and inside the line."""
    out = []
    prev = t_start - 1.0
    for t in times:
        t = max(t, prev + 0.05)
        prev = t
        out.append(t)
    if out and out[-1] > t_end + 0.2:
        out = [min(x, t_end + 0.2) for x in out]
    return out


def _line_span(line, nxt_t):
    """The time the line is sung over, from the line's own first character to its last."""
    times = line.get("times") or []
    if times:
        return times[0], times[-1] + 0.12
    t0 = line["t0"]
    span = (nxt_t - t0) if nxt_t else 3.0
    return t0, t0 + span * 0.86


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="draw the flux curve too")
    args = ap.parse_args()

    flux, smooth, rate = _load_flux()
    old = json.loads(WT_OLD.read_text(encoding="utf-8"))
    lines = old["lines"]

    out_lines = []
    stats = []
    for i, line in enumerate(lines):
        text = line["text"]
        n = len(text)
        t0 = line["t0"]
        nxt_t = lines[i + 1]["t0"] if i + 1 < len(lines) else None
        span_start, span_end = _line_span(line, nxt_t)
        span = max(0.2, span_end - span_start)

        onsets = _onset_times(smooth, rate, span_start, span_end)
        picked = _pick(onsets, n, span, span_start, span_end)

        # the spread-out baseline, for the report
        base = [span_start + (k + 0.5) * span / n for k in range(n)]
        devs = [abs(p - b) for p, b in zip(picked, base)]
        stats.append({
            "t0": t0, "text": text, "n": n,
            "onsets": len(onsets),
            "max_dev": max(devs) if devs else 0.0,
            "mean_dev": sum(devs) / len(devs) if devs else 0.0,
        })
        out_lines.append({"t0": t0, "text": text, "times": [round(x, 3) for x in picked]})

    out = {
        "bpm": old.get("bpm"), "phase": old.get("phase"), "beat": old.get("beat"),
        "source": "vocals stem spectral flux + grid-constrained DP (src/align_chars.py)",
        "note": "times are the measured syllable onsets of the vocals stem, constrained to "
                "the line's own window; they are NOT uniform spread",
        "lines": out_lines,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON, len(out_lines), "lines")

    # ---- the report -------------------------------------------------------------
    tot_n = sum(s["n"] for s in stats)
    tot_md = sum(s["mean_dev"] * s["n"] for s in stats) / max(1, tot_n)
    tot_max = max((s["max_dev"] for s in stats), default=0.0)
    rows = ["# 逐字对齐报告（档 B：人声谱通量 + 网格 Viterbi）", "",
            f"输入：`data/audio/vocals_flux.npy`（172.27 Hz，htdemucs vocals stem 的正谱通量）",
            f"输出：`data/word_times_v2.json`　字总数 {tot_n}",
            f"平均位移 **{tot_md*1000:.0f} ms**，单行最大位移 **{tot_max*1000:.0f} ms**",
            "",
            "`dev` 是这一行的字相对「均分」基准的位移。位移大不是错——它说明这一句的字"
            "在歌里本来就挤在一起或者拉得很开，而均分把它抹平了。", "",
            "| t | 句 | 字 | 候选起音 | 平均位移 | 最大位移 |",
            "|---:|---|---:|---:|---:|---:|"]
    for s in stats:
        rows.append(f"| {s['t0']:.2f} | {s['text']} | {s['n']} | {s['onsets']} | "
                    f"{s['mean_dev']*1000:.0f} ms | {s['max_dev']*1000:.0f} ms |")
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("wrote", OUT_REPORT)

    if args.preview:
        _draw(smooth, rate, out_lines)


def _draw(flux, rate, out_lines):
    from PIL import Image, ImageDraw

    W, H = 1200, 700
    img = Image.new("RGB", (W, H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    t0, t1 = 60.0, 125.0
    i0, i1 = int(t0 * rate), int(t1 * rate)
    seg = flux[i0:i1]
    peak = max(1e-6, float(seg.max()))
    for k, v in enumerate(seg):
        x = int((k / len(seg)) * (W - 40))
        h = int((v / peak) * (H - 80))
        d.line([(x, H - 30), (x, H - 30 - h)], fill=(70, 90, 160))
    for line in out_lines:
        for t in line["times"]:
            x = int(((t - t0) / (t1 - t0)) * (W - 40))
            d.line([(x, 20), (x, H - 30)], fill=(255, 176, 0), width=1)
    d.text((20, H - 22), "orange = measured character onset", fill=(255, 176, 0))
    p = ROOT / "out" / "align-preview.png"
    img.save(p)
    print("wrote", p)


if __name__ == "__main__":
    main()
