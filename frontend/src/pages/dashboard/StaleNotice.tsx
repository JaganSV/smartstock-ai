import Alert from '@mui/material/Alert';

import RecalculateButton from './RecalculateButton';

export const STALE_NOTICE = 'Data changed since the last snapshot. Figures may be out of date.';

/**
 * A 409 "stale snapshot" (the API's recompute differs from the stored row). Admins get a
 * Recalculate action (``RecalculateButton`` renders nothing without the capability).
 */
export default function StaleNotice({ onRecalculated }: { onRecalculated: () => void }) {
  return (
    <Alert severity="warning" action={<RecalculateButton onDone={onRecalculated} variant="text" />}>
      {STALE_NOTICE}
    </Alert>
  );
}
