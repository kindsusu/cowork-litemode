"""자체 점검: 추출기(뉴스 URL) + MCP 서버 스모크 테스트. 저장소 루트에서  python test_lite.py
네트워크가 필요하다(뉴스 URL 2건). 선택 환경변수:
  LITE_TEST_DOCX    "[대괄호] 안만 바꾸면 바로 쓸 수 있습니다" 문장이 든 .docx 경로 → docx 원문 대조 검사
  LITE_TEST_FOLDER  Cowork에 마운트된 적 있는 폴더 이름(경로 아님). 그 폴더의 outputs/체크포인트.md 로 컨테이너 경로 매핑 검사
"""
import json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
os.makedirs("outputs", exist_ok=True)

print("=== 추출기: 뉴스 URL ===")
for u in ["https://www.newspim.com/news/view/20260702000140",
          "https://www.etoday.co.kr/news/view/2470000",
          "https://www.yna.co.kr/view/AKR20260622000100003"]:
    r = subprocess.run([sys.executable, "scripts/fetch_lite.py", u, "--max", "300"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
    print("---", u.split("/")[2]); print((r.stdout or r.stderr).strip()[:420])

# 픽스처
FOLDER = os.environ.get("LITE_TEST_FOLDER", "no-such-folder")
HAS_FOLDER = FOLDER != "no-such-folder"
SRC_DOCX = os.environ.get("LITE_TEST_DOCX", "")
HAS_DOCX = bool(SRC_DOCX) and os.path.exists(SRC_DOCX)
# 진짜 인용 1 + 지어낸 인용 1 + 대화/확인 오표기 1 + 대화/추정 1 -> ✗ 2건이어야 한다
open("outputs/체크포인트_test.md", "w", encoding="utf-8").write(
    "# 체크포인트 — 테스트\n\n## 사실 표\n| 항목 | 원문 인용 | 출처 | 상태 |\n|---|---|---|---|\n"
    '| 서버 설명 | "경량 MCP 서버 - 의존성 0" | server/index.js 2행 | 확인 |\n'
    '| 지어낸 것 | "계약금은 540만 원(부가세 별도)으로 한다" | server/index.js 99행 | 확인 |\n'
    '| 담당 | "김OO 부장" | 대화 | 확인 |\n'
    '| 담당2 | "박OO 과장" | 대화 | 추정 |\n')
if HAS_DOCX:
    import shutil; shutil.copy(SRC_DOCX, "outputs/샘플 문서.docx")
    with open("outputs/체크포인트_test.md", "a", encoding="utf-8") as fh:
        fh.write('| 사용법 | "[대괄호] 안만 바꾸면 바로 쓸 수 있습니다" | 샘플 문서.docx 1행 | 확인 |\n')
# 행 번호 오기재 + 웹 출처 '확인' 오표기 -> ✗ 2건
open("outputs/체크포인트_line.md", "w", encoding="utf-8").write(
    "## 사실 표\n| 항목 | 원문 인용 | 출처 | 상태 |\n|---|---|---|---|\n"
    '| 서버 설명 | "경량 MCP 서버 - 의존성 0" | server/index.js 99행 | 확인 |\n'
    '| 웹값 | "아무 문장" | https://example.com/a | 확인 |\n')

print("\n=== MCP 서버 스모크 테스트 ===")
print("node", subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip())
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "fetch_lite", "arguments": {"url": "https://www.etoday.co.kr/news/view/2470000", "max": 300}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "read_lite", "arguments": {"path": "server/index.js", "head": 2, "grep": "TOOLS", "max": 400}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "run_quiet", "arguments": {"cmd": sys.executable + " -c \"print('A'*5000)\"", "tail": 2, "max": 200}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "fetch_lite", "arguments": {"url": "https://www.yna.co.kr/view/AKR20260622000100003", "max": 300}}},
    {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "checkpoint_verify", "arguments": {"path": "outputs/체크포인트_test.md"}}},
    {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "checkpoint_verify", "arguments": {"path": "/sessions/any-name/mnt/" + FOLDER + "/outputs/체크포인트.md"}}},
    {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "checkpoint_verify", "arguments": {"path": "outputs/체크포인트_line.md"}}},
]
env = dict(os.environ, CLAUDE_PLUGIN_ROOT=HERE)
r = subprocess.run(["node", "server/index.js"], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=90)
ok = 0; texts = {}
for line in r.stdout.splitlines():
    m = json.loads(line); res = m.get("result", {})
    if "tools" in res: print("tools/list ->", [t["name"] for t in res["tools"]]); ok += 1
    elif "content" in res:
        t = res["content"][0]["text"]; texts[m["id"]] = t; print(f"call#{m['id']} -> {len(t)}자 |", t[:150].replace("\n", " | ")); ok += 1
    else: print("init ->", res.get("serverInfo")); ok += 1
if r.stderr: print("[stderr]", r.stderr[:300])
assert ok == 9, f"응답 {ok}/9"
assert len(texts[5]) < 300, "run_quiet 바이트 캡 실패"
assert "실패" in texts[6] or "og:description" in texts[6] or "[article]" in texts[6], "JS 페이지 폴백 실패"
assert "✗ 2건" in texts[7], "checkpoint_verify: ✗ 2건이어야 함, 실제: " + texts[7][:200]
assert "✓ 서버 설명" in texts[7] and "✓ 담당2" in texts[7], "checkpoint_verify: 진짜 인용/추정 행이 통과해야 함"
if HAS_DOCX: assert "✓ 사용법" in texts[7], "docx 원문 대조 실패: " + texts[7][:300]
if HAS_FOLDER: assert "✗ 0건" in texts[8], "컨테이너 경로 매핑 실패: " + texts[8][:300]
else: assert "읽기 실패" in texts[8], "존재하지 않는 마운트 폴더는 읽기 실패여야 함"
assert "인용은 2행에 있음" in texts[9] and "웹 출처는 상태가" in texts[9], "행 번호/웹 출처 검출 실패: " + texts[9][:300]
print("\nOK: 9/9 응답, 바이트 캡, JS 페이지 폴백, 체크포인트 검증(✗ 2건), 행 번호·웹 출처 검출"
      + (", 컨테이너 경로 매핑" if HAS_FOLDER else " (경로 매핑은 LITE_TEST_FOLDER 지정 시 검사)")
      + (", docx 대조" if HAS_DOCX else ""))
