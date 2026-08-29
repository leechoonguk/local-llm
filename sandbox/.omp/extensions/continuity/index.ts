/**
 * Continuity Extension
 *
 * Auto-loaded from `<cwd>/.omp/extensions/` — nothing invokes it, which is the
 * point: work continuity must not depend on someone remembering a command.
 *
 * It does four things, all mechanically:
 *
 *   1. **Compaction recovery.** When automatic compaction fails, the session is
 *      stuck: it cannot shrink and cannot continue. This arms a deterministic
 *      pass and asks for one more compaction, and `session_before_compact` then
 *      answers with a summary built from session data — no summarizer model, no
 *      network, no vision requirement.
 *   2. **Context preservation.** Whatever strategy runs, the goal card is
 *      injected verbatim and the state rides along in `preserveData`.
 *   3. **Loop escalation.** Repetition, oscillation, an error loop or a stall
 *      raise evidence; the ladder answers with the cheapest intervention that can
 *      break it, and resets the moment real progress appears.
 *   4. **Goal enforcement.** A declared goal with declared acceptance is measured
 *      at settle time; an unmet goal continues the session with the failing
 *      predicates named.
 *
 * Constraint honoured deliberately: `newSession`/`switchSession` exist only on
 * the command context, so an event handler cannot open a session. Escalation
 * therefore ends at compaction, never a surprise session switch.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join, resolve } from "node:path";
import { type Predicate, type Verdict, allMet, evaluate, render } from "./acceptance.ts";
import { type CallRecord, detect, readPaths, signature, touchedPaths } from "./detectors.ts";
import { registerDiscipline } from "./discipline.ts";
import { mechanicalSummary, readPreparation, renderGoalCard } from "./goalcard.ts";
import { profileFor, usagePercent, usageTokens } from "./profile.ts";
import type {
  AutoCompactionEndEvent,
  ZodLike,
  ExtensionHost,
  HandlerContext,
  MessageStartEvent,
  SessionBeforeCompactEvent,
  SessionStopEvent,
  ToolCallEvent,
  ToolResultEvent,
  TurnEndEvent,
} from "./runtime.ts";
import {
  ENTRY_TYPE,
  type ContinuityState,
  type LoopEvidence,
  emptyState,
  recordFact,
  recordIntervention,
  recordLoop,
  recordRequest,
  resetEscalation,
  resolveInterventions,
  restoreFromBranch,
  saveToDisk,
} from "./state.ts";

// ============================================================
// Constants
// ============================================================

/** Turns between interventions: a steer storm is worse than a loop. */
const INTERVENTION_COOLDOWN_TURNS = 2;

/** The ladder stops here. Beyond it the session needs a human decision. */
const MAX_ESCALATION = 3;

/** Calls kept for repetition analysis. */
const CALL_HISTORY = 48;

/** Tools whose success is a verified fact worth carrying across compaction. */
const VERIFYING_TOOLS = new Set(["bash", "eval"]);

/** Tools whose success means the workspace changed — that is progress. */
const MUTATING_TOOLS = new Set(["write", "edit", "ast_edit"]);

/**
 * Continuations allowed when nothing armed the session from outside: the ladder
 * stops early so an interactive session is never held open against its operator.
 * An armed goal replaces this with its own deadline - see `armedDeadlineMs`.
 */
const MAX_CONTINUATIONS = 2;

/**
 * Hard ceiling on continuations even under an armed deadline. A settle loop that
 * has run this many times is not making progress the acceptance can see, and the
 * honest answer is to stop and say so rather than spin until the budget expires.
 */
const MAX_ARMED_CONTINUATIONS = 200;

/**
 * Usage-driven compaction was removed after measuring it. On a tool-heavy run
 * every turn is mid-loop, where compacting cancels the request the agent loop is
 * holding, so the trigger deferred 24 turns out of 24 and only became eligible
 * on the closing text turn — as the process exited, reclaiming nothing. When it
 * did fire below the runtime's real boundary (35,749 tokens on a 65k window) the
 * answer was "Nothing to compact (session too small)". OMP's own mid-run
 * compaction handled the same run at 75% and 78%. The profile is therefore kept
 * for reporting only, and the compaction paths that remain are the two that were
 * observed to work: loop escalation and recovery from a failed pass.
 */

/**
 * How long an intervention is given before it is recorded as failed. Two turns
 * is the cooldown, so three turns of silence means the steer changed nothing.
 */
const INTERVENTION_PATIENCE_TURNS = 3;

/**
 * A command that answers "did that work": the project gate, its parts, and the
 * hooks themselves. Anything else is a shell call that proves nothing about the
 * edits made before it.
 */
const VERIFYING_COMMAND = /\b(make|pytest|ruff|pyright|alembic|selftest|npm (run )?test)\b|\.venv\/bin|node \.omp/;

/**
 * Turns of measuring without writing before the deliverable is named. Six is
 * two full read-measure-think cycles: long enough not to interrupt a genuine
 * investigation, short enough that twenty-seven turns of it cannot happen.
 */
