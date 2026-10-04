import { useContext } from 'react';

import { formatByType } from '../utils/format.js';
import { EmptyState, RateMetricValidityContext } from './StateViews.jsx';

/**
 * columns: [{ key, label, type?: 'text'|'integer'|'amount'|'amount2'|'percent'|'number'|'number3'|'p',
 *            render?: (value, row) => node, align?: 'left'|'right' }]
 */
export default function DataTable({ columns, rows, caption, rowKey, dense = false, rateMetricsValid }) {
  const inheritedRateMetricsValid = useContext(RateMetricValidityContext);
  const canShowRateMetrics = rateMetricsValid ?? inheritedRateMetricsValid;
  if (!rows?.length) return <EmptyState minHeight={100}>No rows are available for this selection.</EmptyState>;
  const pad = dense ? 'px-3 py-1.5' : 'px-3 py-2';
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13.5px] tabular-nums">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-rule bg-paper/60">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`${pad} whitespace-nowrap font-medium text-muted ${(c.align || (c.type === 'text' ? 'left' : 'right')) === 'left' ? 'text-left' : 'text-right'}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey ? row[rowKey] : i} className="border-b border-rule/70 last:border-0">
              {columns.map((c) => {
                const left = (c.align || (c.type === 'text' ? 'left' : 'right')) === 'left';
                const value = row[c.key];
                const unavailable = c.rateMetric && !canShowRateMetrics;
                return (
                  <td key={c.key} className={`${pad} ${left ? 'text-left' : 'text-right'} ${c.type === 'text' && c.key === columns[0].key ? 'font-medium' : ''}`}>
                    {unavailable
                      ? <span title="Claim-status or claim-date filters make this rate statistically invalid">Unavailable</span>
                      : c.render ? c.render(value, row) : formatByType(value, c.type || 'text')}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
