# cowork-litemode

**Claude Cowork 한도 절약 플러그인.** 답변을 줄이지 않는다. 툴 결과가 대화에 밀어넣는 원문을 **서버가 예산 안으로 자르고**, 대화가 커지면 **기계 검증된 체크포인트**로 이어간다. Team / Enterprise 조직에 ZIP 하나로 배포된다.

> **English.** A Claude Cowork plugin that cuts usage-limit burn without shortening answers. It bounds what tool results push into context (web pages, large files, long command output) and, when a session grows, writes a checkpoint whose quoted facts are mechanically verified against their source files. Ships as a single ZIP for Team/Enterprise org plugin upload. Zero npm dependencies. Korean-first docs; the code and tool descriptions are self-explanatory.

## 왜 이 방식인가

Cowork 세션 6,632건을 실측한 결과(한 사용자·30일):

| 관찰 | 값 | 결론 |
|---|---|---|
| 출력 토큰 비중 | **0.02%** | 답변 줄이기는 무의미 |
| 캐시 적중률 | 93.9% | 캐싱은 이미 최적 |
| 호출당 평균 컨텍스트 | **137K** (최대 635K) | 이게 비용 |
| 컨텍스트에 실리는 바이트 | web_fetch 39% · WebSearch 22% · bash 17.5% · Read 15.6% | **툴 결과 크기가 지렛대** |
| 호출당 한도 소모 | 컨텍스트 50~100K: 0.23% → 250K+: **0.68%** | 큰 세션은 호출당 3배 |

Team 플랜 Cowork에서 훅·권한 거부·기본 모델 지정은 동작하지 않는다. **플러그인에 동봉한 MCP 서버**만이 툴 결과 크기를 강제할 수 있는 수단이고, 이 플러그인은 그 구조다.

## 도구 4개

| 도구 | 대체 대상 | 하는 일 |
|---|---|---|
| `fetch_lite(url, max, grep)` | web_fetch / WebFetch | 본문만 예산 안으로. 사용자 PC에서 실행되어 컨테이너 네트워크 제한을 받지 않고, **원문 그대로**라 인용 대조가 된다 |
| `read_lite(path, head, grep)` | 대형 Read | 앞 N줄 + 키워드 일치 줄(행 번호 포함) |
| `run_quiet(cmd, cwd, tail)` | 긴 bash | 마지막 N줄 + 종료코드, 바이트 캡 |
| `checkpoint_verify(path)` | — | 체크포인트의 인용문이 출처 파일에 **실제로 있는지, 행 번호가 맞는지** 대조. ✗ 0건이어야 통과 |

서버는 Claude 데스크톱이 **사용자 PC에서** 띄우고, 클라우드·로컬 세션 어느 쪽이든 브리지로 연결된다. Claude가 넘기는 컨테이너 경로(`/sessions/…/mnt/폴더/…`)는 서버가 PC 경로로 바꾼다.

## 체크포인트 — 맥락을 잃지 않고 대화를 끊는 법

긴 세션의 컨텍스트는 95%가 원문 덩어리다. 체크포인트는 **원문은 버리고 위치만 남기며, 사실은 요약하지 않고 원문 그대로 복사**한다.

```
| 항목   | 원문 인용                                  | 출처                  | 상태 |
| 계약금 | "계약금은 540만 원(부가세 별도)으로 한다"   | 계약서_v3.docx 12행   | 확인 |
| 담당   | 김OO 부장                                  | 대화                  | 추정 |
```

- 파일 출처 행은 따옴표 안에 원문 그대로. 검증기가 파일을 열어 **문자열과 행 번호**를 대조한다 (docx/xlsx/pptx 포함)
- 웹(URL) 출처는 무조건 `추정` — 웹 읽기 도구는 모델이 다시 쓴 텍스트를 돌려주므로 인용이 성립하지 않는다. 원문이 필요하면 `fetch_lite` 결과를 파일로 저장해 그 파일을 출처로
- `대화` 출처는 `추정`만 허용
- 서사(뭘 했고 왜)는 짧게. 사실 표와 다르면 사실 표가 우선

