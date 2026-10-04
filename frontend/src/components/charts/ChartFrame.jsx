import { ResponsiveContainer } from 'recharts';

import { EmptyState } from '../StateViews.jsx';
import { formatByType } from '../../utils/format.js';

export default function ChartFrame({ height = 260, ariaLabel, children, isEmpty = false }) {
  if (isEmpty) return <EmptyState minHeight={height}>No observations are available for this chart.</EmptyState>;
  return (
    <div role="img" aria-label={ariaLabel} style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

/** Shared tooltip. `formats` maps a series dataKey to a formatByType() type. */
export function ChartTooltip({ active, payload, label, formats = {}, labelFormatter }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value !== null && p.value !== undefined);
  return (
    <div className="rounded-panel border border-rule bg-white px-3 py-2 text-xs shadow-sm">
      {(label !== undefined || labelFormatter) && (
        <p className="mb-1 font-medium text-ink">{labelFormatter ? labelFormatter(label, payload) : label}</p>
      )}
      <ul className="space-y-0.5">
        {rows.map((p) => (
          <li key={`${p.dataKey}-${p.name}`} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted">
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: p.color || p.fill || p.stroke }} aria-hidden="true" />
              {p.name}
            </span>
            <span className="tabular-nums text-ink">{formatByType(p.value, formats[p.dataKey] || 'number')}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
