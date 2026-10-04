# Data Dictionary

Source: `backend/data/InsuranceData.csv` (never modified). Cleaned output: `backend/data/cleaned_insurance_data.csv`
(10,000 rows x 23 columns; dates written as `YYYY-MM-DD`). **All data is synthetic.**

## Original columns (13)

| Column | Type | Meaning | Notes from the audit |
|---|---|---|---|
| PolicyNumber | text | Unique policy id (`P1`...`P10000`) | Unique after removing 4 duplicate rows. One row = one policy. |
| CustomerID | text | Customer id (`C1`...) | 1 policy per customer, so no repeat-customer analysis is possible. |
| Gender | text | Male / Female | 5,000 each after de-duplication. |
| Age | int | Policyholder age at policy level | 18-87; roughly uniform. Single snapshot, not age at claim. |
| PolicyType | text | Auto, Health, Home, Life, Travel | Travel 41%, Health 20%, Auto 16%, Life 12%, Home 10%. |
| PolicyStartDate | date | Start of cover (DD-MM-YYYY in source) | 14-Jul-2023 to 12-Jul-2024. |
| PolicyEndDate | date | End of cover (DD-MM-YYYY in source) | Always 365 or 366 days after start. |
| PremiumAmount | float | Premium for the policy term | 100.02-1,099.70. Treated as **written** premium for the full term. Currency not stated. |
| CoverageAmount | float | Sum insured / coverage limit | 10,020-109,992. No claim exceeds it. |
| ClaimNumber | text | Claim id | **Equals CustomerID on every row**, so it is not an independent claim key. |
| ClaimDate | date | Date of claim (DD-MM-YYYY in source) | Blank for 4,354 policies (all Rejected). Always within the policy term. |
| ClaimAmount | float | Claimed amount | 0 for Rejected; 500.34-5,499.25 otherwise. For Pending it is an estimate. |
| ClaimStatus | text | Settled / Pending / Rejected | The status "Approved" does not exist; **Settled** is the equivalent. |

## Derived columns added by the cleaning pipeline (10)

| Column | Definition |
|---|---|
| AgeBand | 18-25, 26-35, 36-45, 46-55, 56-65, 66-75, 76+ |
| IsClaim | `True` if status is Settled/Pending, ClaimAmount > 0, and ClaimDate is on or before the valuation date (5,646 policies at the default date) |
| IncurredAmount | ClaimAmount for observed Settled + Pending claims on or before the valuation date; otherwise 0 |
| PaidAmount | ClaimAmount for observed Settled claims on or before the valuation date; otherwise 0 |
| OutstandingAmount | IncurredAmount - PaidAmount (Pending amounts) |
| ClaimToCoverage | IncurredAmount / CoverageAmount for claims; 0 otherwise |
| ClaimMonth | First day of the month of ClaimDate, blank if no claim was observed by the valuation date |
| TermDays | PolicyEndDate - PolicyStartDate in days |
| EarnedFraction | min(1, days from start to valuation date / TermDays); default valuation date = 2025-07-08 (latest ClaimDate) |
| EarnedPremium | PremiumAmount x EarnedFraction (pro-rata **proxy**, not a source field) |

The configured `VALUATION_DATE` is applied when loading raw CSV, cleaned CSV, or MongoDB data. Claim outcomes after
that date are excluded from claim frequency, severity, incurred/paid amounts, loss ratios and claim-month trends;
they are represented as "Not yet occurred as of valuation date" in as-of claim-status summaries. Policy counts,
written premium and earned exposure remain measured on the selected cohort and valuation date.
