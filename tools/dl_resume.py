import urllib.request, ssl, time, pathlib, hashlib, sys
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
URL="https://github.com/ALittleLov/dsh-soundcheck/releases/download/models-v1/htdemucs_fp16weights.onnx"
EXP="d05c269d0178d2a72ad484b10b11dd370193fc923201c3b27a99f848745db70a"
out=pathlib.Path("data/models/stems/htdemucs_fp16weights.onnx")
total=165612636
for attempt in range(200):
    have=out.stat().st_size if out.exists() else 0
    if have>=total: break
    req=urllib.request.Request(URL, headers={"User-Agent":"Mozilla/5.0","Range":f"bytes={have}-"} if have else {"User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r, open(out,"ab" if have else "wb") as f:
            while True:
                b=r.read(1048576)
                if not b: break
                f.write(b)
    except Exception as e:
        time.sleep(0.5)
        if attempt%10==0: print(f"retry {attempt} at {out.stat().st_size if out.exists() else 0}", flush=True)
    if attempt%20==0 and out.exists():
        print(f"  {out.stat().st_size/1048576:.0f}/{total/1048576:.0f} MB", flush=True)
size=out.stat().st_size if out.exists() else 0
print("size", size, "of", total)
if size==total:
    h=hashlib.sha256(out.read_bytes()).hexdigest()
    print("sha256", h, "OK" if h==EXP else "MISMATCH")
