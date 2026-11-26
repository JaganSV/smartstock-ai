import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router';

import RequireAuth from './auth/RequireAuth';
import RequireCapability from './auth/RequireCapability';
import AppShell from './layout/AppShell';
import PageSkeleton from './layout/PageSkeleton';
import Login from './pages/Login';

// Route-level code splitting (BOB-P4-02 E2): each page is its own chunk, loaded on first visit.
// The shell and the login page stay in the main chunk so sign-in needs no extra request.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AuditLog = lazy(() => import('./pages/admin/AuditLog'));
const NotFound = lazy(() => import('./pages/NotFound'));

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

/** Declarative routes (React Router v7, no framework mode). */
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route
          path="dashboard"
          element={
            <RequireCapability cap="view_inventory">
              <Page>
                <Dashboard />
              </Page>
            </RequireCapability>
          }
        />
        <Route
          path="admin/audit-log"
          element={
            <RequireCapability cap="view_governance">
              <Page>
                <AuditLog />
              </Page>
            </RequireCapability>
          }
        />
        <Route
          path="*"
          element={
            <Page>
              <NotFound />
            </Page>
          }
        />
      </Route>
    </Routes>
  );
}
