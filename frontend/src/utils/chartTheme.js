export const COLORS = {
  ink: '#17212E',
  muted: '#5B6877',
  rule: '#D3DAE2',
  grid: '#E3E8EE',
  primary: '#16607A',
  ochre: '#B98320',
  slate: '#58688A',
  sage: '#6E9A7B',
  brick: '#A24A42',
  neutral: '#9AA6B4',
};

export const SERIES = [COLORS.primary, COLORS.ochre, COLORS.slate, COLORS.sage, COLORS.brick];
export const STATUS_COLORS = { Settled: COLORS.primary, Pending: COLORS.ochre, Rejected: COLORS.neutral };
export const TIER_COLORS = { Low: COLORS.sage, Medium: COLORS.ochre, High: COLORS.brick };
export const SCENARIO_COLORS = { baseline: COLORS.slate, optimistic: COLORS.sage, stress: COLORS.brick, custom: COLORS.primary };
export const axisTick = { fontSize: 12, fill: COLORS.muted };

export const colorFor = (map, name, index) => map[name] || SERIES[index % SERIES.length];
