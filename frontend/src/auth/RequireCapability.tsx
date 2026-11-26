import type { ReactNode } from 'react';

import Forbidden from '../pages/Forbidden';
import { useAuth, type Capability } from './AuthContext';

/**
 * Shows the 403 page unless the user holds ``cap``. This is convenience only: the backend
 * enforces every capability on every call.
 */
export default function RequireCapability({
  cap,
  children,
}: {
  cap: Capability;
  children: ReactNode;
}) {
  const { can } = useAuth();
  if (!can(cap)) return <Forbidden />;
  return <>{children}</>;
}
