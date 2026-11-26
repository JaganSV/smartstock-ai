import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithTheme } from '../test/utils';
import { RISK_CLASSES } from '../theme/theme';
import AiNarrativePanel, {
  AI_BLOCKED,
  AI_DISCLAIMER,
  AI_UNAVAILABLE,
  type AiStatus,
} from './AiNarrativePanel';
import KpiTile from './KpiTile';
import RiskBadge from './RiskBadge';
import VerifiedDataPanel from './VerifiedDataPanel';

const SNAPSHOT = {
  snapshot_id: 8,
  calculated_at: '2026-11-25T16:10:00Z',
  data_as_of_date: '2026-09-30',
  verified: true as const,
};

describe('VerifiedDataPanel', () => {
  it('shows the Verified badge with the calculated time and time zone (FR-A5)', () => {
    renderWithTheme(
      <VerifiedDataPanel
        title="Stock position"
        snapshot={SNAPSHOT}
        locale="en-IN"
        timeZone="Asia/Kolkata"
      >
        <span>242 units</span>
      </VerifiedDataPanel>,
    );
    const panel = screen.getByRole('region', { name: 'Stock position' });
    expect(within(panel).getByTestId('verified-badge')).toHaveTextContent(
      'Verified · calculated 25 Nov 2026, 21:40 IST',
    );
    expect(within(panel).getByText('242 units')).toBeInTheDocument();
    expect(within(panel).queryByText(/AI-generated/)).not.toBeInTheDocument();
  });
});

describe('AiNarrativePanel', () => {
  const statuses: AiStatus[] = ['OK', 'UNAVAILABLE', 'BLOCKED', 'LOADING'];

  it.each(statuses)('always shows the disclaimer and disabled feedback (%s)', (status) => {
    renderWithTheme(<AiNarrativePanel status={status} text="Stock is low." />);
    const panel = screen.getByRole('region', { name: 'AI-generated explanation' });
    expect(within(panel).getByText(AI_DISCLAIMER)).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: 'Helpful' })).toBeDisabled();
    expect(within(panel).getByRole('button', { name: 'Not helpful' })).toBeDisabled();
  });

  it('shows the unavailable, blocked and loading states', () => {
    const { rerender } = renderWithTheme(<AiNarrativePanel status="UNAVAILABLE" />);
    expect(screen.getByText(AI_UNAVAILABLE)).toBeInTheDocument();
    rerender(<AiNarrativePanel status="BLOCKED" />);
    expect(screen.getByText(AI_BLOCKED)).toBeInTheDocument();
    rerender(<AiNarrativePanel status="LOADING" />);
    expect(screen.getByLabelText('AI explanation loading')).toHaveAttribute('aria-busy', 'true');
  });

  it('renders AI text as text, with model id and time', () => {
    renderWithTheme(
      <AiNarrativePanel
        status="OK"
        text={'<img src=x onerror="alert(1)"> Reorder soon.'}
        modelId="ibm/granite-3-8b-instruct"
        generatedAt="2026-11-25T16:10:00Z"
        locale="en-IN"
        timeZone="Asia/Kolkata"
      />,
    );
    expect(screen.getByText('<img src=x onerror="alert(1)"> Reorder soon.')).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
    expect(
      screen.getByText('ibm/granite-3-8b-instruct · 25 Nov 2026, 21:40 IST'),
    ).toBeInTheDocument();
  });

  it('enables feedback only when asked and the status is OK', () => {
    const onFeedback = vi.fn();
    renderWithTheme(
      <AiNarrativePanel status="OK" text="x" feedbackEnabled onFeedback={onFeedback} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    fireEvent.click(screen.getByRole('button', { name: 'Not helpful' }));
    expect(onFeedback.mock.calls).toEqual([[true], [false]]);
  });
});

describe('KpiTile', () => {
  it('shows label, value, unit, sub-label and the Verified chip', () => {
    renderWithTheme(
      <KpiTile
        label="Inventory value"
        value="₹8,99,44,367.37"
        unit="INR"
        subLabel="All warehouses"
      />,
    );
    const tile = screen.getByRole('region', { name: 'Inventory value' });
    expect(within(tile).getByText('₹8,99,44,367.37')).toBeInTheDocument();
    expect(within(tile).getByText('INR')).toBeInTheDocument();
    expect(within(tile).getByText('All warehouses')).toBeInTheDocument();
    expect(within(tile).getByText('Verified')).toBeInTheDocument();
  });

  it('shows a skeleton while loading and a dash for null', () => {
    const { rerender } = renderWithTheme(<KpiTile label="Units" value={null} loading />);
    expect(screen.getByTestId('kpi-skeleton')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Units' })).toHaveAttribute('aria-busy', 'true');
    rerender(<KpiTile label="Units" value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('RiskBadge', () => {
  it.each(RISK_CLASSES)('%s has an accessible name and visible text', (risk) => {
    renderWithTheme(<RiskBadge risk={risk} />);
    const badge = screen.getByRole('img', { name: `Risk: ${risk}` });
    expect(badge).toHaveTextContent(risk);
  });
});
