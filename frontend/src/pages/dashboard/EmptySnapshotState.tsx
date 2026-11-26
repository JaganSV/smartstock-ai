import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';

import { useAuth } from '../../auth/AuthContext';
import RecalculateButton from './RecalculateButton';

export const NO_SNAPSHOT = 'No verified analytics snapshot yet.';
export const ASK_ADMIN = 'Ask an administrator to run a calculation.';

/** Page-level state when the API has no snapshot (409 on summary or distribution). */
export default function EmptySnapshotState({ onDone }: { onDone: () => void }) {
  const { can } = useAuth();
  return (
    <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }} role="status">
      <Typography variant="h2" gutterBottom>
        {NO_SNAPSHOT}
      </Typography>
      {can('recalculate_analytics') ? (
        <>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            Run the first calculation to create a verified snapshot.
          </Typography>
          <RecalculateButton onDone={onDone} label="Run first calculation" variant="contained" />
        </>
      ) : (
        <Typography color="text.secondary">{ASK_ADMIN}</Typography>
      )}
    </Paper>
  );
}
