/**
 * Continuity Self-Test
 *
 * Drives the extension against a fake host, so every branch that only a live
 * session would otherwise exercise is checked from the CLI: loop escalation, the
 * compaction-failure fallback, goal enforcement, the intervention ledger, and the
 * guards that keep a failure inside the extension.
 *
 * This lives in the repository on purpose. Verification kept in a temp directory
 * is invisible to review and disappears (it did — the earlier drivers were lost
 * to `/tmp` cleanup, which is how this file came to exist).
 *
 * Run with `make continuity-selftest`. Exits nonzero on the first broken claim.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { tmpdir } from "node:os";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import continuity from "./index.ts";
import type { HandlerContext } from "./runtime.ts";
import { ENTRY_TYPE, STATE_SUFFIX, emptyState, loadFromDisk, recordRequest } from "./state.ts";

declare const process: {
  argv: string[];
  cwd(): string;
  exit(code?: number): never;
  on(event: string, listener: (reason: unknown) => void): void;
  off(event: string, listener: (reason: unknown) => void): void;
};

// ============================================================
// Constants
// ============================================================

/**
 * State written by a run must not land in `.omp/state/`: measured, a self-test
 * session appeared in `make continuity-report` as a real sample, which is the
 * one table that must contain nothing but live sessions.
 */
const STATE_ROOT = mkdtempSync(join(tmpdir(), "continuity-selftest-"));

/**
 * Every kind `state.ts` declares. Kept as a literal so the coverage claim fails
 * loudly when a kind is added here and driven by no case.
 */
const DECLARED_KINDS: string[] = (() => {
  const source = readFileSync(join(process.cwd(), ".omp", "extensions", "continuity", "state.ts"), "utf-8");
  const declared = /export type LoopKind =([^;]+);/.exec(source);
  return [...(declared?.[1] ?? "").matchAll(/"([A-Za-z]+)"/g)].map((match) => match[1]);
})();

/** Kinds the cases actually drove, filled by `fire` as states are recorded. */
const observedKinds = new Set<string>();

/** Above OMP's `keepRecentTokens` default, so a compaction request is plausible. */
/** Above the 30k floor but below the 45k ceiling, so the percent path decides. */
const TOKENS_ABOVE_FLOOR = 35_000;
const SMALL_WINDOW = 128_000;
const LARGE_WINDOW = 1_000_000;

// ============================================================
// Types
// ============================================================

interface Recorded {
  handlers: Map<string, (event: unknown, ctx: HandlerContext) => unknown>;
  tools: Map<string, ToolLike>;
  steers: string[];
  deliveries: string[];
  entries: Record<string, unknown>[];
  notices: string[];
  compactRequests: number;
  appendThrows?: boolean;
}

interface ToolLike {
  execute: (
    id: string,
    params: unknown,
    signal: unknown,
    onUpdate: unknown,
    ctx: HandlerContext,
  ) => Promise<{ content: { type: string; text: string }[]; details?: unknown }>;
}

// ============================================================
// Functions
// ============================================================

export async function selftest(): Promise<string[]> {
  const failures: string[] = [];
  const check = (claim: string, held: boolean, detail = ""): void => {
    if (held) {
      console.log("    ok   " + claim);
      return;
    }
    failures.push(claim + (detail === "" ? "" : " — " + detail));
    console.log("    FAIL " + claim + (detail === "" ? "" : " — " + detail));
  };

  await loopAndRecovery(check);
  await goalEnforcement(check);
  await silentWithoutGoal(check);
  await ledgerOutcomes(check);
  await unansweredEdits(check);
  await alternatingAndFailing(check);
  await rejectionContainment(check);
  await shutdownPersistence(check);
  await restoreKeepsEveryField(check);
  await readsAreCounted(check);
  await readingIsProgress(check);
  await midLoopShapes(check);
  await automaticPersistence(check);
  await nothingWrittenIsNotDone(check);
  await deliverableBlind(check);
  await resumeArmsItself(check);

  // Coverage measured, not declared: a kind no case drives is a threshold nobody
  // can change safely, and grepping this file for the kind's name proves only
  // that someone typed it. `check-omp-hooks` asks the static half (does anything
  // emit the kind); this asks the half that matters.
  for (const kind of DECLARED_KINDS) {
    check("a case drives the '" + kind + "' detector", observedKinds.has(kind));
  }
  rmSync(STATE_ROOT, { recursive: true, force: true });
  return failures;
}

// ============================================================
// Cases
// ============================================================

/**
 * The two detectors no case drove until the coverage claim said so.
 *
 * `oscillation` is ABAB - two attempts alternating, which reads as progress
 * because each call differs from the last. `errorLoop` is the same failure text
 * from the same tool three times: the session is not learning from the error it
 * keeps receiving.
 */
async function alternatingAndFailing(check: Check): Promise<void> {
  console.log("  oscillation and error loops");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(host, "session_start", {}, ctx);
  for (let cycle = 0; cycle < 3; cycle += 1) {
    for (const path of ["a.py", "b.py"]) {
      fire(host, "tool_call", { toolName: "edit", input: { path } }, ctx);
    }
  }
  fire(host, "turn_end", { toolResults: [{ toolName: "edit" }], messages: [] }, ctx);
  check(
    "alternating between two attempts is a loop",
    (lastState(host)?.loops ?? []).some((loop) => loop.kind === "oscillation"),
  );

  const failing = fakeHost();
  const failingCtx = fakeContext(failing, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(failing, "session_start", {}, failingCtx);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    fire(failing, "tool_call", { toolName: "bash", input: { command: "make check-" + attempt } }, failingCtx);
    fire(
      failing,
      "tool_result",
      { toolName: "bash", isError: true, content: [{ type: "text", text: "make: *** No rule to make target" }] },
      failingCtx,
    );
  }
  fire(failing, "turn_end", { toolResults: [{ toolName: "bash" }], messages: [] }, failingCtx);
  check(
    "the same failure three times is a loop",
    (lastState(failing)?.loops ?? []).some((loop) => loop.kind === "errorLoop"),
  );
}

