import VerifiedIcon from '@mui/icons-material/Verified';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

import type { SnapshotMeta } from '../api/types';
import { formatDateTime } from '../lib/format';

export function verifiedLabel(calculatedAt: string, locale?: string, timeZone?: string): string {
  return `Verified · calculated ${formatDateTime(calculatedAt, locale, timeZone)}`;
}

interface Props {
  title: string;
  snapshot: SnapshotMeta;
  /** Tables or numbers from the API only. AI text belongs in ``AiNarrativePanel`` (BP §4.1 p3). */
  children: ReactNode;
  locale?: string;
  timeZone?: string;
}

/**
 * Neutral surface for deterministic, verified numbers (FR-A5): a "Verified · calculated <time>"
 * badge from the snapshot metadata. It never renders AI-generated text.
 */
export default function VerifiedDataPanel({ title, snapshot, children, locale, timeZone }: Props) {
  const theme = useTheme();
  return (
    <Paper
      component="section"
      aria-label={title}
      variant="outlined"
      sx={{ bgcolor: theme.verified.background, borderColor: theme.verified.border, p: 2 }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
        <Typography variant="h3" component="h2" sx={{ color: theme.verified.text, flexGrow: 1 }}>
          {title}
        </Typography>
        <Chip
          icon={<VerifiedIcon />}
          label={verifiedLabel(snapshot.calculated_at, locale, timeZone)}
          size="small"
          variant="outlined"
          color="success"
          data-testid="verified-badge"
        />
      </Box>
      {children}
    </Paper>
  );
}
