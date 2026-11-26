import InfoOutlined from '@mui/icons-material/InfoOutlined';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import { useTheme } from '@mui/material/styles';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

interface Props {
  label: string;
  /** An already formatted verified value (see ``lib/format``). Never AI text (BP §10.10). */
  value: string | number | null;
  unit?: string;
  subLabel?: string;
  /** One-line definition shown as a tooltip on the info icon (e.g. the BP §7.4 rule). */
  description?: string;
  loading?: boolean;
}

/** One verified KPI: label, value, optional unit or sub-label and a "Verified" chip. */
export default function KpiTile({
  label,
  value,
  unit,
  subLabel,
  description,
  loading = false,
}: Props) {
  const theme = useTheme();
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-label={label}
      aria-busy={loading || undefined}
      sx={{
        p: 2,
        bgcolor: theme.palette.background.paper,
        borderColor: theme.verified.border,
        minWidth: 0,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
          <Typography variant="body2" color="text.secondary" noWrap>
            {label}
          </Typography>
          {description ? (
            <Tooltip title={description} arrow describeChild>
              <InfoOutlined
                tabIndex={0}
                titleAccess={`About ${label}`}
                sx={{ fontSize: 16, color: 'text.secondary', cursor: 'help' }}
              />
            </Tooltip>
          ) : null}
        </Box>
        <Chip label="Verified" size="small" color="success" variant="outlined" />
      </Box>
      {loading ? (
        <Skeleton variant="text" width="60%" sx={{ fontSize: '2rem' }} data-testid="kpi-skeleton" />
      ) : (
        <Typography
          variant="h2"
          component="p"
          sx={{ mt: 1, color: theme.verified.text, overflowWrap: 'anywhere' }}
        >
          {value ?? '—'}
          {unit ? (
            <Typography component="span" variant="body2" sx={{ ml: 0.5 }} color="text.secondary">
              {unit}
            </Typography>
          ) : null}
        </Typography>
      )}
      {subLabel ? (
        <Typography variant="caption" color="text.secondary">
          {subLabel}
        </Typography>
      ) : null}
    </Paper>
  );
}
