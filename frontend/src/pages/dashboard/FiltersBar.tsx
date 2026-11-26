import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { getCategories, getWarehouses } from '../../api/endpoints';
import type { Category, DashboardFilters, Warehouse } from '../../api/types';
import { useApi } from '../../hooks/useApi';

export const WAREHOUSE_PARAM = 'warehouse_id';
export const CATEGORY_PARAM = 'category_id';
export const UNKNOWN_WAREHOUSE = 'The warehouse in the link was not found. Showing all warehouses.';
export const UNKNOWN_CATEGORY = 'The category in the link was not found. Showing all categories.';

/** A positive integer id from the URL, or ``undefined`` (absent) or ``NaN`` (malformed). */
function parseId(value: string | null): number | undefined {
  if (value === null || value === '') return undefined;
  return /^[1-9]\d*$/.test(value) ? Number(value) : Number.NaN;
}

function known(id: number | undefined, list: { id: number }[] | null): boolean | null {
  if (id === undefined) return true;
  if (Number.isNaN(id)) return false;
  if (list === null) return null; // not loaded (or failed): cannot tell yet
  return list.some((item) => item.id === id);
}

export interface DashboardFilterState {
  filters: DashboardFilters;
  /** Filters are validated (or validation is impossible): sections may fetch. */
  ready: boolean;
  warehouses: Warehouse[];
  categories: Category[];
  notices: string[];
  dismissNotices: () => void;
  setWarehouse: (id: number | undefined) => void;
  setCategory: (id: number | undefined) => void;
  clear: () => void;
}

/**
 * The warehouse and category filters (FR-A4), kept in the URL (``?warehouse_id=&category_id=``)
 * so a reload or a shared link keeps them. An id that is malformed or not in the reference list
 * is removed from the URL and reported as a notice ("All" applies).
 */
export function useDashboardFilters(): DashboardFilterState {
  const [params, setParams] = useSearchParams();
  const warehouses = useApi(getWarehouses, 'warehouses');
  const categories = useApi(getCategories, 'categories');
  const [notices, setNotices] = useState<string[]>([]);

  const rawWarehouse = parseId(params.get(WAREHOUSE_PARAM));
  const rawCategory = parseId(params.get(CATEGORY_PARAM));
  // A failed reference load leaves the list null: filters then pass through as given and the
  // API itself rejects an unknown id (404 per section).
  const warehouseList = warehouses.loading ? null : warehouses.data;
  const categoryList = categories.loading ? null : categories.data;
  const warehouseOk = known(rawWarehouse, warehouseList);
  const categoryOk = known(rawCategory, categoryList);
  const refsSettled = !warehouses.loading && !categories.loading;

  const update = useCallback(
    (changes: Record<string, number | undefined>) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [name, value] of Object.entries(changes)) {
            if (value === undefined) next.delete(name);
            else next.set(name, String(value));
          }
          next.delete('page'); // a new filter starts at page 1 (list pages)
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  useEffect(() => {
    const found: string[] = [];
    const drop: Record<string, undefined> = {};
    if (warehouseOk === false) {
      found.push(UNKNOWN_WAREHOUSE);
      drop[WAREHOUSE_PARAM] = undefined;
    }
    if (categoryOk === false) {
      found.push(UNKNOWN_CATEGORY);
      drop[CATEGORY_PARAM] = undefined;
    }
    if (found.length) {
      setNotices((current) => [...current, ...found.filter((n) => !current.includes(n))]);
      update(drop);
    }
  }, [warehouseOk, categoryOk, update]);

  const filters = useMemo<DashboardFilters>(
    () => ({
      warehouse_id: warehouseOk !== false ? rawWarehouse : undefined,
      category_id: categoryOk !== false ? rawCategory : undefined,
    }),
    [warehouseOk, categoryOk, rawWarehouse, rawCategory],
  );

  return {
    filters,
    ready: refsSettled && warehouseOk !== false && categoryOk !== false,
    warehouses: warehouses.data ?? [],
    categories: categories.data ?? [],
    notices,
    dismissNotices: () => setNotices([]),
    setWarehouse: (id) => update({ [WAREHOUSE_PARAM]: id }),
    setCategory: (id) => update({ [CATEGORY_PARAM]: id }),
    clear: () => update({ [WAREHOUSE_PARAM]: undefined, [CATEGORY_PARAM]: undefined }),
  };
}

/** Warehouse and category selects, active-filter chips and "Clear filters". */
export default function FiltersBar({ state }: { state: DashboardFilterState }) {
  const { filters, warehouses, categories, notices } = state;
  const warehouse = warehouses.find((item) => item.id === filters.warehouse_id);
  const category = categories.find((item) => item.id === filters.category_id);
  const active = warehouse !== undefined || category !== undefined;

  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box
        role="search"
        aria-label="Dashboard filters"
        sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}
      >
        <TextField
          select
          size="small"
          label="Warehouse"
          value={warehouse ? String(warehouse.id) : ''}
          onChange={(event) =>
            state.setWarehouse(event.target.value ? Number(event.target.value) : undefined)
          }
          sx={{ minWidth: 220 }}
          slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
        >
          <MenuItem value="">All warehouses</MenuItem>
          {warehouses.map((item) => (
            <MenuItem key={item.id} value={String(item.id)}>
              {item.code} – {item.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Category"
          value={category ? String(category.id) : ''}
          onChange={(event) =>
            state.setCategory(event.target.value ? Number(event.target.value) : undefined)
          }
          sx={{ minWidth: 220 }}
          slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
        >
          <MenuItem value="">All categories</MenuItem>
          {categories.map((item) => (
            <MenuItem key={item.id} value={String(item.id)}>
              {item.name}
            </MenuItem>
          ))}
        </TextField>
        {warehouse ? (
          <Chip
            label={`Warehouse: ${warehouse.code}`}
            onDelete={() => state.setWarehouse(undefined)}
          />
        ) : null}
        {category ? (
          <Chip
            label={`Category: ${category.name}`}
            onDelete={() => state.setCategory(undefined)}
          />
        ) : null}
        {active ? <Button onClick={state.clear}>Clear filters</Button> : null}
      </Box>
      {notices.length ? (
        <Alert severity="info" onClose={state.dismissNotices}>
          {notices.map((notice) => (
            <div key={notice}>{notice}</div>
          ))}
        </Alert>
      ) : null}
    </Box>
  );
}
