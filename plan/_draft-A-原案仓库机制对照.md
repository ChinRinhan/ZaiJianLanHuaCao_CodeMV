# 原案仓库机制 × 我们 src 逐条对照（只读审计）

> 2026-10-27 · 审计员 A · 只读，未改动 `src/` `out/` 与其它 `plan/`
> 路径口径：`src/...` 相对 `F:\dafeiyu\lanhuacao-mv`；`film/...` 相对 `F:\dafeiyu\repo-analysis\world-execute-me-dsh-pv-main`

**一句话结论**：借来的三样东西（单一时钟、拍网格、纯函数）代码都在，但**挂载面只做了五分之一**（pulse 24 处 → 5 处，且新片的框线一处没挂）；真正缺的是 **6（断言式时间轴：函数写了但渲染路径从不调用）** 和 **5/4（落定手感：ease_back 新片 0 调用、settle 只变暗不乱跳）**；7（2.2 s 密度）是**明确不借**，代价得用「41 s 一段」认账。

---

## 11 行对照表

| # | 机制 | 原案实现（file:line + 关键常数） | 我们实现（file:line + 常数 / 调用点数） | 判定 | 一句话影响 |
|---|---|---|---|---|---|
| 1 | 全片单一时钟 `pulse` | `film/.../full/engine.py:66-67` `def pulse(t, decay=0.14): exp(-(t-beat_t(beat_index(t)))/decay)`；全库 **24 处 / 14 文件**；挂点是「每个框」：`engine.py:205` `0.45+0.3*pulse`、`engine.py:265` `0.45+0.35*pulse`（所有 me_pane）、`stage.py:322` 发丝线 | `src/clock.py:121-123` 同公式，`DECAY=0.14`（`clock.py:47`），拍表读实测 `data/beat_times.json`（`clock.py:44`）。**真实调用点只有 5 个**：`drive.py:114`、`instruments.py:660`（钢琴卷帘 playhead）、`preview.py:82`（`beat_breath`，只在旧片 preview 路径）、`layout4.py:594`（呐喊光环）、`layout4.py:604`（吉他涟漪）。新片四个区的框线亮度是**常数**：`layout4.py:692` 0.22 / `713` 0.32 / `785` 0.30 | **差异** | 新片只有「呐喊环」「涟漪」跟着拍子亮，**框、表头、token 带不呼吸**——原案那种「整块界面同一拍一起亮」没有 |
| 2 | 切点落在拍网格 `snap(t,div)` | `engine.py:58-59` `snap8` = 1/2 拍（八分）**无条件**吸附；调用 **23 处**（`sec_intro.py:407`、`sec_chorus1.py:655`、`sec_final.py:278/281/282`、`sec_verse1.py:321`、`choreo.py:113-119`…） | `clock.snap(t, div=3)`（`clock.py:126-134`）**全库 0 调用**（死代码）。实际用的是 `shots._snap`（`shots.py:58-65`）：`GRID_DIV=6`（1/6 拍）、`GRID_TOL=0.030` s，**超差就不吸**；实测 10 镜最差偏差 **1.09 帧**；首尾两边界故意不吸（`shots.py:77-80`） | **差异** | 现在 10 个切点确实都在网格上（≤1.09 帧），但 30 ms 容差是「静默不吸」的入口，且时钟自带的 `snap` 从没被用过 |
| 3 | 文字落在唱词起音 | `words.py:29-30` `MAX_TYPE=0.25` / `MIN_TYPE=0.06`；时间来自 `data/timing/word_timeline_notext.json`，每个词 4 个候选 `mms_line` / `whisper_line` / `mms_block` / `mms_initial` + `candidate_spread_ms` + `review_flags` → **声学模型强制对齐**（`words.py:3-4` "vocal stem forced-aligned per LRC line"） | `data/word_times_v2.json` 由 `src/align_chars.py` 生成：`align_chars.py:7` 自述「谱通量 + 网格 Viterbi（DP）」，`SLACK=0.42` / `PACE_PENALTY=0.55`（`align_chars.py:51-53`）——**没有声学模型**；`scene4.py:67-84` 读表，缺表退回均分（`scene4.py:277-282`） | **差异** | 逐字时刻是「从人声能量里找起音」，不是「知道这个字唱在哪」；连音、弱起、气声仍会错——这是档 B 的天花板，不是 bug |
| 4 | `SETTLE=0.08` 先乱跳再定住 | `words.py:93` `SETTLE=0.08`；`words.py:96-99` 每个字母 0.08 s 内 `rng.choice(tk.SCR)` 随机字形，之后锁死 | `tk.pen_typed` 的 `settle` 默认 0.08（`tk.py:814`），**4 个调用点**（`layout4.py:834/839/951/954`）；但 fresh 分支只做 **alpha×0.55 + 偏移 1 px**（`tk.py:834-836`），**没有随机字形**。乱跳只在 `tk.decode`（`tk.py:81-97`，默认 `settle=0.12`），用于界面文字（`layout4.py:225/347/795`） | **差异** | 窗口对了、手感没对：我们「变暗抖一下」，原案「乱码→锁字」。最便宜的一条补丁（SCR 已在 `tk.py:78`） |
| 5 | `ease_back` 过冲回弹 | `continuity_full_v2/kit.py:257` `def ease_back(u, s=1.2)`；**11 个调用点 / 6 个场景文件**：`cuts.py:153/204/241`、`s_boot.py:361/440/556`、`s_deploy.py:259/272/285`、`s_exec.py:597`、`s_sft.py:166`、`s_userleft.py:395` | `tk.py:69-75` 有 `ease_back`（docstring 直接引 `kit.py:257`），但**新片 0 调用**：3 个调用点全在旧片 `preview.py:1087/1100/1190`；`scene4.py` / `layout4.py` 里一次都没有 | **差异** | 新片所有入场是 `ease_io/ease_out`（到位就停），plan/13 §3-4 说的「生硬」原封不动 |
| 6 | 断言式时间轴 | `engine.py:355-362` `finalize()` 里 `raise ValueError`：gap/overlap 直接抛，且必须覆盖 `0..END_T`；`continuity_full_v1/full_continuity.py:323-325` 再断言一遍（无 placeholder、覆盖 0..211、首尾相接） | `shots.check_coverage()`（`shots.py:116-129`）**只返回 list，不抛**；全库唯一调用点是 `shots.py:138` 的 `__main__` 自检；渲染路径（`render.py` / `scene4.py`）**不调用**；且只校验 A① 的 67.85–103.84，全片 0–395.667 无覆盖校验；`chapter.py:28-41` 的 6 个楼层之间也没有任何校验 | **缺失** | plan/16 §0 声称「借了断言式时间轴」，**实际没接**。段落漏了/叠了不会被发现，只能靠人眼 |
| 7 | 镜头密度 | `engine.py:36` `SONG_LEN=211.91` / `END_T=211.0`；7 个 `sec_*.build()` 注册镜头，**实测 81 个手写**（intro 12 / verse1 12 / chorus1 10 / verse2 12 / chorus2 14 / final 10 / outro 11），缺口由 `build.py:36-45` 的 `shot_placeholder` 补满；v2 侧索引到 96（`s_eval.py:1` "cuts 86-96"、`s_exec.py:55` `range(64,87)`）→ **97 镜 / 96 切点 / 211.0 s ≈ 2.20 s 一切** | 全片 **395.667 s**（`scene.py:27`）；镜头表只有 A① **10 镜**（`shots.py:35-49`，67.85–103.84，平均 **3.60 s**）；`_body` 明写「其余全片一个广角」（`scene4.py:877-879`）。全片切点 **5 个**：70.523 / 81.183 / 84.014 / 99.298 / 103.84（`scene4.py:801-803`，实跑确认），全在 A① 的 36 s 里；**0–245.79 s 内 5 切点 → 6 段 → 平均 40.97 s**；结尾 386.5 / 387.0 是两次硬切但不是 shutter 切点（`scene4.py:857-859`） | **故意不借** | plan/16 §0 明写不借。但代价要认账：**41 s/段 vs 2.2 s/段，差 18 倍**——动效再好也只是「同一张画在动」 |
| 8 | 每段换主色、硬切（非渐变） | **原案并非如此**：全片一个调色板（`tuikit.py:27-41`，`PALETTE` 由 `TUI_PALETTE` 选）；唯一的全局色彩弧是 `ui_gain` **关键帧连续衰减**（`engine.py:91-94`，`engine.py:399` 写进 `tk.UI_GAIN`）；离散换色只有逐镜 `alert`（`engine.py:149/181`：err→RED、anom→黄）。转场默认 **11 帧 glide**（`direction.py:231`），硬切是少数（报告统计 22/96） | 没有整屏主色切换；有的是**连续色温**：`warm = 0.40*rise`（`layout4.py:566-568`），`tk.sky` / `tk.terrain` 用 warm 在两组颜色间 mix（`tk.py:199-204`、`256-265`）。切版式时有 3 帧 CRT 压缩快门（`scene4.py:797-803`、`834-843`） | **差异** | 两边都不是「硬切主色」。原案是「固定调色板 + 全片增益衰减」，我们是「天慢慢变暖」——前者是系统状态，后者是天气 |
| 9 | 版式是函数、切版式=切枚举 | **两级**：`direction.layout(shot)` → `(mode, kind, extra)`，mode 是 **9 值枚举**（`direction.py:109-123`：split/mirror/pip/fullbleed/cinema/tiles/floating/raw/shell）；`stage.geometry(mode, kind, extra)` → 面板矩形表（`stage.py:224-254`） | **一级**：`layout4.zones(collapse=0.0, mode="W", cell=0.0, cell_px=0.0, status=None, dial=None)` → 7 个矩形（`layout4.py:66-117`）；`mode` 只有 W/P 两值，**V 是 `collapse` 连续插值**（`layout4.py:79-104`）；`layout4.frame` 只调一次（`layout4.py:972`） | **部分相同** | 「版式是函数」成立；「切版式=切枚举」只对 W/P 成立——V 是浮点参数，所以间奏的进出必然是渐变（这正是那条 1.2 s 收缩），想硬切做不到 |
| 10 | 高潮用排版砸 | 大字是**字/词级 110–120 px**：`sec_final.py:91` `"EPERM", 110`、`sec_intro.py:235` `"RUN", 120`、`sec_verse2.py:190` `"281", 120`；且可整幅放大（`stage.py:238-239` fullbleed 按 `W/FULL_W` 放大 FULL 区） | B① 四句口号走 `layout4._big_line`（`layout4.py:1244-1282`），字号被 `BIG_CAP=60` 夹住（`layout4.py:1038`、`1264`），绘制区被 `box=z["cell"]` 收进 **640 px 的器乐格**（`layout4.py:1018-1019`；无 box 时退到 world 半区 `1257-1258`）；有 3 px 暗描边 + 0.22 s 缩放冲拳（`layout4.py:1265-1266`、`1272-1274`） | **差异** | B① 是全片最响的 18 s（`scene4.py:311` 自述「covers both panes」），**但代码把它关在 640 px 的格子里**——注释与实现不符，上限是别人的一半、面积是别人的四分之一，砸不下来 |
| 11 | 「真实数据」差异点 | 右屏画模型内部（Transformer / 注意力 / KV cache），数字来自 `full/facts.py:8-18`（模型规格常量）；与**这首歌的音频无关**——内容确实虚构（歌本身没有可画的数据） | 真读：`data/beat_times.json`（`clock.py:44-67`）、`data/word_times_v2.json`（`scene4.py:67-84`）、`data/piano_score.json` + `data/onsets_*.json`（`score3.py:22-57`）、`data/audio/stem_*.npy`（`drive.py:36`；`scene4.py:413-419`、`765-766`）、`rms.npy`（`layout4.py:862-863`）、`bands24.npy`（`layout4.py:871-872`、`scene4.py:988-993`），每个都有缺文件降级分支。**但结构节点是写死的**：`B1_T0=103.84` / `B1_END=136.6`（`scene4.py:435`）、`CELL_END=245.79`（`scene4.py:345`）、`COUNTDOWN=145.0`（`scene4.py:440`）、188–214 窗口（`scene4.py:980`）、`W_TERRAIN/W_BEAM/W_HUD` 三张关键帧表（`scene4.py:105-107`） | **相同** | 「仪表板画真实数据」属实，不是写死。但「什么时候该发生什么」仍是人工常数——别把它说成全自动 |

