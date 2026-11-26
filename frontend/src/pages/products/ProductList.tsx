import ClearIcon from '@mui/icons-material/Clear';
import SearchIcon from '@mui/icons-material/Search';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import Link from '@mui/material/Link';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router';

import { getProducts, getSuppliers } from '../../api/endpoints';
import type { ProductSummary } from '../../api/types';
import DataTable, { type Column, type SortOrder } from '../../components/DataTable';
import ErrorState from '../../components/ErrorState';
import RiskBadge from '../../components/RiskBadge';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi } from '../../hooks/useApi';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { usePageParams, useUrlParams } from '../../hooks/useUrlParams';
import { formatDays, formatMoney, formatNumber } from '../../lib/format';
import { RISK_CLASSES, type RiskClass } from '../../theme/theme';
import EmptySnapshotState from '../dashboard/EmptySnapshotState';
import FiltersBar, { useDashboardFilters } from '../dashboard/FiltersBar';
import { isNoSnapshot } from '../dashboard/snapshotErrors';

export const PAGE_SIZES = [25, 50, 100];
export const SEARCH_DEBOUNCE_MS = 300;
export const MAX_QUERY = 50;
export const SORT_KEYS = ['sku', 'name', 'risk', 'days_of_cover'] as const;
type SortKey = (typeof SORT_KEYS)[number];
export const UNKNOWN_SUPPLIER = 'The supplier in the link was not found. Showing all suppliers.';

function Flags({ row }: { row: ProductSummary }) {
  return (
    <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
      {row.is_dead_stock ? (
        <Chip label="Dead stock" size="small" color="error" variant="outlined" />
      ) : null}
      {row.is_slow_moving && !row.is_dead_stock ? (
        <Chip label="Slow-moving" size="small" color="warning" variant="outlined" />
      ) : null}
      {row.is_high_demand ? <Chip label="High demand" size="small" color="info" /> : null}
    </Stack>
  );
}

export const COLUMNS: Column<ProductSummary>[] = [
  {
    id: 'sku',
    header: 'SKU',
    sortKey: 'sku',
    nowrap: true,
    render: (row) => (
      <Link component={RouterLink} to={`/products/${row.product_id}`} underline="hover">
        {row.sku}
      </Link>
    ),
  },
  { id: 'name', header: 'Name', sortKey: 'name', render: (row) => row.name },
  { id: 'category', header: 'Category', render: (row) => row.category_code, nowrap: true },
  { id: 'supplier', header: 'Supplier', render: (row) => row.supplier_code, nowrap: true },
  {
    id: 'risk',
    header: 'Risk',
    sortKey: 'risk',
    render: (row) => (
      <Stack spacing={0.25} sx={{ alignItems: 'flex-start' }}>
        <RiskBadge risk={row.risk_class} />
        <Typography variant="caption" color="text.secondary" noWrap>
          {row.risk_warehouse_code}
        </Typography>
      </Stack>
    ),
  },
  { id: 'onhand', header: 'On hand', render: (row) => formatNumber(row.on_hand), align: 'right' },
  {
    id: 'available',
    header: 'Available',
    render: (row) => formatNumber(row.available),
    align: 'right',
  },
  {
    id: 'cover',
    header: 'Days of cover',
    sortKey: 'days_of_cover',
    render: (row) => formatDays(row.days_of_cover),
    align: 'right',
  },
  {
    id: 'value',
    header: 'Inventory value',
    render: (row) => formatMoney(row.inventory_value),
    align: 'right',
    nowrap: true,
  },
  { id: 'flags', header: 'Flags', render: (row) => <Flags row={row} /> },
];

/** Search box: local text, written to ``?q=`` once typing pauses (one request per pause). */
function SearchBox({ value, onSearch }: { value: string; onSearch: (q: string) => void }) {
  const [text, setText] = useState(value);
  const debounced = useDebouncedValue(text.trim(), SEARCH_DEBOUNCE_MS);
  // The last query sent: a search fires only when the debounced text differs from it, so a
  // re-render (or a pending debounce after "Clear") never repeats or undoes a search.
  const lastSent = useRef(value);
  useEffect(() => {
    if (debounced !== lastSent.current) {
      lastSent.current = debounced;
      onSearch(debounced);
    }
  }, [debounced, onSearch]);
  return (
    <TextField
      size="small"
      label="Search SKU or name"
      value={text}
      onChange={(event) => setText(event.target.value)}
      sx={{ minWidth: 280 }}
      slotProps={{
        htmlInput: { maxLength: MAX_QUERY },
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
          endAdornment: text ? (
            <InputAdornment position="end">
              <IconButton
                size="small"
                aria-label="Clear search"
                onClick={() => {
                  setText('');
                  lastSent.current = '';
                  onSearch('');
                }}
              >
                <ClearIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : null,
        },
      }}
    />
  );
}

/**
 * Product catalogue (#8): search, filters, sort and page all in the URL. Rows are the API's
 * roll-up per product; nothing is computed here.
 */
