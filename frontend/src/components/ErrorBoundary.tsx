import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import { Component, type ReactNode } from 'react';

export const RENDER_FAILED = 'Something went wrong while showing this page.';

interface State {
  failed: boolean;
}

/**
 * Catches render errors and shows a safe fallback: no stack, no error text. The error is not
 * logged either, since its message could carry user data.
 */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <Alert
        severity="error"
        role="alert"
        sx={{ m: 3 }}
        action={
          <Button color="inherit" size="small" onClick={() => window.location.assign('/')}>
            Reload
          </Button>
        }
      >
        {RENDER_FAILED}
      </Alert>
    );
  }
}
