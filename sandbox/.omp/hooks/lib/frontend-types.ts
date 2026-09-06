/**
 * Backend ↔ frontend *type* extraction — the half `frontend-contract.ts` left
 * to review.
 *
 * Field names were compared; the types beside them were not. So a `datetime`
 * declared as `number`, a nullable column typed `string`, or a required request
 * field spelled optional all compiled, shipped, and failed at runtime — a
 * `.toUpperCase()` on a number, a `null` reaching a formatter, a 422 for a body
 * the form thought was complete.
 *
 * The parsers are deliberately shallow: they read the annotation syntax this
 * repository actually writes (`backend-domain.md` fixes it) and nothing more. An
 * annotation they cannot read is reported, never assumed equal — a parser that
 * silently skips is worse than no parser, because it reports PASS.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { readFileSync } from "node:fs";

export interface FieldType {
  /** The annotation with `| None` stripped: `list[str]`, `Literal[...]`, `int`. */
  base: string;
  /** `X | None` on the server, `T | null` on the client. */
  nullable: boolean;
  /** The server field has a default, so a request may omit it. */
  optional: boolean;
}

/** A Pydantic field with its annotation: `name: type` or `name: type = default`. */
const PY_FIELD_TYPED = /^ {4}(\w+)\s*:\s*([^=\n]+?)(?:\s*=\s*(.+))?$/;

const PY_CLASS_LINE = /^class\s+(\w+)\(([^)]*)\)\s*:/;

/** `FieldDirection = Literal["REQUEST", "RESPONSE"]` and `JsonObject = dict[...]`. */
const PY_ALIAS = /^(\w+)\s*=\s*(Literal\[[\s\S]*?\]|dict\[[^\]]*\]|list\[[^\]]*\])/gm;

const TS_FIELD_TYPED = /^ {2}(\w+)(\??)\s*:\s*(.+?);?$/;