> 口径注：
> ① 第 7 条「97 镜」用两路交叉验证：静态/运行时数出的 81 个手写镜头（我按 `build()` 逐段跑了一遍）+ `build.py:36-45` 的 placeholder 补位，再对上 v2 侧索引到 96（`s_eval.py:1`、`s_exec.py:55`）。**97 这个总数我没能在本机复算**——仓库缺 `audio/lyrics_synced.lrc`，`lyric_start()` 起不来，缺口的段数算不出；81 与 96 是源码事实，97 是二者相容的推论。
> ② 第 1 条原案 24 处含 def 与 import 行，实际挂载点约 15 处；我们 5 处是**去重后的真实调用点**（`clock.py` 内 3 处是 docstring/自检）。
> ③ 第 3 条「Demucs + CTC」的原始表述见 plan/13 §3-1；**源码里找不到 demucs/ctc 字样**，`word_timeline_notext.json` 的候选方法是 `mms_*` / `whisper_*`。结论按源码写：声学模型强制对齐（MMS + Whisper），不是 CTC。
> ④ 未找到：我们这边没有任何「按段落整屏换主色」的代码（第 8 条），也没有任何断言在渲染路径上（第 6 条）。
> ⑤ 第 10 条顺带查出一处**注释与实现不符**：`scene4.py:311` 写「the only place in the film where type covers both panes」，但 `layout4.py:1018-1019` 把 `big` 塞进 `box=z["cell"]`（B① 时 640 px），`1257-1258` 的兜底也只是 world 半区。要么改注释，要么把 box 放开——这是全片最响的 18 s，建议后者。

