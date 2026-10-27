# input/ —— 你要自备的东西

这个目录里**只有两样东西进仓库**：

| 文件 | 是什么 |
|---|---|
| `album-cover.jpg` | 1994《卡拉OK·台北·我》原版封面（500×500），从歌曲文件里内嵌的那张取出来的。版权归原权利人，见 `../NOTICE.md` |
| `README.md` | 本文件 |

**下面这些不在仓库里**（版权素材，也不该由这个仓库分发）：

## 1. 歌曲 `input/song.flac`

片子的时间轴、逐字起音、响度、分轨分析全是从**这一份音频**量出来的，所以它必须和你手上的一致：

- 张雨生《再见 兰花草》，1994，专辑《卡拉OK·台北·我》末曲
- **395.666667 s**（6:35），44.1 kHz / 立体声
- 文件名固定为 `song.flac`（也认 `song.mp3`，但 FLAC 更好——`src/probes/` 里的分轨探针要无损）

```bash
# 校验长度（应该是 395.666667）
tools/ffprobe.exe -v error -show_entries format=duration -of default=nw=1:nk=1 input/song.flac
```

时长对不上，`data/timeline.json` 里的每一句都会错位——**这是唯一一个必须严格对上的输入**。

## 2. 歌词 `input/lyrics.lrc`

只有 `src/audio_analysis.py` 用它（分析阶段），出片不需要。想要就自己放一份。

## 3. 原曲分轨 `再见 兰花草 - 张雨生_分轨/`（257 MB）

合唱段的「第几句几个人在唱」「和声比主唱响多少 dB」是从这份 **17 轨分轨**量出来的
（Demucs 的四轨量不出来——它把所有和声压进 vocals 一轨）。

**量出来的结论已经进仓库了**（`data/backing_vocal*.json`），所以出片不需要这份分轨；
只有想重新量的时候才需要。目录名和位置要严格一致（见 `.gitignore` 最后一条）。

重新量需要一套音频分析环境（仓库里不带，本地也删了）：

```bash
python -m venv .venv-audio
.venv-audio/Scripts/python.exe -m pip install librosa onnxruntime soundfile soxr demucs-onnx
```

模型（htdemucs，4 轨约 150 MB）放到 `data/models/`，由 demucs 首次运行时自动下载。
完整步骤见 `plan/07-插件审查-dsh-soundcheck.md` §Step 1。
