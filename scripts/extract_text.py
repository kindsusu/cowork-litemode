#!/usr/bin/env python3
"""docx / xlsx / pptx 에서 텍스트만 뽑는다 (표준 라이브러리만). checkpoint_verify 가 인용문 대조에 쓴다."""
import sys, re, html, zipfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def strip(xml: bytes) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", xml.decode("utf-8", "replace")))


def main(p: str) -> int:
    ext = p.lower().rsplit(".", 1)[-1]
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        if ext == "docx":
            parts = ["word/document.xml"] + [n for n in names if re.match(r"word/(header|footer|footnotes)\d*\.xml", n)]
        elif ext == "xlsx":
            parts = [n for n in names if n == "xl/sharedStrings.xml" or n.startswith("xl/worksheets/sheet")]
        elif ext == "pptx":
            parts = sorted(n for n in names if re.match(r"ppt/slides/slide\d+\.xml", n))
        else:
            print(f"# 미지원 형식: {ext}"); return 1
        for n in parts:
            if n in names:
                print(strip(z.read(n)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
