# -*- coding: utf-8 -*-
"""Download ffmpeg static build (BtbN) into the workspace. gyan.dev's cert is expired here, BtbN works."""
import os, time, urllib.request, zipfile, shutil, pathlib

DEST = pathlib.Path(r"F:\dafeiyu\lanhuacao-mv\tools")
DEST.mkdir(parents=True, exist_ok=True)
ZIP = DEST / "ffmpeg.zip"
URL = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"

for attempt in range(60):
    have = ZIP.stat().st_size if ZIP.exists() else 0
    req = urllib.request.Request(URL, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        with urllib.request.urlopen(req, timeout=90) as r, open(ZIP, "ab" if have else "wb") as f:
            total = int(r.headers.get("Content-Length") or 0) + have
            while True:
                chunk = r.read(1048576)
                if not chunk:
                    break
                f.write(chunk)
                if f.tell() % (20 * 1048576) < 1048576:
                    print(f"  {f.tell()/1048576:.0f} MB / {total/1048576:.0f} MB", flush=True)
        break
    except Exception as e:
        print(f"  retry {attempt}: {type(e).__name__} at {ZIP.stat().st_size if ZIP.exists() else 0}", flush=True)
        time.sleep(2)

print("downloaded", ZIP.stat().st_size, "bytes", flush=True)
with zipfile.ZipFile(ZIP) as z:
    for n in z.namelist():
        if n.endswith(("ffmpeg.exe", "ffprobe.exe")):
            target = DEST / os.path.basename(n)
            with z.open(n) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print("extracted", target, target.stat().st_size, flush=True)
ZIP.unlink(missing_ok=True)
print("DONE", flush=True)
