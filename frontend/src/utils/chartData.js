// Reshapes API responses into the rows Recharts expects. These functions only rename and select fields
// (plus geometry for error bars); they never compute actuarial measures.
import { formatInteger } from './format.js';

export function segmentRows(segments = []) {
  return segments.map((s) => ({
    name: s.segment,
    policies: s.policies,
    claims: s.claiming_policies,
    frequency: s.claim_frequency,
    severity: s.claim_severity,
    premium: s.total_premium,
    claimAmount: s.total_claim_amount,
    lossRatio: s.loss_ratio,
    pureAmount: s.pure_premium,
  }));
}

export function monthlyRows(months = []) {
  return months.map((m) => ({
    name: m.month,
    claims: m.claims,
    rate: m.claims_per_100_policy_months,
    exposure: m.exposure_policy_months,
    lowExposure: Boolean(m.low_exposure),
    incurred: m.incurred_amount,
  }));
}

export function statusRows(statuses = []) {
  return statuses.map((s) => ({ name: s.status, value: s.policies, share: s.share_of_policies, amount: s.incurred_amount }));
}

export function tierRows(tiers = []) {
  return tiers.map((t) => ({
    name: t.segment,
    value: t.policies,
    share: t.share_of_policies,
    frequency: t.claim_frequency,
    lossRatio: t.loss_ratio,
  }));
}

// Recharts' ErrorBar takes [distance below, distance above] the bar value.
export function frequencyRows(segments = []) {
  return segments.map((s) => {
    const low = s.ci_95_low ?? s.claim_frequency_ci_low ?? null; // /frequency uses ci_95_*, segment tables use claim_frequency_ci_*
    const high = s.ci_95_high ?? s.claim_frequency_ci_high ?? null;
    const hasCi = low != null && high != null && s.claim_frequency != null;
    return {
      name: s.segment,
      frequency: s.claim_frequency,
      ciLow: low,
      ciHigh: high,
      ci: hasCi ? [s.claim_frequency - low, high - s.claim_frequency] : null,
      policies: s.policies,
      claims: s.claiming_policies,
    };
  });
}

export function scatterRows(points = []) {
  return points.map((p) => ({ x: p.CoverageAmount, y: p.ClaimAmount, premium: p.PremiumAmount, id: p.PolicyNumber, type: p.PolicyType }));
}

export function coverageBandRows(bands = []) {
  return bands.map((b) => ({
    name: b.band,
    coverage: b.average_coverage,
    premium: b.average_premium,
    claimAmount: b.average_claim_amount,
    frequency: b.claim_frequency,
    policies: b.policies,
  }));
}

export function histogramRows(hist = []) {
  return hist.map((h) => ({ name: `${formatInteger(h.from)}-${formatInteger(h.to)}`, claims: h.claims }));
}

export function tornadoRows(items = []) {
  return items.map((t) => ({
    name: t.driver,
    swing: t.swing_percentage_points,
    lossRatioAtMinus: t.loss_ratio_at_minus,
    lossRatioAtPlus: t.loss_ratio_at_plus,
  }));
}

export function scenarioRows(scenarios = []) {
  return scenarios.filter((s) => s.results).map((s) => ({
    key: s.key,
    name: s.label,
    claimCost: s.results.adjusted_expected_claim_cost,
    premium: s.results.adjusted_premium,
    lossRatio: s.results.adjusted_loss_ratio,
    margin: s.results.underwriting_margin,
  }));
}
