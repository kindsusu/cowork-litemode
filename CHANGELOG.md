# Changelog

## 0.2.2 — 2026-09-03
- 서버가 자기 호출을 `%APPDATA%\Claude\lite-mode\calls.jsonl`에 기록 (시각·툴·반환 글자·원본 KB·성공 여부. 내용 없음). 클라우드 세션 사용량 측정의 유일한 근거
- `tools/lite_report.py` 추가 — 한도 소모 속도 / lite 툴 호출 / 로컬 세션 상세를 배포 전후로 비교

## 0.2.1 — 2026-09-03
- 경로 매핑에 **로컬 세션** 기록(`claude-code-sessions\…\local_<id>.json`) 추가. 최후 폴백으로 바탕화면·문서에서 동명 폴더 검색
- 3차 파일럿(로컬 세션)에서 매핑 누락이 드러나 수정. 4차(다른 PC)에서 세션 안 ✗ 0건 확인

## 0.2.0 — 2026-09-03
- **컨테이너 경로 → PC 경로 매핑** (`/sessions/<이름>/mnt/<폴더>/…`). 서버는 PC에서 돌고 Claude는 컨테이너 경로를 넘긴다는 걸 2차 파일럿에서 확인
- `checkpoint_verify`: 행 번호 대조, 웹(URL) 출처는 `추정` 강제, '대화' 출처 행은 따옴표 불요, 파일 출처는 따옴표 필수
- `fetch_lite`: 본문 뒤 관련기사 목록 절단 (문장 종결 없는 150자+ 문단에서 컷)
- SKILL.md v0.2: 긴 툴 이름 안내, 위험 구간은 30~200KB 중간 파일, 서브에이전트 위임은 조건부(고정비 4만 토큰), 웹 인용은 fetch_lite 원문을 파일로 저장해 출처로
- `run_quiet`에 `cwd`, `max`(바이트 캡)

## 0.1.0 — 2026-09-03
- 최초. 툴 3개(fetch_lite / read_lite / run_quiet) + checkpoint_verify + docx/xlsx/pptx 추출기 + SKILL.md
- 자체 점검 7/7. 조직 플러그인 ZIP 업로드로 배포하는 구조
