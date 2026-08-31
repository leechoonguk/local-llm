/**
 * The navigation model — grouped under subheaders, as in the reference
 * application.
 *
 * A subheader is not decoration: it is how a sidebar stays readable past four
 * entries, and it names the part of the product each screen belongs to. A route
 * that exists but is not listed is a screen nobody can reach, so
 * `check-frontend-routing` compares this list against the path registry in both
 * directions.
 */

import { PATHS } from '@/routes/paths'
import type { NavIcon } from '@/components/iconify/icons'

export interface NavItem {
  /** Key inside the `nav` namespace. */
  titleKey: string
  path: string
  /** Key into `NAV_ICONS` — a local SVG drawn through `SvgColor`. */
  icon: NavIcon
}

export interface NavGroup {
  /** Key inside the `nav` namespace, rendered as the group's subheader. */
  subheaderKey: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    subheaderKey: 'group.overview',
    items: [{ titleKey: 'dashboard', path: PATHS.dashboard, icon: 'dashboard' }],
  },
  {
    subheaderKey: 'group.admin',
    items: [
      { titleKey: 'user', path: PATHS.user, icon: 'user' },
      { titleKey: 'batch', path: PATHS.batch, icon: 'batch' },
      { titleKey: 'integration', path: PATHS.integration, icon: 'integration' },
    ],
  },
]
