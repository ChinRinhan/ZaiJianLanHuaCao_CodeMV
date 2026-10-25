import subprocess, sys
from pathlib import Path
from PIL import Image
SRC = r"D:/Program Files/JiJiDown/Download/张雨生《再见 兰花草》解析 - 1.lv_0_20260828113910(Av117371859703610,P1).mp4"
OUT = Path("out/ref-analysis"); OUT.mkdir(parents=True, exist_ok=True)
CROP = (40, 400, 1180, 670)      # the commentary band at 1080p
step, per = 10, 5
frames = list(range(4, 392, step))
sheets = []
for si in range(0, len(frames), per):
    group = frames[si:si+per]
    rows = []
    for t in group:
        p = OUT / f"_t{t}.png"
        subprocess.run(["tools/ffmpeg.exe","-v","error","-y","-ss",str(t),"-i",SRC,"-frames:v","1",str(p)], check=True)
        im = Image.open(p).crop(CROP)
        rows.append((t, im))
    w = CROP[2]-CROP[0]; h = (CROP[3]-CROP[1]) * len(rows)
    sheet = Image.new("RGB", (w, h), (0,0,0))
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 22)
    for i,(t,im) in enumerate(rows):
        sheet.paste(im, (0, i*(CROP[3]-CROP[1])))
        d.text((6, i*(CROP[3]-CROP[1])+4), f"{t}s", font=f, fill=(255,80,80))
    out = OUT / f"sheet-{si//per:02d}.png"
    sheet.save(out); sheets.append(out)
    print(out, sheet.size)
