import Notice from './Notice.jsx';
import { formatByType } from '../utils/format.js';

/** Presents a statistical-test result exactly as the backend computed it. */
export default function Verdict({ label, test }) {
  if (!test) return null;
  if (!test.computable) {
    return <Notice tone="info" title={label}>Not computable here: {test.reason}.</Notice>;
  }
  return (
    <Notice tone={test.significant_at_5pct ? 'warning' : 'info'} title={label}>
      <p>{test.interpretation}</p>
      <p className="mt-1 text-xs text-muted">
        {test.test}: statistic {formatByType(test.statistic, 'number')}, p-value {formatByType(test.p_value, 'p')}
        {test.approximation_reliable === false && '. Expected counts are small, so treat this approximation with care'}
      </p>
    </Notice>
  );
}