const TS_INTERFACE_LINE = /^export interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{/;

/** `export type ValueType = 'STRING' | 'NUMBER'`, possibly wrapped over lines. */
const TS_ALIAS = /^export type\s+(\w+)\s*=\s*([\s\S]*?)(?=\n(?:export|interface|\/\*|$))/gm;

/**
 * Pydantic scalars and their only correct TypeScript spelling.
 *
 * `datetime` is the one worth naming: it arrives as an ISO string, and typing it
 * `number` passes a name-only check while every date formatter on the screen
 * receives a string it was told was a number.
 */
const SCALARS: Record<string, string> = {
  str: "string",
  UUID: "string",
  datetime: "string",
  date: "string",
  time: "string",
  int: "number",
  float: "number",
  Decimal: "number",
  bool: "boolean",
  object: "unknown",
};

export function parsePydanticTypes(source: string): Map<string, Map<string, FieldType>> {
  const own = new Map<string, Map<string, FieldType>>();
  const bases = new Map<string, string[]>();
  let current: string | null = null;
  let pending = "";

  for (const line of source.split("\n")) {
    const classMatch = PY_CLASS_LINE.exec(line);
    if (classMatch !== null) {
      current = classMatch[1];
      bases.set(current, classMatch[2].split(",").map((b: string) => b.trim()).filter(Boolean));
      own.set(current, new Map());
      pending = "";
      continue;
    }
    if (current === null) continue;
    if (/^\S/.test(line) && line.trim() !== "") {
      current = null;
      continue;
    }

    // A wrapped `Field(...)` or `Literal[...]` spans lines; accumulate first.
    pending = pending === "" ? line : `${pending} ${line.trim()}`;
    if (balance(pending) > 0) continue;
    const declaration = pending;
    pending = "";

    const fieldMatch = PY_FIELD_TYPED.exec(declaration);
    if (fieldMatch === null || fieldMatch[1] === "model_config") continue;
    own.get(current)!.set(fieldMatch[1], {
      base: stripNone(fieldMatch[2].trim()),
      nullable: /\|\s*None\b|Optional\[/.test(fieldMatch[2]),
      optional: hasDefault(fieldMatch[3]),
    });
  }

  return resolve(own, bases);
}

export function parseTsTypes(source: string): Map<string, Map<string, FieldType>> {
  const own = new Map<string, Map<string, FieldType>>();
  const bases = new Map<string, string[]>();
  let current: string | null = null;

  for (const line of source.split("\n")) {
    const interfaceMatch = TS_INTERFACE_LINE.exec(line);
    if (interfaceMatch !== null) {
      current = interfaceMatch[1];
      bases.set(
        current,
        (interfaceMatch[2] ?? "").split(",").map((b: string) => b.trim()).filter(Boolean),
      );
      own.set(current, new Map());
      continue;
    }
    if (current === null) continue;
    if (line.startsWith("}")) {
      current = null;
      continue;
    }

    const fieldMatch = TS_FIELD_TYPED.exec(line);
    if (fieldMatch === null) continue;
    const declared = fieldMatch[3].trim();
    own.get(current)!.set(fieldMatch[1], {
      base: declared.replace(/\s*\|\s*null\b/g, "").trim(),
      nullable: /\|\s*null\b/.test(declared),
      optional: fieldMatch[2] === "?",
    });
  }

  return resolve(own, bases);
}

/** Type aliases in one module, mapped to their normalised member set or type. */
export function parseAliases(source: string, language: "py" | "ts"): Map<string, string> {
  const aliases = new Map<string, string>();
  const pattern = language === "py" ? PY_ALIAS : TS_ALIAS;
  pattern.lastIndex = 0;
  for (const match of source.matchAll(pattern)) {
    aliases.set(match[1], normaliseUnion(match[2], language));
  }
  return aliases;
}

/**
 * The TypeScript spelling one Pydantic annotation requires, or `null` when the
 * annotation is not one this parser claims to understand.
 *
 * `null` is the honest answer for an unread annotation: the caller reports it
 * rather than treating unknown as equal.
 */
export function expectedTsType(
  base: string,
  pyAliases: Map<string, string>,
  modelToInterface: (model: string) => string | null,
): string | null {
  const scalar = SCALARS[base];
  if (scalar !== undefined) return scalar;

  const list = /^list\[(.+)\]$/.exec(base);
  if (list !== null) {
    const inner = expectedTsType(list[1].trim(), pyAliases, modelToInterface);
    return inner === null ? null : `${inner}[]`;
  }

  // A typed value (`dict[str, int]`) mirrors as a typed record; a value this
  // parser cannot read (`dict[str, Any]`, nested generics) stays `unknown`.
  const record = /^dict\[\s*str\s*,\s*(.+)\]$/.exec(base);
  if (record !== null) {
    const value = expectedTsType(record[1].trim(), pyAliases, modelToInterface);
    return value === null ? "Record<string, unknown>" : `Record<string, ${value}>`;
  }
  if (/^dict\[/.test(base)) return "Record<string, unknown>";
  if (base === "JsonObject") return "Record<string, unknown>";

  const literal = pyAliases.get(base);
  if (literal !== undefined) return literal;
  if (base.startsWith("Literal[")) return normaliseUnion(base, "py");

  return modelToInterface(base);
}

/** A union rendered as a sorted member list, so the two languages compare. */
export function normaliseUnion(declaration: string, language: "py" | "ts"): string {
  const quote = language === "py" ? /"([^"]+)"/g : /'([^']+)'/g;
  const members = [...declaration.matchAll(quote)].map((m: string[]) => m[1]);
  if (members.length === 0) return declaration.replace(/\s+/g, " ").trim();
  return members.sort().join(" | ");
}

export function readModule(path: string): string | null {
  try {
    return readFileSync(path, "utf-8");
  } catch {
    return null;
  }
}

function stripNone(annotation: string): string {
  return annotation
    .replace(/^Optional\[(.+)\]$/, "$1")
    .split("|")
    .map((part: string) => part.trim())
    .filter((part: string) => part !== "None")
    .join(" | ")
    .trim();
}

function balance(text: string): number {
  let depth = 0;
  for (const character of text) {
    if (character === "(" || character === "[") depth += 1;
    if (character === ")" || character === "]") depth -= 1;
  }
  return depth;
}

/**
 * Whether the field may be omitted.
 *
 * `= Field(min_length=1)` is *not* a default — the field is still required, and
 * reading the bare `=` as one reported every constrained field as optional
 * (measured: three on `UserCreateRequest`).
 */
function hasDefault(assigned: string | undefined): boolean {
  if (assigned === undefined) return false;
  const value = assigned.trim();
  if (!value.startsWith("Field(")) return true;
  return /\bdefault(?:_factory)?\s*=/.test(value);
}

/** Own fields plus inherited ones, the subclass winning on a redeclared field. */
function resolve(
  own: Map<string, Map<string, FieldType>>,
  bases: Map<string, string[]>,
): Map<string, Map<string, FieldType>> {
  const resolved = new Map<string, Map<string, FieldType>>();
  for (const name of own.keys()) {
    const fields = new Map<string, FieldType>();
    const seen = new Set<string>();
    const stack = [name];
    while (stack.length > 0) {
      const current = stack.pop()!;
      if (seen.has(current)) continue;
      seen.add(current);
      for (const [field, type] of own.get(current) ?? []) {
        if (!fields.has(field)) fields.set(field, type);
      }
      for (const base of bases.get(current) ?? []) stack.push(base);
    }
    resolved.set(name, fields);
  }
  return resolved;
}
