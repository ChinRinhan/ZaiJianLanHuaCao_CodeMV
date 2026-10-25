# -*- coding: utf-8 -*-
"""M0: decode the song, measure energy/onsets, verify the 11 section boundaries, and settle the ending.

Writes:
  data/audio/mono22050.wav      decoded analysis signal
  data/audio/rms.npy            RMS envelope, 100 fps
  data/audio/flux.npy           spectral-flux onset envelope, 100 fps
  data/timeline.json            sections + lyric lines + measured features
  plan/01-音频校验.md            human-readable report
"""
from __future__ import annotations
import json, math, os, re, subprocess, sys, wave
from pathlib import Path

import numpy as np
from scipy.signal import stft

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools" / "ffmpeg.exe"
FLAC = ROOT / "input" / "song.flac"
LRC = ROOT / "input" / "lyrics.lrc"
AUD = ROOT / "data" / "audio"
AUD.mkdir(parents=True, exist_ok=True)

SR, HOP, WIN = 22050, 220, 1024           # 10 ms hop -> 100 fps
FPS_A = SR / HOP

# ---------------------------------------------------------------- decode
wav_path = AUD / "mono22050.wav"
if not wav_path.exists():
    subprocess.run([str(FFMPEG), "-v", "error", "-y", "-i", str(FLAC),
                    "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(wav_path)], check=True)
with wave.open(str(wav_path), "rb") as w:
    n = w.getnframes()
    pcm = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
dur = len(pcm) / SR
print(f"decoded {dur:.3f} s, {len(pcm)} samples @ {SR} Hz")

# ---------------------------------------------------------------- features
nperseg, noverlap = WIN, WIN - HOP
f, t, Z = stft(pcm, fs=SR, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False)
mag = np.abs(Z)
rms = np.sqrt(np.convolve(pcm ** 2, np.ones(WIN) / WIN, mode="same"))[::HOP][: mag.shape[1]]
db = 20 * np.log10(np.maximum(rms, 1e-6))
flux = np.maximum(0.0, np.diff(mag, axis=1)).sum(axis=0)
flux = np.concatenate([[0.0], flux])
flux_n = flux / (np.percentile(flux, 99) + 1e-9)
np.save(AUD / "rms.npy", rms.astype(np.float32))
np.save(AUD / "flux.npy", flux_n.astype(np.float32))
print(f"features: {len(rms)} frames @ {FPS_A:.0f} fps, rms {db.min():.1f}..{db.max():.1f} dB")

# ---------------------------------------------------------------- tempo
env = flux_n - flux_n.mean()
ac = np.correlate(env, env, mode="full")[len(env) - 1:]
lo, hi = int(FPS_A * 60 / 200), int(FPS_A * 60 / 60)     # 60..200 BPM
lag = lo + int(np.argmax(ac[lo:hi]))
bpm = 60 * FPS_A / lag
print(f"tempo ~ {bpm:.1f} BPM (lag {lag} frames)")

# ---------------------------------------------------------------- lyric lines
raw = LRC.read_bytes().decode("utf-8-sig")
TS = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
lines = []
for ln in raw.splitlines():
    st = TS.findall(ln)
    if not st:
        continue
    body = TS.sub("", ln).strip()
    for h, m, s in st:
        lines.append({"t": round(int(h) * 60 + int(m) + (int(s.ljust(3, "0")) / 1000 if s else 0), 3),
                      "text": body})
lines.sort(key=lambda x: x["t"])

# ---------------------------------------------------------------- boundaries
BOUND = [
    ("前奏", "A①", 67.85), ("A①", "B①", 103.84), ("B①", "间奏", 122.00),
    ("间奏", "B②", 245.79), ("B②", "A②-上", 266.31), ("A②-上", "A②-下", 289.64),
    ("A②-下", "A③-上", 312.45), ("A③-上", "A③-下", 334.69), ("A③-下", "A④-上", 358.92),
    ("A④-上", "A④-下", 380.99),
]

def near_onset(t0, win=0.5):
    a, b = max(0, int((t0 - win) * FPS_A)), min(len(flux_n), int((t0 + win) * FPS_A))
    if b <= a:
        return None, None
    i = a + int(np.argmax(flux_n[a:b]))
    return i / FPS_A, float(flux_n[i])

def level(t0, span=0.3):
    a, b = int(max(0, t0 - span) * FPS_A), int(min(dur, t0 + span) * FPS_A)
    if b <= a:
        return None
    return float(np.percentile(db[a:b], 90))

rows = []
for prev, nxt, t0 in BOUND:
    on, strength = near_onset(t0)
    before, after = level(t0 - 0.25), level(t0 + 0.25)
    rows.append({"from": prev, "to": nxt, "t_lrc": t0, "nearest_onset": round(on, 3) if on else None,
                 "offset": round(on - t0, 3) if on else None, "onset_strength": round(strength, 3) if strength else None,
                 "db_before": round(before, 1) if before else None, "db_after": round(after, 1) if after else None})
    print(f"{prev:>6} -> {nxt:<6} lrc={t0:7.2f}  onset={on:7.2f}  d={on - t0:+.3f}  "
          f"flux={strength:5.2f}  dB {before:5.1f}->{after:5.1f}")

# ---------------------------------------------------------------- ending
print("\nending 375..396 s, 0.5 s windows (RMS dB):")
tail = []
t0 = 375.0
while t0 < dur:
    a, b = int(t0 * FPS_A), int(min(dur, t0 + 0.5) * FPS_A)
    v = float(np.percentile(db[a:b], 90)) if b > a else -99
    tail.append((round(t0, 1), round(v, 1)))
    t0 += 0.5
print("  " + "  ".join(f"{t:.0f}s:{v:.0f}" for t, v in tail))
last_loud = max((t for t, v in tail if v > -45), default=None)
print(f"last window above -45 dB: {last_loud}")

# ---------------------------------------------------------------- leading silence
first = next((i for i, v in enumerate(db) if v > -45), 0) / FPS_A
print(f"first audio above -45 dB at {first:.2f} s")

# ---------------------------------------------------------------- write timeline
sections = [
    {"id": "intro", "label": "前奏", "start": 0.0, "end": 67.85, "type": "instrumental"},
    {"id": "A1", "label": "A①", "start": 67.85, "end": 103.84, "type": "verse_a", "round": 1},
    {"id": "B1", "label": "B①", "start": 103.84, "end": 122.0, "type": "refrain", "round": 1},
    {"id": "break", "label": "大间奏", "start": 122.0, "end": 245.79, "type": "instrumental"},
    {"id": "B2", "label": "B②", "start": 245.79, "end": 266.31, "type": "refrain", "round": 2},
    {"id": "A2a", "label": "A②-上", "start": 266.31, "end": 289.64, "type": "verse_a", "round": 2, "cue": "啊预备唱"},
    {"id": "A2b", "label": "A②-下", "start": 289.64, "end": 312.45, "type": "verse_a", "round": 2, "cue": "第二步"},
    {"id": "A3a", "label": "A③-上", "start": 312.45, "end": 334.69, "type": "verse_a", "round": 3, "cue": "升key"},
    {"id": "A3b", "label": "A③-下", "start": 334.69, "end": 358.92, "type": "verse_a", "round": 3, "cue": "再升"},
    {"id": "A4a", "label": "A④-上", "start": 358.92, "end": 380.99, "type": "verse_a", "round": 4},
    {"id": "A4b", "label": "A④-下", "start": 380.99, "end": 391.0, "type": "verse_a", "round": 4},
    {"id": "outro", "label": "尾", "start": 391.0, "end": round(dur, 3), "type": "instrumental"},
]
tl = {"song": {"title": "再见 兰花草", "artist": "张雨生", "duration": round(dur, 3),
               "sr_analysis": SR, "fps_analysis": round(FPS_A, 3), "bpm_estimate": round(bpm, 1)},
      "sections": sections, "lines": lines, "boundaries_measured": rows,
      "ending": {"tail_db": tail, "last_loud_window": last_loud},
      "leading_silence_s": round(first, 3)}
(ROOT / "data" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------------------------------------------------------------- report
rep = ROOT / "plan" / "01-音频校验.md"
out = []
out.append("# M0 音频校验报告\n")
out.append(f"- 解码：{dur:.3f} s @ {SR} Hz 单声道（源 FLAC 44.1 kHz 双声道）")
out.append(f"- 分析帧率：{FPS_A:.0f} fps（10 ms 步长），共 {len(rms)} 帧")
out.append(f"- 估计速度：**{bpm:.1f} BPM**（自相关）")
out.append(f"- 起唱前静音：{first:.2f} s（> -45 dB 才算有声）")
out.append(f"- 结尾最后一个 > -45 dB 的 0.5 s 窗口：**{last_loud} s**\n")
out.append("## 段落边界校验（LRC 时间 vs 实测最强起音）\n")
out.append("| 边界 | LRC | 最近起音 | 偏差 | 起音强度 | 前后电平 |")
out.append("|---|---:|---:|---:|---:|---|")
for r in rows:
    out.append(f"| {r['from']} → {r['to']} | {r['t_lrc']:.2f} | {r['nearest_onset']:.2f} | "
               f"{r['offset']:+.3f} | {r['onset_strength']:.2f} | {r['db_before']:.0f} → {r['db_after']:.0f} dB |")
out.append("\n## 结尾 375–396 s（每 0.5 s 的 90 分位电平）\n")
out.append("```")
out.append("  ".join(f"{t:.0f}s:{v:.0f}dB" for t, v in tail))
out.append("```")
out.append(f"\n最后一个有声音的窗口：**{last_loud} s**；文件总长 {dur:.3f} s。")
rep.write_text("\n".join(out) + "\n", encoding="utf-8")
print("\nwrote", ROOT / "data" / "timeline.json", "and", rep)
