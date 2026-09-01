// omp 18.x 호환 심 (2026-09-01): 이 플러그인은 upstream pi(@earendil-works)의
// withFileMutationQueue 를 쓰는데 omp 의 레거시 심에는 아직 없다. 의미는 "파일별
// 뮤테이션 직렬화"뿐이라 Promise 체인으로 로컬 구현한다. 나머지 심볼은 omp 심 재수출.
export { DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, formatSize, keyHint } from "@oh-my-pi/pi-coding-agent";
export type { ExtensionAPI, Theme, TruncationResult } from "@oh-my-pi/pi-coding-agent";

const queues = new Map<string, Promise<unknown>>();
export function withFileMutationQueue<T>(path: string, work: () => Promise<T>): Promise<T> {
  const prev = queues.get(path) ?? Promise.resolve();
  const next = prev.then(work, work);
  queues.set(path, next.catch(() => {}));
  return next;
}
// createReadTool·truncateHead 는 omp 심에 실재(번들 export map 확인) — 재수출.
export { createReadTool, truncateHead } from "@oh-my-pi/pi-coding-agent";
// ToolDefinition 은 타입 전용(런타임 소거). omp 심 .d.ts 에 없어 로컬 별칭으로 둔다.
export type ToolDefinition<TParams = any, TDetails = any, TState = any> = {
  name: string;
  label?: string;
  description: string;
  parameters: any;
  execute: (...args: any[]) => any;
} & Record<string, any>;
