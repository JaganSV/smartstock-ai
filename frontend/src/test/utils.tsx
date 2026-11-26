/** Test helpers: render inside the theme, the snackbar provider and a router. */
import { ThemeProvider } from '@mui/material/styles';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
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
      <ApiErrorSnackbarProvider>{children}</ApiErrorSnackbarProvider>
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
