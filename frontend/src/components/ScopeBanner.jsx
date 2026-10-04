import Notice from './Notice.jsx';
import { formatInteger } from '../utils/format.js';

/** Shows how much of the portfolio the current filters select, plus any warnings the API attached. */
export default function ScopeBanner({ state }) {
  const meta = state?.data?.meta;
  if (!meta) return <div className="h-5" aria-hidden="true" />;
  return (
    <div className="space-y-2">
      <p className="text-[13px] text-muted">
        Showing <strong className="font-semibold text-ink">{formatInteger(meta.policies_in_scope)}</strong> of {formatInteger(meta.policies_total)} policies
        with <strong className="font-semibold text-ink">{formatInteger(meta.claims_in_scope)}</strong> claims.
        {meta.valuation_date && <> Premium earned to {meta.valuation_date}.</>}
      </p>
      {meta.warnings.map((w) => (
        <Notice key={w} tone="warning">{w}</Notice>
      ))}
    </div>
  );
}
