import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';

import type { Explanation, RiskDetail, SnapshotMeta, WarehouseMetric } from '../../../api/types';
import VerifiedDataPanel from '../../../components/VerifiedDataPanel';
import { EMPTY, formatDays, formatNumber, formatShare } from '../../../lib/format';
import KeyValueList from './KeyValueList';

/** The verified result of one metric from ``/explain``, or ``undefined`` if unavailable. */
export function explainResult(explanation: Explanation | null, metric: string): unknown {
  return explanation?.metrics.find((item) => item.metric === metric)?.result;
}

function numberOrDash(value: unknown, digits = 0): string {
  return typeof value === 'number' ? formatNumber(value, digits) : EMPTY;
}

interface Props {
  row: WarehouseMetric;
  /** ``/risk/{id}``: the row's lead time. Null while loading, on error or when stale. */
  risk: RiskDetail | null;
  /** ``/explain``: inventory position and demand sigma (not part of the stored row). */
  explanation: Explanation | null;
  snapshot: SnapshotMeta;
}

/**
 * Section 3: the selected warehouse's stored metrics (``GET /products/{id}``). Inventory
 * position and demand sigma are not stored, so they come from the verified ``/explain`` results,
 * and the lead time from ``/risk/{id}``; each shows "—" until those load (or when stale).
 */
export default function WarehouseMetrics({ row, risk, explanation, snapshot }: Props) {
  const policy = row.policy;
  const leadTime = risk?.lead_time_days ?? explainResult(explanation, 'lead_time_days');
  return (
    <VerifiedDataPanel
      title={`Metrics at ${row.warehouse_code}`}
      snapshot={snapshot}
      actions={
        <Stack direction="row" spacing={0.5}>
          {row.is_high_demand ? <Chip label="High demand" size="small" color="info" /> : null}
          {row.is_slow_moving ? (
            <Chip label="Slow-moving" size="small" color="warning" variant="outlined" />
          ) : null}
        </Stack>
      }
    >
      <KeyValueList
        label={`Metrics at ${row.warehouse_code}`}
        items={[
          { label: 'On hand', value: formatNumber(row.on_hand) },
          { label: 'Committed', value: formatNumber(row.committed) },
          { label: 'Available', value: formatNumber(row.available), emphasis: true },
          { label: 'Incoming within lead time', value: formatNumber(row.incoming_in_lt) },
          {
            label: 'Inventory position',
            value: numberOrDash(explainResult(explanation, 'inventory_position')),
          },
          { label: 'ADS 30', value: formatNumber(row.ads_30, 4) },
          { label: 'ADS 90', value: formatNumber(row.ads_90, 4) },
          {
            label: 'Demand σ (30 d)',
            value: numberOrDash(explainResult(explanation, 'demand_std_30'), 4),
          },
          {
            label: 'Lead time',
            value: typeof leadTime === 'number' ? `${formatNumber(leadTime)} days` : EMPTY,
            note: policy?.lead_time_override_days != null ? 'override' : undefined,
          },
          {
            label: 'Safety stock',
            value: formatNumber(row.safety_stock),
            note: policy?.safety_stock_override != null ? 'override' : undefined,
          },
          { label: 'Reorder point', value: formatNumber(row.reorder_point) },
          { label: 'Days of cover', value: formatDays(row.days_of_cover) },
          { label: 'Reorder quantity', value: formatNumber(row.reorder_qty) },
          { label: 'Service level', value: policy ? formatShare(policy.service_level) : EMPTY },
          {
            label: 'Review period',
            value: policy ? `${formatNumber(policy.review_period_days)} days` : EMPTY,
          },
        ]}
      />
    </VerifiedDataPanel>
  );
}