const DELIVERABLE_PATIENCE_TURNS = 6;

/** Turns before the same nudge may fire again. */
const DELIVERABLE_COOLDOWN_TURNS = 6;

/** Verification does not re-run inside this window — settle must stay quick. */
const ACCEPTANCE_DEBOUNCE_MS = 60_000;

/**
 * The command that decides whether work is finished in this repository. It is
 * the whole gate on purpose: a narrow command invites satisfying the command -
 * measured, a local model handed a one-target predicate added a catch-all rule
 * to the Makefile instead of doing the work.
 */
const PROJECT_GATE = "make verify";

/** The gate runs hooks, lint, types and tests; it is allowed to take minutes. */
const GATE_TIMEOUT_MS = 600_000;

/** Failure lines quoted back to the session - enough to act on, not a log. */
const GATE_LINES = 12;

const STATUS_TIMEOUT_MS = 30_000;

/**
 * Gate-driven continuations before the session is allowed to stop. Three is a
 * real chance to fix what the gate named; beyond that the session needs a human,
 * and holding it open only burns the budget.
 */
const MAX_GATE_CONTINUATIONS = 3;

/**
 * Settles refused for producing nothing. Two is enough to be told twice; a third
 * refusal would hold a session open against a request it cannot act on.
 */
const MAX_DELIVERABLE_CONTINUATIONS = 2;

/** The ask, kept whole enough to act on and short enough to carry everywhere. */
const GOAL_LENGTH = 600;
// ============================================================
// Functions
// ============================================================

