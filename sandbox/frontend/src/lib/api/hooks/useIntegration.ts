/**
 * Integration query/mutation hooks.
 *
 * Provider configuration is reference data — it changes when someone edits it,
 * not on its own — so the list is cached for `LONG`. `useExecuteOperation` is a
 * mutation even though it only reads upstream: it spends an external API call,
 * so it must be triggered, never refetched on focus.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import { integrationKeys } from '@/lib/api/queryKeys'
import { integrationService } from '@/lib/api/services/integration.service'
import type {
  IntegrationListParams,
  IntegrationCreateRequest,
  IntegrationExecuteRequest,
  IntegrationSecretCreateRequest,
  IntegrationSecretUpdateRequest,
  IntegrationUpdateRequest,
} from '@/types/integration'

export function useIntegrationList(params: IntegrationListParams) {
  return useQuery({
    queryKey: integrationKeys.list(params),
    queryFn: () => integrationService.list(params),
    staleTime: QUERY_STALE_TIME.LONG,
    placeholderData: (previous) => previous,
  })
}

export function useIntegration(id: string | null) {
  return useQuery({
    queryKey: integrationKeys.detail(id ?? ''),
    queryFn: () => integrationService.detail(id ?? ''),
    staleTime: QUERY_STALE_TIME.LONG,
    enabled: id !== null,
  })
}

export function useCreateIntegration() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IntegrationCreateRequest) => integrationService.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationKeys.lists() }),
  })
}

export function useUpdateIntegration() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: IntegrationUpdateRequest }) =>
      integrationService.update(id, data),
    onSuccess: (integration) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.lists() })
      queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integration.id) })
    },
  })
}

export function useDeleteIntegration() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => integrationService.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationKeys.lists() }),
  })
}

/**
 * A credential's three writes.
 *
 * Each invalidates the provider detail, not a secrets list: the dialog reads the
 * whole provider (`secrets` is nested in it), so the detail is the cache entry
 * that holds these rows.
 */
export function useCreateSecret(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IntegrationSecretCreateRequest) =>
      integrationService.createSecret(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationKeys.detail(id) }),
  })
}

export function useUpdateSecret(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: IntegrationSecretUpdateRequest }) =>
      integrationService.updateSecret(id, name, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationKeys.detail(id) }),
  })
}

export function useDeleteSecret(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => integrationService.removeSecret(id, name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationKeys.detail(id) }),
  })
}

/**
 * One configured operation, run once.
 *
 * No cache entry: the result belongs to the inputs the operator just typed, and
 * a second identical call spends another upstream request — which is exactly
 * what a query would do on a window focus.
 */
export function useExecuteOperation(id: string) {
  return useMutation({
    mutationFn: ({ operation, data }: { operation: string; data: IntegrationExecuteRequest }) =>
      integrationService.execute(id, operation, data),
  })
}
