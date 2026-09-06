/**
 * The path registry — every route in the app, named once.
 *
 * A route string typed into a `<Link>` is a link that breaks silently when the
 * route moves. `check-frontend-routing` compares this table against the router
 * and the navigation config in both directions, so a path can only exist if it
 * is reachable and named.
 */

const ROOT_AUTH = '/auth'

export const PATHS = {
  root: '/',
  dashboard: '/dashboard',
  auth: {
    login: `${ROOT_AUTH}/login`,
  },
  user: '/user',
  batch: '/batch',
  integration: '/integration',
  food: {
    rawMaterial: '/food/raw-material',
  },
} as const
