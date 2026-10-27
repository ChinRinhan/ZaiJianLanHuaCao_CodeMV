# -*- coding: utf-8 -*-
"""外部二进制（ffmpeg / ffprobe）的位置。

仓库里**不再带 ffmpeg.exe**（169 MB 一个，GitHub 单文件上限 100 MB，而且没必要）。
所以这里统一成一条规则：

1. 有 `tools/ffmpeg.exe`（或 `tools/ffmpeg`）就用它——本地开发机就是这么用的；
2. 没有就用 PATH 里的 `ffmpeg`。

    winget install Gyan.FFmpeg        # 或者自己下一个丢进 tools/

`src/` 里所有需要 ffmpeg 的模块都从这里取，不再各自写死路径。
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SUFFIX = ".exe" if os.name == "nt" else ""


def _pick(name: str) -> str:
    local = ROOT / "tools" / (name + _SUFFIX)
    return str(local) if local.exists() else name


FFMPEG = _pick("ffmpeg")
FFPROBE = _pick("ffprobe")
