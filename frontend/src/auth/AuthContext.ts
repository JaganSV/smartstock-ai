import { createContext, useContext } from 'react';

import type { MeResponse } from '../api/types';

/**
 * Capability keys of the BP 10.2 role matrix as the backend names them. The UI never maps roles
 * to capabilities: it only reads the ``capabilities`` list ``GET /auth/me`` returns.
 */
export type Capability =
  | 'view_inventory'
  | 'ask_ai'
  | 'generate_recommendations'
  | 'decide_recommendations'
  | 'export_approved_csv'
  | 'generate_executive_report'
  | 'manage_documents'
  | 'recalculate_analytics'
  | 'view_governance';

export interface Session {
  token: string;
  user: MeResponse;
  capabilities: readonly string[];
  /** Epoch milliseconds at which the token expires. */
  expiresAt: number;
}

export const SESSION_EXPIRED = 'Your session expired. Please sign in again.';
export const SIGN_IN_AGAIN = 'Please sign in again.';

export interface AuthContextValue {
  session: Session | null;
  /** Message for the login page after an automatic sign-out (expiry or a 401). */
  notice: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: (notice?: string) => void;
  can: (capability: Capability) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}