/**
 * Rewriting one file again and again without running anything is guessing. The
 * guard must fire on the third edit, and a check must clear the count — for the
 * hashline `edit` tool too, whose paths live inside the body.
 */
async function unansweredEdits(check: Check): Promise<void> {
  console.log("  unanswered edits");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(host, "session_start", {}, ctx);

  const write = (path: string): void => {
    fire(host, "tool_call", { toolName: "write", input: { path, content: "x" } }, ctx);
    fire(host, "tool_result", { toolName: "write", isError: false, input: { path, content: "x" }, content: [] }, ctx);
  };
  const endTurn = (): void => {
    fire(host, "turn_end", { toolResults: [{ toolName: "write" }] }, ctx);
  };

  write("app/thrash.py");
  write("app/thrash.py");
  endTurn();
  check("two edits are not a verdict", host.steers.every((text) => !text.includes("no check run")));

  write("app/thrash.py");
  endTurn();
  check("the third unanswered edit is called out", host.steers.some((text) => text.includes("no check run")));
  check("the steer names the file", host.steers.some((text) => text.includes("app/thrash.py")));

  // A check answers the edits that came before it.
  const cleared = fakeHost();
  const clearedCtx = fakeContext(cleared, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(cleared, "session_start", {}, clearedCtx);
  for (let round = 0; round < 4; round++) {
    fire(cleared, "tool_call", { toolName: "write", input: { path: "app/checked.py", content: String(round) } }, clearedCtx);
    fire(cleared, "tool_result", { toolName: "write", isError: false, input: { path: "app/checked.py", content: String(round) }, content: [] }, clearedCtx);
    fire(cleared, "tool_call", { toolName: "bash", input: { command: "make verify" } }, clearedCtx);
    fire(cleared, "tool_result", { toolName: "bash", isError: false, input: { command: "make verify" }, content: [] }, clearedCtx);
    fire(cleared, "turn_end", { toolResults: [{ toolName: "write" }, { toolName: "bash" }] }, clearedCtx);
  }
  check("a check clears the count", cleared.steers.every((text) => !text.includes("no check run")));

  // A shell call that proves nothing must not count as an answer.
  const idle = fakeHost();
  const idleCtx = fakeContext(idle, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(idle, "session_start", {}, idleCtx);
  for (let round = 0; round < 3; round++) {
    const body = "[app/hashline.py#A1B2]\nPUT 1.=1:\n+x = " + String(round) + "\n";
    fire(idle, "tool_call", { toolName: "edit", input: { input: body } }, idleCtx);
    fire(idle, "tool_result", { toolName: "edit", isError: false, input: { input: body }, content: [] }, idleCtx);
    fire(idle, "tool_call", { toolName: "bash", input: { command: "echo still thinking" } }, idleCtx);
    fire(idle, "tool_result", { toolName: "bash", isError: false, input: { command: "echo still thinking" }, content: [] }, idleCtx);
    fire(idle, "turn_end", { toolResults: [{ toolName: "edit" }] }, idleCtx);
  }
  check("an echo is not an answer", idle.steers.some((text) => text.includes("no check run")));
  check("hashline paths are read out of the body", idle.steers.some((text) => text.includes("app/hashline.py")));

  // Writing through `eval` is the harness's own editing path — measured on this
  // session, every harness edit went that way and the guard could not see it.
  const cell = fakeHost();
  const cellCtx = fakeContext(cell, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(cell, "session_start", {}, cellCtx);
  for (let round = 0; round < 3; round++) {
    const code = 'fsx.writeFileSync(".omp/rules/tooling.md", next);';
    fire(cell, "tool_call", { toolName: "eval", input: { code } }, cellCtx);
    fire(cell, "tool_result", { toolName: "eval", isError: false, input: { code }, content: [] }, cellCtx);
    fire(cell, "turn_end", { toolResults: [{ toolName: "eval" }] }, cellCtx);
  }
  check("an eval that writes is an edit", cell.steers.some((text) => text.includes(".omp/rules/tooling.md")));

  // A cell that writes and then runs the gate has answered itself.
  const answered = fakeHost();
  const answeredCtx = fakeContext(answered, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(answered, "session_start", {}, answeredCtx);
  for (let round = 0; round < 4; round++) {
    const code = 'fsx.writeFileSync("a.ts", next); sp("make", ["verify"]);';
    fire(answered, "tool_call", { toolName: "eval", input: { code } }, answeredCtx);
    fire(answered, "tool_result", { toolName: "eval", isError: false, input: { code }, content: [] }, answeredCtx);
    fire(answered, "turn_end", { toolResults: [{ toolName: "eval" }] }, answeredCtx);
  }
  check("a cell that runs the gate answers itself", answered.steers.every((text) => !text.includes("no check run")));
}

/** Loop evidence escalates, and a failed compaction is answered mechanically. */
async function loopAndRecovery(check: Check): Promise<void> {
  console.log("  loop escalation and compaction recovery");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });

  fire(host, "session_start", {}, ctx);
  for (let turn = 0; turn < 3; turn++) {
    for (let call = 0; call < 3; call++) {
      fire(host, "tool_call", { toolName: "grep", input: { pattern: "X", path: "/repo/a.py" } }, ctx);
      fire(host, "tool_result", { toolName: "grep", isError: false, content: [] }, ctx);
    }
    fire(host, "turn_end", { toolResults: [] }, ctx);
  }
  check("a repeated call escalates to a steer", host.steers.length >= 1, "steers=" + String(host.steers.length));
  check("the steer names the evidence", host.steers.some((text) => text.includes("Loop detected")));
  check("the exhausted signature is banned", lastState(host)?.banned?.length === 1);

  fire(
    host,
    "auto_compaction_end",
    { action: "context-full", result: undefined, aborted: false, skipped: false, errorMessage: "summarizer 429" },
    ctx,
  );
  check("a failed pass asks for one more compaction", host.compactRequests === 1);

  const answer = fire(
    host,
    "session_before_compact",
    {
      preparation: {
        firstKeptEntryId: "e42",
        tokensBefore: 180_000,
        messagesToSummarize: [
          { role: "assistant", content: [{ type: "toolCall", name: "grep" }] },
          { role: "toolResult", isError: true, content: [{ type: "text", text: "ECONNREFUSED postgres:5432" }] },
        ],
        previousSummary: "earlier work",
        fileOps: { readFiles: ["x.py"], modifiedFiles: ["y.py"] },
      },
      branchEntries: [],
    },
    ctx,
  );
  const compaction = readCompaction(answer);
  check("the fallback produces a compaction", compaction !== null);
  check("it keeps the runtime's boundary", compaction?.firstKeptEntryId === "e42" && compaction?.tokensBefore === 180_000);
  check("it names the failure", String(compaction?.summary).includes("summarizer 429"));
  check("it carries unresolved errors", String(compaction?.summary).includes("ECONNREFUSED"));
  check("it carries the state forward", Object.keys(compaction?.preserveData ?? {}).includes("continuity"));

  const skipped = fire(
    host,
    "auto_compaction_end",
    { action: "snapcompact", result: undefined, aborted: false, skipped: true },
    ctx,
  );
  check("a skipped pass is not a failure", skipped === undefined && host.compactRequests === 1);

  const compacting = fire(host, "session.compacting", { sessionId: "s", messages: [] }, ctx);
  const context = readContext(compacting);
  check("the goal card is injected as compaction context", context.startsWith("<continuity>"));

  const unrecognised = fire(host, "session_before_compact", { preparation: { nope: true }, branchEntries: [] }, ctx);
  check("an unrecognised payload is left to the runtime", unrecognised === undefined);

  const before = host.notices.length;
  fire(host, "tool_call", { toolName: "grep", get input(): never { throw new Error("boom"); } }, ctx);
  check("a throwing handler is contained", host.notices.length > before);
  check("state is persisted as a session entry", host.entries.length > 0);
}

/** A declared goal with declared acceptance is measured at settle time. */
async function goalEnforcement(check: Check): Promise<void> {
  console.log("  goal enforcement");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(host, "session_start", {}, ctx);

  check("the goal tool is registered", host.tools.has("continuity_goal"));
  check("no goal means settle is untouched", fire(host, "session_stop", { stop_hook_active: false }, ctx) === undefined);

  const tool = host.tools.get("continuity_goal");
  await tool?.execute(
    "t1",
    {
      goal: "probe",
      nextAction: "stop",
      acceptance: [
        { kind: "shell", cmd: "make definitely-not-a-target" },
        { kind: "file", path: "present.txt", exists: true },
        { kind: "manual", text: "a human decides" },
        { kind: "shell", cmd: "rm -rf /" },
      ],
    },
    null,
    null,
    ctx,
  );
  const unmet = fire(host, "session_stop", { stop_hook_active: false }, ctx);
  const context = readAdditionalContext(unmet);
  check("an unmet goal continues the session", readContinue(unmet));
  check("the failing predicate is named", context.includes("NOT met") && context.includes("definitely-not-a-target"));
  check("a manual predicate stays undecided", context.includes("undecided") && context.includes("a human decides"));
  check("an unallowlisted command is rejected, not run", context.includes("rejected"));
  check("verification is debounced", fire(host, "session_stop", { stop_hook_active: false }, ctx) === undefined);

  writeFileSync(join(STATE_ROOT, "present.txt"), "measured\n");
  await tool?.execute("t2", { goal: "the file is there", acceptance: [{ kind: "file", path: "present.txt", exists: true }] }, null, null, ctx);
  check("a met goal settles", fire(host, "session_stop", { stop_hook_active: false }, ctx) === undefined);

  await tool?.execute("t3", { goal: "x", acceptance: [{ kind: "file", path: "nope", exists: true }] }, null, null, ctx);
  check("the recursion guard is honoured", fire(host, "session_stop", { stop_hook_active: true }, ctx) === undefined);

  // The summarizer may paraphrase the card it was handed as context, and
  // `appendEntry` state never reaches the model — so after a rewrite the card is
  // posted as a message. That is the only channel that puts it back verbatim.
  const before = host.steers.length;
  fire(host, "session_compact", { fromExtension: false }, ctx);
  const posted = host.steers.slice(before);
  check("it re-posts the card after a compaction", posted.some((text) => text.includes("<continuity>")));
  check("the re-posted card names the goal", posted.some((text) => text.includes("goal: x")));
  check("it steers into a live run", host.deliveries[host.deliveries.length - 1] === "steer");

  // An idle session can wait for the next prompt; a running one cannot.
  const idleHost = fakeHost();
  const idleCtx = fakeContext(idleHost, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  idleCtx.isIdle = () => true;
  fire(idleHost, "session_start", {}, idleCtx);
  const idleTool = idleHost.tools.get("continuity_goal");
  await idleTool?.execute("t4", { goal: "idle" }, null, null, idleCtx);
  fire(idleHost, "session_compact", { fromExtension: false }, idleCtx);
  check("an idle session waits for the next prompt", idleHost.deliveries[idleHost.deliveries.length - 1] === "nextTurn");
}

/** With no goal declared there is nothing to restate, so nothing is posted. */
async function silentWithoutGoal(check: Check): Promise<void> {
  console.log("  quiet when there is no goal");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(host, "session_start", {}, ctx);
  const before = host.steers.length;
  fire(host, "session_compact", { fromExtension: false }, ctx);
  check("no goal means no card", host.steers.length === before);
}

/** The ledger answers each intervention, and the model profile decides timing. */
async function ledgerOutcomes(check: Check): Promise<void> {
  console.log("  intervention ledger and model profile");
  const host = fakeHost();
  const large = fakeContext(host, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(host, "session_start", {}, large);

  for (let turn = 0; turn < 3; turn++) {
    for (let call = 0; call < 3; call++) {
      fire(host, "tool_call", { toolName: "grep", input: { pattern: "Y" } }, large);
      fire(host, "tool_result", { toolName: "grep", isError: false, content: [] }, large);
    }
    fire(host, "turn_end", { toolResults: [] }, large);
  }
  const opened = lastState(host)?.interventions ?? [];
  check("an intervention opens a ledger row", opened.length >= 1);

  fire(host, "tool_call", { toolName: "write", input: { path: "x.ts" } }, large);
  fire(host, "tool_result", { toolName: "write", isError: false, content: [] }, large);
  fire(host, "turn_end", { toolResults: [{ toolName: "write" }] }, large);
  const resolved = lastState(host)?.interventions ?? [];
  check("progress closes a row as broke", resolved.some((row) => row.outcome === "broke"));
  check("a row records how long it took", resolved.some((row) => typeof row.turnsToOutcome === "number"));

  // Usage is reported, never acted on: the trigger that used to live here
  // deferred on every mid-loop turn and was declined below the runtime's real
  // boundary, so a full window must produce a reading and no request.
  const smallHost = fakeHost();
  const small = fakeContext(smallHost, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  fire(smallHost, "session_start", {}, small);
  fire(smallHost, "turn_end", { toolResults: [] }, small);
  check("a full small window is not compacted from usage", smallHost.compactRequests === 0);
  check("what it read is recorded", /^small 60% \d+$/.test(String(lastState(smallHost)?.lastUsage)),
    String(lastState(smallHost)?.lastUsage));

  // The reading must survive the case that produced the wrong answer before:
  // a catalog window larger than the model's real one.
  const lyingHost = fakeHost();
  const lying = fakeContext(lyingHost, { window: 128_000, percent: 36, tokens: 46_000 });
  fire(lyingHost, "session_start", {}, lying);
  fire(lyingHost, "turn_end", { toolResults: [] }, lying);
  check("a lying window still reports its token count",
    String(lastState(lyingHost)?.lastUsage).includes("46000"), String(lastState(lyingHost)?.lastUsage));
  check("and asks for nothing", lyingHost.compactRequests === 0);

  // A mid-loop turn is the one the runtime cannot be interrupted on, so the
  // reading says so — that is what made the dead trigger visible.
  const loopHost = fakeHost();
  const midLoop = fakeContext(loopHost, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  fire(loopHost, "session_start", {}, midLoop);
  fire(
    loopHost,
    "turn_end",
    { toolResults: [{ toolName: "read" }], messages: [{ role: "assistant", content: [{ type: "toolCall" }] }] },
    midLoop,
  );
  check("a mid-loop turn is marked as such",
    String(lastState(loopHost)?.lastUsage).includes("(mid-loop)"), String(lastState(loopHost)?.lastUsage));
  check("and is never compacted", loopHost.compactRequests === 0);

  const bigHost = fakeHost();
  const big = fakeContext(bigHost, { window: LARGE_WINDOW, percent: 95, tokens: 950_000 });
  fire(bigHost, "session_start", {}, big);
  fire(bigHost, "turn_end", { toolResults: [] }, big);
  check("a large window defers to the runtime", bigHost.compactRequests === 0);
  check("its profile is reported as standard",
    String(lastState(bigHost)?.lastUsage).startsWith("standard"), String(lastState(bigHost)?.lastUsage));
}

/** A rejecting runtime action must not escape as an unhandled rejection. */
async function rejectionContainment(check: Check): Promise<void> {
  console.log("  rejection containment");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  ctx.compact = (): Promise<void> => {
    host.compactRequests += 1;
    return Promise.reject(new Error("Nothing to compact (session too small)"));
  };

  let escaped: unknown = null;
  const onRejection = (reason: unknown): void => {
    escaped = reason;
  };
  process.on("unhandledRejection", onRejection);
  fire(host, "session_start", {}, ctx);
  // The recovery pass is the request that survives: usage no longer asks for
  // anything, so this is the path a rejection can still arrive on.
  fire(
    host,
    "auto_compaction_end",
    { action: "context-full", result: undefined, aborted: false, skipped: false, errorMessage: "summarizer 429" },
    ctx,
  );
  const settled = Promise.withResolvers<void>();
  setTimeout(() => settled.resolve(), 50);
  await settled.promise;
  process.off("unhandledRejection", onRejection);

  check("the recovery request was made", host.compactRequests === 1);
  check("its rejection did not escape", escaped === null, String(escaped));
}

/**
 * A restored blob must keep every field: a field `merge` omits is deleted on
 * every restore, and the next write throws on `undefined.push`.
 */
async function restoreKeepsEveryField(check: Check): Promise<void> {
  console.log("  restore fidelity");
  const root = mkdtempSync(join(tmpdir(), "continuity-restore-"));
  const dir = join(root, ".omp", "state");
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "legacy" + STATE_SUFFIX),
    JSON.stringify({ v: 1, goal: "g", turns: 3, toolCalls: 5 }),
  );

  const restored = loadFromDisk(root, "legacy");
  check("a blob written before a field existed still restores", restored?.turns === 3);
  const state = restored ?? emptyState();
  let threw: unknown = null;
  try {
    recordRequest(state, "small-model-percent", false);
  } catch (error: unknown) {
    threw = error;
  }
  check("recording a request after a restore does not throw", threw === null, String(threw));
  check("the request landed", state.requests.includes("small-model-percent"));
  rmSync(root, { recursive: true, force: true });
}

/**
 * A stall is declared from what was *not* written, so a session reading its way
 * through unfamiliar code looks exactly like a stuck one. The ledger counts the
 * files opened after an intervention, which is the only way to tell a wrong
 * signal from a wrong answer once the samples are in.
 */
/**
 * A turn spent reading has no mutating and no verifying call, so the stall
 * detector cannot tell research from silence on its own. Opening a file for the
 * first time is the evidence that the turn learned something.
 */
async function readingIsProgress(check: Check): Promise<void> {
  console.log("  reading as progress");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(host, "session_start", {}, ctx);

  const readTurn = (path: string): void => {
    fire(host, "tool_call", { toolName: "read", input: { path } }, ctx);
    fire(host, "turn_end", { toolResults: [{ toolName: "read" }] }, ctx);
  };
  readTurn("one.ts");
  readTurn("two.ts");
  readTurn("three.ts");
  readTurn("four.ts");
  check("four turns of new files raise nothing", (lastState(host)?.interventions ?? []).length === 0);

  // the same file again is not a new finding
  readTurn("four.ts");
  readTurn("four.ts");
  readTurn("four.ts");
  check("re-reading the same file still stalls", (lastState(host)?.interventions ?? []).length >= 1);
}

async function readsAreCounted(check: Check): Promise<void> {
  console.log("  reads after an intervention");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 20, tokens: 5_000 });
  fire(host, "session_start", {}, ctx);

  // three empty turns raise the stall and open a ledger row
  for (let turn = 0; turn < 3; turn++) fire(host, "turn_end", { toolResults: [] }, ctx);
  const opened = lastState(host)?.interventions ?? [];
  check("a stall opens a row", opened.length >= 1);

  // The signature repeats on every quiet turn, so failing a row on repetition
  // would close it after one turn and no evidence could land.
  fire(host, "turn_end", { toolResults: [] }, ctx);
  const still = (lastState(host)?.interventions ?? [])[0];
  check("a repeated signature alone does not close the row", still?.outcome === "pending", String(still?.outcome));

  const read = (path: string): void => {
    fire(host, "tool_call", { toolName: "read", input: { path } }, ctx);
    fire(host, "tool_result", { toolName: "read", isError: false, input: { path }, content: [] }, ctx);
  };
  read("a.ts");
  read("b.ts");
  read("a.ts");
  read("a.ts:10-20");
  fire(host, "turn_end", { toolResults: [{ toolName: "read" }] }, ctx);
  const row = (lastState(host)?.interventions ?? [])[0];
  check("the row counts the files opened after it", row?.newPathsAfter === 2, String(row?.newPathsAfter));
  check("a re-read is not a new file", row?.newPathsAfter !== 4, String(row?.newPathsAfter));
}

/**
 * The message shapes a real runtime sends.
 *
 * `event.messages` ends with the **tool result**, not with the assistant message
 * that carried the calls: reading only its last entry called a mid-loop turn a
 * safe boundary, the early compaction cancelled the held request, and a local
 * 35B died with `Request was aborted` forty seconds into every long run. These
 * claims are that shape, plus the `stopReason` the same runtime provides.
 */
async function midLoopShapes(check: Check): Promise<void> {
  console.log("  mid-loop shapes");
  const resultLast = fakeHost();
  const ctx = fakeContext(resultLast, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  fire(resultLast, "session_start", {}, ctx);
  fire(
    resultLast,
    "turn_end",
    {
      toolResults: [{ toolName: "read" }],
      messages: [
        { role: "assistant", content: [{ type: "toolCall" }] },
        { role: "toolResult", content: [{ type: "text", text: "file contents" }] },
      ],
    },
    ctx,
  );
  check("a tool result after the calls is still mid-loop", resultLast.compactRequests === 0);

  const stopReason = fakeHost();
  const stopCtx = fakeContext(stopReason, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  fire(stopReason, "session_start", {}, stopCtx);
  fire(
    stopReason,
    "turn_end",
    {
      toolResults: [{ toolName: "bash" }],
      message: { role: "assistant", stopReason: "toolUse", content: [{ type: "text", text: "checking" }] },
      messages: [{ role: "toolResult", content: [{ type: "text", text: "ok" }] }],
    },
    stopCtx,
  );
  check("stopReason toolUse is mid-loop whatever the content says",
    String(lastState(stopReason)?.lastUsage).includes("(mid-loop)"), String(lastState(stopReason)?.lastUsage));

  // The ladder's third rung compacts. Reached mid-loop it must steer instead,
  // or it cancels the request the loop is holding.
  const rungHost = fakeHost();
  const rungCtx = fakeContext(rungHost, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  fire(rungHost, "session_start", {}, rungCtx);
  for (let turn = 0; turn < 9; turn++) {
    for (let call = 0; call < 3; call++) {
      fire(rungHost, "tool_call", { toolName: "grep", input: { pattern: "Z" } }, rungCtx);
      fire(rungHost, "tool_result", { toolName: "grep", isError: false, content: [] }, rungCtx);
    }
    fire(
      rungHost,
      "turn_end",
      {
        toolResults: [{ toolName: "grep" }],
        message: { role: "assistant", stopReason: "toolUse", content: [{ type: "toolCall" }] },
      },
      rungCtx,
    );
  }
  check("the ladder reached its third rung", (lastState(rungHost)?.escalation ?? 0) >= 3,
    String(lastState(rungHost)?.escalation));
  check("mid-loop the third rung steers instead of compacting", rungHost.compactRequests === 0);
  check("and the steer still went out", rungHost.steers.length >= 3, String(rungHost.steers.length));

  // The closing turn has the same `toolResults` and the same trailing tool
  // result; only the assistant message before it differs.
  const closing = fakeHost();
  const closingCtx = fakeContext(closing, { window: SMALL_WINDOW, percent: 60, tokens: TOKENS_ABOVE_FLOOR });
  fire(closing, "session_start", {}, closingCtx);
  fire(
    closing,
    "turn_end",
    {
      toolResults: [{ toolName: "read" }],
      message: { role: "assistant", stopReason: "endTurn", content: [{ type: "text", text: "done" }] },
      messages: [{ role: "assistant", content: [{ type: "text", text: "done" }] }],
    },
    closingCtx,
  );
  check("a text-only close is a real boundary",
    !String(lastState(closing)?.lastUsage).includes("(mid-loop)"), String(lastState(closing)?.lastUsage));
}

/** A torn-down runtime must not take the final state with it. */
async function shutdownPersistence(check: Check): Promise<void> {
  console.log("  shutdown persistence");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: SMALL_WINDOW, percent: 20, tokens: 26_000 });
  fire(host, "session_start", {}, ctx);
  fire(host, "tool_call", { toolName: "bash", input: { command: "make verify" } }, ctx);
  fire(host, "turn_end", { toolResults: [{ toolName: "bash" }] }, ctx);
  const path = join(STATE_ROOT, ".omp", "state", "selftest.continuity.json");
  rmSync(path, { force: true });
  // This is the shutdown the local runs hit: the runtime rejects every action.
  host.appendThrows = true;
  let threw: unknown = null;
  try {
    fire(host, "session_shutdown", {}, ctx);
  } catch (error: unknown) {
    threw = error;
  }
  check("shutdown does not throw when the runtime is gone", threw === null, String(threw));
  check("the final state reached the disk anyway", existsSync(path));
  host.appendThrows = false;
}

/**
 * Persistence nobody asked for.
 *
 * The goal is the request itself, read off the user's own message - a local
 * model never called `continuity_goal` in any measured run, so anything that
 * depends on declaring a goal does not exist in practice. And "done" is decided
 * by the gate this repository already trusts, not by the model's account of its
 * work: a session that changed files and stops on a red `make verify` has not
 * finished.
 */
async function automaticPersistence(check: Check): Promise<void> {
  console.log("  automatic persistence");
  const repo = join(STATE_ROOT, "auto-repo");
  mkdirSync(repo, { recursive: true });
  run("git", ["init", "-q"], repo);
  // `.omp/state/` is ignored in the real repository, and the gate reads
  // `git status`: without this the extension's own state file makes every
  // worktree dirty, which is exactly what it measured here first.
  writeFileSync(join(repo, ".gitignore"), ".omp/\n");
  run("git", ["add", "-A"], repo);
  writeFileSync(join(repo, "Makefile"), "verify:\n\t@echo 'FAIL: something is broken'; exit 1\n");
  run("git", ["add", "-A"], repo);
  run("git", ["-c", "user.email=s@t", "-c", "user.name=selftest", "commit", "-qm", "base"], repo);

  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  ctx.cwd = repo;
  fire(host, "session_start", {}, ctx);
  fire(host, "message_start", { message: { role: "user", content: [{ type: "text", text: "add the readiness field" }] } }, ctx);
  check("the request becomes the goal", lastGoal(host) === "add the readiness field");

  check(
    "a session that changed nothing settles",
    fire(host, "session_stop", { stop_hook_active: false }, ctx) === undefined,
  );

  // Now the session has changed a file, and the gate says no.
  writeFileSync(join(repo, "touched.txt"), "work\n");
  const blocked = fire(host, "session_stop", { stop_hook_active: false }, ctx);
  check("a red gate refuses the settle", readContinue(blocked));
  const context = readAdditionalContext(blocked);
  check("the gate's own words come back", context.includes("something is broken"));
  check("the request is restated with it", context.includes("add the readiness field"));

  // A green gate on the same dirty worktree settles - the change is finished.
  writeFileSync(join(repo, "Makefile"), "verify:\n\t@true\n");
  const green = fakeHost();
  const greenCtx = fakeContext(green, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  greenCtx.cwd = repo;
  fire(green, "session_start", {}, greenCtx);
  fire(green, "message_start", { message: { role: "user", content: [{ type: "text", text: "finish it" }] } }, greenCtx);
  check(
    "a green gate settles even with a dirty worktree",
    fire(green, "session_stop", { stop_hook_active: false }, greenCtx) === undefined,
  );

  // A steer this extension posted must never be mistaken for a new request.
  fire(green, "message_start", { message: { role: "user", content: [{ type: "text", text: "<continuity>…</continuity>" }] } }, greenCtx);
  check("its own steer is not a new goal", lastGoal(green) === "finish it");
}

/**
 * A green gate is not evidence of finished work.
 *
 * Measured: asked for two migrations, a request file and a fixture, a local
 * model read for eighteen turns, wrote nothing, and settled - the gate was green
 * because the tree it had read was already green. Producing nothing is the one
 * outcome no gate can catch, so the settle asks for the files by name.
 */
async function nothingWrittenIsNotDone(check: Check): Promise<void> {
  console.log("  producing nothing is not finishing");
  const repo = join(STATE_ROOT, "empty-repo");
  mkdirSync(repo, { recursive: true });
  run("git", ["init", "-q"], repo);
  writeFileSync(join(repo, ".gitignore"), ".omp/\n");
  writeFileSync(join(repo, "Makefile"), "verify:\n\t@true\n");
  run("git", ["add", "-A"], repo);
  run("git", ["-c", "user.email=s@t", "-c", "user.name=selftest", "commit", "-qm", "base"], repo);

  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  ctx.cwd = repo;
  fire(host, "session_start", {}, ctx);
  fire(
    host,
    "message_start",
    { message: { role: "user", content: [{ type: "text", text: "write api/new.http and backend/seed_72.py" }] } },
    ctx,
  );
  // A turn that only read, exactly like the measured run.
  fire(host, "turn_end", { toolResults: [{ toolName: "read" }], messages: [] }, ctx);
  const refused = fire(host, "session_stop", { stop_hook_active: false }, ctx);
  check("a session that wrote nothing cannot settle", readContinue(refused));
  const context = readAdditionalContext(refused);
  check("both named files come back", context.includes("api/new.http") && context.includes("backend/seed_72.py"));

  mkdirSync(join(repo, "api"), { recursive: true });
  mkdirSync(join(repo, "backend"), { recursive: true });
  writeFileSync(join(repo, "api", "new.http"), "GET http://localhost:18000/health\n");
  writeFileSync(join(repo, "backend", "seed_72.py"), "revision = '72'\n");
  const answered = fakeHost();
  const answeredCtx = fakeContext(answered, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  answeredCtx.cwd = repo;
  fire(answered, "session_start", {}, answeredCtx);
  fire(
    answered,
    "message_start",
    { message: { role: "user", content: [{ type: "text", text: "write api/new.http and backend/seed_72.py" }] } },
    answeredCtx,
  );
  fire(answered, "turn_end", { toolResults: [{ toolName: "write" }], messages: [] }, answeredCtx);
  check(
    "a session that produced them settles",
    fire(answered, "session_stop", { stop_hook_active: false }, answeredCtx) === undefined,
  );
}

/**
 * Measuring forever instead of delivering.
 *
 * No repetition detector can see this: every call is different and every turn
 * learns something. Measured on a local 35B handed a report to write - twenty
 * minutes, twenty-seven turns, sixty-six tool calls, zero writes. Nothing is
 * declared here either: the request names a file, and the file is not there.
 */
async function deliverableBlind(check: Check): Promise<void> {
  console.log("  deliverable blindness");
  const host = fakeHost();
  const ctx = fakeContext(host, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(host, "session_start", {}, ctx);
  fire(
    host,
    "message_start",
    { message: { role: "user", content: [{ type: "text", text: "write the findings to report-never-written.md" }] } },
    ctx,
  );
  check("asking for a file says nothing by itself", host.steers.length === 0);
  const arrival = host.steers.length;
  const reading = (index: number): void => {
    fire(host, "tool_call", { toolName: "read", input: { path: "note-" + index + ".md" } }, ctx);
    fire(host, "tool_result", { toolName: "read", input: { path: "note-" + index + ".md" }, isError: false }, ctx);
    fire(host, "turn_end", { toolResults: [{ toolName: "read" }], messages: [] }, ctx);
  };
  for (let index = 0; index < 5; index += 1) reading(index);
  check("five turns of honest research are left alone", host.steers.length === arrival);

  reading(5);
  check("the sixth names the deliverable", host.steers.some((text) => text.includes("report-never-written.md")));
  const before = host.steers.length;
  reading(6);
  check("it does not fire again immediately", host.steers.length === before);

  // The same session, once the file exists: silence, because there is nothing
  // to say - the predicate the nudge is built from is met.
  writeFileSync(join(STATE_ROOT, "report-never-written.md"), "measured\n");
  const quietHost = fakeHost();
  const quietCtx = fakeContext(quietHost, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(quietHost, "session_start", {}, quietCtx);
  for (let index = 0; index < 8; index += 1) {
    fire(quietHost, "tool_call", { toolName: "read", input: { path: "other-" + index + ".md" } }, quietCtx);
    fire(quietHost, "turn_end", { toolResults: [{ toolName: "read" }], messages: [] }, quietCtx);
  }
  check("a met predicate says nothing", quietHost.steers.length === 0);
}

/**
 * Reopening a session is the cheapest resume there is, and it only continues the
 * work if the session arms itself from its own history. The acceptance is
 * declared once, in a process that has since exited; kept only in a local
 * variable it was gone, so the resumed session knew its goal and no longer knew
 * what would prove it - and settled on the first "I think I am done".
 */
async function resumeArmsItself(check: Check): Promise<void> {
  console.log("  a resumed session arms itself");
  const first = fakeHost();
  const firstCtx = fakeContext(first, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 });
  fire(first, "session_start", {}, firstCtx);
  const tool = first.tools.get("continuity_goal");
  await tool?.execute(
    "arm",
    { goal: "the absent file appears", acceptance: [{ kind: "file", path: "resume-target.md", exists: true }] },
    null,
    null,
    firstCtx,
  );
  const armed = lastState(first);
  check("the declared acceptance is written into state", (armed?.acceptance ?? []).length === 1);

  // A new process, a new host: everything it knows arrives through the branch,
  // in the shape the runtime stores - a custom entry, not a bare state blob.
  const branch = first.entries.map((data) => ({ type: "custom", customType: ENTRY_TYPE, data }));
  const resumed = fakeHost();
  const resumedCtx = fakeContext(resumed, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 }, branch);
  fire(resumed, "session_start", {}, resumedCtx);
  check("arrival restates the goal", resumed.steers.some((text) => text.includes("the absent file appears")));
  check(
    "the resumed session refuses to settle",
    readContinue(fire(resumed, "session_stop", { stop_hook_active: false }, resumedCtx)),
  );

  writeFileSync(join(STATE_ROOT, "resume-target.md"), "done\n");
  const met = fakeHost();
  const metCtx = fakeContext(met, { window: LARGE_WINDOW, percent: 10, tokens: 4_000 }, branch);
  fire(met, "session_start", {}, metCtx);
  check("a met goal does not nag on arrival", met.steers.length === 0);
}

// ============================================================
// Fake host
// ============================================================

type Check = (claim: string, held: boolean, detail?: string) => void;

interface LedgerRow {
  outcome: string;
  turnsToOutcome: number | null;
  newPathsAfter?: number;
}

/**
 * Only the fields the claims read. Kept in step with `state.ts` on purpose:
 * this shape going stale is what hid `merge` dropping `requests` and
 * `lastUsage` until a live session died on it.
 */
interface StateShape {
  escalation?: number;
  banned?: string[];
  loops?: Array<{ kind: string; count: number }>;
  interventions?: LedgerRow[];
  requests?: string[];
  lastUsage?: string;
  facts?: string[];
  acceptance?: unknown[];
}

function fakeHost(): Recorded {
  return {
    handlers: new Map(),
    tools: new Map(),
    steers: [],
    deliveries: [],
    entries: [],
    notices: [],
    compactRequests: 0,
    appendThrows: false,
  };
}

function fakeContext(
  host: Recorded,
  usage: { window: number; percent: number; tokens: number },
  branch: unknown[] = [],
): HandlerContext {
  return {
    cwd: STATE_ROOT,
    sessionManager: { getSessionId: () => "selftest", getBranch: () => branch },
    models: { current: () => ({ contextWindow: usage.window }) },
    getContextUsage: () => ({ tokens: usage.tokens, contextWindow: usage.window, percent: usage.percent }),
    compact: async () => {
      host.compactRequests += 1;
    },
    ui: {
      notify: (message: string) => host.notices.push(message),
      setStatus: () => undefined,
    },
  };
}

/** The registration surface the factory expects, recorded instead of executed. */
function install(host: Recorded): void {
  const schema = {
    object: () => ({}),
    string: () => ({ describe: () => ({}), optional: () => ({}) }),
    number: () => ({ optional: () => ({}) }),
    boolean: () => ({ optional: () => ({}) }),
    array: () => ({ optional: () => ({ describe: () => ({}) }) }),
    enum: () => ({}),
  };
  continuity({
    logger: { error: () => undefined, info: () => undefined },
    zod: schema,
    setLabel: () => undefined,
    on: (event: string, handler: (event: never, ctx: HandlerContext) => unknown) => {
      host.handlers.set(event, handler as (event: unknown, ctx: HandlerContext) => unknown);
    },
    sendMessage: (message: { content: string }, options?: { deliverAs?: string }) => {
      host.steers.push(message.content);
      host.deliveries.push(String(options?.deliverAs ?? "default"));
    },
    appendEntry: (_type: string, data?: unknown) => {
      if (host.appendThrows === true) {
        throw new Error("Extension runtime not initialized. Action methods cannot be called during extension loading.");
      }
      if (data === null || typeof data !== "object") return;
      host.entries.push({ ...data });
      const loops = Reflect.get(data, "loops");
      if (!Array.isArray(loops)) return;
      for (const loop of loops) {
        if (loop !== null && typeof loop === "object") observedKinds.add(String(Reflect.get(loop, "kind") ?? ""));
      }
    },
    registerTool: (definition: { name: string } & ToolLike) => host.tools.set(definition.name, definition),
  });
}

function fire(host: Recorded, event: string, payload: unknown, ctx: HandlerContext): unknown {
  if (host.handlers.size === 0) install(host);
  return host.handlers.get(event)?.(payload, ctx);
}

function lastState(host: Recorded): StateShape | null {
  const entry = host.entries[host.entries.length - 1];
  return entry === undefined ? null : (entry as StateShape);
}

function readCompaction(
  answer: unknown,
): { firstKeptEntryId: string; tokensBefore: number; summary: string; preserveData: Record<string, unknown> } | null {
  if (answer === null || typeof answer !== "object" || !("compaction" in answer)) return null;
  const compaction = Reflect.get(answer, "compaction");
  if (compaction === null || typeof compaction !== "object") return null;
  const firstKeptEntryId = Reflect.get(compaction, "firstKeptEntryId");
  const tokensBefore = Reflect.get(compaction, "tokensBefore");
  const summary = Reflect.get(compaction, "summary");
  const preserveData = Reflect.get(compaction, "preserveData");
  if (typeof firstKeptEntryId !== "string" || typeof tokensBefore !== "number" || typeof summary !== "string") {
    return null;
  }
  return {
    firstKeptEntryId,
    tokensBefore,
    summary,
    preserveData: preserveData !== null && typeof preserveData === "object" ? { ...preserveData } : {},
  };
}

function readContext(answer: unknown): string {
  if (answer === null || typeof answer !== "object" || !("context" in answer)) return "";
  const context = Reflect.get(answer, "context");
  return Array.isArray(context) && typeof context[0] === "string" ? context[0] : "";
}

function readContinue(answer: unknown): boolean {
  if (answer === null || typeof answer !== "object" || !("continue" in answer)) return false;
  return Reflect.get(answer, "continue") === true;
}

function readAdditionalContext(answer: unknown): string {
  if (answer === null || typeof answer !== "object" || !("additionalContext" in answer)) return "";
  const value = Reflect.get(answer, "additionalContext");
  return typeof value === "string" ? value : "";
}

/** The goal as the extension last recorded it. */
function lastGoal(host: Recorded): string {
  const entry = host.entries[host.entries.length - 1];
  return entry !== undefined && typeof entry === "object" ? String(Reflect.get(entry, "goal") ?? "") : "";
}

function run(command: string, args: string[], cwd: string): void {
  spawnSync(command, args, { cwd, encoding: "utf-8", timeout: 30_000 });
}

// Direct execution (make continuity-selftest): run every case and report.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("selftest.ts")) {
  console.log("==> continuity-selftest");
  const failures = await selftest();
  if (failures.length === 0) {
    console.log("    PASS: every continuity claim holds");
    process.exit(0);
  }
  console.log("    " + String(failures.length) + " claim(s) broken");
  process.exit(1);
}
