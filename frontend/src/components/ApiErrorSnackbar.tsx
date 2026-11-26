import Alert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { setForbiddenHandler, type ApiError } from '../api/client';
import { referenceText } from './ErrorState';

export const NO_PERMISSION = "You don't have permission for this action.";

interface SnackbarMessage {
  message: string;
  requestId: string | null;
}

interface SnackbarContextValue {
  showError: (error: ApiError | string) => void;
}

const SnackbarContext = createContext<SnackbarContextValue>({ showError: () => {} });

export function useApiErrorSnackbar(): SnackbarContextValue {
  return useContext(SnackbarContext);
}

/** One error snackbar for the app: the message and "Reference: <request_id>". */
export function ApiErrorSnackbar({
  message,
  onClose,
}: {
  message: SnackbarMessage | null;
  onClose: () => void;
}) {
  const reference = message ? referenceText(message.requestId) : null;
  return (
    <Snackbar
      open={message !== null}
      autoHideDuration={6000}
      // A click elsewhere must not hide an error before it can be read.
      onClose={(_, reason) => reason !== 'clickaway' && onClose()}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
    >
      <Alert severity="error" onClose={onClose} variant="filled" sx={{ width: '100%' }}>
        {message?.message}
        {reference ? (
          <div style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{reference}</div>
        ) : null}
      </Alert>
    </Snackbar>
  );
}

/** Provides ``showError`` and shows the permission message on every 403 from the API client. */
export default function ApiErrorSnackbarProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<SnackbarMessage | null>(null);

  const showError = useCallback((error: ApiError | string) => {
    setMessage(
      typeof error === 'string'
        ? { message: error, requestId: null }
        : { message: error.message, requestId: error.requestId },
    );
  }, []);

  useEffect(() => setForbiddenHandler(() => showError(NO_PERMISSION)), [showError]);

  const value = useMemo(() => ({ showError }), [showError]);
  return (
    <SnackbarContext.Provider value={value}>
      {children}
      <ApiErrorSnackbar message={message} onClose={() => setMessage(null)} />
    </SnackbarContext.Provider>
  );
}
