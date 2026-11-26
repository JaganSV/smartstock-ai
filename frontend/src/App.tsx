import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import { BrowserRouter } from 'react-router';

import AuthProvider from './auth/AuthProvider';
import ApiErrorSnackbarProvider from './components/ApiErrorSnackbar';
import ErrorBoundary from './components/ErrorBoundary';
import AppRoutes from './routes';
import { theme } from './theme/theme';

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <ApiErrorSnackbarProvider>
          <AuthProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </AuthProvider>
        </ApiErrorSnackbarProvider>
      </ErrorBoundary>
    </ThemeProvider>
  );
}
