import { Bar, BarChart, CartesianGrid, Cell, ErrorBar, Legend, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';

import ChartFrame, { ChartTooltip } from './ChartFrame.jsx';
import { COLORS, axisTick } from '../../utils/chartTheme.js';
import { formatByType } from '../../utils/format.js';

const cursor = { fill: 'rgba(22,96,122,0.06)' };
const margin = { top: 10, right: 12, bottom: 0, left: 0 };

/** Vertical bars. bars: [{ key, name, color }]. format: formatByType type for the value axis. */
export function CategoryBar({ data, bars, format = 'amount', height = 260, refLine, ariaLabel, cellColors }) {
  const formats = Object.fromEntries(bars.map((b) => [b.key, format]));
  return (
    <ChartFrame height={height} ariaLabel={ariaLabel} isEmpty={!data?.length}>
      <BarChart data={data} margin={margin}>
        <CartesianGrid stroke={COLORS.grid} vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={{ stroke: COLORS.rule }} tick={axisTick} />
        <YAxis tickLine={false} axisLine={false} tick={axisTick} width={58} tickFormatter={(v) => formatByType(v, format, { compact: true, digits: 0 })} />
        <Tooltip content={<ChartTooltip formats={formats} />} cursor={cursor} />
        {bars.length > 1 && <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} />}
        {refLine && (
          <ReferenceLine y={refLine.value} stroke={COLORS.brick} strokeDasharray="4 3" label={{ value: refLine.label, position: 'insideTopRight', fill: COLORS.brick, fontSize: 11 }} />
        )}
        {bars.map((b) => (
          <Bar key={b.key} dataKey={b.key} name={b.name} fill={b.color || COLORS.primary} radius={[2, 2, 0, 0]} maxBarSize={56}>
            {cellColors && data.map((d, i) => <Cell key={d.name} fill={cellColors(d, i)} />)}
          </Bar>
        ))}
      </BarChart>
    </ChartFrame>
  );
}

/** Frequency bars with 95% interval whiskers and a reference line at the portfolio frequency. */
export function FrequencyCI({ data, portfolio, height = 260, ariaLabel }) {
  return (
    <ChartFrame height={height} ariaLabel={ariaLabel} isEmpty={!data?.length}>
      <BarChart data={data} margin={margin}>
        <CartesianGrid stroke={COLORS.grid} vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={{ stroke: COLORS.rule }} tick={axisTick} />
        <YAxis tickLine={false} axisLine={false} tick={axisTick} width={50} domain={[0, 'auto']} tickFormatter={(v) => formatByType(v, 'percent', { digits: 0 })} />
        <Tooltip
          cursor={cursor}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const row = payload[0].payload;
            return (
              <div className="rounded-panel border border-rule bg-white px-3 py-2 text-xs shadow-sm">
                <p className="mb-1 font-medium text-ink">{label}</p>
                <p className="tabular-nums">Frequency {formatByType(row.frequency, 'percent', { digits: 1 })}</p>
                {row.ciLow != null && <p className="tabular-nums text-muted">95% interval {formatByType(row.ciLow, 'percent')} to {formatByType(row.ciHigh, 'percent')}</p>}
                <p className="tabular-nums text-muted">{formatByType(row.claims, 'integer')} of {formatByType(row.policies, 'integer')} policies</p>
              </div>
            );
          }}
        />
        {portfolio != null && (
          <ReferenceLine y={portfolio} stroke={COLORS.ochre} strokeDasharray="4 3" label={{ value: 'Portfolio', position: 'insideTopRight', fill: COLORS.ochre, fontSize: 11 }} />
        )}
        <Bar dataKey="frequency" name="Claim frequency" fill={COLORS.primary} radius={[2, 2, 0, 0]} maxBarSize={56}>
          <ErrorBar dataKey="ci" width={6} strokeWidth={1.5} stroke={COLORS.ink} />
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}

/** Horizontal bars (used for the sensitivity ranking). */
export function HorizontalBar({ data, dataKey, name, format = 'number', height = 220, ariaLabel }) {
  return (
    <ChartFrame height={height} ariaLabel={ariaLabel} isEmpty={!data?.length}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={COLORS.grid} horizontal={false} />
        <XAxis type="number" tickLine={false} axisLine={{ stroke: COLORS.rule }} tick={axisTick} tickFormatter={(v) => formatByType(v, format, { digits: 0 })} />
        <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} tick={axisTick} width={130} />
        <Tooltip content={<ChartTooltip formats={{ [dataKey]: format }} />} cursor={cursor} />
        <Bar dataKey={dataKey} name={name} fill={COLORS.slate} radius={[0, 2, 2, 0]} maxBarSize={28} />
      </BarChart>
    </ChartFrame>
  );
}
