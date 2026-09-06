/**
 * User query/mutation hooks — the caching half of the user domain.
 *
 * Every mutation invalidates `userKeys.lists()` because a create, an update or
 * a delete all change what the list shows. `placeholderData` keeps the previous
 * page on screen while the next one loads, so paging does not flash empty.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import { userKeys } from '@/lib/api/queryKeys'
import { userService } from '@/lib/api/services/user.service'
import type { UserCreateRequest, UserListParams, UserUpdateRequest } from '@/types/user'

export function useUserList(params: UserListParams) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () => userService.list(params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

export function useUser(id: string | null) {
  return useQuery({
    queryKey: userKeys.detail(id ?? ''),
    queryFn: () => userService.detail(id ?? ''),
    staleTime: QUERY_STALE_TIME.STANDARD,
    enabled: id !== null,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: UserCreateRequest) => userService.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userKeys.lists() }),
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdateRequest }) =>
      userService.update(id, data),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() })
      queryClient.invalidateQueries({ queryKey: userKeys.detail(user.id) })
    },
  })
}

export function useDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => userService.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userKeys.lists() }),
  })
}
