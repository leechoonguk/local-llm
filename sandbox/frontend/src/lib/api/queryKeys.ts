/**
 * Central query-key factory.
 *
 * A hook that spells its own key array cannot be invalidated by anyone else:
 * the mutation and the query drift apart and the list silently shows stale
 * rows. Every domain therefore takes its keys from `createQueryKeys`, and
 * `check-frontend-api-layer` rejects an inline `queryKey: ['...']` literal.
 */

interface QueryKeyFactory {
  all: readonly [string]
  lists: () => readonly [string, 'list']
  list: (params: object) => readonly [string, 'list', object]
  details: () => readonly [string, 'detail']
  detail: (id: string) => readonly [string, 'detail', string]
}

function createQueryKeys(scope: string): QueryKeyFactory {
  return {
    all: [scope],
    lists: () => [scope, 'list'],
    list: (params) => [scope, 'list', params],
    details: () => [scope, 'detail'],
    detail: (id) => [scope, 'detail', id],
  }
}

export const userKeys = createQueryKeys('users')
export const foodItemReportKeys = createQueryKeys('food-item-reports')
export const foodSafetyRecordKeys = createQueryKeys('food-item-report-events')
export const foodRawMaterialKeys = createQueryKeys('food-raw-materials')
export const foodBusinessKeys = createQueryKeys('food-businesses')

export const batchKeys = createQueryKeys('batches')

/**
 * A schedule's executions, and one execution's units — each its own scope, not
 * a `scope:` discriminator folded into `batchKeys.list(...)`.
 *
 * Invalidation matches by prefix, so `batchKeys.lists()` (`['batches','list']`)
 * matched `['batches','list',{scope:'runs',…}]` too, and a schedule's own
 * create/update/delete marked the run log and the step log invalid. Nothing
 * asked for that: those rows are written by the scheduler, outside HTTP, and no
 * mutation in this client can produce one.
 *
 * What it cost so far is a marking, not a request — `invalidateQueries` defaults
 * to `refetchType: 'active'`, and these queries are only mounted while the run
 * dialog is open, which cannot coincide with editing the schedule behind it. It
 * becomes a refetch the first time a screen shows a run log beside a schedule
 * write. The key was claiming a containment that does not hold, and a key that
 * lies is repaired before it is copied — separate scopes have no prefix relation.
 */
export const batchRunKeys = createQueryKeys('batch-runs')

export const batchStepKeys = createQueryKeys('batch-steps')

export const integrationKeys = createQueryKeys('integrations')

/**
 * A provider's call log — its own scope, for the reason `batchRunKeys` is one:
 * the rows are written by whatever exercised the operation (a nightly sync job,
 * outside any request of this client), so a provider's own writes must not mark
 * them invalid, and a prefix relation would claim exactly that.
 */
export const integrationCallKeys = createQueryKeys('integration-calls')
