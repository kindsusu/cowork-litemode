#!/usr/bin/env python3
"""lite-mode 절감 리포트 — 각 PC에서 실행. 표준 라이브러리만. 대화 내용은 읽지 않고 숫자만 집계한다.
사용:  python lite_report.py --since 2026-09-03        (배포일 기준 전/후 비교)
근거 3가지:
  [A] 한도 소모율   %APPDATA%\\Claude\\plan-usage-history.json  (5분 간격 5시간 한도 %)  ← 직원이 체감하는 그 숫자
  [B] lite 툴 호출  %APPDATA%\\Claude\\lite-mode\\calls.jsonl     (플러그인 서버 자체 기록, 클라우드·로컬 무관)
  [C] 로컬 세션     %APPDATA%\\Claude\\local-agent-mode-sessions\\**\\*.jsonl  (호출당 컨텍스트·툴별 바이트; 로컬 세션만)
"""
import argparse, collections, datetime, glob, json, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
APP = os.path.join(os.environ.get("APPDATA", ""), "Claude")
ap = argparse.ArgumentParser(); ap.add_argument("--since", required=True, help="배포일 YYYY-MM-DD"); ap.add_argument("--days", type=int, default=14, help="전/후 각 기간(일)")
a = ap.parse_args()
SINCE = datetime.datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(hours=9)  # KST 자정 → UTC
BEFORE0 = SINCE - datetime.timedelta(days=a.days); AFTER1 = SINCE + datetime.timedelta(days=a.days)
period = lambda dt: "전" if BEFORE0 <= dt < SINCE else "후" if SINCE <= dt < AFTER1 else None
F = lambda n: f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}K" if n >= 1e3 else f"{n:.0f}"
def delta(before, after):  # 전→후 변화율을 사람 말로
    if not before: return ""
    r = (1 - after / before) * 100
    return f"{r:.0f}% 절감" if r >= 0 else f"{-r:.0f}% 증가"

print(f"lite-mode 절감 리포트 — PC {os.environ.get('COMPUTERNAME','?')} · 배포일 {a.since} · 전/후 각 {a.days}일")

# [A] 한도 소모율: 활동 중(한도 %가 오르는 5분 구간)의 상승분 합 / 활동 시간
print("\n[A] 5시간 한도 소모 속도 (plan-usage-history)")
try:
    H = sorted(json.load(open(os.path.join(APP, "plan-usage-history.json"), encoding="utf-8"))["samples"], key=lambda s: s["t"])
    acc = {"전": [0, 0.0, 0], "후": [0, 0.0, 0]}  # 상승분 합, 활동 시간(h), 100% 도달 샘플 수
    for p, q in zip(H, H[1:]):
        dt = datetime.datetime.fromtimestamp(q["t"] / 1000, datetime.timezone.utc); k = period(dt)
        if not k or q["t"] - p["t"] > 20 * 60 * 1000: continue
        d = q["u"].get("fh", 0) - p["u"].get("fh", 0)
        if d > 0: acc[k][0] += d; acc[k][1] += (q["t"] - p["t"]) / 3.6e6
        if q["u"].get("fh", 0) >= 100: acc[k][2] += 1
    for k in ("전", "후"):
        s, h, full = acc[k]
        print(f"  {k}: 활동 {h:5.1f}h 동안 +{s:4.0f}%  → {s/h if h else 0:5.1f}%/시간   한도 100% 샘플 {full}회")
    b, c = acc["전"], acc["후"]
    if b[1] and c[1]: print(f"  → 시간당 소모 변화: {b[0]/b[1]:.1f}% → {c[0]/c[1]:.1f}%  ({delta(b[0]/b[1], c[0]/c[1])})")
except Exception as e: print("  (읽기 실패:", e, ")")

