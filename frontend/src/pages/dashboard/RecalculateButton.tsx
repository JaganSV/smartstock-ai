import RefreshIcon from '@mui/icons-material/Refresh';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Snackbar from '@mui/material/Snackbar';
import { useState } from 'react';

import { toApiError } from '../../api/client';
import { recalculate } from '../../api/endpoints';
import { useAuth } from '../../auth/AuthContext';
import { useApiErrorSnackbar } from '../../components/ApiErrorSnackbar';
import { formatNumber } from '../../lib/format';

export const CONFIRM_TEXT =
  'Recalculate all inventory metrics now? This creates a new verified snapshot.';
export const LOCK_HELD = 'A recalculation is already running.';

interface Props {
  /** Called after a new snapshot exists, to reload every section. */
  onDone: () => void;
  label?: string;
  variant?: 'text' | 'outlined' | 'contained';
}

interface Notice {
  severity: 'success' | 'warning';
  message: string;
}

/**
 * FR-B5 for admins: confirm, ``POST /analytics/recalculate``, report the new snapshot. Rendered
 * only with the ``recalculate_analytics`` capability; the backend enforces the role regardless.
 */
export default function RecalculateButton({
  onDone,
  label = 'Recalculate',
  variant = 'outlined',
}: Props) {
  const { can } = useAuth();
  const { showError } = useApiErrorSnackbar();
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  if (!can('recalculate_analytics')) return null;

  const run = async () => {
    setConfirming(false);
    setRunning(true);
    try {
      const result = await recalculate();
      setNotice({
        severity: 'success',
        message:
          `Snapshot ${result.snapshot_id} created ` +
          `(${formatNumber(result.row_count)} rows, ${formatNumber(result.duration_ms)} ms)`,
      });
      onDone();
    } catch (caught) {
      const error = toApiError(caught);
      if (error.status === 409 && error.message === LOCK_HELD) {
        setNotice({ severity: 'warning', message: LOCK_HELD });
      } else if (error.status !== 403) {
        // A 403 already shows the permission snackbar (API client interceptor).
        showError(error);
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <Button
        variant={variant}
        startIcon={<RefreshIcon />}
        onClick={() => setConfirming(true)}
        disabled={running}
      >
        {running ? 'Recalculating…' : label}
      </Button>
      <Dialog open={confirming} onClose={() => setConfirming(false)}>
        <DialogTitle>Recalculate analytics</DialogTitle>
        <DialogContent>
          <DialogContentText>{CONFIRM_TEXT}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirming(false)}>Cancel</Button>
          <Button variant="contained" onClick={run} autoFocus>
            Recalculate
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={notice !== null}
        autoHideDuration={6000}
        onClose={(_, reason) => reason !== 'clickaway' && setNotice(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={notice?.severity ?? 'success'}
          variant="filled"
          onClose={() => setNotice(null)}
        >
          {notice?.message}
        </Alert>
      </Snackbar>
    </>
  );
}
