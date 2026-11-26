import { describe, expect, it } from 'vitest';

import {
  formatDate,
  formatDateTime,
  formatDays,
  formatMoney,
  formatNumber,
  formatPercentRatio,
} from './format';

describe('formatMoney', () => {
  it.each([
    ['89944367.37', '₹8,99,44,367.37'],
    ['0', '₹0.00'],
    ['0.00', '₹0.00'],
    ['-0.00', '₹0.00'],
    ['5', '₹5.00'],
    ['999.9', '₹999.90'],
    ['1000', '₹1,000.00'],
    ['100000', '₹1,00,000.00'],
    ['-1234.5', '-₹1,234.50'],
    ['-10741403.52', '-₹1,07,41,403.52'],
    ['007.10', '₹7.10'],
    ['+12.00', '₹12.00'],
    // Beyond float precision: every digit survives because no float is involved.
    ['123456789012345678901.23', '₹12,34,56,78,90,12,34,56,78,901.23'],
    ['9007199254740993.01', '₹9,00,71,99,25,47,40,993.01'],
    // Extra decimals round half up on the digits.
    ['1.005', '₹1.01'],
    ['1.004', '₹1.00'],
    ['999.995', '₹1,000.00'],
    ['-0.004', '₹0.00'],
  ])('%s -> %s', (input, expected) => {
    expect(formatMoney(input)).toBe(expected);
  });

  it.each([null, undefined, '', 'abc', '1,000.00', '1e5', '12.'])('invalid %s -> dash', (input) => {
    expect(formatMoney(input as string | null | undefined)).toBe('—');
  });
});

describe('formatNumber', () => {
  it('uses en-IN grouping and limits decimals', () => {
    expect(formatNumber(1234567.891)).toBe('12,34,567.89');
    expect(formatNumber(-42)).toBe('-42');
    expect(formatNumber(0)).toBe('0');
    expect(formatNumber(21.53333, 4)).toBe('21.5333');
    expect(formatNumber(3, 1, 1)).toBe('3.0');
  });

  it('gives a dash for null, undefined and NaN', () => {
    expect(formatNumber(null)).toBe('—');
    expect(formatNumber(undefined)).toBe('—');
    expect(formatNumber(Number.NaN)).toBe('—');
  });
});

describe('formatDays', () => {
  it('shows one decimal and "days"', () => {
    expect(formatDays(5.6643)).toBe('5.7 days');
    expect(formatDays(0)).toBe('0.0 days');
    expect(formatDays(1234.56)).toBe('1,234.6 days');
  });

  it('shows "No recent demand" for null', () => {
    expect(formatDays(null)).toBe('No recent demand');
    expect(formatDays(undefined)).toBe('No recent demand');
  });
});

describe('formatPercentRatio', () => {
  it.each([
    [0.25, '+25.0%'],
    [-0.125, '-12.5%'],
    [0, '0.0%'],
    [0.00001, '0.0%'],
    [1.5, '+150.0%'],
    [-1, '-100.0%'],
  ])('%s -> %s', (input, expected) => {
    expect(formatPercentRatio(input)).toBe(expected);
  });

  it('gives a dash for null', () => {
    expect(formatPercentRatio(null)).toBe('—');
  });
});

describe('formatDate', () => {
  it('shows a date-only value as that calendar day', () => {
    expect(formatDate('2026-09-30', 'en-IN')).toBe('30 Sept 2026');
    expect(formatDate('2026-01-01', 'en-US')).toBe('Jan 1, 2026');
  });

  it('formats a timestamp and rejects bad input', () => {
    expect(formatDate('2026-11-25T12:00:00Z', 'en-GB')).toBe('25 Nov 2026');
    expect(formatDate('not a date')).toBe('—');
    expect(formatDate(null)).toBe('—');
  });
});

describe('formatDateTime', () => {
  it('shows the time zone', () => {
    expect(formatDateTime('2026-11-25T16:10:00Z', 'en-IN', 'Asia/Kolkata')).toBe(
      '25 Nov 2026, 21:40 IST',
    );
    expect(formatDateTime('2026-11-25T16:10:00Z', 'en-GB', 'UTC')).toBe('25 Nov 2026, 16:10 UTC');
  });

  it('gives a dash for missing or bad input', () => {
    expect(formatDateTime(undefined)).toBe('—');
    expect(formatDateTime('nope')).toBe('—');
  });
});
