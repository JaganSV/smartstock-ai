import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Skeleton from '@mui/material/Skeleton';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useParams } from 'react-router';

import { getExplanation, getProductDetail, getRiskDetail } from '../../api/endpoints';
import ErrorState from '../../components/ErrorState';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi, type ApiState } from '../../hooks/useApi';
import { useUrlParams } from '../../hooks/useUrlParams';
import EmptySnapshotState from '../dashboard/EmptySnapshotState';
import { isNoSnapshot, isStale } from '../dashboard/snapshotErrors';
import StaleNotice from '../dashboard/StaleNotice';
import NotFound from '../NotFound';
import MetricExplanations from './detail/MetricExplanations';
import ProductHeader from './detail/ProductHeader';
import ProductSalesChart from './detail/ProductSalesChart';
import ProjectionChart from './detail/ProjectionChart';
import RuleTrace from './detail/RuleTrace';
import WarehouseMetrics from './detail/WarehouseMetrics';
import WarehouseTabs from './detail/WarehouseTabs';

export const UNKNOWN_WAREHOUSE_NOTICE =
  'The warehouse in the link is not stocked for this product. Showing the default warehouse.';

function parseId(value: string | null | undefined): number | null {
  return value && /^[1-9]\d*$/.test(value) ? Number(value) : null;
}

/** Sections 4–6: stale notice, error with Retry, skeleton, or the content. */
function sectionBody<T>(
  state: ApiState<T>,
  stale: boolean,
  onRecalculated: () => void,
  render: (data: T) => ReactNode,
  label: string,
  height = 240,
): ReactNode {
  if (stale) return <StaleNotice onRecalculated={onRecalculated} />;
  if (state.error) {
    return (
      <ErrorState error={state.error} title={`Could not load ${label}`} onRetry={state.reload} />
    );
  }
  if (state.loading || !state.data) {
    return (
      <Skeleton
        variant="rounded"
        height={height}
        aria-label={`Loading ${label}`}
        role="progressbar"
      />
    );
  }
  return render(state.data);
}

/**
 * Product detail (FR-C2, FR-C3, FR-B6). Sections fetch on their own: the product (1–3), the
 * selected warehouse's risk detail (4–5) and explanation (6), and sales (7). A stale snapshot
 * (409 with ``details.fields`` on risk or explain) affects sections 4–6 only.
 */
export default function ProductDetail() {
  const productId = parseId(useParams().productId);
  const { params, update } = useUrlParams();
  const [reloadSignal, setReloadSignal] = useState(0);
  const [notice, setNotice] = useState(false);
  const [showExplanations, setShowExplanations] = useState(false);
  const reloadAll = useCallback(() => setReloadSignal((value) => value + 1), []);

  const detail = useApi(
    (signal) => getProductDetail(productId ?? 0, signal),
    productId ? `${productId}-${reloadSignal}` : null,
  );
  const warehouses = detail.data?.warehouses ?? [];
  const rollupCode = detail.data?.rollup?.risk_warehouse_code;
  const defaultRow =
    warehouses.find((row) => row.warehouse_code === rollupCode) ?? warehouses[0] ?? null;
  const rawParam = params.get('warehouse_id');
  const paramId = parseId(rawParam);
  const paramRow = warehouses.find((row) => row.warehouse_id === paramId) ?? null;
  const invalidParam = rawParam !== null && detail.data !== null && paramRow === null;
  const selectedRow = paramRow ?? defaultRow;
  const warehouseId = selectedRow?.warehouse_id ?? null;

  useEffect(() => {
    if (invalidParam) {
      setNotice(true);
      update({ warehouse_id: undefined }, { keepPage: true });
    }
  }, [invalidParam, update]);

  const sectionKey =
    productId && warehouseId && !invalidParam
      ? JSON.stringify({ productId, warehouseId, reloadSignal })
      : null;
  const risk = useApi(
    (signal) => getRiskDetail(productId ?? 0, warehouseId ?? 0, signal),
    sectionKey,
  );
  const explanation = useApi(
    (signal) => getExplanation(productId ?? 0, warehouseId ?? 0, signal),
    sectionKey,
  );
  const stale = isStale(risk.error) || isStale(explanation.error);

  if (productId === null || detail.error?.status === 404) return <NotFound />;
  if (detail.error) {
    return isNoSnapshot(detail.error) ? (
      <EmptySnapshotState onDone={reloadAll} />
    ) : (
      <ErrorState error={detail.error} title="Could not load the product" onRetry={detail.reload} />
    );
  }
  if (detail.loading || !detail.data || !selectedRow) {
    return (
      <Box sx={{ display: 'grid', gap: 2 }} aria-busy="true" aria-label="Loading product">
        <Skeleton variant="text" width={420} sx={{ fontSize: '1.75rem' }} />
        <Skeleton variant="rounded" height={160} />
        <Skeleton variant="rounded" height={320} />
      </Box>
    );
  }

  const { snapshot } = detail.data;
  return (
    <Box sx={{ display: 'grid', gap: 2, minWidth: 0 }}>
      <ProductHeader detail={detail.data} />
      {notice ? (
        <Alert severity="info" onClose={() => setNotice(false)}>
          {UNKNOWN_WAREHOUSE_NOTICE}
        </Alert>
      ) : null}
      <WarehouseTabs
        warehouses={warehouses}
        selected={selectedRow.warehouse_id}
        onChange={(id) => update({ warehouse_id: id }, { keepPage: true })}
      />
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'minmax(0, 3fr) minmax(0, 2fr)' },
          alignItems: 'start',
        }}
      >
        <WarehouseMetrics
          row={selectedRow}
          risk={risk.data}
          explanation={explanation.data}
          snapshot={snapshot}
        />
        <VerifiedDataPanel title="Why this risk class" snapshot={risk.data?.snapshot ?? null}>
          {sectionBody(
            risk,
            stale,
            reloadAll,
            (data) => (
              <RuleTrace risk={data} />
            ),
            'the rule trace',
          )}
        </VerifiedDataPanel>
      </Box>
      <VerifiedDataPanel title="Lead-time projection" snapshot={risk.data?.snapshot ?? null}>
        {sectionBody(
          risk,
          stale,
          reloadAll,
          (data) => (
            <ProjectionChart projection={data.projection} />
          ),
          'the projection',
          340,
        )}
      </VerifiedDataPanel>
      <VerifiedDataPanel
        title="How each number is calculated"
        snapshot={explanation.data?.snapshot ?? null}
        actions={
          <Button
            size="small"
            onClick={() => setShowExplanations((value) => !value)}
            aria-expanded={showExplanations}
            aria-controls="metric-explanations"
            endIcon={showExplanations ? <ExpandLess /> : <ExpandMore />}
          >
            {showExplanations ? 'Hide' : 'Show'} calculations
          </Button>
        }
      >
        <Box id="metric-explanations">
          {stale || showExplanations
            ? sectionBody(
                explanation,
                stale,
                reloadAll,
                (data) => <MetricExplanations explanation={data} />,
                'the calculations',
              )
            : null}
        </Box>
      </VerifiedDataPanel>
      <ProductSalesChart
        productId={productId}
        warehouseId={selectedRow.warehouse_id}
        warehouseCode={selectedRow.warehouse_code}
      />
      {/* P6 adds "Explain with AI" here, beside the verified panels. Nothing visible yet. */}
      <Box component="aside" data-slot="ai-explanation" hidden />
    </Box>
  );
}
