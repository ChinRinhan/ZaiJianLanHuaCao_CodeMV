import hashlib, urllib.request, ssl, pathlib, sys
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
DST=pathlib.Path("data/models/stems"); DST.mkdir(parents=True, exist_ok=True)
URLS=["https://github.com/ALittleLov/dsh-soundcheck/releases/download/models-v1/htdemucs_fp16weights.onnx",
      "https://hf-mirror.com/StemSplitio/htdemucs-onnx/resolve/main/htdemucs_fp16weights.onnx"]
EXP="d05c269d0178d2a72ad484b10b11dd370193fc923201c3b27a99f848745db70a"
out=DST/"htdemucs_fp16weights.onnx"
for u in URLS:
    try:
        req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r, open(out,"wb") as f:
            total=int(r.headers.get("Content-Length") or 0); got=0
            while True:
                b=r.read(1048576)
                if not b: break
                f.write(b); got+=len(b)
            print("downloaded", got, "of", total)
        h=hashlib.sha256(out.read_bytes()).hexdigest()
        print("sha256", h, "OK" if h==EXP else "MISMATCH")
        if h==EXP: break
    except Exception as e:
        print("fail", u[:60], type(e).__name__, str(e)[:80])
