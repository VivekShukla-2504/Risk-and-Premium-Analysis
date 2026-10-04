# Data Audit (Phase 1)

> **All data is synthetic.** Nothing here is a real-world pricing indication, and this is not
> production actuarial software. Figures below were verified by `backend/scripts/audit_dataset.py`
> and the test-suite in `backend/tests`.

## 1. Shape and cleaning

| Item | Result |
|---|---|
| Raw rows / columns | 10,004 / 13 |
| Exact duplicate rows removed | 4 (P1 x1 extra, P2 x2 extra, P4 x1 extra) |
| Same PolicyNumber, different content | 0 |
| **Unique policies after cleaning** | **10,000** |
| Invalid numerics, impossible dates, end <= start | 0 |
| Missing values | only `ClaimDate` (4,354 after de-duplication) |
| Gender | Male 5,003 / Female 5,001 (raw) |
| Policy type (clean) | Travel 4,145 · Health 2,000 · Auto 1,594 · Life 1,248 · Home 1,013 |
| Age | 18-87 |
| Policy term | 365 or 366 days (all ~1 year) |
| Policy start / end | 14-Jul-2023 to 12-Jul-2024 / 14-Jul-2024 to 12-Jul-2025 |
| Claim dates | 21-Jul-2023 to 08-Jul-2025; always inside the policy term |
| Claim amount > coverage | 0 rows (max claim = 53% of coverage) |

## 2. Findings that change the analysis

| # | Finding | Consequence / decision |
|---|---|---|
| 1 | **One row per policy; `ClaimNumber` equals `CustomerID` on every row.** | A policy has at most one claim. Frequency is a *claim-incidence rate* (claiming policies / policies), not claims per policy-year. |
| 2 | **All 4,354 `Rejected` rows have amount = 0 and no ClaimDate.** `Settled` and `Pending` always have both. | Rejected cannot be told apart from "no claim". We do **not** report a rejection rate. Rejected = "no payable claim". |
| 3 | `Pending` has an amount (2,260 policies, 6.80M). | Treated as an outstanding case-reserve estimate. **Incurred = Settled (paid) + Pending (outstanding).** Paid-only metrics are also exposed. No IBNR is possible. |
| 4 | **56.5% of policies have a claim; incurred loss ratio is 283%.** | Far outside real-world levels, so the data is synthetic. Every output is labelled illustrative. |
| 5 | Policies start across one year; claims occur 1-366 days after start. | Raw monthly claim counts follow policies-in-force (a ramp up then down). The trend chart will show **claims per policy in force** and not present raw counts as a risk trend. |
| 6 | No earned-premium column. | Pro-rata proxy (section 3). |
| 7 | Correlation of claim amount with Age / Premium / Coverage is about 0.01. Exploratory chi-square on claim incidence: policy type p = 0.18, gender p = 0.51, age band p = 0.21; ANOVA on severity by type p = 0.61. | **No statistically significant differences** between segments. We will label segments as *rule-based classifications* and flag when differences are not significant, rather than claiming a segment is "riskier". (SciPy was used only for this exploration; Phase 3 implements the tests with NumPy.) |

## 3. Earned premium proxy (assumption)

No earned premium exists, and using written premium would overstate exposure for policies still running.

```
EarnedFraction = min(1, days from PolicyStartDate to valuation date / policy term days)
EarnedPremium  = PremiumAmount x EarnedFraction
```

* Valuation date defaults to the **latest ClaimDate (08-Jul-2025)**, a proxy for the data cut-off. Override with `VALUATION_DATE` in `.env`.
* Effect here is tiny: 96 policies are still in force, earned 5,973,679.88 vs written 5,974,060.08.
* Limitation: this assumes premium is earned evenly over time and ignores cancellations and endorsements.
* The configured valuation date is applied consistently to raw CSV, cleaned CSV and MongoDB loads. Claims dated after the
  selected date do not contribute to frequency, severity, claim amounts, loss ratios, status summaries or claim-month
  trends; they appear as "Not yet occurred as of valuation date" in status summaries. Policies and their earned exposure
  are retained as of that date.

## 4. Formulas as applied to this dataset

| Measure | Applied formula | Preview (whole portfolio, descriptive only) |
|---|---|---|
| Claim frequency | policies with `IsClaim` / policies = 5,646 / 10,000 | 56.46% |
| Claim severity | total incurred / number of claims = 16,904,295.27 / 5,646 | 2,994.03 |
| Pure premium | frequency x severity (= total incurred / policies) | 1,690.43 per policy |
| Average premium | written premium / policies | 597.41 |
| Loss ratio (incurred) | incurred / earned premium = 16,904,295 / 5,973,680 | 283.0% |
| Loss ratio (paid only) | settled / earned premium | 169.2% |
| Claim-to-coverage | incurred claim / coverage, claims only | max 0.53 |

Pure premium (1,690) is ~2.8x the average premium (597), which is just the loss ratio seen another way. This is a property of the synthetic data.

## 5. Claim status treatment

| Status | Counts as claim? | Paid | Outstanding | Incurred |
|---|---|---|---|---|
| Settled | Yes | amount | 0 | amount |
| Pending | Yes | 0 | amount | amount |
| Rejected | No | 0 | 0 | 0 |

## 6. Cleaning rules (implemented in `app/services/data_loader.py`)

1. Read everything as text; convert explicitly so failures are counted, not hidden.
2. Trim whitespace; blank text becomes missing.
3. Remove exact duplicate rows; if a PolicyNumber repeats with different content keep the first and report it.
4. Numeric rules: Age 0-120, premium > 0, coverage > 0, claim amount >= 0. Violating rows are dropped and counted per reason.
5. Dates parsed with strict `%d-%m-%Y`. Blank `ClaimDate` is valid (no claim). Bad policy dates drop the row.
6. Logical inconsistencies (claim outside term, claim > coverage, status/amount mismatch) are **reported, not altered**.
7. Derived columns: `AgeBand`, `IsClaim` (only a payable claim on or before the valuation date), `IncurredAmount`,
   `PaidAmount`, `OutstandingAmount`, `ClaimToCoverage`, `ClaimMonth`, `TermDays`, `EarnedFraction`, `EarnedPremium`.

## 7. Distributions (cleaned data, n = 10,000)

| Variable | Shape |
|---|---|
| Age | 18-87, mean 52.3, skew 0.02; near-uniform (each 10-year band holds ~1,400-1,700 policies) |
| PremiumAmount | 100-1,100, mean 597, skew 0.01, CV 0.48; near-uniform |
| CoverageAmount | 10k-110k, mean 60k, skew -0.01, CV 0.48; near-uniform |
| ClaimAmount (claims only, n = 5,646) | 500-5,500, mean 2,994, median 2,980, skew 0.03; near-uniform, **no heavy tail** |
| Gender | 5,000 / 5,000 |
| ClaimStatus | Rejected 4,354 · Settled 3,386 · Pending 2,260 |

Real insurance severities are usually right-skewed with a heavy tail. These flat, bounded distributions,
independent of each other, confirm the data was generated randomly. Any "pattern" in later charts should be treated as noise unless a test says otherwise.
Statistical precision of the headline frequency: 56.5% with a 95% confidence interval of about 55.5%-57.4%.
