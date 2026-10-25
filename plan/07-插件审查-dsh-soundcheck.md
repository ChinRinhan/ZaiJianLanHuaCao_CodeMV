# dsh-soundcheck 审查与接入评估

> 2026-10-26 · 审查对象 <https://github.com/ALittleLov/dsh-soundcheck>（MIT，v0.8.1，Python + Node）
> 结论：**值得用，但只用它的"测量能力"，不让它进渲染管线。**

---

## 1. 它是什么

一个 DeepSeek Harness 插件：在本机把音频拆成可读的测量值，音频不出本机。

- **宿主侧**：`lib/index.js`（952 行）——注册 4 个工具、建 Python venv、装依赖、下模型、校验 sha256、跑子进程。
- **引擎侧**：`engine/analyze.py`（2953 行）——librosa + ONNX 模型：YAMNet（音色标签）、MusicNN（曲风）、Beat-This（节拍）、htdemucs（分轨）、可选 faster-whisper（歌词听写）。
- **工具**：`audio_analyze`（整曲）、`audio_section`（区间）、`audio_bands`（5 频段诊断）、`audio_provision`（装引擎）。
- **许可 MIT**，`package.json` 写明 `os: win32`，正好是我们这台机器。

---

## 2. 代码审查

### 2.1 做得好的地方（比多数同类脚本扎实）

| 点 | 证据 |
|---|---|
| **模型哈希写死在代码里**，不是运行时拉取 | `lib/index.js` 的 `CHECKSUMS`；注释直接说"否则镜像站可以把文件和哈希一起换掉" |
| 校验失败换源，全失败就停，不拿可疑文件推理 | 下载逻辑三轮镜像（GitHub release → hf-mirror） |
| **缓存带分析逻辑版本号** | `analyze.py:1042` 附近 `...|v8`，注释记录了"字段改名后旧缓存读不到，误以为算法坏了"的教训 |
| 不确定就明说，不给降级稿 | 人声证据不足时不跑 ASR（三档门控 −20 / 灰区 / −15 dB）；ASR 无可信段时**只报数量不给正文** |
| 输出分层 | `[判断] / [依据] / [可信] / [听不到]`，把"测不到什么"写在 README 里 |
| 阈值标注来源 | 两个门控阈值明确写着"初始工程参数，未用人工标注校准" |

这几点说明作者踩过坑并且把教训写进了代码——比"看起来能用"的脚本可信。

### 2.2 风险与限制

| 风险 | 说明 | 对我们的影响 |
|---|---|---|
| Windows 专用 | `package.json` 的 `os: win32` | 无（我们就是 Windows） |
| 安装体积 | 完整安装 ~570 MB（含可选组件） | 一次性成本，可接受 |
| 无 lockfile | 依赖是 `pip install librosa onnxruntime` 这种浮动版本 | 复现性一般；我们只取测量值，不传播这个风险 |
| 只给聚合值 | 分轨只给整曲 RMS/占比 + **16 秒块**能量，没有逐帧包络 | **核心缺口，要我们自己做**（见 3.2） |
| 歌词是候选 | ASR 音对字错是常态 | 不能当歌词用；版权上更不能用 |
| 插件权限 | manifest 声明 `process.spawn` + `filesystem-read` | 我们**不装插件**，只把 `engine/analyze.py` 当本地脚本跑，权限面小得多 |

### 2.3 两个未关的 issue（都直接影响我们）

**#2 可选组件装不上**：`/audio-install` 之后 `.provisioned` 标记存在，`audio_provision({stems})` 直接短路返回"无需重复"，分轨和听写永远装不上；而且装到 `engine/models/stems`、分析时找 `dsh-soundcheck-data/models/stems`，路径对不上，白下一次 158 MB。
→ **对我们的影响**：不要走它的安装器。手动 `pip install demucs-onnx` + 手动放模型（我们已经在这么做）。

**#1 整合响度偏低约 4.7 dB**：`integrated_lufs()` 两处不符合 BS.1770——立体声跨声道取平均（差 3 dB）、缺相对门限（再差 1–2 dB）；另外 `--json` 的 loudness 里没有 lufs 字段；数据目录落在包内部，升级会丢。
→ **对我们的影响**：**LUFS 不用它的**。我用 ffmpeg `ebur128` 实测本曲：**−15.3 LUFS / 真峰值 −0.5 dBFS / LRA 14.5 LU**，以这个为准。

### 2.4 实测：在本曲上跑了一遍

