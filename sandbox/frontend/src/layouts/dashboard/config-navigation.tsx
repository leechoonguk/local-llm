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

import type { ParseKeys } from 'i18next'
import { PATHS } from '@/routes/paths'
import type { NavIcon } from '@/components/iconify/icons'

/**
 * A key the `nav` namespace really has.
 *
 * Typed rather than `string` because these keys are read at a distance: the
 * sidebar renders `t(item.titleKey)`, so a key that exists nowhere renders as
 * itself in the navigation and no test looks at a label.
 */
type NavKey = ParseKeys<'nav'>

export interface NavItem {
  /** Key inside the `nav` namespace. */
  titleKey: NavKey
  path: string
  /** Key into `NAV_ICONS` — a local SVG drawn through `SvgColor`. */
  icon: NavIcon
}

export interface NavGroup {
  /**
   * Key inside the `nav` namespace, rendered as the group's subheader — and the
   * **area** the group's screens answer to (rule://product-areas): the pattern
   * every domain under it must carry is mapped from this key.
   *
   * `null` for the ungrouped head, which is the dashboard: an overview of every
   * area is in none of them, and a subheader over a single item is a label for a
   * group that does not exist.
   */
  subheaderKey: NavKey | null
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    subheaderKey: null,
    items: [{ titleKey: 'dashboard', path: PATHS.dashboard, icon: 'dashboard' }],
  },
  {
    subheaderKey: 'group.user',
    items: [{ titleKey: 'user', path: PATHS.user, icon: 'user' }],
  },
  {
    /**
     * 배치 — configuration whose work happens elsewhere. 외부 연동 stands here
     * rather than beside the dashboard because it *is* this pattern: a provider
     * row is configuration, its operations are exercised on demand, and the
     * calls are logged the way a schedule's runs are (rule://product-areas).
     */
    subheaderKey: 'group.batch',
    items: [
      { titleKey: 'batch', path: PATHS.batch, icon: 'batch' },
      { titleKey: 'integration', path: PATHS.integration, icon: 'integration' },
    ],
  },
  {
    subheaderKey: 'group.food',
    items: [
      { titleKey: 'food_chat', path: PATHS.food.chat, icon: 'food_chat' },
      { titleKey: 'food_item_report', path: PATHS.food.itemReport, icon: 'food_item_report' },
      { titleKey: 'food_raw_material', path: PATHS.food.rawMaterial, icon: 'food_raw_material' },
      { titleKey: 'food_business', path: PATHS.food.business, icon: 'food_business' },
      {
        titleKey: 'food_safety_record',
        path: PATHS.food.safetyRecord,
        icon: 'food_event',
      },
    ],
  },
]
