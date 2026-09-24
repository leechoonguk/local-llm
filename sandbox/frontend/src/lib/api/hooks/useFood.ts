/**
 * Food query hooks — the caching half of the food domain.
 *
 * Queries only: no mutation exists here, because the rows change when the
 * nightly derive job runs, not when a user clicks. That is also why the
 * staleness is `REALTIME`: a cache window is only safe when a write on this
 * side can cut it short by invalidating the key, and no write here can - so
 * the query refetches on mount and focus, and the toolbar's refresh covers the
 * reader who knows a rebuild just ran (`check-frontend-api-layer`).
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import {
  foodBusinessKeys,
  foodSafetyRecordKeys,
  foodItemReportKeys,
  foodRawMaterialKeys,
} from '@/lib/api/queryKeys'
import { toApiError } from '@/lib/api/errors'
import { foodService } from '@/lib/api/services/food.service'
import type { OffsetLimitParams } from '@/types/api'
import type {
  FoodChatEndEvent,
  FoodChatErrorEvent,
  FoodChatTokenEvent,
  ReportKind,
} from '@/types/food'
import type {
  FoodBusinessListParams,
  FoodSafetyRecordListParams,
  FoodItemReportListParams,
  FoodRawMaterialListParams,
} from '@/types/food'

export function useFoodItemReportList(params: FoodItemReportListParams) {
  return useQuery({
    queryKey: foodItemReportKeys.list(params),
    queryFn: () => foodService.listItemReports(params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

/**
 * The 식품유형 select's options - the table's own values, keyed as a list with a
 * discriminator so the page and the vocabulary never share a key.
 */
