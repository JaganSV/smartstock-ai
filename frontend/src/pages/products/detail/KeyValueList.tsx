import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

export interface KeyValue {
  label: string;
  value: ReactNode;
  /** Short qualifier after the value, e.g. "override". */
  note?: string;
  emphasis?: boolean;
}

/** A ``<dl>`` of label–value pairs in two columns (one on narrow screens). */
export default function KeyValueList({ items, label }: { items: KeyValue[]; label?: string }) {
  return (
    <Box
      component="dl"
      aria-label={label}
      sx={{
        m: 0,
        display: 'grid',
        gap: 1.5,
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' },
      }}
    >
      {items.map((item) => (
        <Box
          key={item.label}
          data-testid={`kv-${item.label}`}
          sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, minWidth: 0 }}
        >
          <Typography component="dt" variant="body2" color="text.secondary">
            {item.label}
          </Typography>
          <Typography
            component="dd"
            variant="body2"
            sx={{ m: 0, fontWeight: item.emphasis ? 700 : 500, textAlign: 'right' }}
          >
            {item.value}
            {item.note ? (
              <Typography
                component="span"
                variant="caption"
                sx={{ ml: 0.75, px: 0.5, border: 1, borderColor: 'divider', borderRadius: 0.5 }}
              >
                {item.note}
              </Typography>
            ) : null}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
