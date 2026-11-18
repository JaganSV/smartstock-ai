import { createTheme } from '@mui/material/styles';

/**
 * Semantic surface tokens (BP §10.10). Verified (deterministic) content uses a neutral surface;
 * AI-generated content uses a distinctly tinted surface. Keep the two visually distinct.
 */
export const verified = {
  background: '#f5f5f5',
  border: '#d0d0d0',
  text: '#1f2328',
} as const;

export const aiGenerated = {
  background: '#ede7f6',
  border: '#7c5cd8',
  text: '#2a1a5e',
} as const;

export const theme = createTheme({
  palette: {
    primary: { main: '#0f62fe' },
    background: { default: '#ffffff', paper: '#ffffff' },
  },
  typography: {
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
  },
});
