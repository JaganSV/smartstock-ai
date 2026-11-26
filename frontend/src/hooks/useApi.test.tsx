import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/client';
import { useApi } from './useApi';

function deferred<T>() {
  let resolve: (value: T) => void = () => {};
  let reject: (reason: unknown) => void = () => {};
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('useApi', () => {
  it('loads data', async () => {
    const fetcher = vi.fn().mockResolvedValue({ n: 1 });
    const { result } = renderHook(() => useApi(fetcher, 'k'));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.data).toEqual({ n: 1 }));
    expect(result.current).toMatchObject({ loading: false, error: null });
  });

  it('turns failures into ApiError', async () => {
    const failure = new ApiError({ status: 500, code: 'X', message: 'Service unavailable.' });
    const { result } = renderHook(() => useApi(vi.fn().mockRejectedValue(failure), 'k'));
    await waitFor(() => expect(result.current.error).toBe(failure));
    expect(result.current.data).toBeNull();
  });

  it('aborts on unmount and ignores the late response', async () => {
    const pending = deferred<string>();
    let seen: AbortSignal | undefined;
    const { result, unmount } = renderHook(() =>
      useApi((signal) => {
        seen = signal;
        return pending.promise;
      }, 'k'),
    );
    unmount();
    expect(seen?.aborted).toBe(true);
    pending.resolve('late');
    await Promise.resolve();
    expect(result.current.data).toBeNull();
  });

  it('aborts the previous request when the key changes', async () => {
    const calls: { signal: AbortSignal; d: ReturnType<typeof deferred<string>> }[] = [];
    const { result, rerender } = renderHook(
      ({ key }) =>
        useApi((signal) => {
          const d = deferred<string>();
          calls.push({ signal, d });
          return d.promise;
        }, key),
      { initialProps: { key: 'a' } },
    );
    rerender({ key: 'b' });
    expect(calls).toHaveLength(2);
    expect(calls[0].signal.aborted).toBe(true);
    expect(calls[1].signal.aborted).toBe(false);
    await act(async () => calls[0].d.resolve('old'));
    expect(result.current.data).toBeNull();
    await act(async () => calls[1].d.resolve('new'));
    expect(result.current.data).toBe('new');
  });

  it('waits while the key is null, then fetches', async () => {
    const fetcher = vi.fn().mockResolvedValue('x');
    const { result, rerender } = renderHook(({ key }) => useApi(fetcher, key), {
      initialProps: { key: null as string | null },
    });
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(true);
    rerender({ key: 'ready' });
    await waitFor(() => expect(result.current.data).toBe('x'));
  });

  it('reload fetches again and aborts the previous request', async () => {
    const signals: AbortSignal[] = [];
    const fetcher = vi.fn((signal: AbortSignal) => {
      signals.push(signal);
      return Promise.resolve(signals.length);
    });
    const { result } = renderHook(() => useApi(fetcher, 'k'));
    await waitFor(() => expect(result.current.data).toBe(1));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.data).toBe(2));
    expect(signals[0].aborted).toBe(true);
  });
});
