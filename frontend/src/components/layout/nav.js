export const NAV = [
  { to: '/', label: 'Dashboard', title: 'Portfolio dashboard', description: 'Headline figures and charts for the selected part of the portfolio.', filters: true, exportable: true },
  { to: '/portfolio', label: 'Portfolio analytics', title: 'Portfolio analytics', description: 'Frequency, severity, pure premium and loss ratio by policy type, age band and gender, with significance tests.', filters: true, exportable: true },
  { to: '/claims', label: 'Claims analytics', title: 'Claims analytics', description: 'Claim status, coverage versus claim size, severity distribution and loss ratio drivers.', filters: true, exportable: true },
  { to: '/risk', label: 'Risk segmentation', title: 'Risk segmentation', description: 'Rule-based risk tiers, tested against what actually happened.', filters: true, exportable: true },
  { to: '/scenario', label: 'Scenario analysis', title: 'Scenario analysis', description: 'See how changes in frequency, severity, inflation and premium move the loss ratio.', filters: true, exportable: false },
  { to: '/rate-indication', label: 'Rate indication', title: 'Rate adequacy indication', description: 'Compare baseline experience with current earned premium at a selected target loss ratio.', filters: true, exportable: false },
  { to: '/methodology', label: 'Methodology', title: 'Methodology and assumptions', description: 'Formulas, assumptions, limitations and data-quality findings behind every figure.', filters: false, exportable: false },
];
