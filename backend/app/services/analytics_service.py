"""
Actuarial analytics engine (pandas + NumPy only, no ML).

Design
------
* ``_sums`` aggregates a slice of the cleaned data into plain totals.
* ``_derive`` turns totals into metrics. Portfolio, segment and monthly results all go
  through these two functions, so every number is defined in exactly one place.
* ``METRIC_DEFINITIONS`` documents each metric: formula, numerator, denominator,
  assumptions, limitations. A unit test checks every returned metric has an entry.
* Division by zero never raises: undefined ratios come back as ``None`` (JSON ``null``).

All inputs are the cleaned dataframe produced by ``data_loader`` (see docs/DATA_AUDIT.md).
The data is SYNTHETIC; results are descriptive, not predictions or pricing advice.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.services.data_loader import AGE_BAND_LABELS, CLAIM_STATUS_TREATMENT

DAYS_PER_YEAR = 365.25
# Classical limited-fluctuation credibility standard for claim counts:
# (1.645 / 0.05)^2 = 1,082 claims -> estimate within +/-5% of truth with 90% probability.
FULL_CREDIBILITY_CLAIMS = 1082
Z_95 = 1.96

MONEY_KEYS = {
    "total_premium", "total_earned_premium", "total_coverage", "total_claim_amount",
    "total_paid_amount", "total_outstanding_amount", "average_premium", "average_coverage",
    "claim_severity", "pure_premium",
}
COUNT_KEYS = {"policies", "claiming_policies", "settled_claims", "pending_claims"}


# --------------------------------------------------------------------------- #
# Metric documentation
# --------------------------------------------------------------------------- #
def _d(name, formula, numerator, denominator, assumptions, limitations) -> dict:
    return {"name": name, "formula": formula, "numerator": numerator, "denominator": denominator,
            "assumptions": assumptions, "limitations": limitations}


METRIC_DEFINITIONS: dict[str, dict] = {
    "policies": _d(
        "Number of policies", "count(unique PolicyNumber)", "-", "-",
        "One row = one policy, after removing 4 exact duplicate rows.",
        "Each policy counts as 1 however long it was in force; see exposure_policy_years."),
    "claiming_policies": _d(
        "Number of claiming policies", "count(policies with status Settled or Pending and ClaimAmount > 0)",
        "Policies with a payable claim", "-",
        "Rejected = no payable claim. At most one claim per policy (ClaimNumber just repeats CustomerID).",
        "Rejected rows have zero amount and no date, so a claim that was made and rejected cannot be told apart from no claim."),
    "settled_claims": _d(
        "Settled claims", "count(IsClaim and ClaimStatus = Settled)", "Settled claim records", "-",
        "Settled is the dataset's equivalent of 'approved'.", "Settlement dates are not recorded."),
    "pending_claims": _d(
        "Pending claims", "count(IsClaim and ClaimStatus = Pending)", "Pending claim records", "-",
        "Pending claims are real claims not yet paid.", "Final outcome (settled or rejected) is unknown."),
    "total_premium": _d(
        "Total written premium", "sum(PremiumAmount)", "Premium of all policies", "-",
        "PremiumAmount is the full-term premium; currency not stated.",
        "Includes the unexpired part of policies still running, so it is NOT the loss-ratio denominator."),
    "total_earned_premium": _d(
        "Total earned premium (proxy)", "sum(PremiumAmount x EarnedFraction); EarnedFraction = min(1, days elapsed / term days)",
        "Premium x elapsed fraction", "-",
        "Premium is earned evenly (pro-rata by day) up to the valuation date (latest ClaimDate in the data).",
        "Estimate only: ignores cancellations, endorsements and uneven risk during the term. A source earned-premium field would replace this."),
    "total_coverage": _d(
        "Total coverage (sum insured)", "sum(CoverageAmount)", "Coverage limits of all policies", "-",
        "CoverageAmount is each policy's limit / sum insured.",
        "A measure of maximum potential exposure, not expected loss. Limits for Life, Health, Travel etc. are not like-for-like."),
    "total_claim_amount": _d(
        "Total claim amount (incurred)", "sum(IncurredAmount) = Settled paid + Pending outstanding",
        "Settled + Pending claim amounts", "-",
        "Pending amounts are case-reserve estimates taken at face value. Rejected contributes 0.",
        "No IBNR (incurred but not reported) or development allowance is possible; pending amounts may change; no inflation adjustment."),
    "total_paid_amount": _d(
        "Total paid amount", "sum(ClaimAmount where status = Settled)", "Settled claim amounts", "-",
        "Settled amounts are fully paid.", "Payment dates are unknown, so paid-to-date cannot be tied to a calendar period."),
    "total_outstanding_amount": _d(
        "Total outstanding amount", "total_claim_amount - total_paid_amount", "Pending claim amounts", "-",
        "Equals the Pending amounts.", "Treated as a reserve estimate; may be over- or under-stated."),
    "average_premium": _d(
        "Average premium", "total_premium / policies", "Total written premium", "Number of policies",
        "Simple mean of full-term premium.",
        "Premium in this data is unrelated to age, coverage or policy type, so it is not a risk-based rate."),
    "average_coverage": _d(
        "Average coverage", "total_coverage / policies", "Total coverage", "Number of policies",
        "Simple mean of coverage limits.", "Mixes very different product lines."),
    "claim_frequency": _d(
        "Claim frequency (incidence)", "claiming_policies / policies", "Policies with a payable claim", "All policies",
        "At most one claim per policy; every policy is observed for (almost) its full ~1-year term.",
        "A proportion of policies, not a count of claims per exposure unit. 96 policies are still in force, so their frequency is slightly understated."),
    "exposure_policy_years": _d(
        "Exposure (policy-years)", "sum(TermDays x EarnedFraction) / 365.25", "Days of cover provided up to the valuation date",
        "Days per year (365.25)", "Exposure ends at the valuation date or policy end, whichever is first.",
        "Ignores cancellations; here almost every policy contributes ~1.0."),
    "claim_frequency_per_exposure_year": _d(
        "Claim frequency per policy-year", "claiming_policies / exposure_policy_years", "Policies with a payable claim",
        "Policy-years of exposure", "Exposure-adjusted version of claim_frequency.",
        "Still at most one claim per policy. Nearly equal to claim_frequency because all terms are ~1 year and almost all have expired."),
    "claim_severity": _d(
        "Claim severity (average claim)", "total_claim_amount / claiming_policies", "Incurred claim amount",
        "Number of claiming policies", "Computed over claims only (zero-claim policies excluded); includes Pending estimates.",
        "A mean: sensitive to large claims (none here, claims are capped near 5,500); no deductible or limit information; not inflation-adjusted."),
    "pure_premium": _d(
        "Pure premium (expected claim cost per policy)", "claim_frequency x claim_severity  (= total_claim_amount / policies)",
        "Incurred claim amount", "Number of policies",
        "Frequency and severity are measured on the same policy set and basis.",
        "Excludes expenses, profit, taxes, reinsurance, investment income and risk margin, so it is not a price. One year of synthetic data."),
    "claim_to_coverage_ratio": _d(
        "Claim-to-coverage ratio (mean per claim)", "mean over claiming policies of IncurredAmount / CoverageAmount",
        "Each claim's incurred amount", "That policy's coverage amount",
        "Only policies with a claim are included (ratio is 0 by definition otherwise).",
        "Unweighted mean, so small-coverage policies count as much as large ones; see claim_to_coverage_aggregate."),
    "claim_to_coverage_aggregate": _d(
        "Claim-to-coverage ratio (aggregate)", "total_claim_amount / sum(CoverageAmount of claiming policies)",
        "Total incurred claim amount", "Coverage of claiming policies only",
        "Weights policies by coverage size.", "Excludes coverage of policies without claims by design."),
    "max_claim_to_coverage": _d(
        "Largest claim-to-coverage ratio", "max over claims of IncurredAmount / CoverageAmount", "Largest single ratio", "That claim's coverage",
        "-", "A single extreme value; shows no claim exhausts its limit in this data."),
    "coverage_utilization": _d(
        "Coverage utilization (portfolio)", "total_claim_amount / total_coverage", "Total incurred claim amount",
        "Total coverage of ALL policies", "Shows how much of the sum insured was consumed by claims.",
        "Depends on the coverage mix; not a probability of loss."),
    "loss_ratio": _d(
        "Loss ratio (incurred, headline)", "total_claim_amount / total_earned_premium", "Settled + Pending claim amounts",
        "Earned premium (pro-rata proxy)",
        "Most defensible definition available: incurred losses over earned (not written) premium, so claims are matched to the exposure that produced them.",
        "No IBNR; Pending at face value; earned premium is a proxy; excludes expenses, so it is a loss ratio, not a combined ratio. Values far above 100% indicate synthetic data."),
    "paid_loss_ratio": _d(
        "Loss ratio (paid only)", "total_paid_amount / total_earned_premium", "Settled claim amounts", "Earned premium (pro-rata proxy)",
        "Counts only claims already paid.", "A lower bound: ignores outstanding Pending claims."),
    "credibility_z": _d(
        "Credibility factor", "min(1, sqrt(claiming_policies / 1082))", "Observed number of claims", "Full-credibility standard (1,082 claims)",
        "Classical limited-fluctuation standard for claim counts: +/-5% accuracy with 90% probability.",
        "A guide to how much weight a segment's own experience deserves; derived for Poisson counts, applied here as a heuristic."),
}


def get_metric_definitions() -> dict[str, dict]:
    return {k: dict(v) for k, v in METRIC_DEFINITIONS.items()}


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #
def _div(num, den):
    """Safe division: None when the denominator is zero/missing."""
    if num is None or den is None or den == 0 or (isinstance(den, float) and math.isnan(den)):
        return None
    return num / den


def _round(key: str, value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if key in COUNT_KEYS:
        return int(value)
    return round(float(value), 2 if key in MONEY_KEYS else 6)


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float | None, float | None]:
    """Wilson score 95% confidence interval for a proportion k/n (well-behaved for small n)."""
    if n <= 0:
        return None, None
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)


# --------------------------------------------------------------------------- #
# Core: totals -> metrics (single source of truth)
# --------------------------------------------------------------------------- #
def _sums(df: pd.DataFrame) -> dict:
    claims = df["IsClaim"]
    inc = df.loc[claims, "IncurredAmount"]
    ctc = df.loc[claims, "ClaimToCoverage"]
    return {
        "policies": int(len(df)),
        "claims": int(claims.sum()),
        "settled": int((claims & (df["ClaimStatus"] == "Settled")).sum()),
        "pending": int((claims & (df["ClaimStatus"] == "Pending")).sum()),
        "premium": float(df["PremiumAmount"].sum()),
        "earned": float(df["EarnedPremium"].sum()),
        "coverage": float(df["CoverageAmount"].sum()),
        "claim_coverage": float(df.loc[claims, "CoverageAmount"].sum()),
        "incurred": float(df["IncurredAmount"].sum()),
        "paid": float(df["PaidAmount"].sum()),
        "ctc_sum": float(ctc.sum()),
        "ctc_max": float(ctc.max()) if len(ctc) else None,
        "sev_std": float(inc.std(ddof=1)) if len(inc) > 1 else None,
        "exposure_years": float((df["TermDays"] * df["EarnedFraction"]).sum() / DAYS_PER_YEAR),
    }


def _derive(s: dict) -> dict:
    n, c = s["policies"], s["claims"]
    freq = _div(c, n)
    sev = _div(s["incurred"], c)
    if freq is None:
        pure = None
    elif c == 0:
        pure = 0.0
    else:
        pure = freq * sev
    raw = {
        "policies": n,
        "claiming_policies": c,
        "settled_claims": s["settled"],
        "pending_claims": s["pending"],
        "total_premium": s["premium"],
        "total_earned_premium": s["earned"],
        "total_coverage": s["coverage"],
        "total_claim_amount": s["incurred"],
        "total_paid_amount": s["paid"],
        "total_outstanding_amount": s["incurred"] - s["paid"],
        "average_premium": _div(s["premium"], n),
        "average_coverage": _div(s["coverage"], n),
        "claim_frequency": freq,
        "exposure_policy_years": s["exposure_years"],
        "claim_frequency_per_exposure_year": _div(c, s["exposure_years"]),
        "claim_severity": sev,
        "pure_premium": pure,
        "claim_to_coverage_ratio": _div(s["ctc_sum"], c),
        "claim_to_coverage_aggregate": _div(s["incurred"], s["claim_coverage"]),
        "max_claim_to_coverage": s["ctc_max"],
        "coverage_utilization": _div(s["incurred"], s["coverage"]),
        "loss_ratio": _div(s["incurred"], s["earned"]),
        "paid_loss_ratio": _div(s["paid"], s["earned"]),
        "credibility_z": min(1.0, math.sqrt(c / FULL_CREDIBILITY_CLAIMS)),
    }
    return {k: _round(k, v) for k, v in raw.items()}


# --------------------------------------------------------------------------- #
# 1-13. Portfolio-level metrics
# --------------------------------------------------------------------------- #
def portfolio_summary(df: pd.DataFrame) -> dict:
    """All headline metrics plus confidence information and the assumptions in force."""
    s = _sums(df)
    metrics = _derive(s)
    lo, hi = wilson_interval(s["claims"], s["policies"])
    sev_ci = (None, None)
    if s["sev_std"] is not None and s["claims"] > 1 and metrics["claim_severity"] is not None:
        half = Z_95 * s["sev_std"] / math.sqrt(s["claims"])
        sev_ci = (round(metrics["claim_severity"] - half, 2), round(metrics["claim_severity"] + half, 2))
    return {
        "metrics": metrics,
        "confidence_intervals_95": {
            "claim_frequency": {"low": lo, "high": hi, "method": "Wilson score interval"},
            "claim_severity": {"low": sev_ci[0], "high": sev_ci[1], "method": "mean +/- 1.96 x std / sqrt(n)"},
        },
        "basis": {
            "valuation_date": df.attrs.get("valuation_date"),
            "incurred_definition": "Settled (paid) + Pending (outstanding case estimate); Rejected = 0",
            "premium_basis_for_loss_ratio": "pro-rata earned premium proxy",
            "data_is_synthetic": True,
        },
    }


def total_premium(df: pd.DataFrame) -> float:
    return _round("total_premium", df["PremiumAmount"].sum())


def total_coverage(df: pd.DataFrame) -> float:
    return _round("total_coverage", df["CoverageAmount"].sum())


def total_claim_amount(df: pd.DataFrame, basis: str = "incurred") -> float:
    """basis = 'incurred' (Settled+Pending) or 'paid' (Settled only)."""
    col = {"incurred": "IncurredAmount", "paid": "PaidAmount"}.get(basis)
    if col is None:
        raise ValueError("basis must be 'incurred' or 'paid'")
    return _round("total_claim_amount", df[col].sum())


def number_of_policies(df: pd.DataFrame) -> int:
    return int(len(df))


def number_of_claiming_policies(df: pd.DataFrame) -> int:
    return int(df["IsClaim"].sum())


def claim_frequency(df: pd.DataFrame):
    return _round("claim_frequency", _div(int(df["IsClaim"].sum()), len(df)))


def claim_severity(df: pd.DataFrame):
    return _round("claim_severity", _div(float(df["IncurredAmount"].sum()), int(df["IsClaim"].sum())))


def pure_premium(df: pd.DataFrame):
    return _derive(_sums(df))["pure_premium"]


def average_premium(df: pd.DataFrame):
    return _round("average_premium", _div(float(df["PremiumAmount"].sum()), len(df)))


def average_coverage(df: pd.DataFrame):
    return _round("average_coverage", _div(float(df["CoverageAmount"].sum()), len(df)))


def claim_to_coverage_ratio(df: pd.DataFrame) -> dict:
    m = _derive(_sums(df))
    return {k: m[k] for k in ("claim_to_coverage_ratio", "claim_to_coverage_aggregate",
                              "max_claim_to_coverage", "coverage_utilization")}


def loss_ratio(df: pd.DataFrame) -> dict:
    m = _derive(_sums(df))
    return {"loss_ratio": m["loss_ratio"], "paid_loss_ratio": m["paid_loss_ratio"]}


# --------------------------------------------------------------------------- #
# 14-16. Segment analytics (policy type, age band, gender)
# --------------------------------------------------------------------------- #
SEGMENT_NOTES = [
    "Segment results are descriptive. 'frequency_ci_includes_portfolio' = True means the segment's 95% interval "
    "contains the portfolio frequency, i.e. the difference could be random noise. It is a screening aid, not a formal "
    "hypothesis test (no multiple-comparison adjustment).",
    "credibility_z < 1 means the segment has fewer than 1,082 claims, so its own experience should not be relied on fully.",
    "Premium in this dataset is not related to risk characteristics, so loss ratios by segment mainly reflect random variation.",
]


def segment_analytics(df: pd.DataFrame, column: str, order: list | None = None) -> dict:
    """Metrics for each value of ``column`` plus index/confidence information vs the portfolio."""
    if column not in df.columns:
        raise ValueError(f"Unknown segment column: {column}")
    total = _sums(df)
    port_freq = _div(total["claims"], total["policies"])
    keys = order if order is not None else sorted(df[column].dropna().unique().tolist())

    rows = []
    for key in keys:
        part = df[df[column] == key]
        s = _sums(part)
        row = {"segment": key, **_derive(s)}
        lo, hi = wilson_interval(s["claims"], s["policies"])
        freq = _div(s["claims"], s["policies"])   # unrounded, so indices are not distorted by display rounding
        row.update({
            "share_of_policies": _round("x", _div(s["policies"], total["policies"])),
            "share_of_claim_amount": _round("x", _div(s["incurred"], total["incurred"])),
            "claim_frequency_ci_low": lo,
            "claim_frequency_ci_high": hi,
            "frequency_index_vs_portfolio": _round("x", _div(freq, port_freq)),
            "frequency_ci_includes_portfolio": None if lo is None else bool(lo <= port_freq <= hi),
        })
        rows.append(row)
    return {
        "dimension": column,
        "segments": rows,
        "portfolio_claim_frequency": _round("claim_frequency", port_freq),
        "notes": SEGMENT_NOTES,
    }


def policy_type_analytics(df: pd.DataFrame) -> dict:
    return segment_analytics(df, "PolicyType")


def age_band_analytics(df: pd.DataFrame) -> dict:
    return segment_analytics(df, "AgeBand", order=AGE_BAND_LABELS)


def gender_analytics(df: pd.DataFrame) -> dict:
    return segment_analytics(df, "Gender")


# --------------------------------------------------------------------------- #
# 17. Claim-status analytics
# --------------------------------------------------------------------------- #
def claim_status_analytics(df: pd.DataFrame) -> dict:
    total_incurred = float(df["IncurredAmount"].sum())
    status_col = "ClaimStatusAsOf" if "ClaimStatusAsOf" in df.columns else "ClaimStatus"
    statuses = list(CLAIM_STATUS_TREATMENT) + [s for s in df[status_col].unique() if s not in CLAIM_STATUS_TREATMENT]
    rows = []
    for st in statuses:
        part = df[df[status_col] == st]
        observed_claims = part.loc[part["IsClaim"]]
        with_amount = observed_claims["IncurredAmount"]
        treat = CLAIM_STATUS_TREATMENT.get(st, {"counts_as_claim": False, "paid": False, "incurred": False})
        rows.append({
            "status": st,
            "policies": int(len(part)),
            "share_of_policies": _round("x", _div(len(part), len(df))),
            "claim_records": int(part["IsClaim"].sum()),
            "recorded_claim_amount": round(float(part["IncurredAmount"].sum()), 2),
            "average_claim_amount": _round("claim_severity", with_amount.mean()) if len(with_amount) else None,
            "paid_amount": round(float(part["PaidAmount"].sum()), 2),
            "outstanding_amount": round(float(part["OutstandingAmount"].sum()), 2),
            "incurred_amount": round(float(part["IncurredAmount"].sum()), 2),
            "share_of_incurred": _round("x", _div(float(part["IncurredAmount"].sum()), total_incurred)),
            "treatment": treat,
        })
    return {
        "statuses": rows,
        "notes": [
            "Settled = paid. Pending = unpaid case estimate, included in incurred. Rejected = no payable claim.",
            "Claim counts, amounts and status group are evaluated as of the portfolio valuation date; later-dated claims are shown separately as not yet occurred.",
            "Rejected policies have zero amount and no ClaimDate, so they cannot be distinguished from policies that never "
            "claimed. A 'rejection rate' is therefore NOT reported.",
            "Share of policies by status is not a claim-settlement rate, because the no-claim policies sit inside 'Rejected'.",
        ],
    }


# --------------------------------------------------------------------------- #
# 18. Monthly claim analytics (exposure-adjusted)
# --------------------------------------------------------------------------- #
def monthly_claim_analytics(df: pd.DataFrame, low_exposure_fraction: float = 0.10) -> dict:
    """
    Claims by calendar month of ClaimDate, shown beside the exposure in force that month.
    Raw monthly counts rise and fall mainly with how many policies were in force, so the
    rate per 100 policy-months is the comparable figure.
    """
    notes = [
        "Raw monthly counts mostly reflect how many policies were in force (policies start over one year).",
        "claims_per_100_policy_months = claims / exposure x 100, where exposure is the policy-months of cover in that calendar month.",
        "ClaimDate is treated as the claim occurrence month; reporting/settlement lags are unknown.",
        "Months flagged low_exposure have under 10% of peak exposure; their rates are volatile and should not be read as trends.",
    ]
    claims = df[df["IsClaim"] & df["ClaimMonth"].notna()]
    if claims.empty:
        return {"months": [], "notes": notes}

    month_starts = pd.date_range(claims["ClaimMonth"].min(), claims["ClaimMonth"].max(), freq="MS")
    starts = df["PolicyStartDate"].values.astype("datetime64[D]")
    ends = df["PolicyEndDate"].values.astype("datetime64[D]")

    by_month = claims.groupby("ClaimMonth").agg(
        claims=("IsClaim", "sum"), incurred=("IncurredAmount", "sum"), paid=("PaidAmount", "sum"))

    records = []
    for ms in month_starts:
        nxt = ms + pd.offsets.MonthBegin(1)
        lo = np.maximum(starts, np.datetime64(ms.date(), "D"))
        hi = np.minimum(ends, np.datetime64(nxt.date(), "D"))
        overlap = np.clip((hi - lo).astype("timedelta64[D]").astype(float), 0, None)
        days_in_month = (nxt - ms).days
        exposure = float(overlap.sum() / days_in_month)
        in_force = int((overlap > 0).sum())
        n = int(by_month["claims"].get(ms, 0))
        inc = float(by_month["incurred"].get(ms, 0.0))
        records.append({
            "month": ms.strftime("%Y-%m"),
            "claims": n,
            "incurred_amount": round(inc, 2),
            "paid_amount": round(float(by_month["paid"].get(ms, 0.0)), 2),
            "average_severity": _round("claim_severity", _div(inc, n)),
            "policies_in_force": in_force,
            "exposure_policy_months": round(exposure, 2),
            "claims_per_100_policy_months": _round("x", _div(n, exposure) * 100) if exposure > 0 else None,
        })
    peak = max((r["exposure_policy_months"] for r in records), default=0)
    for r in records:
        r["low_exposure"] = bool(r["exposure_policy_months"] < low_exposure_fraction * peak)
    return {"months": records, "notes": notes}


# --------------------------------------------------------------------------- #
# Bundle for the API layer (Phase 3)
# --------------------------------------------------------------------------- #
def build_analytics_report(df: pd.DataFrame) -> dict:
    return {
        "portfolio": portfolio_summary(df),
        "policy_type": policy_type_analytics(df),
        "age_band": age_band_analytics(df),
        "gender": gender_analytics(df),
        "claim_status": claim_status_analytics(df),
        "monthly": monthly_claim_analytics(df),
        "definitions": get_metric_definitions(),
    }
