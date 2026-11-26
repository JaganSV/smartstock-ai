import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import type { ApiError } from '../api/client';

export function referenceText(requestId: string | null | undefined): string | null {
  return requestId ? `Reference: ${requestId}` : null;
}

interface Props {
  error: ApiError;
  title?: string;
  /** Shows a Retry button that calls this. */
  onRetry?: () => void;
}

/** Inline error: the message and the request reference. Never a stack trace or raw exception. */
export default function ErrorState({ error, title, onRetry }: Props) {
  const reference = referenceText(error.requestId);
  return (
    <Alert
      severity="error"
      role="alert"
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    >
      {title ? <AlertTitle>{title}</AlertTitle> : null}
      <Typography variant="body2">{error.message}</Typography>
      {reference ? (
        <Typography variant="caption" component="p" sx={{ fontFamily: 'monospace' }}>
          {reference}
        </Typography>
      ) : null}
    </Alert>
  );
}