규칙 전문은 [`skills/lite-mode/SKILL.md`](skills/lite-mode/SKILL.md).

## 설치

**전제조건 — 각 PC에 `node`와 `python`이 PATH에 있어야 한다.** 서버는 PC의 Node로, 본문 추출기와 문서 추출기는 Python으로 실행된다(둘 다 표준 라이브러리만).

```bash
node -v
python --version
```

**조직 배포 (Owner):**

1. [Releases](../../releases)에서 ZIP을 받거나 직접 만든다:
   ```bash
   python tools/build_zip.py        # outputs/·zip 제외, BOM 없는 UTF-8·LF 로 정규화
   ```
2. claude.ai → 조직 설정 → 플러그인 → **플러그인 추가 → 파일 업로드** (≤50MB)
3. 상태: **필수**(전원 자동 설치·삭제 불가) / 기본 설치 / 설치 가능 / 숨김
4. 같은 이름으로 재업로드하면 덮어쓰기. 데스크톱 앱 재시작 후 반영

**확인:** Cowork 새 작업에서 *"사용할 수 있는 도구 이름을 나열해줘"* → `…lite_tools__fetch_lite` 등 4개가 보이면 된다. 이름에 긴 접두어가 붙는 것이 정상이다.

## 효과 검증

기준선은 각 PC에 이미 쌓여 있다(한도 기록 30일, 세션 기록). 배포 2주 후 각 PC에서:

```bash
python tools/lite_report.py --since 2026-09-03
```

세 칸이 나온다 — **[A] 5시간 한도 소모 속도(%/시간)**: 직원이 체감하는 성적표 / **[B] lite 툴 호출·막은 KB**: 채택 여부 / **[C] 로컬 세션 상세**: 원인 진단. 읽는 법과 판정 규칙은 [`docs/measure.md`](docs/measure.md).

기대치는 정직하게: 비슷한 구조의 도구들이 **훅으로 강제 가능할 때 ~98%, 지시만으로 ~60%** 절감을 보고한다. Cowork는 후자라 **절반 전후**가 현실적 목표다. 파일 조회 과제의 A/B 실측에서는 읽기 규율만으로 변동 토큰 88.7% 절감(정확도 동률), 서브에이전트 위임은 고정비 약 4만 토큰이라 대부분 손해였다.

## 구성

```
.claude-plugin/plugin.json   매니페스트
.mcp.json                    node server/index.js
server/index.js              MCP 서버 (의존성 0). 경로 매핑, 호출 기록
scripts/fetch_lite.py        URL → 본문 (컨테이너 우선 → 밀도 폴백 → og:description → 실패 명시)
scripts/extract_text.py      docx/xlsx/pptx 텍스트
skills/lite-mode/SKILL.md    규칙·양식
test_lite.py                 자체 점검 (python test_lite.py)
tools/lite_report.py         전후 비교 리포트
tools/cowork_usage.py        Cowork 세션 토큰·툴별 바이트 집계
tools/cc_usage.py            Claude Code 세션 토큰 집계
tools/build_zip.py           배포 ZIP 생성
docs/pilot.md                파일럿 절차 (관문 순서대로)
docs/measure.md              측정·판정
```

## 알아둘 것

- **강제가 아니다.** Claude가 native `web_fetch`/`Read` 대신 lite 툴을 고르는 건 SKILL.md 지시를 따르는 것이다. 다만 일단 고르면 크기는 서버가 강제하고, 「필수」 배포로 전원에게 동일하게 깔린다
- 위험 구간은 큰 파일이 아니라 **30~200KB 중간 파일**이다. 작으면 통째로 읽어도 싸고, 크면 모델이 알아서 grep 한다
- JS 렌더링 페이지는 `fetch_lite`가 실패를 명시하고 WebFetch로 넘긴다
- 호출 기록(`%APPDATA%\Claude\lite-mode\calls.jsonl`)에는 시각·툴·글자 수만 남고 내용은 남지 않는다

## 라이선스

MIT
