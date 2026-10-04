import { Cell, Pie, PieChart, Tooltip } from 'recharts';

import ChartFrame, { ChartTooltip } from './ChartFrame.jsx';
import { EmptyState } from '../StateViews.jsx';
import { colorFor } from '../../utils/chartTheme.js';
import { formatByType } from '../../utils/format.js';

/** Donut with a legend table. rows: [{ name, value, share }]; shares are the API's, not recomputed here. */
export default function Donut({ rows, colors = {}, valueLabel = 'Policies', height = 220, ariaLabel }) {
  if (!rows?.length) return <EmptyState minHeight={height}>No observations are available for this chart.</EmptyState>;
  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:gap-6">
      <div className="w-full max-w-[220px] shrink-0">
        <ChartFrame height={height} ariaLabel={ariaLabel}>
          <PieChart>
            <Tooltip content={<ChartTooltip formats={{ value: 'integer' }} />} />
            <Pie data={rows} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="92%" paddingAngle={1} stroke="#fff" strokeWidth={2}>
              {rows.map((r, i) => (
                <Cell key={r.name} fill={colorFor(colors, r.name, i)} />
              ))}
            </Pie>
          </PieChart>
        </ChartFrame>
      </div>
      <table className="w-full text-[13.5px] tabular-nums">
        <thead>
          <tr className="text-muted">
            <th scope="col" className="py-1 text-left font-medium">Group</th>
            <th scope="col" className="py-1 text-right font-medium">{valueLabel}</th>
            <th scope="col" className="py-1 text-right font-medium">Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.name} className="border-t border-rule/70">
              <td className="py-1.5">
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: colorFor(colors, r.name, i) }} aria-hidden="true" />
                {r.name}
              </td>
              <td className="py-1.5 text-right">{formatByType(r.value, 'integer')}</td>
              <td className="py-1.5 text-right">{formatByType(r.share, 'percent')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
