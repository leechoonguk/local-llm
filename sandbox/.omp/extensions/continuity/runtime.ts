/**
 * Runtime Shapes
 *
 * The surface of the extension runtime this module actually touches, written as
 * structural types instead of `any`. The real types live in the OMP package, but
 * an extension is loaded by type-stripping — nothing type-checks it at build
 * time — so a precise local shape is the only thing that keeps a rename or a
 * payload change visible to a reader.
 *
 * Every member is optional on purpose: a handler runs in interactive, print, RPC
 * and subagent hosts, and each of those omits part of the surface.
 */

// ============================================================
// Types
// ============================================================

export interface UiContext {
  notify?: (message: string, level?: string) => void;
  setStatus?: (key: string, text: string | undefined) => void;
}

export interface SessionManagerView {
  getSessionId?: () => string;
  getBranch?: () => unknown[];
}

export interface ModelsView {
  current?: () => unknown;
}

export interface HandlerContext {
  cwd?: string;
  ui?: UiContext;
  sessionManager?: SessionManagerView;
  models?: ModelsView;
  getContextUsage?: () => unknown;
  isIdle?: () => boolean;
  compact?: (instructions?: string) => Promise<void>;
}

export interface ToolCallEvent {
  toolName: string;
  input?: Record<string, unknown>;
}

export interface ToolResultEvent {
  toolName: string;
  isError?: boolean;
  content?: unknown;
  input?: Record<string, unknown>;
}

export interface TurnEndEvent {
  toolResults?: { toolName?: string }[];
  /**
   * The turn's messages. Read to tell a mid-loop turn (it closes with an
   * assistant message carrying tool calls) from the closing text turn:
   * `toolResults` is populated on both.
   */
  messages?: unknown[];
}

export interface AutoCompactionEndEvent {
  action?: string;
  result?: unknown;
  aborted?: boolean;
  skipped?: boolean;
  errorMessage?: string;
}

export interface SessionBeforeCompactEvent {
  preparation: unknown;
  branchEntries?: unknown[];
}

export interface SessionStopEvent {
  stop_hook_active?: boolean;
}

export interface Logger {
  error?: (message: string, fields?: Record<string, unknown>) => void;
  info?: (message: string, fields?: Record<string, unknown>) => void;
}

/**
 * The injected schema builder, narrowed to the members used here. The host
 * exports it as an opaque value, so this is the one place a named assertion is
 * unavoidable — a runtime check would tell us nothing about a builder's API.
 */
export interface ZodLike {
  object: (shape: Record<string, unknown>) => unknown;
  string: () => { describe: (text: string) => unknown; optional: () => unknown };
  number: () => { optional: () => unknown };
  boolean: () => { optional: () => unknown };
  array: (item: unknown) => { optional: () => { describe: (text: string) => unknown } };
  enum: (values: string[]) => unknown;
}

/**
 * `message_start` for a user turn. Measured on a live stream: the request text
 * is the first `text` block of `message.content`, and `role` is `"user"` -
 * assistant and `toolResult` messages arrive through the same event.
 */
export interface MessageStartEvent {
  message?: { role?: string; content?: unknown[] };
}
/** Only the members this extension calls — registration plus three actions. */
export interface ExtensionHost {
  logger?: Logger;
  zod: unknown;
  setLabel: (label: string) => void;
  on: (event: string, handler: (event: never, ctx: HandlerContext) => unknown) => void;
  sendMessage: (
    message: { customType: string; content: string; display?: boolean },
    options?: { deliverAs?: "steer" | "followUp" | "nextTurn"; triggerTurn?: boolean },
  ) => void;
  appendEntry: (customType: string, data?: unknown) => void;
  registerTool: (definition: ToolDefinition) => void;
  /**
   * Slash commands. Optional on purpose: a host that predates them must not make
   * the whole extension fail to load, so the call site uses `?.`.
   */
  registerCommand?: (
    name: string,
    definition: { description: string; handler: (args: string, ctx: HandlerContext) => unknown },
  ) => void;
}

export interface ToolDefinition {
  name: string;
  label: string;
  description: string;
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: unknown,
    signal: unknown,
    onUpdate: unknown,
    ctx: HandlerContext,
  ) => Promise<{ content: { type: string; text: string }[]; details?: unknown }>;
}
