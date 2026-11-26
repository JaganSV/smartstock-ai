/**
 * Holds the session ``{token, user, capabilities, expiresAt}`` in React state only (ADR-006): no
 * localStorage, sessionStorage or cookie, so a page refresh means signing in again.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { setAuthHandlers } from '../api/client';
import * as endpoints from '../api/endpoints';
import {
  AuthContext,
  SESSION_EXPIRED,
  SIGN_IN_AGAIN,
  type AuthContextValue,
  type Capability,
  type Session,
} from './AuthContext';

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(null);

  const logout = useCallback((message?: string) => {
    tokenRef.current = null;
    setSession(null);
    setNotice(message ?? null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await endpoints.login({ username, password });
    const user = await endpoints.getMe(result.access_token);
    tokenRef.current = result.access_token;
    setNotice(null);
    setSession({
      token: result.access_token,
      user,
      capabilities: [...user.capabilities],
      expiresAt: Date.now() + result.expires_in * 1000,
    });
  }, []);

  // The API client reads the token from here and signs out on a 401.
  useEffect(
    () =>
      setAuthHandlers({
        getToken: () => tokenRef.current,
        onUnauthorized: () => {
          if (tokenRef.current !== null) logout(SIGN_IN_AGAIN);
        },
      }),
    [logout],
  );

  // Automatic sign-out when the token expires.
  useEffect(() => {
    if (!session) return undefined;
    const timer = setTimeout(
      () => logout(SESSION_EXPIRED),
      Math.max(0, session.expiresAt - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [session, logout]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      notice,
      login,
      logout,
      can: (capability: Capability) => session?.capabilities.includes(capability) ?? false,
    }),
    [session, notice, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
