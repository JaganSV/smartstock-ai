import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined';
import type { SvgIconComponent } from '@mui/icons-material';

import type { Capability } from '../auth/AuthContext';

/**
 * Navigation as data. Later prompts add a page by adding an entry here. Only ``built`` entries are
 * shown, and only to users whose ``capabilities`` (from ``GET /auth/me``) include ``capability``.
 * Modules not built yet are not listed at all.
 */
export interface NavItem {
  label: string;
  path: string;
  icon: SvgIconComponent;
  capability: Capability;
  status: 'built' | 'planned';
  /** Optional group heading, e.g. "Admin". */
  section?: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: DashboardOutlined,
    capability: 'view_inventory',
    status: 'built',
  },
  {
    label: 'Audit log',
    path: '/admin/audit-log',
    icon: ReceiptLongOutlined,
    capability: 'view_governance',
    status: 'built',
    section: 'Admin',
  },
];

/** The entries a user may see: built and allowed by their capabilities. */
export function visibleNavItems(
  can: (capability: Capability) => boolean,
  items: readonly NavItem[] = NAV_ITEMS,
): NavItem[] {
  return items.filter((item) => item.status === 'built' && can(item.capability));
}
