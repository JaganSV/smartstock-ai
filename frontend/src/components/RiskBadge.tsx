import Chip from '@mui/material/Chip';
import { useTheme } from '@mui/material/styles';

import type { RiskClass } from '../theme/theme';

/**
 * A risk class as colour and text together, never colour alone. Colours and their AA contrast
 * are documented in ``theme.ts`` (``riskColors``).
 */
export default function RiskBadge({
  risk,
  size = 'small',
}: {
  risk: RiskClass;
  size?: 'small' | 'medium';
}) {
  const theme = useTheme();
  const { background, text } = theme.risk[risk];
  return (
    <Chip
      label={risk}
      size={size}
      role="img"
      aria-label={`Risk: ${risk}`}
      sx={{ bgcolor: background, color: text, fontWeight: 600, letterSpacing: 0.3 }}
    />
  );
}
