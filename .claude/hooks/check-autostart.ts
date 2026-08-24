/**
 * check-autostart — Ollama 와 oMLX 의 자동 시작·자동 재시작이 **둘 다 꺼져** 있는지.
 *
 * 규칙: .claude/rules/autostart.md
 *  레포 쪽(항상):
 *  - ollama/com.ollama.serve.plist.template, omlx/com.local-llm.omlx.plist.template: RunAtLoad·KeepAlive 가 false
 *  - ollama/install.sh, omlx/install.sh: `brew services start|restart|run` 없음. omlx/install.sh 는
 *    settings.json 의 auto_start_on_launch 를 False 로 쓴다
 *  라이브 쪽(미설치는 skip):
 *  - `brew services list` 에서 ollama·omlx 가 started/scheduled 가 아니다
 *  - ~/Library/LaunchAgents 에 homebrew.mxcl.(ollama|omlx).plist 가 없고, com.ollama.serve / com.local-llm.omlx
 *    plist 는 RunAtLoad·KeepAlive 가 false 이거나 launchctl 에서 disabled 다
 *  - /Library/LaunchAgents, /Library/LaunchDaemons 에 ollama/omlx 항목이 없다
 *  - 로그인 항목(System Events)에 Ollama/oMLX 앱이 없다(권한이 없으면 skip)
 *  - ~/.omlx/settings.json server.auto_start_on_launch === false (키가 없으면 oMLX 기본값 true → 위반)
 */
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { type Check, type Issue, isMain, read, runCli } from "./lib/harness.ts";

export const notes: string[] = [];
const AGENTS = [
  { label: "com.ollama.serve", what: "Ollama" },
  { label: "com.local-llm.omlx", what: "oMLX" },
];

export function run(root: string): Issue[] {
  notes.length = 0;
  return [...checkRepo(root), ...checkLive()];
}

function checkRepo(root: string): Issue[] {
  const issues: Issue[] = [];
  for (const rel of ["ollama/com.ollama.serve.plist.template", "omlx/com.local-llm.omlx.plist.template"]) {
    const t = read(root, rel);
    if (t === null) { issues.push(`${rel} 가 없다`); continue; }
    for (const k of ["RunAtLoad", "KeepAlive"]) if (plistBool(t, k) !== false) issues.push(`${rel}: <key>${k}</key> 는 <false/> 여야 한다(자동 시작·재시작 금지)`);
  }
  for (const rel of ["ollama/install.sh", "omlx/install.sh"]) {
    const t = read(root, rel) ?? "";
    for (const m of t.matchAll(/^[^#\n]*\bbrew\s+services\s+(start|restart|run)\b.*$/gm)) issues.push(`${rel}: '${m[0].trim()}' — brew services 로 띄우지 않는다(KeepAlive/RunAtLoad true)`);
  }
  const omlx = read(root, "omlx/install.sh") ?? "";
  if (!/\['auto_start_on_launch'\]\s*=\s*False/.test(omlx)) issues.push("omlx/install.sh: settings.json 의 server.auto_start_on_launch 를 False 로 쓰지 않는다");
  return issues;
}

function checkLive(): Issue[] {
  const issues: Issue[] = [];
  const home = homedir();
  const uid = process.getuid?.() ?? 501;

  // brew services
  try {
    const list = execFileSync("brew", ["services", "list"], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"], timeout: 15000 });
    for (const l of list.split("\n")) {
      const m = l.match(/^(ollama|omlx)\s+(\S+)/);
      if (m && /^(started|scheduled|error)$/.test(m[2])) issues.push(`brew services: ${m[1]} 가 '${m[2]}' — brew services stop ${m[1] === "omlx" ? "jundot/omlx/omlx" : "ollama"} (자동 재시작 서비스 금지)`);
    }
  } catch { notes.push("brew 없음 또는 services 조회 실패 — brew services 항목 건너뜀"); }

  // ~/Library/LaunchAgents
  const la = join(home, "Library", "LaunchAgents");
  if (existsSync(la)) {
    for (const f of readdirSync(la)) {
      if (/^homebrew\.mxcl\.(ollama|omlx)\.plist$/.test(f)) issues.push(`${la}/${f} 가 있다 — brew services 서비스 잔재, 제거할 것`);
    }
    let disabled = "";
    try { disabled = execFileSync("launchctl", ["print-disabled", `gui/${uid}`], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] }); } catch { /* 읽기 실패 시 plist 값만 본다 */ }
    for (const a of AGENTS) {
      const p = join(la, `${a.label}.plist`);
      if (!existsSync(p)) { notes.push(`${a.what}: ${a.label}.plist 없음 — 건너뜀`); continue; }
      const t = readFileSync(p, "utf-8");
      const isDisabled = new RegExp(`"${a.label}"\\s*=>\\s*disabled`).test(disabled);
      const flags = ["RunAtLoad", "KeepAlive"].filter((k) => plistBool(t, k) !== false);
      if (flags.length && !isDisabled) issues.push(`${a.what}: ${p} 의 ${flags.join("/")} 가 true 이고 서비스도 disabled 가 아니다 — 자동 시작·재시작이 켜져 있다. 레포 템플릿으로 다시 설치(install.sh)`);
    }
  } else notes.push("~/Library/LaunchAgents 없음 — 건너뜀");

  // 시스템 전역
  for (const d of ["/Library/LaunchAgents", "/Library/LaunchDaemons"]) {
    if (!existsSync(d)) continue;
    for (const f of readdirSync(d)) if (/ollama|omlx/i.test(f)) issues.push(`${d}/${f}: 전역 launchd 항목 — 자동 시작 금지`);
  }

  // 로그인 항목 (앱)
  try {
    const items = execFileSync("osascript", ["-e", 'tell application "System Events" to get the name of every login item'], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"], timeout: 10000 });
    for (const n of items.split(",").map((s) => s.trim())) if (/ollama|omlx/i.test(n)) issues.push(`로그인 항목에 '${n}' 이 있다 — 시스템 설정 > 일반 > 로그인 항목에서 제거`);
  } catch { notes.push("로그인 항목 조회 실패(자동화 권한 없음) — 건너뜀"); }

  // oMLX settings.json
  const sp = join(home, ".omlx", "settings.json");
  if (existsSync(sp)) {
    try {
      const s = JSON.parse(readFileSync(sp, "utf-8")) as { server?: { auto_start_on_launch?: unknown } };
      if (s.server?.auto_start_on_launch !== false) issues.push(`${sp}: server.auto_start_on_launch = ${JSON.stringify(s.server?.auto_start_on_launch ?? "없음(기본 true)")} — false 여야 한다(omlx/install.sh 가 쓴다, 또는 admin 설정)`);
    } catch (e) { issues.push(`${sp}: JSON 파싱 실패 — ${(e as Error).message}`); }
  } else notes.push("oMLX: ~/.omlx/settings.json 없음 — 건너뜀");
  return issues;
}

function plistBool(text: string, key: string): boolean | null {
  const m = text.match(new RegExp(`<key>${key}</key>\\s*<(true|false)/>`));
  return m ? m[1] === "true" : null;
}

export const check: Check = { name: "check-autostart", run, notes: () => notes };
if (isMain(import.meta.url)) runCli(check);
