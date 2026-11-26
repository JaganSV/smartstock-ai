import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from 'recharts';

import type { Projection } from '../../../api/types';
import ChartFrame from '../../../components/ChartFrame';
import { formatDate, formatNumber } from '../../../lib/format';

export const NO_STOCKOUT = 'No stockout projected within the lead time';
export const PROJECTION_HEIGHT = 300;

type Point = Projection['points'][number];

function ProjectionTooltip({ active, payload }: TooltipProps<number, string>) {
  const point = payload?.[0]?.payload as Point | undefined;
  if (!active || !point) return null;
  return (
    <Box
      sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider', p: 1, fontSize: 13 }}
    >
      <strong>
        Day {point.day} ({formatDate(point.date)})
      </strong>
      <div>Projected units: {formatNumber(point.projected_units, 2)}</div>
    </Box>
  );
}

/** Dashed / dotted / solid swatch for the text legend (markers never rely on colour alone). */
function Swatch({ dash, color }: { dash?: string; color: string }) {
  return (
    <svg width="28" height="10" aria-hidden="true" style={{ flexShrink: 0 }}>
      <line x1="0" y1="5" x2="28" y2="5" stroke={color} strokeWidth="2" strokeDasharray={dash} />
    </svg>
  );
}

/**
 * Section 5 body (FR-C3): the API's projected stock for day 0..L (BP 7.3) with a zero line, the
 * projected stockout day, each open arrival inside the horizon and the end of the lead time.
 * Every value is the API's; the chart only places them.
 */
export default function ProjectionChart({ projection }: { projection: Projection }) {
  const theme = useTheme();
  const { points, horizon_days: horizon, projected_stockout_day: stockoutDay } = projection;
  const stockoutPoint = points.find((point) => point.day === stockoutDay);
  // Place each arrival on the day whose date matches (a lookup, not date arithmetic).
  const arrivals = projection.open_incoming.map((arrival) => ({
    ...arrival,
    day: points.find((point) => point.date === arrival.expected_arrival_date)?.day,
  }));
  const inHorizon = arrivals.filter((arrival) => arrival.day !== undefined);
  const later = arrivals.filter((arrival) => arrival.day === undefined);

  const stockoutLabel = stockoutPoint
    ? `Projected stockout: Day ${stockoutPoint.day} (${formatDate(stockoutPoint.date)})`
    : null;
  const endLabel = `End of lead time (L = ${horizon} days)`;
  const colors = {
    stockout: theme.palette.error.main,
    arrival: theme.palette.success.main,
    end: theme.palette.text.secondary,
  };

  if (points.length === 0) {
    return <Typography color="text.secondary">No data</Typography>;
  }

  return (
    <Box>
      <Box
        role="img"
        aria-label={`Projected units from day 0 to day ${horizon}. ${stockoutLabel ?? NO_STOCKOUT}.`}
      >
        <ChartFrame height={PROJECTION_HEIGHT}>
          <LineChart data={points} margin={{ top: 28, right: 24, bottom: 24, left: 8 }}>
            <CartesianGrid stroke={theme.palette.divider} vertical={false} />
            <XAxis
              dataKey="day"
              type="number"
              domain={[0, horizon]}
              allowDecimals={false}
              tickCount={Math.min(horizon + 1, 15)}
              tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
              label={{
                value: 'Days after t0',
                position: 'insideBottom',
                offset: -16,
                fill: theme.palette.text.secondary,
              }}
            />
            <YAxis
              tickFormatter={(value: number) => formatNumber(value)}
              tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
              width={64}
              label={{
                value: 'Projected units',
                angle: -90,
                position: 'insideLeft',
                fill: theme.palette.text.secondary,
              }}
            />
            <Tooltip content={ProjectionTooltip} />
            <ReferenceLine
              y={0}
              stroke={theme.palette.text.primary}
              label={{ value: '0 units', position: 'insideBottomLeft', fontSize: 11 }}
            />
            <ReferenceLine
              x={horizon}
              stroke={colors.end}
              strokeWidth={2}
              label={{
                value: endLabel,
                position: 'insideTopRight',
                fontSize: 11,
                fill: colors.end,
              }}
            />
            {inHorizon.map((arrival) => (
              <ReferenceLine
                key={`${arrival.expected_arrival_date}-${arrival.quantity}`}
                x={arrival.day}
                stroke={colors.arrival}
                strokeDasharray="2 3"
                strokeWidth={2}
                label={{
                  value: `Arrival +${formatNumber(arrival.quantity)}`,
                  position: 'insideTopLeft',
                  fontSize: 11,
                  fill: theme.palette.text.primary,
                }}
              />
            ))}
            {stockoutPoint ? (
              <ReferenceLine
                x={stockoutPoint.day}
                stroke={colors.stockout}
                strokeDasharray="6 4"
                strokeWidth={2}
                label={{
                  value: stockoutLabel ?? '',
                  position: 'top',
                  fontSize: 12,
                  fill: theme.palette.text.primary,
                }}
              />
            ) : null}
            <Line
              type="linear"
              dataKey="projected_units"
              name="Projected units"
              stroke={theme.palette.primary.main}
              strokeWidth={2}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartFrame>
      </Box>
      <Box
        component="ul"
        aria-label="Projection markers"
        sx={{ listStyle: 'none', p: 0, m: 0, mt: 1, display: 'grid', gap: 0.5 }}
      >
        {stockoutLabel ? (
          <Box component="li" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Swatch dash="6 4" color={colors.stockout} />
            <Typography variant="body2">{stockoutLabel}</Typography>
          </Box>
        ) : null}
        {inHorizon.map((arrival) => (
          <Box
            component="li"
            key={`legend-${arrival.expected_arrival_date}-${arrival.quantity}`}
            sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <Swatch dash="2 3" color={colors.arrival} />
            <Typography variant="body2">
              Arrival: {formatNumber(arrival.quantity)} units on{' '}
              {formatDate(arrival.expected_arrival_date)} (Day {arrival.day})
            </Typography>
          </Box>
        ))}
        <Box component="li" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Swatch color={colors.end} />
          <Typography variant="body2">{endLabel}</Typography>
        </Box>
        {later.map((arrival) => (
          <Box
            component="li"
            key={`later-${arrival.expected_arrival_date}-${arrival.quantity}`}
            sx={{ pl: 4.5 }}
          >
            <Typography variant="body2" color="text.secondary">
              Later arrival (after the lead time): {formatNumber(arrival.quantity)} units on{' '}
              {formatDate(arrival.expected_arrival_date)}
            </Typography>
          </Box>
        ))}
      </Box>
      {stockoutPoint ? null : (
        <Alert severity="success" variant="outlined" sx={{ mt: 1 }}>
          {NO_STOCKOUT}
        </Alert>
      )}
    </Box>
  );
}
