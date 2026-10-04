// Display formatting only. No actuarial calculation happens in the frontend: every figure comes from the API.

const EMPTY = 'n/a';
const isMissing = (v) => v === null || v === undefined || Number.isNaN(v);

const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 });

export function formatInteger(v) {
  return isMissing(v) ? EMPTY : int.format(v);
}

// The dataset does not state a currency, so amounts are shown as plain numbers.
export function formatAmount(v, { decimals = 0, compact: useCompact = false } = {}) {
  if (isMissing(v)) return EMPTY;
  if (useCompact) return compact.format(v);
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(v);
}

export function formatNumber(v, digits = 2) {
  if (isMissing(v)) return EMPTY;
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);
}

// The API returns ratios (0.5646); show them as percentages.
export function formatPercent(v, digits = 1) {
  if (isMissing(v)) return EMPTY;
  return `${new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v * 100)}%`;
}

// Percentage-point or already-percent values (the API's "percent" fields, e.g. +13.3).
export function formatSignedPercent(v, digits = 1) {
  if (isMissing(v)) return EMPTY;
  const s = new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(v));
  return `${v > 0 ? '+' : v < 0 ? '-' : ''}${s}%`;
}

// Percentage points, e.g. +103.6 pts (the API already returns the difference in points)
export function formatPoints(v, digits = 1) {
  if (isMissing(v)) return EMPTY;
  const s = new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(v));
  return `${v > 0 ? '+' : v < 0 ? '-' : ''}${s} pts`;
}

export function formatPValue(p) {
  if (isMissing(p)) return EMPTY;
  return p < 0.001 ? '<0.001' : p.toFixed(3);
}

export function formatByType(v, type = 'number', opts = {}) {
  switch (type) {
    case 'integer':
      return opts.compact && !isMissing(v) ? compact.format(v) : formatInteger(v);
    case 'amount':
    case 'currency':
      return formatAmount(v, { decimals: opts.decimals ?? 0, compact: opts.compact });
    case 'amount2':
      return formatAmount(v, { decimals: 2, compact: opts.compact });
    case 'percent':
      return formatPercent(v, opts.digits ?? 1);
    case 'p':
      return formatPValue(v);
    case 'text':
      return isMissing(v) ? EMPTY : String(v);
    case 'number3':
      return formatNumber(v, 3);
    default:
      return formatNumber(v, opts.digits ?? 2);
  }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
// "2024-03" -> "Mar 24"
export function formatMonth(ym) {
  const m = /^(\d{4})-(\d{2})$/.exec(ym || '');
  if (!m) return ym ?? EMPTY;
  return `${MONTHS[Number(m[2]) - 1]} ${m[1].slice(2)}`;
}