环境：`.venv-audio`（librosa 1.0.0 / onnxruntime 1.31 / demucs-onnx 0.3.4），模型 `htdemucs_fp16weights.onnx`（158 MB，sha256 与作者写死的一致）。

```
[分轨] 有人声 · drums 21% | bass 19% | other 18% | vocals 47%
[分轨] 无人声区间: 0:00–0:48, 0:56–1:04, 2:20–3:16, 3:36–4:00
[依据] 峰值 -0.8 dBFS | 整合 -20.0 LUFS | RMS -20.3 dBFS | 起音 2.94/s | E minor 0.75 | 112 / 56 拍
[可信] beat 0.93 | 调性 0.48 | 根音 0.38
```

**三个必须注意的结果：**

1. **LUFS 再次确认偏低**：−20.0 vs ffmpeg −15.3，**差 4.7 dB**，与 issue #1 完全一致。不用它。
2. **BPM 不稳定**：preview 段给 167/83，全曲给 112/56。同一首歌两次不同 → 节奏估计不可信，继续用我们自己算的 167。
3. **人声区间与 LRC 冲突**：工具说 0:48 就有人声，而 LRC 第一句在 1:08。可能是前奏里有哼唱/和声，也可能是 demucs 把主奏吉他漏进了人声轨。**这条必须自己验证**——它直接影响开场 48–68 秒的画面设计。

---

## 3. 对我们的用处

### 3.1 它直接解决的三个问题

1. **"动效廉价"的根因**。我们现在所有运动都是平移/淡入淡出，因为没有"状态量"可驱动。分轨给了我们四个独立的状态源。

2. **间奏与段落判断**。它的 16 秒块活动时间线（`activity_timeline`）与 `_instrumental_ranges` 可以交叉验证我们手算的段落边界，尤其是 147–161 秒那 14 秒骤静。

3. **人声段**。分轨给出"哪几段在唱"，可以验证 A①/B①/A② 的边界，也能确认"最后只剩两句"。

### 3.2 它没给、但我们可以从它身上拿到的

`demucs_onnx.inference.separate()` 返回的是**四轨数组**。插件拿完就丢，只存聚合值。

我们可以直接调用它，把四轨算成 **100 Hz 包络**存成 npy——这才是驱动画面的东西：

| 轨 | 驱动什么 | 运动类型（取代平移） |
|---|---|---|
| `drums` | 网格脉冲、跳字、扫描线亮度 | **阈值事件**：过阈才闪一帧 |
| `bass` | 山脊振幅、地形起伏速度 | **生长/形变**：山随低频呼吸 |
| `vocals` | 光柱亮度与高度、歌词时机校验 | **亮度/形态变化**：唱才亮 |
| `other` | 雨密度、字符噪点比例 | **密度变化**：不是位移 |

这四条正好对应我上一版文档里写的"动效应由数值驱动"。

---

## 4. 接入方案（三步）

### Step 1 · 环境（进行中）

```bash
cd F:/dafeiyu/lanhuacao-mv
python -m venv .venv-audio
.venv-audio/Scripts/python.exe -m pip install librosa onnxruntime soundfile soxr demucs-onnx
```
模型（4 轨，约 150 MB）从插件 release 下，校验后放到 `data/models/`。

### Step 2 · 取包络（新写 `src/stems.py`）

```python
from demucs_onnx.inference import separate
stems = separate("input/song.flac", None, model="htdemucs", precision="fp16weights")
# stems: {"vocals","drums","bass","other"} -> 44100 Hz 数组
# 对每轨算 100 Hz RMS，存 data/audio/stem_<name>.npy
```

### Step 3 · 接进 `scene.py`

`frame(t)` 保持纯函数，但改为查表：`stem_drums[t*100]`、`stem_bass[t*100]`……渲染函数据此决定脉冲、振幅、亮度。**不引入随机，不引入跨帧状态。**

验收：出一段 **15 秒无声测试片**，只看运动质感——如果还需要靠平移制造"动感"，说明接错了。

---

## 5. 不建议做的事

- **不装成 DSH 插件**：我们只要测量，不需要 `process.spawn` 权限常驻。
- **不用它的 ASR 当歌词**：版权 + 准确率双重问题；歌词仍用你提供的 LRC。
- **不用它的"曲风/乐器标签"**：README 自己写了中文民乐不可靠。
- **不让它进渲染管线**：分析是离线的，渲染必须是 `f(t)` 纯函数 + 查表。

---

## 6. 一句话结论

**这个插件的价值不是"它能分析歌"，而是"它能把歌拆成四条独立的时间序列"。** 我们缺的正是这个——有了四条序列，运动才有内容可依，才不会只剩平移。
