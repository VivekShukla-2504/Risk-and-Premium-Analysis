import { CartesianGrid, Line, LineChart, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';

import ChartFrame, { ChartTooltip } from './ChartFrame.jsx';
import { COLORS, axisTick } from '../../utils/chartTheme.js';
import { formatByType } from '../../utils/format.js';

const compactAmount = (v) => formatByType(v, 'amount', { compact: true });

/** Sampled claims: claim amount against policy coverage. */
export function ClaimScatter({ data, height = 280 }) {
  return (
    <ChartFrame height={height} ariaLabel="Scatter plot of claim amount against coverage" isEmpty={!data?.length}>
      <ScatterChart margin={{ top: 10, right: 16, bottom: 16, left: 0 }}>
        <CartesianGrid stroke={COLORS.grid} />
        <XAxis type="number" dataKey="x" name="Coverage" tickLine={false} axisLine={{ stroke: COLORS.rule }} tick={axisTick} tickFormatter={compactAmount} domain={['dataMin', 'dataMax']} label={{ value: 'Coverage amount', position: 'insideBottom', offset: -10, fill: COLORS.muted, fontSize: 12 }} />
        <YAxis type="number" dataKey="y" name="Claim amount" tickLine={false} axisLine={false} tick={axisTick} width={56} tickFormatter={compactAmount} />
        <ZAxis range={[22, 22]} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<ChartTooltip formats={{ x: 'amount', y: 'amount' }} />} />
        <Scatter data={data} name="Claims" fill={COLORS.primary} fillOpacity={0.45} />
      </ScatterChart>
    </ChartFrame>
  );
}

/** Average premium (and optionally average claim) by coverage band, plotted against average coverage. */
export function CoverageLine({ data, lines, height = 280 }) {
  return (
    <ChartFrame height={height} ariaLabel="Average premium by coverage band" isEmpty={!data?.length}>
      <LineChart data={data} margin={{ top: 10, right: 16, bottom: 16, left: 0 }}>
        <CartesianGrid stroke={COLORS.grid} />
        <XAxis type="number" dataKey="coverage" domain={['dataMin', 'dataMax']} tickLine={false} axisLine={{ stroke: COLORS.rule }} tick={axisTick} tickFormatter={compactAmount} label={{ value: 'Average coverage in band', position: 'insideBottom', offset: -10, fill: COLORS.muted, fontSize: 12 }} />
        <YAxis tickLine={false} axisLine={false} tick={axisTick} width={52} domain={[0, 'auto']} tickFormatter={compactAmount} />
        <Tooltip content={<ChartTooltip formats={Object.fromEntries(lines.map((l) => [l.key, 'amount']))} labelFormatter={(v) => `Coverage ${formatByType(v, 'amount')}`} />} />
        {lines.map((l) => (
          <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color || COLORS.primary} strokeWidth={2} dot={{ r: 3 }} />
        ))}
      </LineChart>
    </ChartFrame>
  );
}
