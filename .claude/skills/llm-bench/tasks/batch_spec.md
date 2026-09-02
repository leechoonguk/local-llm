# Requirement — 휴면 계정 정리 배치 잡 (`purge_stale_users`)

이 저장소의 배치 체계는 "함수 하나 + 행 하나"다: 실행 코드는 `app.core.scheduler.BATCH_JOBS`
레지스트리에, 스케줄은 `batch_schedule` 테이블의 행에 산다. 이 요구는 그 체계에 잡 하나를 추가한다.

## Policy (fixed — do not invent)

- job code: `purge_stale_users`
- semantics: `created_at` 이 **90일**보다 오래된 계정을 삭제한다. 반환값은 삭제한 계정 수.
- grace 파라미터: `days: int = 90` — 기본값을 바꾸지 말 것.
- 삭제 도중 이미 사라진 계정(NotFoundError)은 건너뛰고 계속한다 — 배치는 개별 실패로 멈추지 않는다.

## Seed row (fixed — the migration seeds exactly this)

| column | value |
|---|---|
| code | `purge_stale_users` |
| name | `휴면 계정 정리` |
| description | `가입 90일이 지난 계정을 매일 새벽에 정리한다` |
| cron | `0 4 * * *` |
| enabled | `true` |

## Constraints (the harness enforces these — read the rules it names)

- 배치 잡은 raw `session.begin()`/commit 을 만지지 않는다 — 트랜잭션은 서비스 층 소유.
  읽기 국면과 쓰기 국면은 각각 자기 세션으로 연다(형제 잡이 그 형태다).
- 스케줄러 lifespan·라우터는 손대지 않는다 — 레지스트리 항목과 시드 행만으로 잡이 스케줄된다.
- backend `make verify` 는 커버리지 100% 를 요구한다 — 새로 쓴 모든 줄에 테스트가 필요하다.
