import { useCallback, useEffect, useRef, useState } from 'react';

import { toApiError, type ApiError } from '../api/client';

export interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  /** Fetch again with the same parameters. */
  reload: () => void;
}

/**
 * Runs ``fetcher`` and tracks ``{data, error, loading}``. It fetches again whenever ``key``
 * changes (pass the request parameters, e.g. ``JSON.stringify(filters)``) or ``reload`` is
 * called. The previous request is aborted on a new key, on reload and on unmount, so a slow
 * old response can never overwrite a newer one. ``key = null`` means "not ready yet": nothing
 * is fetched and the state stays loading.
 */
export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  key: string | null,
): ApiState<T> {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<Omit<ApiState<T>, 'reload'>>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    if (key === null) return undefined;
    const controller = new AbortController();
    setState((current) => ({ ...current, loading: true }));
    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false });
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setState({ data: null, error: toApiError(caught), loading: false });
        }
      });
    return () => controller.abort();
  }, [key, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  return { ...state, reload };
}
