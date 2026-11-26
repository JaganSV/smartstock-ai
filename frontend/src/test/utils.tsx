/** Test helpers: render inside the theme, the snackbar provider and a router. */
import { ThemeProvider } from '@mui/material/styles';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { vi } from 'vitest';

import type { MeResponse } from '../api/types';
import {
  AuthContext,
  type AuthContextValue,
  type Capability,
  type Session,
} from '../auth/AuthContext';
import AuthProvider from '../auth/AuthProvider';
import ApiErrorSnackbarProvider from '../components/ApiErrorSnackbar';
import { ChartWidthContext } from '../components/ChartFrame';
import AppRoutes from '../routes';
import { theme } from '../theme/theme';

/** Capability rows as ``GET /auth/me`` returns them (BP 10.2), for building fake users. */
export const CAPABILITIES: Record<string, Capability[]> = {
  ADMIN: [
    'ask_ai',
    'decide_recommendations',
    'export_approved_csv',
    'generate_executive_report',
    'generate_recommendations',
    'manage_documents',
    'recalculate_analytics',
    'view_governance',
    'view_inventory',
  ],
  ANALYST: ['ask_ai', 'view_inventory'],
};

export function me(role: 'ADMIN' | 'ANALYST', overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    id: role === 'ADMIN' ? 1 : 3,
    username: role.toLowerCase(),
    role,
    is_active: true,
    capabilities: CAPABILITIES[role],
    ...overrides,
  };
}

export function fakeSession(role: 'ADMIN' | 'ANALYST', capabilities?: string[]): Session {
  const user = me(role, capabilities ? { capabilities } : {});
  return {
    token: 'test-token-not-real',
    user,
    capabilities: user.capabilities,
    expiresAt: Date.now() + 3_600_000,
  };
}

export function fakeAuth(session: Session | null, overrides: Partial<AuthContextValue> = {}) {
  const value: AuthContextValue = {
    session,
    notice: null,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn(),
    can: (capability) => session?.capabilities.includes(capability) ?? false,
    ...overrides,
  };
  return value;
}

function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <ApiErrorSnackbarProvider>
        {/* jsdom cannot measure layout: charts render at a fixed width in tests. */}
        <ChartWidthContext.Provider value={640}>{children}</ChartWidthContext.Provider>
      </ApiErrorSnackbarProvider>
    </ThemeProvider>
  );
}

/** Renders ``ui`` with the theme only (components). */
export function renderWithTheme(ui: ReactElement): RenderResult {
  return render(ui, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    ),
  });
}

/** The whole route tree at ``path`` with a fake auth context. */
export function renderRoutes(path: string, auth: AuthContextValue): RenderResult {
  return render(
    <Providers>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthContext.Provider>
    </Providers>,
  );
}

/** The whole route tree at ``path`` with the real ``AuthProvider`` (signed out at first). */
export function renderApp(path: string): RenderResult {
  return render(
    <Providers>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </Providers>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

/**
 * One page at ``path`` (route pattern ``route``) with a fake signed-in user, the theme, the
 * snackbar provider and fixed-width charts; ``screen.getByTestId('location')`` shows the URL.
 */
export function renderPage(
  path: string,
  route: string,
  element: ReactElement,
  role: 'ADMIN' | 'ANALYST' = 'ADMIN',
): RenderResult {
  return render(
    <Providers>
      <AuthContext.Provider value={fakeAuth(fakeSession(role))}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route
              path={route}
              element={
                <>
                  {element}
                  <LocationProbe />
                </>
              }
            />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </Providers>,
  );
}

/**
 * Imports every lazily routed page once, so tests that render the route tree do not spend their
 * ``findBy`` window compiling a cold module graph (React.lazy then resolves from the cache).
 * Call from ``beforeAll`` with a generous timeout.
 */
export async function preloadPages(): Promise<void> {
  await Promise.all([
    import('../pages/Dashboard'),
    import('../pages/admin/AuditLog'),
    import('../pages/risk/StockoutRisk'),
    import('../pages/risk/SlowMoving'),
    import('../pages/products/ProductList'),
    import('../pages/products/ProductDetail'),
    import('../pages/NotFound'),
  ]);
}
