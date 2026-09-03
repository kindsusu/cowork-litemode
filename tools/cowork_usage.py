import json, glob, os, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""Cowork 로컬 세션 토큰·툴별 바이트 집계. 표준 라이브러리만.  python tools/cowork_usage.py"""
ROOT = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Claude", "local-agent-mode-sessions")
Z = collections.Counter
by_model, by_sess = collections.defaultdict(Z), collections.defaultdict(Z)
tool_calls, tool_bytes = Z(), Z()
id2name, seen = {}, set()
def blen(c):
    if isinstance(c, str): return len(c)
    if isinstance(c, list): return sum(len(x.get("text","")) if isinstance(x,dict) else len(str(x)) for x in c)
    return len(str(c))
for f in glob.glob(os.path.join(ROOT, "**", "*.jsonl"), recursive=True):
    for line in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(line)
        except: continue
        m = d.get("message")
        if not isinstance(m, dict): continue
        content = m.get("content")
        if isinstance(content, list):
            for b in content:
                if not isinstance(b, dict): continue
                if b.get("type") == "tool_use":
                    id2name[b.get("id")] = b.get("name","?"); tool_calls[b.get("name","?")] += 1
                elif b.get("type") == "tool_result":
                    tool_bytes[id2name.get(b.get("tool_use_id"), "?")] += blen(b.get("content"))
        u = m.get("usage")
        if not isinstance(u, dict): continue
        k = (d.get("sessionId"), m.get("id"))
        if k in seen: continue
        seen.add(k)
        c = Z(); c["in"]=u.get("input_tokens",0) or 0; c["out"]=u.get("output_tokens",0) or 0
        c["cr"]=u.get("cache_read_input_tokens",0) or 0; c["cw"]=u.get("cache_creation_input_tokens",0) or 0; c["n"]=1
        by_model[m.get("model") or "?"] += c; by_sess[d.get("sessionId")] += c
tot = Z()
for c in by_model.values(): tot += c
raw = tot["in"]+tot["cw"]+tot["cr"]
F = lambda n: f"{n/1e6:.1f}M" if n>=1e6 else f"{n/1e3:.0f}K"
print(f"Cowork 세션 {len(by_sess)}개 · 호출 {tot['n']:,}건")
print(f"  신규입력 {F(tot['in'])}  캐시쓰기 {F(tot['cw'])}  캐시읽기 {F(tot['cr'])}  출력 {F(tot['out'])}")
print(f"  캐시적중 {tot['cr']/raw*100:.1f}%   출력비중 {tot['out']/(raw+tot['out'])*100:.2f}%   호출당 컨텍스트 평균 {F(raw/max(tot['n'],1))}")
print("\n모델별"); [print(f"  {k[:28]:<28}{c['n']:>6}건  캐시읽기 {F(c['cr']):>7}  출력 {F(c['out']):>6}") for k,c in sorted(by_model.items(), key=lambda kv:-kv[1]['cr'])]
tb = sum(tool_bytes.values()) or 1
print(f"\n툴 결과 크기 TOP (컨텍스트에 실리는 바이트 · 총 {F(tb)}B)")
for name, b in sorted(tool_bytes.items(), key=lambda kv:-kv[1])[:15]:
    print(f"  {name[:40]:<40}{F(b):>8}B {b/tb*100:>5.1f}%  호출 {tool_calls[name]:>5}  평균 {F(b/max(tool_calls[name],1)):>6}B")
print("\n세션 TOP 5 (캐시읽기 기준)")
for s, c in sorted(by_sess.items(), key=lambda kv:-kv[1]['cr'])[:5]:
    print(f"  {str(s)[:12]}  호출 {c['n']:>4}  캐시읽기 {F(c['cr']):>7}  신규 {F(c['in']):>5}  출력 {F(c['out']):>5}")
