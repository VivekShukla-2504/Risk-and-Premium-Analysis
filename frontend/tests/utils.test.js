import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatAmount, formatByType, formatPoints, formatInteger, formatMonth, formatNumber, formatPercent, formatPValue, formatSignedPercent,
} from '../src/utils/format.js';
import { EMPTY_FILTERS, countActiveFilters, filtersToBody, filtersToParams, validateFilters } from '../src/utils/params.js';
import { ApiError, normalizeApiError, parseContentDisposition } from '../src/utils/errors.js';
import { correlationText, testSentence, yesNo } from '../src/utils/describe.js';
import {
  coverageBandRows, frequencyRows, histogramRows, monthlyRows, scenarioRows, scatterRows, segmentRows, statusRows, tierRows, tornadoRows,
} from '../src/utils/chartData.js';

test('formatters render API values and handle missing data', () => {
  assert.equal(formatInteger(10000), '10,000');
  assert.equal(formatInteger(null), 'n/a');
  assert.equal(formatAmount(5974060.08), '5,974,060');
  assert.equal(formatAmount(2994.03, { decimals: 2 }), '2,994.03');
  assert.equal(formatAmount(16904295.27, { compact: true }), '16.9M');
  assert.equal(formatPercent(0.5646), '56.5%');
  assert.equal(formatPercent(2.8298, 1), '283.0%');
  assert.equal(formatPercent(undefined), 'n/a');
  assert.equal(formatNumber(0.5, 3), '0.500');
  assert.equal(formatSignedPercent(13.3), '+13.3%');
  assert.equal(formatSignedPercent(-4.25, 2), '-4.25%');
  assert.equal(formatSignedPercent(0), '0.0%');
  assert.equal(formatPValue(0.1751), '0.175');
  assert.equal(formatPValue(0.00001), '<0.001');
  assert.equal(formatMonth('2024-03'), 'Mar 24');
  assert.equal(formatMonth('bad'), 'bad');
});

test('formatByType dispatches on the type name', () => {
  assert.equal(formatByType(0.25, 'percent'), '25.0%');
  assert.equal(formatByType(1234.5, 'amount2'), '1,234.50');
  assert.equal(formatByType(1234.5, 'amount'), '1,235');
  assert.equal(formatByType(7, 'integer'), '7');
  assert.equal(formatByType(0.0123, 'p'), '0.012');
  assert.equal(formatByType('Auto', 'text'), 'Auto');
  assert.equal(formatByType(1.23456, 'number3'), '1.235');
});

test('filters become query params without empty values', () => {
  assert.deepEqual(filtersToParams(EMPTY_FILTERS), {});
  assert.deepEqual(filtersToParams({ ...EMPTY_FILTERS, policy_type: 'Auto', gender: '' }), { policy_type: 'Auto' });
  // date_basis only travels with a date range
  assert.deepEqual(filtersToParams({ ...EMPTY_FILTERS, date_basis: 'claim_date' }), {});
  assert.deepEqual(
    filtersToParams({ ...EMPTY_FILTERS, start_date: '2024-01-01', date_basis: 'claim_date' }),
    { start_date: '2024-01-01', date_basis: 'claim_date' },
  );
  assert.equal(filtersToBody(EMPTY_FILTERS), null);
  assert.deepEqual(filtersToBody({ ...EMPTY_FILTERS, age_band: '26-35' }), { age_band: '26-35' });
  assert.equal(countActiveFilters({ ...EMPTY_FILTERS, policy_type: 'Auto', end_date: '2024-02-01' }), 2);
});

test('date range validation', () => {
  assert.equal(validateFilters({ start_date: '2024-02-01', end_date: '2024-01-01' }), 'Start date must be on or before end date.');
  assert.equal(validateFilters({ start_date: '2024-01-01', end_date: '2024-01-01' }), null);
  assert.equal(validateFilters({ start_date: '2024-01-01' }), null);
});

test('API errors are normalised into readable messages', () => {
  const net = normalizeApiError(new Error('Network Error'), 'http://localhost:8000/api');
  assert.match(net.message, /Cannot reach the API at http:\/\/localhost:8000\/api/);

  const v422 = normalizeApiError({ response: { status: 422, data: { detail: "Invalid policy_type 'Boat'. Allowed values: ['Auto']" } } });
  assert.equal(v422.status, 422);
  assert.match(v422.message, /Invalid policy_type/);

  const pyd = normalizeApiError({
    response: { status: 422, data: { detail: [{ loc: ['body', 'frequency_change_pct'], msg: 'Input should be less than or equal to 20' }] } },
  });
  assert.equal(pyd.message, 'frequency_change_pct: Input should be less than or equal to 20');

  assert.equal(normalizeApiError({ response: { status: 503, data: {} } }).message, 'The data source is unavailable.');
  assert.match(normalizeApiError({ response: { status: 500, data: {} } }).message, /server hit an error/);
  assert.equal(normalizeApiError({ code: 'ERR_CANCELED' }).canceled, true);
  assert.match(normalizeApiError({ code: 'ECONNABORTED' }).message, /timed out/);
  const e = new ApiError('x');
  assert.equal(normalizeApiError(e), e);
});

