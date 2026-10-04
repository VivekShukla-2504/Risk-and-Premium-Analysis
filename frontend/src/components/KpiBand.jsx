import { formatByType, formatPercent } from '../utils/format.js';

const FORMAT_FOR = { integer: 'integer', currency: 'amount', percent: 'percent' };

function extra(kpi, data, rateMetricsValid) {
  if (kpi.rate_metric && !rateMetricsValid) return null;
  const ci = data.confidence_intervals_95;
  const sec = data.secondary_metrics;
  switch (kpi.key) {
    case 'claim_frequency':
      return ci.claim_frequency.low != null ? `95% interval ${formatPercent(ci.claim_frequency.low)} to ${formatPercent(ci.claim_frequency.high)}` : null;
    case 'average_claim_severity':
      return ci.claim_severity.low != null ? `95% interval ${formatByType(ci.claim_severity.low, 'amount')} to ${formatByType(ci.claim_severity.high, 'amount')}` : null;
    case 'loss_ratio':
      return sec.paid_loss_ratio != null ? `Settled claims only: ${formatPercent(sec.paid_loss_ratio)}` : null;
    default:
      return null;
  }
}

export default function KpiBand({ data, meta }) {
  const valid = meta.rate_metrics_valid;
  return (
    <section aria-label="Key figures" className="overflow-hidden rounded-panel border border-rule bg-rule">
      <dl className="grid grid-cols-2 gap-px lg:grid-cols-4">
        {data.kpis.map((kpi) => {
          const stale = kpi.rate_metric && !valid;
          const decimals = kpi.key === 'average_claim_severity' ? 2 : 0;
          const note = extra(kpi, data, valid);
          return (
            <div key={kpi.key} className="min-w-0 bg-panel px-4 py-4 sm:px-5">
              <dt className="text-[13px] text-muted">{kpi.label}</dt>
              <dd
                className={`mt-1.5 truncate font-serif text-[1.65rem] leading-none tabular-nums sm:text-[1.85rem] ${stale ? 'text-muted line-through decoration-ochre' : 'text-ink'}`}
                title={stale ? 'Not meaningful: the current filters select policies by claim outcome.' : undefined}
              >
                {stale ? 'Unavailable' : formatByType(kpi.value, FORMAT_FOR[kpi.format], { decimals })}
              </dd>
              <p className="mt-2 text-xs leading-snug text-muted">
                {stale ? 'Not meaningful with the current filters.' : note || kpi.note}
              </p>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
