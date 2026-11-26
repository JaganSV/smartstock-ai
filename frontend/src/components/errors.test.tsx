import { act, fireEvent, render, screen } from '@testing-library/react';
import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { describe, expect, it, vi } from 'vitest';

import { ApiError, responseErrorInterceptor } from '../api/client';
import { renderWithTheme } from '../test/utils';
import ApiErrorSnackbarProvider, { NO_PERMISSION, useApiErrorSnackbar } from './ApiErrorSnackbar';
import ErrorBoundary, { RENDER_FAILED } from './ErrorBoundary';
import ErrorState from './ErrorState';

function forbidden(): AxiosError {
  const config = {
    url: '/analytics/recalculate',
    headers: new AxiosHeaders(),
  } as InternalAxiosRequestConfig;
  const response = {
    status: 403,
    statusText: '',
    data: { error: { code: 'FORBIDDEN', message: 'Forbidden.', request_id: 'r-403' } },
    headers: new AxiosHeaders(),
    config,
  } as AxiosResponse;
  return new AxiosError('x', 'ERR', config, null, response);
}

describe('ErrorState', () => {
  it('shows the message and reference, never a stack', () => {
    const error = new ApiError({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'Invalid request.',
      requestId: 'r-1',
    });
    renderWithTheme(<ErrorState error={error} title="Could not load" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Could not load');
    expect(alert).toHaveTextContent('Invalid request.');
    expect(alert).toHaveTextContent('Reference: r-1');
    expect(alert.textContent).not.toMatch(/at \w+ \(|stack/i);
  });

  it('omits the reference when there is no request id', () => {
    renderWithTheme(
      <ErrorState error={new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' })} />,
    );
    expect(screen.queryByText(/Reference:/)).not.toBeInTheDocument();
  });
});

describe('ApiErrorSnackbarProvider', () => {
  it('shows the permission message on any 403', async () => {
    renderWithTheme(
      <ApiErrorSnackbarProvider>
        <p>page</p>
      </ApiErrorSnackbarProvider>,
    );
    await act(async () => {
      await responseErrorInterceptor(forbidden()).catch(() => undefined);
    });
    expect(await screen.findByText(NO_PERMISSION)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
  });

  it('shows an ApiError with its reference via showError', async () => {
    function Trigger() {
      const { showError } = useApiErrorSnackbar();
      return (
        <>
          <button
            onClick={() =>
              showError(
                new ApiError({
                  status: 409,
                  code: 'CONFLICT',
                  message: 'Run a recalculation.',
                  requestId: 'r-9',
                }),
              )
            }
          >
            api
          </button>
          <button onClick={() => showError('Plain message')}>plain</button>
        </>
      );
    }
    renderWithTheme(
      <ApiErrorSnackbarProvider>
        <Trigger />
      </ApiErrorSnackbarProvider>,
    );
    fireEvent.click(screen.getByText('api'));
    expect(await screen.findByText('Run a recalculation.')).toBeInTheDocument();
    expect(screen.getByText('Reference: r-9')).toBeInTheDocument();
    fireEvent.click(screen.getByText('plain'));
    expect(await screen.findByText('Plain message')).toBeInTheDocument();
  });
});

describe('ErrorBoundary', () => {
  it('shows a safe fallback without the error text', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    // jsdom reports the deliberate throw as an uncaught error; keep the test output clean.
    const quiet = (event: ErrorEvent) => event.preventDefault();
    window.addEventListener('error', quiet);
    function Boom(): never {
      throw new Error('secret internal detail');
    }
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent(RENDER_FAILED);
    expect(screen.queryByText(/secret internal detail/)).not.toBeInTheDocument();
    window.removeEventListener('error', quiet);
    spy.mockRestore();
  });

  it('renders children when nothing fails', () => {
    render(
      <ErrorBoundary>
        <p>fine</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('fine')).toBeInTheDocument();
  });
});