export function useFoodItemReportFacets() {
  return useQuery({
    queryKey: foodItemReportKeys.list({ facets: true }),
    queryFn: () => foodService.itemReportFacets(),
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * A page of what authorities published, across every product.
 *
 * Its own key scope, not a discriminator on the report list: the two screens
 * answer different questions and a shared key would make one's page the
 * other's cache.
 */
export function useFoodSafetyRecordList(params: FoodSafetyRecordListParams) {
  return useQuery({
    queryKey: foodSafetyRecordKeys.list(params),
    queryFn: () => foodService.listSafetyRecords(params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

/** The three event selects' options - the event table's own values. */
export function useFoodSafetyRecordFacets() {
  return useQuery({
    queryKey: foodSafetyRecordKeys.list({ facets: true }),
    queryFn: () => foodService.safetyRecordFacets(),
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * The product one (종류, 번호) names, for a screen that holds the key and needs the id.
 *
 * A list read, but an **identity** read: it answers "which row is this key?",
 * so it carries no `placeholderData`. Measured 2026-09-16 with one: clicking a
 * 위해정보 row opened the dialog on the *previous* lookup's product (TEST, 886px
 * tall), which collapsed to 303px and was replaced by the right one two frames
 * later - one blink, and for that moment the reader was looking at another
 * company's product. Disabled while the key is null, so nothing is fetched and
 * nothing is left behind for the next key to inherit.
 */
export function useFoodItemReportByKey(key: { report_kind: ReportKind; item_report_no: string } | null) {
  const params: FoodItemReportListParams = {
    offset: 0,
    limit: 1,
    ...(key === null ? {} : { report_kind: key.report_kind, item_report_no: key.item_report_no }),
  }
  return useQuery({
    queryKey: foodItemReportKeys.list({ ...params, byKey: true }),
    queryFn: () => foodService.listItemReports(params),
    enabled: key !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/** One report with its edges; `null` while no row is open, so nothing is fetched. */
export function useFoodItemReport(id: string | null) {
  return useQuery({
    queryKey: foodItemReportKeys.detail(id ?? ''),
    queryFn: () => foodService.getItemReport(id ?? ''),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * What the Food Code says about the report's types. Keyed under the report's
 * detail with a `standards` discriminator, fetched only while its tab is open -
 * the walk up two trees is the one read here that costs more than a row.
 */
export function useFoodItemReportStandards(id: string | null) {
  return useQuery({
    queryKey: foodItemReportKeys.detail(`${id ?? ''}:standards`),
    queryFn: () => foodService.getItemReportStandards(id ?? ''),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * The 푸드QR 라벨 printed under this report - what the package says, beside the
 * analysed values the detail already carries. Keyed under the report's detail
 * with a `labels` discriminator and fetched only while its tab is open: most
 * reports have none (2,278 labels over 1,424 of 1,640,212 reports), so the read
 * is not worth making with the row.
 */
export function useFoodItemReportLabels(id: string | null) {
  return useQuery({
    queryKey: foodItemReportKeys.detail(`${id ?? ''}:labels`),
    queryFn: () => foodService.getItemReportLabels(id ?? ''),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * The product's declarations - a page of them, fetched only while its tab is
 * open. A product is declared 3.6 times on average and 1,388 times at the
 * widest (2026-09-14), so the window is part of the key and two pages never
 * share one.
 */
export function useFoodItemReportDeclarations(id: string | null, params: OffsetLimitParams) {
  return useQuery({
    queryKey: foodItemReportKeys.detail(`${id ?? ''}:declarations:${params.offset}:${params.limit}`),
    queryFn: () => foodService.itemReportDeclarations(id ?? '', params),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

/**
 * What a supervising authority published about the product - a recall, a failed
 * inspection. Fetched only while the history tab is open: 948 events over 1.9M
 * products (2026-09-14), so most rows have none and the read is not worth
 * making with the row.
 */
export function useFoodItemReportSafetyRecords(id: string | null, params: OffsetLimitParams) {
  return useQuery({
    queryKey: foodItemReportKeys.detail(`${id ?? ''}:events:${params.offset}:${params.limit}`),
    queryFn: () => foodService.itemReportSafetyRecords(id ?? '', params),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

export function useFoodRawMaterialList(params: FoodRawMaterialListParams) {
  return useQuery({
    queryKey: foodRawMaterialKeys.list(params),
    queryFn: () => foodService.listRawMaterials(params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

/** The select filters' options - the table's own values, keyed as a list with a discriminator. */
export function useFoodRawMaterialFacets() {
  return useQuery({
    queryKey: foodRawMaterialKeys.list({ facets: true }),
    queryFn: () => foodService.rawMaterialFacets(),
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/** One material with its base's variants; `null` while no row is open, so nothing is fetched. */
export function useFoodRawMaterial(id: string | null) {
  return useQuery({
    queryKey: foodRawMaterialKeys.detail(id ?? ''),
    queryFn: () => foodService.getRawMaterial(id ?? ''),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * The products whose label names one material - a page of them, fetched only
 * while the tab that shows them is open. Keyed under the material's detail
 * with a discriminator and the window, so two pages never share a key.
 */
export function useFoodRawMaterialItemReports(id: string | null, params: OffsetLimitParams) {
  return useQuery({
    queryKey: foodRawMaterialKeys.detail(`${id ?? ''}:item-reports:${params.offset}:${params.limit}`),
    queryFn: () => foodService.rawMaterialItemReports(id ?? '', params),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

export function useFoodBusinessList(params: FoodBusinessListParams) {
  return useQuery({
    queryKey: foodBusinessKeys.list(params),
    queryFn: () => foodService.listBusinesses(params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

/** The industry select's options - the table's own values, keyed with a discriminator. */
export function useFoodBusinessFacets() {
  return useQuery({
    queryKey: foodBusinessKeys.list({ facets: true }),
    queryFn: () => foodService.businessFacets(),
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/** One business with its namesakes and its site's neighbours; `null` fetches nothing. */
export function useFoodBusiness(id: string | null) {
  return useQuery({
    queryKey: foodBusinessKeys.detail(id ?? ''),
    queryFn: () => foodService.getBusiness(id ?? ''),
    enabled: id !== null,
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}

/**
 * One chat turn, streamed - the transport, and nothing about the transcript.
 *
 * A hook rather than a query: there is nothing to cache. The answer arrives
 * as server-sent events (`foodService.chat`), a `token` at a time, and what a
 * cache would hold is a conversation the server does not keep either.
 *
 * It reports the pieces and lets the caller decide where they land, because
 * the transcript belongs to whichever conversation is open
 * (`ChatConversationsProvider`) and this layer knows nothing of those.
 *
 * Every turn ends on an event: `end` carries the server's own whole answer -
 * the authority in case a token was dropped - and `error` a code the caller
 * words. A stream that simply stopped could not be told from a lost network,
 * which is why the server never ends one that way.
 */
export function useFoodChat(handlers: {
  onToken: (text: string) => void
  onEnd: (text: string) => void
  onFailure: (code: string) => void
}) {
  const [streaming, setStreaming] = useState(false)
  /** Aborting is not a render, and the next ask must see the current one. */
  const controller = useRef<AbortController | null>(null)
  /**
   * The caller's handlers as of the last render. A ref because `ask` is
   * created once and runs across many renders: closing over the handlers
   * would write a turn's tokens through the callbacks of the render that
   * started it.
   */
  const latest = useRef(handlers)
  useEffect(() => {
    latest.current = handlers
  })

  // A turn in flight outlives the screen otherwise: the socket stays open.
  useEffect(() => () => controller.current?.abort(), [])

  const ask = useCallback(async (message: string) => {
    if (controller.current !== null) return
    const inFlight = new AbortController()
    controller.current = inFlight
    setStreaming(true)
    try {
      for await (const event of foodService.chat(message, inFlight.signal)) {
        if (event.event === 'token') latest.current.onToken((event.data as FoodChatTokenEvent).text)
        if (event.event === 'end') latest.current.onEnd((event.data as FoodChatEndEvent).text)
        if (event.event === 'error') {
          latest.current.onFailure((event.data as FoodChatErrorEvent).code)
        }
      }
    } catch (error) {
      // An abort is the reader's own stop: the turn keeps what arrived.
      if (!inFlight.signal.aborted) latest.current.onFailure(toApiError(error).code)
    } finally {
      setStreaming(false)
      controller.current = null
    }
  }, [])

  const stop = useCallback(() => controller.current?.abort(), [])

  return { streaming, ask, stop }
}
