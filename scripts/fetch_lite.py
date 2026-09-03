#!/usr/bin/env python3
"""URL -> 본문만, 예산 안으로. 표준 라이브러리만.  fetch_lite.py URL [--max 2500] [--grep 단어,단어]"""
import sys, re, html, gzip, argparse, urllib.request
from html.parser import HTMLParser
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "tr", "td", "section", "article", "blockquote", "br"}
KEY = re.compile(r"article|articleBody|news_?(body|view|text)|content|story|post[-_]?body", re.I)


class P(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "noscript", "form", "svg", "iframe", "button"}

    def __init__(s):
        super().__init__()
        s.blocks = [[]]; s.skip = 0; s.title = ""; s.in_title = False; s.meta = {}; s.stack = []; s.art = []; s.depth = 0

    def handle_starttag(s, t, attrs):
        a = dict(attrs)
        if t in s.SKIP: s.skip += 1
        elif t == "title": s.in_title = True
        elif t == "meta":
            k = a.get("property") or a.get("name")
            if k in ("og:title", "og:description", "description"): s.meta[k] = a.get("content", "")
            return
        if t in BLOCK: s.blocks.append([])
        if t != "br":
            hit = t == "article" or KEY.search(" ".join(str(a.get(x, "")) for x in ("id", "class", "itemprop"))) is not None
            s.stack.append(hit); s.depth += hit

    def handle_endtag(s, t):
        if t in s.SKIP and s.skip: s.skip -= 1
        elif t == "title": s.in_title = False
        if t in BLOCK: s.blocks.append([])
        if t not in ("br", "meta") and s.stack: s.depth -= s.stack.pop()

    def handle_data(s, d):
        if s.in_title: s.title += d
        elif not s.skip:
            s.blocks[-1].append(d)
            if s.depth: s.art.append(d)


def fetch(url):
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
         "Accept": "text/html,*/*;q=0.8", "Accept-Language": "ko,en;q=0.8", "Accept-Encoding": "gzip"}
    r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=20); raw = r.read()
    if r.headers.get("Content-Encoding", "") == "gzip": raw = gzip.decompress(raw)
    try: return raw, raw.decode("utf-8")
    except UnicodeDecodeError: return raw, raw.decode("cp949", "replace")


def clean(chunks):
    return [x for x in (re.sub(r"\s+", " ", html.unescape(c)).strip() for c in chunks) if len(x) >= 40]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("url"); ap.add_argument("--max", type=int, default=2500); ap.add_argument("--grep", default="")
    a = ap.parse_args()
    try: raw, txt = fetch(a.url)
    except Exception as e:
        print(f"# 가져오기 실패: {e}"); return 1
    p = P(); p.feed(txt)
    art = clean("".join(p.art).split("\n")); src = "article"
    if len(" ".join(art)) >= 200: paras = art                       # 1) 본문 컨테이너 우선
    else:
        src = "density"; paras = clean("".join(b) for b in p.blocks)
        if len(paras) > 8:                                           # 2) 폴백: 40자+ 문단이 가장 밀집된 창(8)부터
            # ponytail: 밀도 창 휴리스틱 - 사이트별 셀렉터 없이 대부분 커버; JS 렌더링 페이지는 og:description 만 답함
            sc = [sum(len(x) for x in paras[i:i + 8]) for i in range(len(paras) - 7)]
            paras = paras[max(range(len(sc)), key=sc.__getitem__):]
    if not a.grep:
        # 본문 뒤에 붙는 관련기사·많이 본 기사 목록 제거 (파일럿 실측: grep 없으면 반환분 절반이 목록).
        # ponytail: 문장 종결("다."/"요.")이 하나도 없는 150자+ 문단 = 헤드라인 뭉치로 보고 그 앞에서 자른다. 본문 400자 확보 후에만 적용
        acc, cut_at = 0, len(paras)
        for i, x in enumerate(paras):
            if acc >= 400 and len(x) > 150 and "다." not in x and "요." not in x:
                cut_at = i; break
            acc += len(x)
        paras = paras[:cut_at]
    if a.grep:
        keys = [k.strip() for k in a.grep.split(",") if k.strip()]
        paras = [x for x in paras if any(k in x for k in keys)] or paras[:5]
    body = "\n".join(paras)
    if src == "density" and len(body) < 150:   # 본문을 못 찾음(JS 렌더링 페이지 등): 메뉴 찌꺼기를 돌려주지 않는다
        if p.meta.get("og:description"): body = p.meta["og:description"]; src = "og:description"
        else: body = ""; src = "실패 - JS 렌더링 페이지일 수 있음. 꼭 필요하면 web_fetch 로 대체"
    cut = len(body) > a.max; body = body[:a.max]
    title = (p.meta.get("og:title") or p.title).strip()[:120]
    print(f"# {title}\n# 원본 {len(raw) // 1024}KB -> {len(body)}자 [{src}]" + (" (잘림: --grep 키워드 또는 --max 확대)" if cut else ""))
    if p.meta.get("og:description"): print(f"# 요약: {p.meta['og:description'][:200]}")
    print(body)


if __name__ == "__main__":
    sys.exit(main() or 0)
