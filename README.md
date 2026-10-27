# 再见兰花草 —— TUI 风格同人 MV

![封面](assets/cover-16x9.png)

张雨生《再见 兰花草!》（1994，专辑《卡拉OK·台北·我》末曲，6:35）的**代码逐帧生成** TUI 风格同人 MV。
每一帧都是歌曲时间 `t` 的纯函数，一条命令从音频渲染到 mp4。**非官方同人，不商用。**

成片 `out/film-v2.mp4`（1280×720 / 24 fps / 395.667 s）· 4K 版 `python src/build.py 4k` → `out/film_4k.mp4`（3840×2160，3× 最近邻）

- 仓库：`ZaiJianLanHuaCao_CodeMV` · 本地 `F:\dafeiyu\lanhuacao-mv` · git `main`
- **接手必读**：[`plan/21-交接文档.md`](plan/21-交接文档.md) → [`plan/INDEX.md`](plan/INDEX.md)

---

## 目录结构

```
lanhuacao-mv/
├── README.md              本文件
├── input/                 素材：song.flac（39 MB）、lyrics.lrc
├── data/                  时间轴与分析数据（json 在 git 内；音频派生文件在 gitignore）
│   ├── timeline.json      段落 + 行级时间，全片唯一时间真源
│   ├── word_times*.json   逐字时间（v2 = 实测 onset）
│   ├── beat_times.json    节拍网格
│   └── audio/             人声分轨、频谱带、谱通量（可由脚本重建）
├── src/                   源码（21 个模块 + probes/ 一次性探针）
│   ├── README.md          源码分层地图
│   └── probes/            7 个一次性调查脚本，不参与出片
├── plan/                  22 份演进文档 + INDEX
│   └── INDEX.md           文档功能地图（先读这份）
├── out/                   产物
│   ├── films/             成片 mp4
│   ├── reports/           对齐报告、OCR、分析图
│   ├── reference/         参考片抽帧、静帧审片、听感记录
│   ├── scene4/ a1/        新版式关键帧
│   ├── m2/ preview/ views/ proof/   各阶段审片静帧
│   └── frames/            渲染中间帧（渲染时自动重建，勿提交）
├── tools/                 ffmpeg.exe / ffprobe.exe + 下载脚本
├── .venv-audio/           音频分离用虚拟环境（htdemucs）
└── .vendor/               proof_motion.py 的本地依赖（cv2/numpy）
```

`再见兰花草-段落结构.md` 在 `F:\WorkBuddy\2026-10-26-01-30-30\`（外部产出，段落结构分析）。

---

## 快速开始

```bash
cd F:/dafeiyu/lanhuacao-mv/src

python shots.py        # 镜头表自检（覆盖 + 网格偏差）
python drive.py        # 四轨信号自检
python views.py --contact   # 审片表（contact sheet，一次看全）
```

**出片**（新四区版式，约 285 秒，后台跑）：

```bash
cd F:/dafeiyu/lanhuacao-mv/src
python render.py 0 395.667 films/film-v2.mp4 --workers 8 --scene scene4
```

> `render.py` 的第三个参数是相对 `out/` 的路径，所以写 `films/xxx.mp4` 会落到 `out/films/`。
> 它会 `rmtree` 同名帧目录后重渲，**不支持断点续渲**。

**环境**（不在 PATH 里，用绝对路径）：

- Python `C:\Users\RedStarCLH\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`
- ffmpeg / ffprobe：仓库内 `tools/`
- 人声分离需要 `.venv-audio`

---

## 当前进度

见 [`plan/21-交接文档.md`](plan/21-交接文档.md)。一句话：**旧片 `out/films/film.mp4` 完整可播；新片（四区版式）只渲到 32 %**，A① 十镜头已验，B① 大字与 UNDO 帧未验。
