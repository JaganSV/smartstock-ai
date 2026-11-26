import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, type Location } from 'react-router';

import { SERVICE_UNAVAILABLE, toApiError, type ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { referenceText } from '../components/ErrorState';

export const INVALID_CREDENTIALS = 'Invalid username or password.';
export const TOO_MANY_ATTEMPTS_LATER = 'Too many failed attempts. Try again later.';

export function tooManyAttempts(retryAfterSeconds: number | null): string {
  if (retryAfterSeconds === null) return TOO_MANY_ATTEMPTS_LATER;
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60));
  return `Too many failed attempts. Try again in ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}.`;
}

interface LoginError {
  message: string;
  requestId: string | null;
}

/** The message for a failed login (BP §6.1 envelope, ADR-015 lockout). */
export function loginErrorMessage(error: ApiError): LoginError {
  if (error.status === 401) return { message: INVALID_CREDENTIALS, requestId: null };
  if (error.status === 429) return { message: tooManyAttempts(error.retryAfter), requestId: null };
  if (error.status === 0 || error.status >= 500) {
    return { message: SERVICE_UNAVAILABLE, requestId: error.requestId };
  }
  return { message: error.message, requestId: error.requestId };
}

function targetPath(state: unknown): string {
  const from = (state as { from?: Location } | null)?.from;
  if (!from || from.pathname === '/login') return '/dashboard';
  return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`;
}

export default function Login() {
  const { session, login, notice } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<LoginError | null>(null);

  if (session) return <Navigate to={targetPath(location.state)} replace />;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      // On success the new session re-renders this page as a <Navigate> to the target.
      await login(username.trim(), password);
    } catch (caught) {
      setError(loginErrorMessage(toApiError(caught)));
      setPassword('');
      setSubmitting(false);
    }
  };

  const reference = error ? referenceText(error.requestId) : null;

  return (
    <Box
      component="main"
      sx={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Paper variant="outlined" sx={{ p: 4, width: '100%', maxWidth: 400 }}>
        <Typography variant="h1" gutterBottom>
          SmartStock AI
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Sign in to continue.
        </Typography>
        {notice && !error ? (
          <Alert severity="info" sx={{ mb: 2 }}>
            {notice}
          </Alert>
        ) : null}
        {error ? (
          <Alert severity="error" role="alert" sx={{ mb: 2 }}>
            {error.message}
            {reference ? (
              <Typography variant="caption" component="p" sx={{ fontFamily: 'monospace' }}>
                {reference}
              </Typography>
            ) : null}
          </Alert>
        ) : null}
        <Box component="form" onSubmit={onSubmit} noValidate>
          <TextField
            label="Username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            fullWidth
            required
            margin="normal"
            autoFocus
          />
          <TextField
            label="Password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            fullWidth
            required
            margin="normal"
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      onClick={() => setShowPassword((value) => !value)}
                      edge="end"
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />
          <Button
            type="submit"
            variant="contained"
            fullWidth
            sx={{ mt: 2 }}
            disabled={submitting || !username.trim() || !password}
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
