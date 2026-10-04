import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, Tooltip, XAxis, YAxis } from 'recharts';

import ChartFrame, { ChartTooltip } from './ChartFrame.jsx';
import { RateMetricUnavailable } from '../StateViews.jsx';
import { COLORS, axisTick } from '../../utils/chartTheme.js';
import { formatByType, formatMonth } from '../../utils/format.js';

/** Raw monthly claim counts (bars) with the exposure-adjusted rate (line). Faded bars = months with little exposure. */
export default function MonthlyChart({ data, height = 300, rateMetricsValid = true }) {
  return (
    <div>
    <ChartFrame height={height} ariaLabel={rateMetricsValid ? 'Monthly claims and claims per 100 policy-months' : 'Monthly claim counts'} isEmpty={!data?.length}>
      <ComposedChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={COLORS.grid} vertical={false} />
        <XAxis dataKey="name" tickFormatter={formatMonth} tickLine={false} axisLine={{ stroke: COLORS.rule }} tick={axisTick} minTickGap={14} />
        <YAxis yAxisId="left" tickLine={false} axisLine={false} tick={axisTick} width={46} tickFormatter={(v) => formatByType(v, 'integer')} />
        {rateMetricsValid && <YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} tick={axisTick} width={40} tickFormatter={(v) => formatByType(v, 'number', { digits: 0 })} />}
        <Tooltip content={<ChartTooltip formats={{ claims: 'integer', rate: 'number' }} labelFormatter={formatMonth} />} cursor={{ fill: 'rgba(22,96,122,0.06)' }} />
        <Legend iconType="square" wrapperStyle={{ fontSize: 12, width: '100%' }} />
        <Bar yAxisId="left" dataKey="claims" name="Claims (count)" fill={COLORS.primary} maxBarSize={26} radius={[2, 2, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.name} fill={COLORS.primary} fillOpacity={d.lowExposure ? 0.3 : 1} />
          ))}
        </Bar>
        {rateMetricsValid && <Line yAxisId="right" type="monotone" dataKey="rate" name="Claims per 100 policy-months" stroke={COLORS.ochre} strokeWidth={2} dot={{ r: 2.5 }} connectNulls={false} />}
      </ComposedChart>
    </ChartFrame>
    {!rateMetricsValid && <RateMetricUnavailable />}
    </div>
  );
}
