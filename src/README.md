# src/ 源码地图

按**被 import 的顺序**分层。**改核心层前先跑 `python shots.py` 和 `python drive.py` 自检。**

---

## 1. 核心层（被其他模块 import，改动最需小心）

| 文件 | 职责 | 被谁用 |
|---|---|---|
| `tk.py` | 绘图原语：噪声、地形、天空、光柱、盆栽兰、雨、仪表、后期、薄纱 | 几乎全部 |
| `clock.py` | 音乐时钟：节拍网格、`pulse(t)`、`snap()` | drive / shots / scene4 |
| `drive.py` | 四轨信号（SCORE / LEVEL 等推出为真函数，不再写死） | scene / scene4 |
| `layout4.py` | **五区版式**：实体（512，器乐格在时 384）+ 世界 + **器乐格 292** + 80 px ops 列 + 90 px token 带。`zones(collapse, mode, cell, cell_px)` | scene4 |
| `instruments.py` | **器乐格与放大视图**：`cellpanel`（多轨）+ 六种画法（六线谱/四线谱/步进格/竖条/曲线/竖柱）+ `stage`（钢琴的落音符与键盘） | layout4、scene4 |
| `score3.py` | 间奏音符表 + 三件乐器的 onset 表（`data/onsets_*.json`，78–250 s） | scene4 |
| `preview.py` | 旧双屏版式 + 开场 / 逐格 CRT / GAME SET / 3% 黑场 | scene、scene4（复用 `intro_scene` `ending_frame`） |
| `crt.py` `intro_fill.py` | 前奏七模块上电、等待嗓子状态 | preview / scene4 |
| `shots.py` | A① 十镜头表（严格照 `plan/14 §2.3`） | scene4 |

## 2. 成片路径（两条并存）

| 文件 | 路径 | 版式 | 状态 |
|---|---|---|---|
| `scene.py` | `scene.frame(t)` | 旧：左右双屏，左 384 px | ✅ 全片已出 `out/films/film.mp4` |
| `scene4.py` | `scene4.frame(t)` | 新：四区 | ⚠️ 单帧 + A① 段已验，全片渲到 32 % |

> 为什么并存：`preview.py` 里有已出片验证过的开场与结尾，重写会让旧片无法回退。
> `scene4.py` **复用** `preview.intro_scene()` / `preview.ending_frame()`，只重写版式层。

## 3. 出片与审片入口

| 文件 | 用途 |
|---|---|
| `build.py` | ⭐ **盖楼（唯一出片入口）**：`python build.py 1` 盖第 1 层并拼进 `out/film-v2.mp4`；`status` 看楼层表；`all` 把没盖的都盖了；`join` 只重拼不渲 |
| `render.py` | 帧 → mp4（build 底层）。`python render.py 0 395.667 films/film-v2.mp4 --workers 8 --scene scene4` |
| `views.py` | 审片表 + contact sheet。`python views.py --contact` |
| `chapter.py` | 章节表（build 的楼层定义）+ 单篇章静帧。`python chapter.py 1 --stills-only` |

**盖楼约定**：楼层在 `out/parts/NN-<名>.mp4`（可单独看，各带音轨切片）；
主文件永远是 `out/film-v2.mp4`——盖一层就整体重拼一次（视频流直拷 + 整轨 FLAC 从 0 灌，
接缝处音画不漂）。盖过的层可以单独重渲（`build.py 3`），没盖的不影响已盖的。

## 4. 音频分析（只读素材，产出 json/npy）

| 文件 | 产出 |
|---|---|
| `audio_analysis.py` / `audio_calibrate.py` / `audio_shift.py` | RMS、节拍、偏移 |
| `spectro.py` | 22 段频谱 `data/audio/bands24.npy` |
| `stems.py` / `stems_flux.py` / `stems_plot.py` | 人声分轨 + 谱通量（正谱通量，不是 RMS） |
| `align_chars.py` | **逐字对齐（档 B）**，网格约束 DP；`python align_chars.py --preview` |

## 5. probes/ 一次性调查脚本

**不参与出片**，跑完即弃；已加路径引导，仍可 `python probes/xxx.py` 运行。

| 文件 | 回答过的问题 |
|---|---|
| `stereo_check.py` | 间奏左右声道是不是真的分轨（结论：几乎单声道） |
| `key_and_fade.py` / `key_shift.py` | A③ / A④ 升了几个半音 |
| `probe_vocs.py` | 0:44–1:04 是人声还是吉他串轨 |
| `m2.py` / `a1_probe.py` / `proof_motion.py` | 标题卡、钢笔逐字、动效 A/B 的早期试验 |

---

## ⚠️ 一个必须知道的坑

`scene.LINES` 里的 `t` = `LRC时间 + OFFSET - LEAD`（**早 0.06 s**，歌词要抢在起音前一点），
而逐字对齐表用 **LRC 原始时间** 做 key。

**两边差 0.06 s，直接查表会全部落空，然后静默退回均分时间**——画面看起来完全正常，
只是逐字精度根本没生效。改任何跟逐字时间有关的代码，先确认这个偏移还在。
