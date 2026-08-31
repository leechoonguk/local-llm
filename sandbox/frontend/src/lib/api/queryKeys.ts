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

export const batchKeys = createQueryKeys('batches')

export const integrationKeys = createQueryKeys('integrations')

export const authKeys = createQueryKeys('auth')