# [B] lite 툴 호출 기록
print("\n[B] lite 툴 호출 (플러그인 서버 기록 — 세션 종류 무관)")
try:
    calls = [json.loads(l) for l in open(os.path.join(APP, "lite-mode", "calls.jsonl"), encoding="utf-8") if l.strip()]
    by = collections.defaultdict(lambda: [0, 0, 0, 0])  # 호출, 반환 글자, 원본 KB, 실패
    for c in calls:
        dt = datetime.datetime.fromisoformat(c["t"].replace("Z", "+00:00"))
        if period(dt) != "후": continue
        r = by[c["tool"]]; r[0] += 1; r[1] += c.get("out", 0); r[2] += c.get("rawKB") or 0; r[3] += 0 if c.get("ok", True) else 1
    if not by: print("  배포 후 호출 기록 없음 — 플러그인 v0.2.2 이상이 설치됐는지, Claude가 lite 툴을 실제로 쓰는지 확인")
    for t, (n, out, raw, bad) in sorted(by.items(), key=lambda kv: -kv[1][0]):
        line = f"  {t:<18} {n:>4}회  반환 {F(out):>6}자  실패 {bad}"
        if raw: line += f"  원본 {raw:,}KB → 컨텍스트에 실린 건 약 {out/1024:.0f}KB ({(1 - out/(raw*1024))*100:.0f}% 차단)"
        print(line)
except FileNotFoundError: print("  기록 파일 없음 — 배포 후 lite 툴이 한 번도 호출되지 않았거나 v0.2.2 미만")
except Exception as e: print("  (읽기 실패:", e, ")")

# [C] 로컬 세션: 호출당 컨텍스트, 툴 결과 바이트, lite 채택률
print("\n[C] 로컬 세션 상세 (클라우드 세션은 여기 안 잡힘)")
Z = lambda: collections.Counter()
ctx = {"전": Z(), "후": Z()}; tb = {"전": Z(), "후": Z()}; tc = {"전": Z(), "후": Z()}; id2 = {}
def blen(c): return len(c) if isinstance(c, str) else sum(len(x.get("text", "")) for x in c if isinstance(x, dict)) if isinstance(c, list) else 0
for f in glob.glob(os.path.join(APP, "local-agent-mode-sessions", "**", "*.jsonl"), recursive=True):
    for line in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(line)
        except: continue
        m = d.get("message") if isinstance(d.get("message"), dict) else None; ts = d.get("timestamp")
        if not (m and ts): continue
        try: k = period(datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except: continue
        if not k: continue
        u = m.get("usage")
        if isinstance(u, dict):
            ctx[k]["calls"] += 1; ctx[k]["tok"] += (u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0) + (u.get("cache_creation_input_tokens", 0) or 0)
        for b in (m.get("content") or []) if isinstance(m.get("content"), list) else []:
            if not isinstance(b, dict): continue
            if b.get("type") == "tool_use":
                n = b.get("name", ""); n = "lite:" + n.split("__")[-1] if "lite_tools" in n or "lite-tools" in n else n.replace("mcp__workspace__", ""); id2[b.get("id")] = n; tc[k][n] += 1
            elif b.get("type") == "tool_result": tb[k][id2.get(b.get("tool_use_id"), "?")] += blen(b.get("content"))
for k in ("전", "후"):
    c = ctx[k]
    if not c["calls"]: print(f"  {k}: 로컬 세션 없음"); continue
    lite = sum(v for n, v in tc[k].items() if n.startswith("lite:")); nat = sum(tc[k][n] for n in ("web_fetch", "WebFetch", "Read", "bash"))
    print(f"  {k}: 호출 {c['calls']:,}  호출당 컨텍스트 평균 {F(c['tok']/c['calls'])}  lite 툴 {lite}회 vs 원래 툴(web_fetch/Read/bash) {nat}회  → lite 채택률 {lite/(lite+nat)*100 if lite+nat else 0:.0f}%")
    top = sorted(tb[k].items(), key=lambda kv: -kv[1])[:5]; tot = sum(tb[k].values()) or 1
    print("     툴 결과 바이트 상위: " + ", ".join(f"{n} {v/1024:.0f}KB({v/tot*100:.0f}%)" for n, v in top))
b, c = ctx["전"], ctx["후"]
if b["calls"] and c["calls"]: print(f"  → 호출당 컨텍스트 변화: {F(b['tok']/b['calls'])} → {F(c['tok']/c['calls'])}  ({delta(b['tok']/b['calls'], c['tok']/c['calls'])})")

print("\n해석 규칙: [A]가 진짜 성적표(직원이 느끼는 한도). [B]는 lite 툴이 실제로 쓰였는지와 막은 양. [C]는 원인 진단용.")
print("[A]가 안 내려갔는데 [B] 호출이 적으면 → Claude가 lite 툴을 안 고르는 것(SKILL.md 지시 강화). [B]는 많은데 [A]가 그대로면 → 세션 길이·모델 등 다른 요인.")
