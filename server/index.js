#!/usr/bin/env node
// 경량 MCP 서버 - 의존성 0. 툴 결과 크기를 서버가 강제한다.
// 이 서버는 Claude 데스크톱이 사용자 PC(호스트)에서 띄운다. Cowork 세션은 컨테이너에서 돌며 컨테이너 경로를 넘기므로
// 경로를 호스트 폴더로 매핑한다 (hostPath). 파일럿(2026-09-03)에서 확인된 구조.
// ponytail: 줄 단위 JSON-RPC만 지원(Content-Length 프레이밍 없음). Claude 데스크톱은 줄 단위를 쓴다.
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.join(__dirname, "..");

const cap = (s, n) => (s.length > n ? s.slice(0, n) + "\n... [" + (s.length - n) + "자 생략 - grep/max 로 좁히세요]" : s);
const norm = (s) => s.replace(/\s+/g, "");

function py(script, args) {
  for (const p of ["python3", "python"]) {
    const r = spawnSync(p, [path.join(ROOT, "scripts", script), ...args], { encoding: "utf8", timeout: 30000 });
    if (!r.error) return (r.stdout || "") + (r.stderr ? "\n[stderr] " + r.stderr.slice(0, 300) : "");
  }
  return "python 실행 불가";
}

// ── 경로 매핑 ─────────────────────────────────────────────
// Cowork가 세션에 마운트한 호스트 폴더 목록: %APPDATA%\Claude\local-agent-mode-sessions\<계정>\<조직>\remote-session-spaces.json
// 클라우드 세션: local-agent-mode-sessions\<계정>\<조직>\remote-session-spaces.json (entries[].folders)
// 로컬 세션:   claude-code-sessions\<계정>\<조직>\local_<id>.json (필드명 무관 - 절대경로 문자열을 전부 수집)
const APPDATA = process.env.APPDATA || "";
const SPACES = path.join(APPDATA, "Claude", "local-agent-mode-sessions");
const CCS = path.join(APPDATA, "Claude", "claude-code-sessions");
function collectPaths(o, out) {
  if (typeof o === "string") { if (/^[A-Za-z]:[\\/]/.test(o) && fs.existsSync(o) && fs.statSync(o).isDirectory() && !out.includes(o)) out.push(o); }
  else if (Array.isArray(o)) o.forEach((v) => collectPaths(v, out));
  else if (o && typeof o === "object") Object.values(o).forEach((v) => collectPaths(v, out));
}
function hostFolders() {
  const out = [];
  for (const root of [SPACES, CCS]) {
    try {
      for (const acc of fs.readdirSync(root)) {
        const accDir = path.join(root, acc);
        if (!fs.statSync(accDir).isDirectory()) continue;
        for (const org of fs.readdirSync(accDir)) {
          const orgDir = path.join(accDir, org);
          if (!fs.statSync(orgDir).isDirectory()) continue;
          const files = [path.join(orgDir, "remote-session-spaces.json")];
          try { for (const f of fs.readdirSync(orgDir)) if (/^local_.*\.json$/.test(f)) files.push(path.join(orgDir, f)); } catch (e) {}
          for (const f of files) { if (!fs.existsSync(f)) continue; try { collectPaths(JSON.parse(fs.readFileSync(f, "utf8")), out); } catch (e) {} }
        }
      }
    } catch (e) {}
  }
  return out;
}
// 최후 폴백: 바탕화면·문서 아래(깊이 3)에서 같은 이름의 폴더를 찾는다. ponytail: 동명 폴더가 여럿이면 최근 수정된 것
function findFolderByName(name) {
  const home = process.env.USERPROFILE || "";
  const roots = [path.join(home, "Desktop"), path.join(home, "Documents"), path.join(home, "OneDrive", "Desktop"), path.join(home, "OneDrive", "Documents")];
  let best = null;
  const walk = (dir, depth) => {
    let ents; try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
    for (const e of ents) {
      if (!e.isDirectory() || e.name === "node_modules" || e.name.startsWith(".")) continue;
      const p = path.join(dir, e.name);
      if (e.name === name) { const m = fs.statSync(p).mtimeMs; if (!best || m > best.m) best = { p, m }; }
      if (depth > 0) walk(p, depth - 1);
    }
  };
  for (const r of roots) if (fs.existsSync(r)) walk(r, 2);
  return best && best.p;
}
// "/sessions/<이름>/mnt/<폴더>/나머지" -> "<호스트 폴더 경로>\나머지". 상대 경로는 마운트 폴더들 아래에서 찾는다.
function hostPath(p) {
  if (!p) return p;
  const s = String(p).replace(/\\/g, "/");
  const m = s.match(/^\/sessions\/[^/]+\/mnt\/([^/]+)(\/.*)?$/);
  if (m) {
    const hit = hostFolders().find((d) => path.basename(d) === m[1]) || findFolderByName(m[1]);
    if (hit) return path.join(hit, (m[2] || "").replace(/\//g, path.sep));
    return p;
  }
  if (!path.isAbsolute(p) && !fs.existsSync(p)) {
    for (const d of hostFolders()) { const c = path.join(d, p); if (fs.existsSync(c)) return c; }
  }
  return p;
}

const TOOLS = {
  fetch_lite: {
    description: "URL의 본문만 예산(max자) 안으로 가져온다. web_fetch/WebFetch 대신 사용 - 원문 그대로라 인용 대조가 되고, 사용자 PC에서 실행되어 컨테이너의 네트워크 제한을 받지 않는다. grep으로 키워드 문단만 남길 수 있다.",
    inputSchema: { type: "object", properties: { url: { type: "string" }, max: { type: "integer", default: 2500 }, grep: { type: "string", description: "쉼표 구분 키워드" } }, required: ["url"] },
    run: (a) => py("fetch_lite.py", [a.url, "--max", String(a.max || 2500), ...(a.grep ? ["--grep", a.grep] : [])]),
  },
  read_lite: {
    description: "큰 파일을 예산 안으로 읽는다: 앞 head줄 + grep 일치 줄(행 번호 포함). 30KB 넘는 파일은 Read 대신 이걸 쓸 것. 경로는 Cowork에 보이는 그대로 넘기면 된다.",
    inputSchema: { type: "object", properties: { path: { type: "string" }, head: { type: "integer", default: 40 }, grep: { type: "string" }, max: { type: "integer", default: 4000 } }, required: ["path"] },
    run: (a) => {
      const p = hostPath(a.path);
      let t;
      try { t = fs.readFileSync(p, "utf8"); } catch (e) { return "읽기 실패: " + e.message; }
      const L = t.split("\n");
      const out = ["# " + a.path + " - " + L.length + "줄 " + ((Buffer.byteLength(t) / 1024) | 0) + "KB", ...L.slice(0, a.head || 40)];
      if (a.grep) {
        const ks = a.grep.split(",").map((s) => s.trim()).filter(Boolean);
        L.forEach((l, i) => { if (ks.some((k) => l.includes(k))) out.push((i + 1) + ": " + l); });
      }
      return cap(out.join("\n"), a.max || 4000);
    },
  },
  run_quiet: {
    description: "사용자 PC에서 명령을 실행하고 마지막 tail줄 + 종료코드만 돌려준다. 출력이 긴 명령에 사용. cwd는 Cowork에 보이는 폴더 경로.",
    inputSchema: { type: "object", properties: { cmd: { type: "string" }, cwd: { type: "string" }, tail: { type: "integer", default: 30 }, max: { type: "integer", default: 4000 } }, required: ["cmd"] },
    run: (a) => {
      const r = spawnSync(a.cmd, { shell: true, encoding: "utf8", timeout: 120000, cwd: a.cwd ? hostPath(a.cwd) : undefined });
      const o = ((r.stdout || "") + (r.stderr || "")).split("\n");
      // 줄 수와 바이트 둘 다 자른다 - 한 줄짜리 5000자 출력이 tail을 통과하던 구멍
      return cap("exit=" + r.status + "\n" + o.slice(-(a.tail || 30)).join("\n"), a.max || 4000);
    },
  },
  checkpoint_verify: {
    description: "체크포인트의 '사실 표' 인용문이 출처 파일에 실제로 있는지, 적힌 행 번호가 맞는지 대조한다. ✗ 0건이어야 체크포인트가 끝난 것이다. 출처가 '대화'나 URL인 행은 상태가 '추정'이어야 통과.",
    inputSchema: { type: "object", properties: { path: { type: "string", description: "체크포인트 파일 경로 (Cowork에 보이는 그대로)" } }, required: ["path"] },
    run: (a) => {
      const cpPath = hostPath(a.path);
      let t;
      try { t = fs.readFileSync(cpPath, "utf8"); } catch (e) { return "읽기 실패: " + e.message + " (넘긴 경로: " + a.path + ")"; }
      const base = path.dirname(path.resolve(cpPath));
      const cache = {};
      // 반환: {body, office} / null(없음) / undefined(수동 확인 형식)
      const loadSource = (file) => {
        if (file in cache) return cache[file];
        let res = null;
        for (const dir of [base, path.join(base, ".."), process.cwd()]) {
          const p = path.resolve(dir, file);
          if (!fs.existsSync(p)) continue;
          const ext = path.extname(p).toLowerCase();
          if ([".docx", ".xlsx", ".pptx"].includes(ext)) res = { body: py("extract_text.py", [p]), office: true };
          else if ([".pdf", ".hwp", ".hwpx"].includes(ext)) res = undefined; // ponytail: PDF/HWP 추출기 없음 -> 수동 확인
          else res = { body: fs.readFileSync(p, "utf8"), office: false };
          break;
        }
        return (cache[file] = res);
      };
      const rows = t.split("\n").filter((l) => /^\|/.test(l) && !/^\|\s*-/.test(l) && !/^\|\s*항목/.test(l));
      const out = []; let bad = 0; let manual = 0; let n = 0;
      for (const l of rows) {
        const cells = l.split("|").map((c) => c.trim()).filter(Boolean);
        if (cells.length < 4) continue;
        n++;
        const [item, quoteCell, src, status] = cells;
        const q = (quoteCell.match(/"([^"]+)"/) || [])[1];
        // 출처가 '대화'인 행은 대조할 원문이 없으므로 따옴표를 요구하지 않는다. 상태만 '추정'이면 통과 (파일럿 2차 체크포인트 실측 반영)
        if (/^대화/.test(src)) {
          if (status !== "추정") { bad++; out.push("✗ " + item + ": 출처가 '대화'인데 상태가 '" + status + "' (추정이어야 함)"); }
          else out.push("✓ " + item + " (대화·추정)");
          continue;
        }
        if (!q) { bad++; out.push("✗ " + item + ": 인용 부호 없음 - 파일·웹 출처는 원문을 \" \" 안에 넣을 것"); continue; }
        if (/^https?:\/\//.test(src)) {
          // 웹 읽기 도구는 모델이 다시 쓴 텍스트를 돌려주므로 인용 대조가 성립하지 않는다 -> 항상 추정
          if (status !== "추정") { bad++; out.push("✗ " + item + ": 웹 출처는 상태가 '추정'이어야 함 (현재 '" + status + "')"); }
          else out.push("✓ " + item + " (웹·추정)");
          continue;
        }
        // 출처 셀: "파일명 12행" / "파일명 12~40행" / "파일명 시트2" - 파일명에 공백이 있어도 되게 위치 토큰만 뒤에서 떼어낸다
        const lnm = src.match(/(\d+)(?:~(\d+))?행\s*$/);
        const file = src.replace(/\s+(?:\d+(?:~\d+)?행|시트\S*|\d+쪽|p\.\s*\d+)\s*$/u, "").trim();
        const srcRes = loadSource(file);
        if (srcRes === null) { bad++; out.push("✗ " + item + ": 출처 파일 없음 " + file); continue; }
        if (srcRes === undefined) { manual++; out.push("? " + item + ": " + file + " 형식은 자동 대조 불가 - 수동 확인"); continue; }
        if (!norm(srcRes.body).includes(norm(q))) { bad++; out.push("✗ " + item + ": \"" + q.slice(0, 40) + "\" - " + file + " 에서 못 찾음"); continue; }
        if (lnm && !srcRes.office) {
          const a1 = parseInt(lnm[1], 10), z1 = parseInt(lnm[2] || lnm[1], 10);
          const hits = [];
          srcRes.body.split("\n").forEach((x, i) => { if (norm(x).includes(norm(q))) hits.push(i + 1); });
          if (hits.length && !hits.some((h) => a1 <= h && h <= z1)) { bad++; out.push("✗ " + item + ": 인용은 " + hits[0] + "행에 있음 - 출처는 '" + a1 + "행'으로 적힘"); continue; }
          if (!hits.length) { out.push("✓ " + item + " (여러 줄에 걸침 - 행 확인 생략)"); continue; }
        }
        out.push("✓ " + item);
      }
      if (!n) return "✗ 사실 표를 찾지 못했다 - '| 항목 | 원문 인용 | 출처 | 상태 |' 표가 있는지 확인할 것";
      return "검사 " + n + "건 / ✗ " + bad + "건 / 수동확인 " + manual + "건\n" + out.join("\n");
    },
  },
};

// ── 호출 기록 (절감 측정용) ─────────────────────────────
// %APPDATA%\Claude\lite-mode\calls.jsonl 에 한 줄씩: 시각·툴·반환 글자 수·원본 크기(KB, 헤더에서 파싱). 내용은 기록하지 않는다.
// 클라우드 세션은 PC에 대화 기록이 안 남으므로 이 로그가 세션 종류와 무관한 유일한 사용량 근거다.
const LOG_DIR = path.join(APPDATA, "Claude", "lite-mode");
function logCall(tool, text) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const raw = (text.match(/원본 (\d+)KB/) || text.match(/- \d+줄 (\d+)KB/) || [])[1];
    const ok = !/^(# 가져오기 실패|읽기 실패|python 실행 불가|툴 오류)/.test(text);
    fs.appendFileSync(path.join(LOG_DIR, "calls.jsonl"), JSON.stringify({ t: new Date().toISOString(), tool, out: text.length, rawKB: raw ? Number(raw) : null, ok }) + "\n");
  } catch (e) {}
}

const send = (m) => process.stdout.write(JSON.stringify(m) + "\n");
let buf = "";
process.stdin.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (line) handle(JSON.parse(line));
  }
});

function handle(m) {
  const ok = (result) => m.id !== undefined && send({ jsonrpc: "2.0", id: m.id, result });
  if (m.method === "initialize") return ok({ protocolVersion: "2024-11-05", capabilities: { tools: {} }, serverInfo: { name: "lite-tools", version: "0.2.2" } });
  if (m.method === "tools/list") return ok({ tools: Object.entries(TOOLS).map(([name, t]) => ({ name, description: t.description, inputSchema: t.inputSchema })) });
  if (m.method === "tools/call") {
    const t = TOOLS[m.params.name];
    let text;
    try { text = t ? String(t.run(m.params.arguments || {})) : "unknown tool"; } catch (e) { text = "툴 오류: " + e.message; }
    logCall(m.params.name, text);
    return ok({ content: [{ type: "text", text }] });
  }
  if (m.id !== undefined) send({ jsonrpc: "2.0", id: m.id, error: { code: -32601, message: "no such method" } });
}