export default function continuity(pi: ExtensionHost): void {
  let state: ContinuityState = emptyState();
  let calls: CallRecord[] = [];
  let sessionId = "unknown";
  let root = ".";
  let turnsWithoutProgress = 0;
  /** Turns since anything was written - the deliverable-blind signal. */
  let turnsWithoutWrites = 0;
  /** Files this session has read once, so a re-read is not counted as new. */
  const pathsRead = new Set<string>();
  let newPathsThisTurn = 0;
  let lastInterventionTurn = -INTERVENTION_COOLDOWN_TURNS;
  /** Turn of the last deliverable nudge, so it cannot become a steer storm. */
  let lastBlindTurn = -DELIVERABLE_COOLDOWN_TURNS;
  let progressThisTurn = false;
  let pendingRecovery: string | null = null;
  let acceptance: Predicate[] = [];
  let continuations = 0;
  /** Wall-clock ceiling for settle-time continuations, or null when unarmed. */
  let armedDeadlineMs: number | null = null;
  let lastAcceptanceAt = 0;
  /** Gate-driven continuations this session, and when the gate last ran. */
  let gateContinuations = 0;
  let lastGateAt = 0;
  let deliverableContinuations = 0;
  let unverifiedEdits = new Map<string, number>();

  pi.setLabel("Continuity");

  // Bench-measured session discipline (shift-left nudge, sickness cuts,
  // hygiene cuts, end/finish gates) — state independent of this file's own
  // goal and loop machinery. Knobs: .omp/continuity.json (+CONTINUITY_PROFILE).
  registerDiscipline(pi);

  on("session_start", (_event: unknown, ctx: HandlerContext) => {
    root = ctx.cwd ?? ".";
    sessionId = ctx.sessionManager?.getSessionId?.() ?? "unknown";
    state = restoreFromBranch(ctx.sessionManager?.getBranch?.() ?? []);
    state.agentDir = String(process.env.PI_CODING_AGENT_DIR ?? "");
    // A resumed session arms itself from its own history: the acceptance a model
    // declared through the tool lives in state, and held only in a local
    // variable it was lost on every restart - the session came back knowing its
    // goal and no longer knowing what would prove it.
    if (state.acceptance.length > 0) {
      acceptance = readPredicates(state.acceptance);
      armedDeadlineMs = state.deadlineMs === 0 ? null : state.deadlineMs;
    }
    // A reopened session with work behind it is told so on arrival - nobody has
    // to declare anything or retype the brief for that to happen.
    if (state.goal !== "") continueOnArrival(ctx);
    publish(ctx);
  });

  // Observation only: a pre-tool handler that throws blocks the tool, so this
  // records and never returns a verdict.
  on("tool_call", (event: ToolCallEvent) => {
    state.toolCalls += 1;
    calls.push({ sig: signature(event.toolName, event.input ?? {}, root), tool: event.toolName });
    if (calls.length > CALL_HISTORY) calls = calls.slice(-CALL_HISTORY);
    // Counted on the call, not the result: a read's `tool_result` carries no
    // `input`.
    for (const path of readPaths(event.toolName, event.input)) {
      if (pathsRead.has(path)) continue;
      pathsRead.add(path);
      newPathsThisTurn += 1;
    }
  });

  on("tool_result", (event: ToolResultEvent) => {
    const last = calls[calls.length - 1];
    if (last !== undefined && event.isError === true) last.error = firstText(event.content);
    if (event.isError !== true && VERIFYING_TOOLS.has(event.toolName)) {
      // A command that ran is the only fact worth carrying: it was measured,
      // not inferred.
      if (recordFact(state, "ran: " + shortInput(event.input))) progressThisTurn = true;
    }
    if (event.isError === true) return;
    // A check answers every edit made before it, whichever file they touched —
    // including the writes made inside the very cell that ran it.
    if (VERIFYING_TOOLS.has(event.toolName) && VERIFYING_COMMAND.test(shortInput(event.input))) {
      unverifiedEdits = new Map();
      return;
    }
    for (const path of touchedPaths(event.toolName, event.input)) {
      unverifiedEdits.set(path, (unverifiedEdits.get(path) ?? 0) + 1);
    }
  });

  on("turn_end", (event: TurnEndEvent, ctx: HandlerContext) => {
    state.turns += 1;
    const mutated = (event.toolResults ?? []).some((result) =>
      MUTATING_TOOLS.has(String(result?.toolName ?? "")),
    );
    // A turn spent reading has no mutating call and no verifying command, so it
    // is indistinguishable from silence. Opening a file for the first time is
    // the evidence that the turn learned something; re-reading one is not.
    const progressed = progressThisTurn || newPathsThisTurn > 0;
    turnsWithoutWrites = mutated ? 0 : turnsWithoutWrites + 1;
    if (mutated || progressed) {
      turnsWithoutProgress = 0;
      resetEscalation(state);
    } else {
      turnsWithoutProgress += 1;
    }
    progressThisTurn = false;

    const evidence = detect({
      calls,
      turnsWithoutProgress,
      unverifiedEdits: [...unverifiedEdits].map(([path, count]) => ({ path, count })),
    });
    // The ledger is answered before new evidence is folded in, so an
    // intervention is judged against the turn that followed it.
    resolveInterventions(state, mutated || progressed, INTERVENTION_PATIENCE_TURNS, newPathsThisTurn);
    newPathsThisTurn = 0;
    for (const item of evidence) recordLoop(state, item);
    const blind = deliverableBlind();
    if (blind !== null) evidence.push(recordLoop(state, blind));
    const midLoop = endedWithToolCalls(event);
    if (evidence.length > 0) escalate(ctx, evidence, midLoop);

    recordUsage(ctx, midLoop);
    persist(ctx);
    publish(ctx);
  });

  // The recovery path. `result: undefined` with no `skipped` flag means the pass
  // produced nothing: arm the mechanical pass and ask for one more compaction.
  on("auto_compaction_end", (event: AutoCompactionEndEvent, ctx: HandlerContext) => {
    if (event.aborted === true) return;
    if (event.result !== undefined || event.skipped === true) return;
    pendingRecovery = event.errorMessage ?? "compaction produced no result (" + String(event.action) + ")";
    ctx.ui?.notify?.("continuity: compaction failed — running mechanical fallback", "warn");
    requestCompaction(ctx, "mechanical-recovery");
  });

  on("session_before_compact", (event: SessionBeforeCompactEvent, ctx: HandlerContext) => {
    if (event.branchEntries !== undefined) state = restoreFromBranch(event.branchEntries);
    if (pendingRecovery === null) return undefined;
    const preparation = readPreparation(event.preparation);
    if (preparation === null) {
      // An unrecognised payload must not become a malformed compaction entry.
      ctx.ui?.notify?.("continuity: compaction payload not recognised — leaving it to the runtime", "warn");
      return undefined;
    }
    const reason = pendingRecovery;
    pendingRecovery = null;
    state.recoveries += 1;
    return { compaction: mechanicalSummary(preparation, state, reason) };
  });

  // Whatever strategy runs, the goal card goes in verbatim and the state rides
  // along in preserveData — the two things a rewritten context must not lose.
  on("session.compacting", () => ({
    context: [renderGoalCard(state)],
    preserveData: { continuity: state },
  }));

  on("session_compact", (_event: unknown, ctx: HandlerContext) => {
    state.compactions += 1;
    calls = [];
    // `appendEntry` state is not sent to the model, and the summarizer is free to
    // paraphrase the card it was handed as context (measured: the stored summary
    // did not quote it). So the card is re-posted as a message — that is the only
    // channel that puts it in front of the model verbatim after a rewrite.
    //
    // Delivery matters more than it looks: `nextTurn` waits for the *next user
    // prompt*, which never arrives in a one-shot run — measured, the card was
    // silently dropped after a real compaction. Mid-run the card must steer into
    // the turn that is still going; only an idle session can afford to wait.
    if (state.goal !== "") {
      deliver(
        { customType: "continuity", content: renderGoalCard(state), display: true },
        { deliverAs: ctx.isIdle?.() === true ? "nextTurn" : "steer" },
      );
    }
    persist(ctx);
    publish(ctx);
  });

  // Settle-time enforcement, in two layers. A declared acceptance wins when
  // there is one; otherwise the project's own gate decides, with nothing
  // declared by anybody. A session that changed files and stops on a red gate
  // has not finished, whatever it says about itself.
  on("session_stop", (event: SessionStopEvent, ctx: HandlerContext) => {
    if (event.stop_hook_active === true) return undefined;
    if (acceptance.length === 0) return gateStop(ctx);
    // An armed run spends a wall-clock budget, not a count: two continuations is
    // the right ceiling for a session someone is watching, and the wrong one for
    // a goal that was handed over with an hour to finish it.
    const cap = armedDeadlineMs === null ? MAX_CONTINUATIONS : MAX_ARMED_CONTINUATIONS;
    const expired = armedDeadlineMs !== null && Date.now() >= armedDeadlineMs;
    if (continuations >= cap || expired) {
      ctx.ui?.notify?.(
        "continuity: goal still unmet after " +
          continuations +
          " continuation(s)" +
          (expired ? " - budget spent" : ""),
        "warn",
      );
      recordFact(state, (expired ? "budget spent, goal unmet: " : "continuations spent, goal unmet: ") + state.goal);
      persist(ctx);
      return undefined;
    }
    if (Date.now() - lastAcceptanceAt < ACCEPTANCE_DEBOUNCE_MS) return undefined;

    lastAcceptanceAt = Date.now();
    const verdicts: Verdict[] = evaluate(acceptance, root);
    if (allMet(verdicts)) {
      recordFact(state, "goal met: " + state.goal);
      persist(ctx);
      publish(ctx);
      return undefined;
    }

    continuations += 1;
    persist(ctx);
    publish(ctx);
    return {
      continue: true,
      additionalContext:
        renderGoalCard(state) +
        "\nThe goal is not met. Acceptance as measured just now:\n" +
        render(verdicts) +
        "\nContinue with the single next action, or change the goal if it is wrong.",
    };
  });

  /**
   * The default answer to "are you done": the repository's gate.
   *
   * Nothing here was declared, armed, or asked for. The session changed tracked
   * files, so `make verify` has an opinion, and it is the only one that survives
   * a model's own account of its work. Capped, because a gate the session cannot
   * fix must eventually reach a human instead of holding the session open.
   */
  function gateStop(ctx: HandlerContext): { continue: boolean; additionalContext: string } | undefined {
    // A green gate is not evidence of finished work when the session produced
    // nothing at all. Measured: asked for two migrations, a request file and a
    // fixture, a local model read for eighteen turns, wrote nothing, and settled
    // - the gate was green because the tree it read was already green. So the
    // first question is whether the deliverables the request names exist.
    const undelivered = goalPaths(state.goal).filter((path) => !existsSync(resolve(root, path)));
    if (undelivered.length > 0 && state.turns > 0 && turnsWithoutWrites >= state.turns) {
      if (deliverableContinuations >= MAX_DELIVERABLE_CONTINUATIONS) {
        ctx.ui?.notify?.(
          "continuity: still nothing written after " + deliverableContinuations + " attempt(s)",
          "warn",
        );
        return undefined;
      }
      deliverableContinuations += 1;
      recordFact(state, "settled with nothing written: " + undelivered.join(", "));
      persist(ctx);
      publish(ctx);
      return {
        continue: true,
        additionalContext:
          renderGoalCard(state) +
          "\nThis session has not written anything, and the request names files that do not " +
          "exist:\n" +
          undelivered.map((path) => "  - " + path).join("\n") +
          "\nStop reading and create the first one now, with the content it needs. If a path " +
          "above is not something to create, say so in one line and continue with the real work.",
      };
    }
    // Dirtiness next, and it costs a `git status`: a session that changed
    // nothing must not consume the gate's debounce window, or the next stop -
    // the one that follows real work - is waved through. Measured in the
    // self-test: the clean settle disarmed the red-gate settle right after it.
    if (!worktreeDirty()) return undefined;
    if (gateContinuations >= MAX_GATE_CONTINUATIONS) {
      ctx.ui?.notify?.("continuity: " + PROJECT_GATE + " still failing after " + gateContinuations + " attempt(s)", "warn");
      return undefined;
    }
    if (Date.now() - lastGateAt < ACCEPTANCE_DEBOUNCE_MS) return undefined;
    lastGateAt = Date.now();
    const failure = gateFailure();
    if (failure === null) return undefined;
    gateContinuations += 1;
    recordFact(state, "gate red at settle: " + failure.split("\n")[0]);
    persist(ctx);
    publish(ctx);
    return {
      continue: true,
      additionalContext:
        renderGoalCard(state) +
        "\nThis session changed files and `" +
        PROJECT_GATE +
        "` fails. That is not finished work:\n" +
        failure +
        "\nFix the first failure above, then run `" +
        PROJECT_GATE +
        "` again.",
    };
  }

  on("session_shutdown", (_event: unknown, ctx: HandlerContext) => {
    persist(ctx);
  });

  // The goal costs nothing to know: it is what was asked for. Declaring it
  // through the tool stays available for a model that wants to sharpen it, but
  // nothing depends on that any more - measured, a local 35B never called it.
  on("message_start", (event: MessageStartEvent, ctx: HandlerContext) => {
    if (event.message?.role !== "user") return;
    const text = firstText(event.message.content ?? []);
    if (text === undefined || text.trim() === "") return;
    // A steer this extension posted is not a new request.
    if (text.startsWith("<continuity")) return;
    state.goal = text.trim().slice(0, GOAL_LENGTH);
    state.nextAction = "";
    continuations = 0;
    gateContinuations = 0;
    // Written down immediately: the goal has to survive a compaction that may
    // land before the first turn even ends.
    persist(ctx);
    publish(ctx);
  });

  registerGoalTool();

  // ============================================================
  // Session-bound helpers
  // ============================================================

  /**
   * A handler that throws is swallowed by the runner, which makes a broken
   * extension indistinguishable from a quiet one. Registration goes through
   * here so a failure is reported instead of vanishing.
   */
  function on<E>(event: string, handler: (event: E, ctx: HandlerContext) => unknown): void {
    pi.on(event, ((raw: E, ctx: HandlerContext): unknown => {
      try {
        return handler(raw, ctx);
      } catch (error: unknown) {
        pi.logger?.error?.("continuity handler failed", { handler: event, error: String(error) });
        ctx?.ui?.notify?.("continuity: " + event + " failed — " + String(error), "warn");
        return undefined;
      }
    }) as (event: never, ctx: HandlerContext) => unknown);
  }

  /**
   * `ctx.compact()` rejects for ordinary reasons — "Nothing to compact (session
   * too small)" is one, measured. A detached rejection is not a small mistake
   * here: it escapes handler dispatch and the postmortem handler tears the whole
   * session down (it did, exit 1). Every request goes through this.
   */
  function requestCompaction(ctx: HandlerContext, why: string): void {
    // Recorded before the answer: a request that fired and succeeded left no
    // trace at all until now, so a threshold could not be judged from the
    // ledger — only refusals were visible.
    recordRequest(state, why, false);
    const pending = ctx.compact?.();
    if (pending === undefined || typeof pending.catch !== "function") return;
    pending.catch((error: unknown) => {
      recordRequest(state, why, true);
      pi.logger?.info?.("continuity: compaction request declined", { why, error: String(error) });
    });
  }

  /**
   * What a reopened session says on arrival.
   *
   * Reopening is the cheapest resume there is - no supervisor, no retyped brief.
   * For it to continue the work rather than restart it, arrival has to say what
   * was left behind: the goal from the session's own history, and the fact that
   * the worktree still carries unfinished changes.
   *
   * Deliberately cheap. `git status` costs milliseconds; the gate costs minutes
   * and belongs at settle time, where a claim of completion is being made. A
   * clean worktree says nothing at all, because there is nothing to continue.
   */
  function continueOnArrival(ctx: HandlerContext): void {
    if (acceptance.length > 0) {
      const verdicts: Verdict[] = evaluate(acceptance, root);
      if (allMet(verdicts)) {
        ctx.ui?.notify?.("continuity: the declared goal is already met - " + state.goal, "info");
        return;
      }
      send(
        renderGoalCard(state) +
          "\nThis session has a declared goal. Acceptance as measured on arrival:\n" +
          render(verdicts) +
          "\nContinue with the single next action that makes the first NOT-met line true.",
      );
      return;
    }
    if (!worktreeDirty()) return;
    send(
      renderGoalCard(state) +
        "\nThis session was reopened with uncommitted changes still in the worktree, so the work " +
        "above is unfinished. Continue it: find what is left, finish it, then run `" +
        PROJECT_GATE +
        "`.",
    );
  }

  /**
   * The gate this project already trusts, run at settle time when the session
   * changed something.
   *
   * Nothing is declared and nothing is armed: a session that edited tracked
   * files and is about to stop is asked the one question the repository can
   * answer mechanically - does `make verify` pass? A model that stops on a red
   * gate has not finished, whatever it says, and a local model measured over
   * many runs says it constantly.
   *
   * Only when the worktree actually changed. Reading, measuring, and answering
   * questions are not work the gate has an opinion about.
   */
  function gateFailure(): string | null {
    if (!worktreeDirty()) return null;
    const gate = spawnSync(PROJECT_GATE, {
      cwd: root,
      shell: true,
      encoding: "utf-8",
      timeout: GATE_TIMEOUT_MS,
    });
    if (gate.status === 0) return null;
    const output = String(gate.stdout ?? "") + String(gate.stderr ?? "");
    const failures = output
      .split("\n")
      .filter((line) => /FAIL|Error|error:|\bfailed\b/.test(line))
      .slice(0, GATE_LINES);
    return failures.length > 0 ? failures.join("\n") : "exit " + String(gate.status);
  }

  /** Tracked or new files differ from HEAD - the only signal that work happened. */
  function worktreeDirty(): boolean {
    const status = spawnSync("git", ["status", "--porcelain"], {
      cwd: root,
      encoding: "utf-8",
      timeout: STATUS_TIMEOUT_MS,
    });
    return String(status.stdout ?? "").trim() !== "";
  }


  /**
   * The goal-driven loop: measuring forever instead of delivering.
   *
   * Repetition detectors cannot see this one. Every call is different, every
   * turn learns something, and nothing repeats - measured on a local 35B given a
   * report to write: twenty minutes, twenty-seven turns, sixty-six tool calls,
   * and **zero** write calls. The armed acceptance is what makes it visible: it
   * names the file, the file is absent, and nothing has been written for turns.
   *
   * Only `file` and `grep` predicates are read here - they cost a `stat`. A
   * shell predicate belongs at settle time, not on every turn boundary.
   */
  function deliverableBlind(): LoopEvidence | null {
    if (turnsWithoutWrites < DELIVERABLE_PATIENCE_TURNS) return null;
    if (state.turns - lastBlindTurn < DELIVERABLE_COOLDOWN_TURNS) return null;
    // Declared acceptance when there is some; otherwise the paths the request
    // itself names. Asking for `/tmp/report.md` and never writing it is the same
    // failure whether or not anyone declared a predicate about it.
    const missing =
      acceptance.length > 0
        ? acceptance
            .filter((predicate) => predicate.kind === "file" || predicate.kind === "grep")
            .map((predicate) => evaluate([predicate], root)[0])
            .filter((verdict) => verdict.met !== true)
        : goalPaths(state.goal)
            .filter((path) => !existsSync(resolve(root, path)))
            .map((path) => ({ met: false as boolean | null, label: "the request names " + path, detail: "absent" }));
    if (missing.length === 0) return null;
    lastBlindTurn = state.turns;
    return {
      kind: "blind",
      count: turnsWithoutWrites,
      detail:
        "nothing written for " +
        turnsWithoutWrites +
        " turn(s) while this is still missing: " +
        missing.map((verdict) => verdict.label).join("; "),
      sig: "blind:" + missing.map((verdict) => verdict.label).join("|"),
    };
  }

  // 이미 보낸 rung-1 증거 문자열(중복 발화 방지).
  const sentDetails = new Set<string>();

  function escalate(ctx: HandlerContext, evidence: LoopEvidence[], midLoop: boolean): void {
    if (state.turns - lastInterventionTurn < INTERVENTION_COOLDOWN_TURNS) return;
    if (state.escalation >= MAX_ESCALATION) return;
    lastInterventionTurn = state.turns;
    state.escalation += 1;
    recordIntervention(state, evidence);

    for (const loop of state.loops) {
      if (loop.kind === "repeat" && !state.banned.includes(loop.sig)) state.banned.push(loop.sig);
    }

    if (state.escalation === 1) {
      const details = evidence.map((item) => item.detail).join("\n- ");
      // 같은 증거로 같은 말을 반복하지 않는다(실측: 최고 성적 셀에서도 12회 재발화).
      if (sentDetails.has(details)) { state.escalation -= 1; return; }
      sentDetails.add(details);
      send("Loop detected:\n- " + details + "\nThat path is exhausted. Take one different action.",
        midLoop ? "nextTurn" : "steer");
      return;
    }
    if (state.escalation === 2) {
      send(renderGoalCard(state) + "\nRe-read the card above. Do not repeat a listed attempt.",
        midLoop ? "nextTurn" : "steer");
      return;
    }
    // The third rung compacts, and compacting while the agent loop still holds a
    // request cancels it — measured as `Request was aborted` on a local 35B. The
    // rung is spent either way: a steer is sent instead, so the ladder keeps
    // moving without killing the turn.
    if (midLoop) {
      send(renderGoalCard(state) + "\nThis is the third attempt on the same path. Change the approach or stop.");
      return;
    }
    ctx.ui?.notify?.("continuity: compacting to break a loop", "warn");
    requestCompaction(ctx, "loop-escalation");
  }

  /**
   * What the runtime says about the window, recorded every turn.
   *
   * This used to also compact ahead of OMP for a small model. Measured on the
   * local roster, that trigger could not reach the runs that needed it (see the
   * note above the constants), so only the reading is kept. It is the one number
   * that makes a compaction decision reviewable after the fact: a session that
   * never compacted and a session whose usage was never reported look identical
   * without it.
   */
  function recordUsage(ctx: HandlerContext, midLoop: boolean): void {
    const profile = profileFor(ctx.models?.current?.());
    const usage = ctx.getContextUsage?.();
    const percent = usagePercent(usage);
    const tokens = usageTokens(usage);
    state.lastUsage =
      profile.name +
      " " +
      (percent === null ? "?" : String(Math.round(percent))) +
      "% " +
      (tokens === null ? "?" : String(tokens)) +
      (midLoop ? " (mid-loop)" : "");
  }

  /**
   * True while the agent loop still owes a provider request.
   *
   * Compacting here cancels the continuation the loop is holding, so the answer
   * has to be right. `event.messages` ends with the **tool result**, not with the
   * assistant message that carried the calls — reading only its last entry
   * therefore called a mid-loop turn safe. Measured on a local 35B through
   * ollama: an early compaction landed on that turn, the held request was
   * cancelled, and the headless run died with `Request was aborted` about forty
   * seconds in, every time. Ten minutes of the same work survived once this
   * answered honestly.
   *
   * `stopReason: "toolUse"` on the turn's own assistant message is the crisp
   * signal; the scan backwards past tool results is the fallback for runtimes
   * that omit it.
   */
  function endedWithToolCalls(event: TurnEndEvent): boolean {
    const holdsToolCall = (value: unknown): boolean => {
      if (value === null || typeof value !== "object") return false;
      const holder: unknown = Reflect.get(value, "message") ?? value;
      if (holder === null || typeof holder !== "object") return false;
      if (String(Reflect.get(holder, "stopReason") ?? "").toLowerCase() === "tooluse") return true;
      const content: unknown = Reflect.get(holder, "content");
      if (!Array.isArray(content)) return false;
      return content.some(
        (block: unknown) =>
          block !== null &&
          typeof block === "object" &&
          String(Reflect.get(block, "type") ?? "").toLowerCase().includes("toolcall"),
      );
    };
    if (holdsToolCall(Reflect.get(event, "message"))) return true;
    const messages: unknown[] = Array.isArray(event.messages) ? event.messages : [];
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const entry: unknown = messages[index];
      const holder: unknown =
        entry !== null && typeof entry === "object" ? (Reflect.get(entry, "message") ?? entry) : null;
      const role = String(
        holder !== null && typeof holder === "object" ? (Reflect.get(holder, "role") ?? "") : "",
      );
      if (role === "toolResult" || role === "tool") continue;
      return holdsToolCall(entry);
    }
    return false;
  }

  function registerGoalTool(): void {
    // The host hands the builder over as an opaque value; this is the named
    // boundary the no-inline-cast rule asks for.
    const z: ZodLike = pi.zod as ZodLike;
    const optionalString = (): unknown => z.string().optional();

    pi.registerTool({
      name: "continuity_goal",
      label: "Declare Continuity Goal",
      description:
        "Declare this session's goal and how it is falsified. Acceptance predicates are measured " +
        "mechanically when the session tries to settle, and an unmet goal continues the session; " +
        "a goal with no predicate is tracked but never enforced. Call again to update it.",
      parameters: z.object({
        goal: z.string().describe("What must be true when the work is done"),
        nextAction: optionalString(),
        acceptance: z
          .array(
            z.object({
              kind: z.enum(["shell", "file", "grep", "manual"]),
              cmd: optionalString(),
              expectExit: z.number().optional(),
              path: optionalString(),
              exists: z.boolean().optional(),
              pattern: optionalString(),
              want: z.boolean().optional(),
              text: optionalString(),
            }),
          )
          .optional()
          .describe("How the goal is falsified. shell commands are limited to make targets and harness hooks."),
      }),
      async execute(_toolCallId: string, params: unknown, _signal: unknown, _onUpdate: unknown, ctx: HandlerContext) {
        if (params === null || typeof params !== "object") {
          return { content: [{ type: "text", text: "continuity_goal needs an object" }] };
        }
        const goal = "goal" in params ? Reflect.get(params, "goal") : undefined;
        const nextAction = "nextAction" in params ? Reflect.get(params, "nextAction") : undefined;
        const declaredAcceptance = "acceptance" in params ? Reflect.get(params, "acceptance") : undefined;
        if (typeof goal === "string" && goal !== "") state.goal = goal;
        if (typeof nextAction === "string") state.nextAction = nextAction;
        if (Array.isArray(declaredAcceptance)) {
          acceptance = readPredicates(declaredAcceptance);
          // Written into state, not just held here: the next process restores
          // state, and a goal whose proof was lost is a goal that settles.
          state.acceptance = declaredAcceptance;
        }
        continuations = 0;
        lastAcceptanceAt = 0;
        persist(ctx);
        publish(ctx);
        return {
          content: [{ type: "text", text: renderGoalCard(state) }],
          details: { goal: state.goal, nextAction: state.nextAction, acceptance },
        };
      },
    });
  }

  /**
   * Deliver a message without letting its failure reach the session.
   *
   * `pi.sendMessage` can fail for reasons that say nothing about this extension —
   * a headless run has no steering channel to accept `deliverAs: "steer"`. Measured
   * on a local model in `-p` mode: the rejection escaped handler dispatch and the
   * postmortem handler tore the session down (`Request was aborted`, exit 1) about
   * fifty seconds into every long run. `--no-extensions` ran the same task for ten
   * minutes. A steer that cannot be delivered is a steer that is skipped, never a
   * dead session.
   */
  function deliver(
    message: { customType: string; content: string; display?: boolean },
    options: { deliverAs?: "steer" | "followUp" | "nextTurn" },
  ): void {
    const note = (error: unknown): void => {
      pi.logger?.info?.("continuity: message not delivered", { error: String(error) });
    };
    try {
      const pending: unknown = pi.sendMessage(message, options);
      if (typeof (pending as { catch?: unknown })?.catch === "function") {
        (pending as Promise<unknown>).catch(note);
      }
    } catch (error: unknown) {
      note(error);
    }
  }

  function send(text: string, mode: "steer" | "nextTurn" = "steer"): void {
    deliver(
      {
        customType: "continuity",
        content: "<continuity-intervention>\n" + text + "\n</continuity-intervention>",
        display: true,
      },
      { deliverAs: mode },
    );
  }

  function persist(ctx: HandlerContext): void {
    // Disk first. `appendEntry` is a runtime action, and at `session_shutdown`
    // the runtime is already gone — measured as "Extension runtime not
    // initialized" in three short local runs, which threw before the state was
    // ever written and lost the final reading. The file is what a later session
    // and `continuity-report` read, so it must not depend on the runtime.
    saveToDisk(ctx.cwd ?? root, sessionId, state);
    try {
      pi.appendEntry(ENTRY_TYPE, state);
    } catch {
      // The session entry only helps compaction carry the card; the file is the record.
    }
  }

  function publish(ctx: HandlerContext): void {
    const percent = usagePercent(ctx.getContextUsage?.());
    const loops = state.loops.length === 0 ? "none" : state.loops.map((loop) => loop.kind).join(",");
    ctx.ui?.setStatus?.(
      "continuity",
      "loop:" + loops +
        " esc:" + String(state.escalation) +
        " cmp:" + String(state.compactions) + "/" + String(state.recoveries) +
        (state.goal === "" ? "" : " goal:" + (acceptance.length === 0 ? "tracked" : "enforced")) +
        (percent === null ? "" : " ctx:" + String(Math.round(percent)) + "%"),
    );
  }
}

