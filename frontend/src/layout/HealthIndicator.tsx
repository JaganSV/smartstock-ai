import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';

import { getHealth } from '../api/endpoints';

type HealthState = 'checking' | 'ok' | 'unavailable';

const LABEL: Record<HealthState, string> = {
  checking: 'Backend: checking…',
  ok: 'Backend: ok',
  unavailable: 'Backend: unavailable',
};
const COLOUR: Record<HealthState, string> = {
  checking: '#6b7280',
  ok: '#166534',
  unavailable: '#b91c1c',
};

/** Small footer status from the public ``GET /health`` (kept from the P0 home page). */
export default function HealthIndicator() {
  const [state, setState] = useState<HealthState>('checking');

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then(() => !cancelled && setState('ok'))
      .catch(() => !cancelled && setState('unavailable'));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Box role="status" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box
        aria-hidden="true"
        sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: COLOUR[state], flexShrink: 0 }}
      />
      <Typography variant="caption" color="text.secondary" noWrap>
        {LABEL[state]}
      </Typography>
    </Box>
  );
}
