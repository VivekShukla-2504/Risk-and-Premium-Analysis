// Short sentences built from values the API already computed (no new calculations).
import { formatByType } from './format.js';

export function correlationText(c, what) {
  if (!c || c.pearson_r == null) return `${what}: correlation not available.`;
  const verdict = c.distinguishable_from_zero ? 'a statistically detectable relationship' : 'not distinguishable from zero';
  return `${what}: correlation ${formatByType(c.pearson_r, 'number')} across ${formatByType(c.n, 'integer')} records, ${verdict}.`;
}

export function testSentence(test) {
  if (!test) return '';
  if (!test.computable) return 'Test not computable for this selection.';
  return `p-value ${formatByType(test.p_value, 'p')}: ${test.significant_at_5pct ? 'statistically significant' : 'within random variation'}.`;
}

export function yesNo(flag) {
  if (flag === null || flag === undefined) return 'n/a';
  return flag ? 'Yes' : 'No';
}