export default function ProductList() {
  const filterState = useDashboardFilters();
  const { filters, ready } = filterState;
  const { params, update } = useUrlParams();
  const { page, pageSize, setPage, setPageSize } = usePageParams(PAGE_SIZES);
  const suppliers = useApi(getSuppliers, 'suppliers');
  const [supplierNotice, setSupplierNotice] = useState(false);

  const q = (params.get('q') ?? '').slice(0, MAX_QUERY);
  const risks = params
    .getAll('risk_class')
    .filter((value): value is RiskClass => (RISK_CLASSES as readonly string[]).includes(value));
  const riskKey = risks.join(',');
  const slowOnly = params.get('slow_moving') === 'true';
  const rawSort = params.get('sort');
  const sort: SortKey = (SORT_KEYS as readonly string[]).includes(rawSort ?? '')
    ? (rawSort as SortKey)
    : 'sku';
  const order: SortOrder = params.get('order') === 'desc' ? 'desc' : 'asc';
  const rawSupplier = params.get('supplier_id');
  const supplierId =
    rawSupplier && /^[1-9]\d*$/.test(rawSupplier) ? Number(rawSupplier) : undefined;
  const supplierKnown =
    supplierId === undefined ||
    suppliers.data === null ||
    suppliers.data.some((item) => item.id === supplierId);
  const malformedSupplier = rawSupplier !== null && supplierId === undefined;

  useEffect(() => {
    if (malformedSupplier || (!suppliers.loading && !supplierKnown)) {
      setSupplierNotice(true);
      update({ supplier_id: undefined });
    }
  }, [malformedSupplier, supplierKnown, suppliers.loading, update]);

  const query = useMemo(
    () => ({
      ...filters,
      supplier_id: supplierKnown ? supplierId : undefined,
      risk_class: riskKey ? (riskKey.split(',') as RiskClass[]) : undefined,
      slow_moving: slowOnly ? true : undefined,
      q: q || undefined,
      sort,
      order,
      page,
      page_size: pageSize,
    }),
    [filters, supplierKnown, supplierId, riskKey, slowOnly, q, sort, order, page, pageSize],
  );
  const canFetch = ready && !suppliers.loading && !malformedSupplier && supplierKnown;
  const { data, error, loading, reload } = useApi(
    (signal) => getProducts(query, signal),
    canFetch ? JSON.stringify(query) : null,
  );

  const onSearch = useCallback((next: string) => update({ q: next || undefined }), [update]);

  const toggleRisk = (risk: RiskClass) => {
    const next = risks.includes(risk) ? risks.filter((r) => r !== risk) : [...risks, risk];
    // Keep the API's severity order in the URL, whatever the click order.
    update({ risk_class: RISK_CLASSES.filter((r) => next.includes(r)) });
  };

  let body;
  if (isNoSnapshot(error)) {
    body = <EmptySnapshotState onDone={reload} />;
  } else if (error) {
    body = <ErrorState error={error} title="Could not load products" onRetry={reload} />;
  } else {
    body = (
      <DataTable
        caption="Products rolled up across the selected warehouses"
        columns={COLUMNS}
        rows={data?.items ?? []}
        getRowId={(row) => row.product_id}
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        pageSizeOptions={PAGE_SIZES}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        sort={sort}
        order={order}
        onSortChange={(nextSort, nextOrder) => update({ sort: nextSort, order: nextOrder })}
        loading={loading || !canFetch}
        emptyMessage="No products match these filters."
      />
    );
  }

  return (
    <Box sx={{ display: 'grid', gap: 2, minWidth: 0 }}>
      <Typography variant="h1">Products</Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
        <SearchBox value={q} onSearch={onSearch} />
        <TextField
          select
          size="small"
          label="Supplier"
          value={supplierKnown && supplierId ? String(supplierId) : ''}
          onChange={(event) =>
            update({ supplier_id: event.target.value ? Number(event.target.value) : undefined })
          }
          sx={{ minWidth: 220 }}
          slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
        >
          <MenuItem value="">All suppliers</MenuItem>
          {(suppliers.data ?? []).map((item) => (
            <MenuItem key={item.id} value={String(item.id)}>
              {item.code} – {item.name}
            </MenuItem>
          ))}
        </TextField>
        <FormControlLabel
          control={
            <Switch
              checked={slowOnly}
              onChange={(event) => update({ slow_moving: event.target.checked || undefined })}
            />
          }
          label="Slow-moving only"
        />
      </Box>
      <FiltersBar state={filterState} />
      <Box
        role="group"
        aria-label="Risk class filter"
        sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}
      >
        <Typography variant="body2" color="text.secondary">
          Risk class:
        </Typography>
        {RISK_CLASSES.map((risk) => (
          <Chip
            key={risk}
            label={risk}
            size="small"
            clickable
            color={risks.includes(risk) ? 'primary' : 'default'}
            variant={risks.includes(risk) ? 'filled' : 'outlined'}
            aria-pressed={risks.includes(risk)}
            onClick={() => toggleRisk(risk)}
          />
        ))}
      </Box>
      {supplierNotice ? (
        <Alert severity="info" onClose={() => setSupplierNotice(false)}>
          {UNKNOWN_SUPPLIER}
        </Alert>
      ) : null}
      <VerifiedDataPanel title="Product catalogue" snapshot={data?.snapshot ?? null}>
        {body}
      </VerifiedDataPanel>
    </Box>
  );
}
