import type { ApiError } from '../../api/client';

/**
 * The API answers 409 for three different reasons on the dashboard's endpoints:
 * - stale snapshot (``/risk/stockout``): ``details.fields`` lists the mismatched metrics;
 * - no snapshot yet (summary, distribution, top 10): no details;
 * - no sales data (trend): no details.
 */
export function isStale(error: ApiError | null): boolean {
  if (!error || error.status !== 409) return false;
  const details = error.details as { fields?: unknown } | null;
  return Array.isArray(details?.fields);
}

export function isNoSnapshot(error: ApiError | null): boolean {
  return error !== null && error.status === 409 && !isStale(error);
}
