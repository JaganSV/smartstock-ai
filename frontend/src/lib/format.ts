/**
 * Display formatters. Money arrives from the API as a decimal string (2 dp) and is formatted
 * from the string itself, never through a float, so large values keep every digit.
 *
 * Numbers and money use Indian digit grouping (en-IN: 8,99,44,367.37), matching INR. Dates and
 * times use the user's locale unless a locale is passed (tests pass one to be deterministic).
 */

export const EMPTY = '—';
export const NO_RECENT_DEMAND = 'No recent demand';

const DECIMAL_RE = /^([+-])?(\d+)(?:\.(\d+))?$/;

/** Groups an unsigned digit string the Indian way: last three digits, then pairs. */
function groupIndian(digits: string): string {
  const trimmed = digits.replace(/^0+(?=\d)/, '');
  if (trimmed.length <= 3) return trimmed;
  const head = trimmed.slice(0, -3);
  const tail = trimmed.slice(-3);
  return `${head.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${tail}`;
}

/** Adds one to an unsigned digit string ("199" -> "200"). */
function incrementDigits(digits: string): string {
  const out = digits.split('');
  for (let i = out.length - 1; i >= 0; i -= 1) {
    if (out[i] !== '9') {
      out[i] = String(Number(out[i]) + 1);
      return out.join('');
    }
    out[i] = '0';
  }
  return `1${out.join('')}`;
}

/**
 * "89944367.37" -> "₹8,99,44,367.37"; "-1234.5" -> "-₹1,234.50". More than two decimals are
 * rounded half up on the digits. Null, undefined or a non-decimal string gives "—".
 */
export function formatMoney(value: string | null | undefined): string {
  if (value === null || value === undefined) return EMPTY;
  const match = DECIMAL_RE.exec(value.trim());
  if (!match) return EMPTY;
  const [, sign, intDigits, fracDigits = ''] = match;
  let whole = intDigits;
  let cents = fracDigits.padEnd(2, '0').slice(0, 2);
  if (fracDigits.length > 2 && Number(fracDigits[2]) >= 5) {
    const rounded = incrementDigits(whole + cents);
    whole = rounded.slice(0, -2) || '0';
    cents = rounded.slice(-2);
  }
  const grouped = groupIndian(whole);
  const isZero = /^0+$/.test(whole) && cents === '00';
  return `${sign === '-' && !isZero ? '-' : ''}₹${grouped}.${cents}`;
}

/** en-IN number with at most ``maxFractionDigits`` decimals. Null gives "—". */
export function formatNumber(
  value: number | null | undefined,
  maxFractionDigits = 2,
  minFractionDigits = 0,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: maxFractionDigits,
    minimumFractionDigits: minFractionDigits,
  }).format(value);
}

/** Days of cover: one decimal and "days"; null (no recent demand, BP 7.2) gives that text. */
export function formatDays(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_RECENT_DEMAND;
  return `${formatNumber(value, 1, 1)} days`;
}

/** A ratio as a signed percentage: 0.25 -> "+25.0%", -0.125 -> "-12.5%", 0 -> "0.0%". */
export function formatPercentRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  const percent = formatNumber(Math.abs(value) * 100, 1, 1);
  if (percent === '0.0') return '0.0%';
  return `${value > 0 ? '+' : '-'}${percent}%`;
}

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * An ISO date ("2026-09-30") or timestamp as a locale date ("30 Sept 2026" in en-IN). A date-only
 * value is shown as that calendar day in every time zone.
 */
export function formatDate(iso: string | null | undefined, locale?: string): string {
  if (!iso) return EMPTY;
  const dateOnly = DATE_ONLY_RE.test(iso);
  const date = new Date(dateOnly ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(date.getTime())) return EMPTY;
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(dateOnly ? { timeZone: 'UTC' } : {}),
  }).format(date);
}

/**
 * An ISO timestamp with the time zone shown: "25 Nov 2026, 21:40 IST" (en-IN, Asia/Kolkata).
 * ``timeZone`` defaults to the user's own.
 */
export function formatDateTime(
  iso: string | null | undefined,
  locale?: string,
  timeZone?: string,
): string {
  if (!iso) return EMPTY;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return EMPTY;
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZoneName: 'short',
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}
