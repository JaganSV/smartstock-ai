import { createTheme } from '@mui/material/styles';

/**
 * Semantic surface tokens (BP §10.10). Verified (deterministic) content uses a neutral surface;
 * AI-generated content uses a distinctly tinted surface. Keep the two visually distinct.
 * Text on each surface passes WCAG AA (checked in theme.test.ts).
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

/** Most severe first, in the BP 7.4 rule order R1-R6 (the backend's ``RiskClass`` order). */
export const RISK_CLASSES = ['STOCKOUT', 'CRITICAL', 'HIGH', 'MEDIUM', 'OVERSTOCK', 'LOW'] as const;
export type RiskClass = (typeof RISK_CLASSES)[number];

/**
 * Risk colours (BP 7.4 classes). Every badge also shows the class name as text, so colour is
 * never the only signal. Each pair passes WCAG AA for normal text (contrast >= 4.5:1):
 *
 * | Class     | Background | Text    | Meaning                          |
 * | --------- | ---------- | ------- | -------------------------------- |
 * | STOCKOUT  | #7f1d1d    | #ffffff | dark red: nothing available      |
 * | CRITICAL  | #b91c1c    | #ffffff | red: out before the lead time    |
 * | HIGH      | #c2410c    | #ffffff | orange: below the reorder point  |
 * | MEDIUM    | #854d0e    | #ffffff | amber-brown: watch               |
 * | LOW       | #166534    | #ffffff | green: healthy                   |
 * | OVERSTOCK | #1e40af    | #ffffff | blue: too much stock             |
 */
export const riskColors: Record<RiskClass, { background: string; text: string }> = {
  STOCKOUT: { background: '#7f1d1d', text: '#ffffff' },
  CRITICAL: { background: '#b91c1c', text: '#ffffff' },
  HIGH: { background: '#c2410c', text: '#ffffff' },
  MEDIUM: { background: '#854d0e', text: '#ffffff' },
  LOW: { background: '#166534', text: '#ffffff' },
  OVERSTOCK: { background: '#1e40af', text: '#ffffff' },
};

declare module '@mui/material/styles' {
  interface Theme {
    verified: typeof verified;
    aiGenerated: typeof aiGenerated;
    risk: typeof riskColors;
  }
  interface ThemeOptions {
    verified?: typeof verified;
    aiGenerated?: typeof aiGenerated;
    risk?: typeof riskColors;
  }
}

export const theme = createTheme({
  palette: {
    primary: { main: '#0f62fe', contrastText: '#ffffff' },
    secondary: { main: '#5b3cc4', contrastText: '#ffffff' },
    error: { main: '#b91c1c' },
    warning: { main: '#854d0e' },
    success: { main: '#166534' },
    text: { primary: '#1f2328', secondary: '#4b5563' },
    background: { default: '#fafafa', paper: '#ffffff' },
  },
  typography: {
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
    h1: { fontSize: '1.75rem', fontWeight: 600 },
    h2: { fontSize: '1.5rem', fontWeight: 600 },
    h3: { fontSize: '1.25rem', fontWeight: 600 },
    h4: { fontSize: '1.125rem', fontWeight: 600 },
    h5: { fontSize: '1rem', fontWeight: 600 },
    h6: { fontSize: '1rem', fontWeight: 600 },
    body1: { fontSize: '0.9375rem' },
    body2: { fontSize: '0.875rem' },
    caption: { fontSize: '0.75rem' },
  },
  verified,
  aiGenerated,
  risk: riskColors,
});
