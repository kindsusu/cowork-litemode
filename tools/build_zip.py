#!/usr/bin/env python3
"""배포 ZIP 생성. 저장소 루트에서:  python tools/build_zip.py
- outputs/, __pycache__, zip, 테스트 산출물 제외
- 텍스트 파일은 BOM 제거 + LF 정규화 (Cowork 업로드가 BOM을 거부한다)
- 평면 ZIP(플러그인 표준)과 lite-mode/ 로 감싼 ZIP 두 개를 만든다. 업로드가 거부되면 다른 쪽을 쓴다"""
import json, os, sys, zipfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"outputs", "__pycache__", ".git", "results", "docs", "tools", "assets"}
SKIP_FILES = {"test_out.txt", "README.md", "CHANGELOG.md", "LICENSE", ".gitignore", ".gitattributes"}
ver = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8"))["version"]

def files():
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in fs:
            if f in SKIP_FILES or f.endswith(".zip"): continue
            p = os.path.join(d, f)
            if f.endswith((".md", ".json", ".py", ".js")):
                b = open(p, "rb").read(); nb = (b[3:] if b.startswith(b"\xef\xbb\xbf") else b).replace(b"\r\n", b"\n")
                if nb != b: open(p, "wb").write(nb)
            yield p, os.path.relpath(p, ROOT).replace(os.sep, "/")

def build(out, prefix):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p, rel in files(): z.write(p, prefix + rel)
    with zipfile.ZipFile(out) as z: names = z.namelist()
    print(f"{out} ({os.path.getsize(out) // 1024}KB, {len(names)}개)"); [print("   ", n) for n in names]

build(os.path.join(ROOT, f"lite-mode-{ver}.zip"), "")
build(os.path.join(ROOT, f"lite-mode-{ver}-wrapped.zip"), "lite-mode/")
