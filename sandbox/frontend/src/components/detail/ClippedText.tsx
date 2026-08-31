/**
 * A value that clips, and shows the rest under it on hover.
 *
 * The native `title` attribute was the first attempt and it is not verifiable:
 * the browser draws that tooltip in its own chrome, so nothing in the DOM proves
 * it ever appeared — and reported from the screen, it did not. This renders MUI's
 * `Tooltip`, which mounts a real `[role=tooltip]` node: hovering can be measured,
 * the delay is ours to set, and a touch device gets a long-press instead of
 * nothing.
 *
 * The bubble appears **above the cursor** and then stays where it appeared. Three
 * attempts, all measured: anchored to the element it landed on top of the table
 * header and read as a label for something else (41px from the pointer);
 * `followCursor` closed the distance and cost the stillness, which is worse — text
 * that slides while the eye reads it cannot be read; under the value it was still
 * and calm but nowhere near the hand on a wide column. So the anchor is the point
 * where the pointer entered, captured once: over the cursor, and then motionless.
 *
 * It attaches **only while the text overflows**. A tooltip that repeats a value
 * already fully readable is noise on every cell of every row, and it trains the
 * reader to ignore the one that matters. Overflow is read from the node
 * (`scrollWidth > clientWidth`) and re-read when the element resizes, because a
 * column narrows when the window does.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { Box, Tooltip } from '@mui/material'

/** Long enough not to fire while the pointer crosses a row on its way elsewhere. */
const HOVER_DELAY_MS = 300

/**
 * How far above the cursor the bubble sits: clear of the pointer glyph, close
 * enough to read as the thing under it. MUI's own default is 14px.
 */
const CURSOR_GAP: [number, number] = [0, 12]

const CLIP_SX = {
  display: 'block',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
} as const

export default function ClippedText({ text }: { text: string }) {
  const node = useRef<HTMLElement | null>(null)
  const [overflows, setOverflows] = useState(false)
  /** Where the pointer entered. Captured once, so the bubble does not chase it. */
  const [entry, setEntry] = useState<{ x: number; y: number } | null>(null)

  const measure = useCallback(() => {
    const element = node.current
    if (element === null) return
    setOverflows(element.scrollWidth > element.clientWidth + 1)
  }, [])

  useEffect(() => {
    measure()
    const element = node.current
    if (element === null || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [measure, text])

  /** A zero-size rect at the entry point: Popper's anchor can be a shape, not a node. */
  const anchor = useMemo(
    () =>
      entry === null
        ? undefined
        : { getBoundingClientRect: () => new DOMRect(entry.x, entry.y, 0, 0) },
    [entry],
  )

  const body = (
    <Box
      component="span"
      ref={node}
      sx={CLIP_SX}
      onMouseEnter={(event: MouseEvent<HTMLElement>) =>
        setEntry({ x: event.clientX, y: event.clientY })
      }
    >
      {text}
    </Box>
  )

  if (!overflows) return body

  return (
    <Tooltip
      title={text}
      enterDelay={HOVER_DELAY_MS}
      placement="top"
      slotProps={{
        popper: {
          anchorEl: anchor,
          modifiers: [{ name: 'offset', options: { offset: CURSOR_GAP } }],
        },
      }}
    >
      {body}
    </Tooltip>
  )
}
