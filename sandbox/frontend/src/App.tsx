/**
 * The route table — the only place a URL is bound to a screen.
 *
 * Layouts carry the guards (`DashboardLayout` → `AuthGuard`, `AuthLayout` →
 * `GuestGuard`), so a route's protection is decided by which layout it sits
 * under and cannot be forgotten per page. Every `path` comes from the registry:
 * `check-frontend-routing` compares the two tables in both directions.
 *
 * Pages are lazy: MUI and the grid are most of the bundle, and a user who only
 * signs in should not download the provider-configuration screen to do it.
 */

import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AuthLayout from '@/layouts/auth/AuthLayout'
import DashboardLayout from '@/layouts/dashboard/DashboardLayout'
import LoadingScreen from '@/components/loading-screen/LoadingScreen'
import { PATHS } from '@/routes/paths'

const LoginPage = lazy(() => import('@/pages/LoginPage'))

const DashboardPage = lazy(() => import('@/pages/DashboardPage'))

const UserPage = lazy(() => import('@/pages/UserPage'))
const FoodItemReportPage = lazy(() => import('@/pages/FoodItemReportPage'))
const FoodSafetyRecordPage = lazy(() => import('@/pages/FoodSafetyRecordPage'))
const FoodRawMaterialPage = lazy(() => import('@/pages/FoodRawMaterialPage'))
const FoodBusinessPage = lazy(() => import('@/pages/FoodBusinessPage'))
const FoodChatPage = lazy(() => import('@/pages/FoodChatPage'))

const BatchPage = lazy(() => import('@/pages/BatchPage'))

const IntegrationPage = lazy(() => import('@/pages/IntegrationPage'))

const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

export default function App() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route path={PATHS.auth.login} element={<AuthLayout />}>
          <Route index element={<LoginPage />} />
        </Route>

        <Route element={<DashboardLayout />}>
          <Route path={PATHS.root} element={<Navigate to={PATHS.dashboard} replace />} />
          <Route path={PATHS.dashboard} element={<DashboardPage />} />
          <Route path={PATHS.user} element={<UserPage />} />
          <Route path={PATHS.food.itemReport} element={<FoodItemReportPage />} />
          <Route path={PATHS.food.safetyRecord} element={<FoodSafetyRecordPage />} />
          <Route path={PATHS.food.rawMaterial} element={<FoodRawMaterialPage />} />
          <Route path={PATHS.food.business} element={<FoodBusinessPage />} />
          <Route path={PATHS.food.chat} element={<FoodChatPage />} />
          <Route path={PATHS.batch} element={<BatchPage />} />
          <Route path={PATHS.integration} element={<IntegrationPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}
