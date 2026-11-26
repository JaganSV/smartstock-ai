import { Navigate, Route, Routes } from 'react-router';

import RequireAuth from './auth/RequireAuth';
import RequireCapability from './auth/RequireCapability';
import AppShell from './layout/AppShell';
import AuditLog from './pages/admin/AuditLog';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import NotFound from './pages/NotFound';

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
              <Dashboard />
            </RequireCapability>
          }
        />
        <Route
          path="admin/audit-log"
          element={
            <RequireCapability cap="view_governance">
              <AuditLog />
            </RequireCapability>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
