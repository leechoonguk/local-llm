/**
 * Whether the page has scrolled past a threshold.
 *
 * The reference application uses framer-motion's `useScroll` for this; a passive
 * scroll listener answers the same question without pulling an animation
 * library in for one boolean. The initial read matters: a route entered while
 * already scrolled must start in the offset state, not snap into it on the
 * first wheel event.
 */

import { useEffect, useState } from 'react'

export default function useOffsetTop(top: number): boolean {
  const [offset, setOffset] = useState(() => window.scrollY > top)

  useEffect(() => {
    const read = () => setOffset(window.scrollY > top)

    read()
    window.addEventListener('scroll', read, { passive: true })

    return () => window.removeEventListener('scroll', read)
  }, [top])

  return offset
}