test('content-disposition filename parsing', () => {
  assert.equal(parseContentDisposition('attachment; filename="insurance_policy_types_20261003.csv"'), 'insurance_policy_types_20261003.csv');
  assert.equal(parseContentDisposition('attachment; filename=report.json'), 'report.json');
  assert.equal(parseContentDisposition(null), null);
});

test('chart mappers select API fields without computing metrics', () => {
  const seg = [{ segment: 'Auto', policies: 10, claiming_policies: 5, claim_frequency: 0.5, claim_severity: 100, total_premium: 1000, total_claim_amount: 500, loss_ratio: 0.5, pure_premium: 50 }];
  assert.deepEqual(segmentRows(seg), [{ name: 'Auto', policies: 10, claims: 5, frequency: 0.5, severity: 100, premium: 1000, claimAmount: 500, lossRatio: 0.5, pureAmount: 50 }]);
  assert.deepEqual(segmentRows(undefined), []);

  const m = monthlyRows([{ month: '2024-03', claims: 4, claims_per_100_policy_months: 4.5, exposure_policy_months: 90, low_exposure: false, incurred_amount: 12 }]);
  assert.deepEqual(m[0], { name: '2024-03', claims: 4, rate: 4.5, exposure: 90, lowExposure: false, incurred: 12 });

  assert.deepEqual(statusRows([{ status: 'Settled', policies: 3, share_of_policies: 0.3, incurred_amount: 9 }]), [{ name: 'Settled', value: 3, share: 0.3, amount: 9 }]);
  assert.equal(tierRows([{ segment: 'Low', policies: 5, share_of_policies: 0.5, claim_frequency: 0.4, loss_ratio: 1 }])[0].share, 0.5);

  const f = frequencyRows([
    { segment: 'A', claim_frequency: 0.5, ci_95_low: 0.45, ci_95_high: 0.56, policies: 10, claiming_policies: 5 },
    { segment: 'B', claim_frequency: null, ci_95_low: null, ci_95_high: null, policies: 0, claiming_policies: 0 },
  ]);
  assert.deepEqual(f[0].ci.map((x) => Number(x.toFixed(2))), [0.05, 0.06]);
  assert.equal(f[1].ci, null);

  assert.deepEqual(scatterRows([{ CoverageAmount: 5, ClaimAmount: 2, PremiumAmount: 1, PolicyNumber: 'P1', PolicyType: 'Auto' }])[0], { x: 5, y: 2, premium: 1, id: 'P1', type: 'Auto' });
  assert.equal(coverageBandRows([{ band: '10k-20k', average_coverage: 15, average_premium: 2, average_claim_amount: 3, claim_frequency: 0.5, policies: 9 }])[0].coverage, 15);
  assert.equal(histogramRows([{ from: 500, to: 1000.4, claims: 3 }])[0].name, '500-1,000');
  assert.deepEqual(tornadoRows([{ driver: 'Premium', swing_percentage_points: 31.5, loss_ratio_at_minus: 3, loss_ratio_at_plus: 2.5 }])[0], { name: 'Premium', swing: 31.5, lossRatioAtMinus: 3, lossRatioAtPlus: 2.5 });
});

test('frequency mapper accepts both API spellings of the interval', () => {
  const a = frequencyRows([{ segment: 'Low', claim_frequency: 0.5, claim_frequency_ci_low: 0.4, claim_frequency_ci_high: 0.7, policies: 1, claiming_policies: 1 }]);
  assert.deepEqual(a[0].ci.map((x) => Number(x.toFixed(2))), [0.1, 0.2]);
});

test('descriptive sentences use API-provided flags only', () => {
  assert.match(correlationText({ pearson_r: -0.0123, n: 10000, distinguishable_from_zero: false }, 'Premium'), /not distinguishable from zero/);
  assert.match(correlationText({ pearson_r: 0.4, n: 50, distinguishable_from_zero: true }, 'X'), /statistically detectable/);
  assert.match(correlationText(null, 'X'), /not available/);
  assert.equal(testSentence({ computable: true, p_value: 0.611, significant_at_5pct: false }), 'p-value 0.611: within random variation.');
  assert.match(testSentence({ computable: false }), /not computable/);
  assert.equal(yesNo(true), 'Yes');
  assert.equal(yesNo(null), 'n/a');
});

test('points formatter and scenario row mapper', () => {
  assert.equal(formatPoints(103.6271), '+103.6 pts');
  assert.equal(formatPoints(-47.9448), '-47.9 pts');
  assert.equal(formatPoints(0), '0.0 pts');
  assert.equal(formatPoints(null), 'n/a');
  const rows = scenarioRows([
    { key: 'stress', label: 'Stress', results: { adjusted_expected_claim_cost: 9, adjusted_premium: 3, adjusted_loss_ratio: 3, underwriting_margin: -2.25 } },
    { key: 'invalid', label: 'Invalid', results: null, validation_error: 'Frequency exceeds 100%.' },
  ]);
  assert.deepEqual(rows, [{ key: 'stress', name: 'Stress', claimCost: 9, premium: 3, lossRatio: 3, margin: -2.25 }]);
  assert.deepEqual(scenarioRows(undefined), []);
});
