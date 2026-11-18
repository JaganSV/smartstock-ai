import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CircularProgress from '@mui/material/CircularProgress';
import Container from '@mui/material/Container';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';

import { getHealth } from '../api/client';
import { verified } from '../theme/theme';

type HealthState = 'loading' | 'ok' | 'unavailable';

export default function Home() {
  const [state, setState] = useState<HealthState>('loading');

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then(() => {
        if (!cancelled) setState('ok');
      })
      .catch(() => {
        if (!cancelled) setState('unavailable');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="h1">
            SmartStock AI
          </Typography>
        </Toolbar>
      </AppBar>
      <Container sx={{ mt: 4 }}>
        <Card variant="outlined" sx={{ bgcolor: verified.background, borderColor: verified.border }}>
          <CardContent>
            {state === 'loading' ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <CircularProgress size={20} />
                <Typography>Checking backend…</Typography>
              </Box>
            ) : (
              <Typography role="status">
                {state === 'ok' ? 'Backend: ok' : 'Backend: unavailable'}
              </Typography>
            )}
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
}