// ============================================================
// Helpers
// ============================================================

function firstText(content: unknown): string | undefined {
  if (!Array.isArray(content)) return undefined;
  for (const chunk of content) {
    if (chunk === null || typeof chunk !== "object") continue;
    const type = "type" in chunk ? Reflect.get(chunk, "type") : undefined;
    const text = "text" in chunk ? Reflect.get(chunk, "text") : undefined;
    if (type === "text" && typeof text === "string") return text;
  }
  return undefined;
}

/**
 * Acceptance arrives from a model, so each predicate is rebuilt field by field
 * and anything unrecognised is dropped: a malformed predicate must not silently
 * become an enforced one.
 */
function readPredicates(items: unknown[]): Predicate[] {
  const predicates: Predicate[] = [];
  for (const item of items) {
    if (item === null || typeof item !== "object") continue;
    const kind = "kind" in item ? Reflect.get(item, "kind") : undefined;

    if (kind === "shell") {
      const cmd = readText(item, "cmd");
      if (cmd === undefined) continue;
      const expectExit = readCount(item, "expectExit");
      predicates.push(expectExit === undefined ? { kind, cmd } : { kind, cmd, expectExit });
      continue;
    }
    if (kind === "file") {
      const path = readText(item, "path");
      if (path === undefined) continue;
      predicates.push({ kind, path, exists: Reflect.get(item, "exists") !== false });
      continue;
    }
    if (kind === "grep") {
      const path = readText(item, "path");
      const pattern = readText(item, "pattern");
      if (path === undefined || pattern === undefined) continue;
      predicates.push({ kind, path, pattern, want: Reflect.get(item, "want") !== false });
      continue;
    }
    if (kind === "manual") {
      const text = readText(item, "text");
      if (text === undefined) continue;
      predicates.push({ kind, text });
    }
  }
  return predicates;
}


function readText(source: object, key: string): string | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  return typeof value === "string" && value !== "" ? value : undefined;
}

/**
 * File paths a request names, as paths - `/tmp/report.md`, `api/x.http`,
 * `backend/app/main.py`. A word with a slash and an extension is a deliverable
 * far more often than it is prose, and a false positive costs one nudge that
 * names a path the session can see is already there.
 */
function goalPaths(goal: string): string[] {
  const found = new Set<string>();
  for (const match of goal.matchAll(/(?:^|[\s`'"(])(\/?(?:[\w.-]+\/)*[\w-]+\.[A-Za-z]{2,6})\b/g)) {
    found.add(match[1]);
  }
  return [...found];
}

function readCount(source: object, key: string): number | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function shortInput(input: unknown): string {
  if (input === null || typeof input !== "object") return "";
  for (const key of ["command", "code", "title"]) {
    if (!(key in input)) continue;
    const value = Reflect.get(input, key);
    if (typeof value === "string") return value.replace(/\s+/g, " ").trim().slice(0, 120);
  }
  return "";
}
