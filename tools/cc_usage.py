#!/usr/bin/env python3
"""Claude Code 로컬 세션 로그에서 토큰 소비를 집계한다. 표준 라이브러리만 사용."""
import io,sys as _s; _s.stdout.reconfigure(encoding="utf-8", errors="replace")
import json, glob, os, sys, collections, datetime

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/.claude/projects")
DAYS = int(os.environ.get("DAYS", "30"))
cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DAYS)).isoformat()

Z = lambda: collections.Counter()
by_model, by_project, by_session = collections.defaultdict(Z), collections.defaultdict(Z), collections.defaultdict(Z)
seen = set()   # (session, message_id) — 스트리밍 중복 방지

for f in glob.glob(os.path.join(ROOT, "**", "*.jsonl"), recursive=True):
    project = os.path.basename(os.path.dirname(f))
    for line in open(f, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("timestamp", "") < cutoff:
            continue
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        u = m.get("usage")
        if not isinstance(u, dict):
            continue
        key = (d.get("sessionId"), m.get("id"))
        if key in seen:
            continue
        seen.add(key)
        c = Z()
        c["in"]    = u.get("input_tokens", 0) or 0
        c["out"]   = u.get("output_tokens", 0) or 0
        c["cread"] = u.get("cache_read_input_tokens", 0) or 0
        c["cwrite"]= u.get("cache_creation_input_tokens", 0) or 0
        c["calls"] = 1
        by_model[m.get("model") or "?"] += c
        by_project[project] += c
        by_session[(project, d.get("sessionId"))] += c

def bill(c):  # 캐시 읽기는 정가의 1/10, 캐시 쓰기는 1.25배로 환산한 "유효 입력"
    return c["in"] + c["cwrite"] * 1.25 + c["cread"] * 0.1

def fmt(n): return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.0f}K"

tot = Z()
for c in by_model.values(): tot += c
raw_in = tot["in"] + tot["cwrite"] + tot["cread"]
print(f"\n최근 {DAYS}일 · 호출 {tot['calls']:,}건 · 세션 {len({s for _, s in by_session}):,}개\n")
print(f"  입력(신규)   {fmt(tot['in']):>8}")
print(f"  캐시 쓰기    {fmt(tot['cwrite']):>8}")
print(f"  캐시 읽기    {fmt(tot['cread']):>8}   ← 정가의 1/10")
print(f"  출력         {fmt(tot['out']):>8}   ← 입력의 5배 단가")
print(f"  ─────────────────────")
print(f"  캐시 적중률  {tot['cread']/raw_in*100:>7.1f}%   (높을수록 좋음, 목표 70%+)")
print(f"  출력 비중    {tot['out']/(raw_in+tot['out'])*100:>7.1f}%\n")

print("모델별 (유효입력 기준 내림차순)")
print(f"  {'모델':<26}{'호출':>7}{'유효입력':>10}{'출력':>9}{'캐시적중':>9}")
for mdl, c in sorted(by_model.items(), key=lambda kv: -bill(kv[1])):
    r = c["in"] + c["cwrite"] + c["cread"]
    print(f"  {mdl[:26]:<26}{c['calls']:>7,}{fmt(bill(c)):>10}{fmt(c['out']):>9}{(c['cread']/r*100 if r else 0):>8.0f}%")

print("\n프로젝트 TOP 10")
for p, c in sorted(by_project.items(), key=lambda kv: -bill(kv[1]))[:10]:
    print(f"  {p[:44]:<44}{fmt(bill(c)):>9}{c['calls']:>7,}회")

print("\n세션 TOP 5 (한 세션이 얼마나 무거워지는가)")
for (p, s), c in sorted(by_session.items(), key=lambda kv: -bill(kv[1]))[:5]:
    r = c["in"] + c["cwrite"] + c["cread"]
    print(f"  {p[:34]:<34}{fmt(bill(c)):>9}{c['calls']:>6}회  캐시{(c['cread']/r*100 if r else 0):>4.0f}%")
print()