---

## 最该补的 3 条

1. **把 `pulse` 挂到框线上**（第 1 条）。`layout4.py:692/713/785` 三处 `_frame(..., 0.22/0.32/0.30)` 改成 `0.45+0.35*clock.pulse(t)` 的形式，表头再加一处——**5 个调用点变 9 个**，就从「两个特效跟拍」变成「整块界面跟拍」。原案 `engine.py:205/265` 就是这个写法，改造成本最低、观感收益最大。
2. **把断言接进渲染路径**（第 6 条）。`shots.check_coverage()` 目前只在 `__main__` 里被调用（`shots.py:138`）；`render.py` 启动时调用一次并 `raise`，再补一条全片楼层覆盖断言（`chapter.py:28-41` 的 6 段首尾相接、覆盖 0–395.667）——就是 `engine.py:355-362` 那一层的等价物。plan/16 §0 已经把这条写进「借」，现在等于**只借了名字**。
3. **落定手感**（第 4、5 条）。`tk.py:834-836` 的 fresh 分支把字换成 `tk.SCR` 里的随机字形（`SCR` 已在 `tk.py:78`），`tk.ease_back`（`tk.py:69`）接到 `layout4` 的入场动作上——现在新片 0 调用，全片「到位就停」。

## 故意不借、别补的 3 条

1. **96 镜 / 2.2 s 的密度**（第 7 条）。plan/16 §0 已明确「不借 96 个镜头的密度」，而且我们的差异点正是「版式随段落变，不是靠切」（plan/16 §2.1）。补它等于把差异点拆掉。要认的账只是：**0–245.79 s 内平均 41 s 一段**，所以那 5 个切点必须落在最该切的地方（现在 4 个是版式切换 + 1 个章节口，站得住）。
2. **每段整屏换主色 + 硬切**（第 8 条）。原案自己也没这么做（单一 `PALETTE` + `UI_GAIN` 关键帧）；我们的 `warm` 渐变挂的是 `rise`——那是「山在长高、天在亮」的物理事实，改成硬切会把这件事丢掉。**别补**。
3. **强制对齐模型**（第 3 条）。MMS/Whisper 约 1 GB 下载 + 额外推理链，`align_chars.py:9-12` 已经写明取舍（「我们不是做卡拉OK」）；档 B 的误差量级对「字跟唱词走」够用。**别补**——真要补，先补第 1 条（挂载面）和第 6 条（断言），那两条是结构性的，这条只是精度。
