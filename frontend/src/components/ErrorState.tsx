import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Typography from '@mui/material/Typography';

import type { ApiError } from '../api/client';

export function referenceText(requestId: string | null | undefined): string | null {
  return requestId ? `Reference: ${requestId}` : null;
}

/** Inline error: the message and the request reference. Never a stack trace or raw exception. */
export default function ErrorState({ error, title }: { error: ApiError; title?: string }) {
  const reference = referenceText(error.requestId);
  return (
    <Alert severity="error" role="alert">
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
