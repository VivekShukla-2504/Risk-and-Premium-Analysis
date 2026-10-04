"""
Data audit service.

Produces a structured, data-driven report describing what the dataset can and cannot
support. Findings are *computed* from the data (not hard-coded) so the audit stays
correct if a different CSV is loaded later.
"""
from __future__ import annotations

import pandas as pd

from app.utils.serialization import to_builtin
from app.services.data_loader import CLAIM_STATUS_TREATMENT, REQUIRED_COLUMNS, CleaningReport


def _finding(fid: str, severity: str, title: str, detail: str, decision: str) -> dict:
    return {"id": fid, "severity": severity, "title": title, "detail": detail, "decision": decision}


def consistency_checks(df: pd.DataFrame) -> dict[str, int]:
    """Row-level logical checks. Rows are reported, not modified."""
    has_amount = df["ClaimAmount"] > 0
    has_date = df["ClaimDate"].notna()
    status = df["ClaimStatus"]
    return {
        "claim_amount_without_claim_date": int((has_amount & ~has_date).sum()),
        "claim_date_without_claim_amount": int((~has_amount & has_date).sum()),
        "claim_date_before_policy_start": int((df["ClaimDate"] < df["PolicyStartDate"]).sum()),
        "claim_date_after_policy_end": int((df["ClaimDate"] > df["PolicyEndDate"]).sum()),
        "claim_amount_exceeds_coverage": int((df["ClaimAmount"] > df["CoverageAmount"]).sum()),
        "rejected_with_positive_amount": int(((status == "Rejected") & has_amount).sum()),
        "settled_or_pending_with_zero_amount": int((status.isin(["Settled", "Pending"]) & ~has_amount).sum()),
        "unknown_claim_status": int((~status.isin(CLAIM_STATUS_TREATMENT)).sum()),
        "age_outside_band_range": int(df["AgeBand"].isna().sum()),
    }


def build_audit_report(df: pd.DataFrame, cleaning: CleaningReport) -> dict:
    n = len(df)
    num_cols = ["Age", "PremiumAmount", "CoverageAmount", "ClaimAmount"]

    status_vs_claim = (
        df.assign(HasClaimDate=df["ClaimDate"].notna(), AmountPositive=df["ClaimAmount"] > 0)
        .groupby("ClaimStatus")
        .agg(
            policies=("PolicyNumber", "size"),
            with_claim_date=("HasClaimDate", "sum"),
            with_positive_amount=("AmountPositive", "sum"),
            total_amount=("ClaimAmount", "sum"),
        )
        .round(2)
        .reset_index()
        .to_dict(orient="records")
    )

    report = {
        "shape": {"rows_raw": cleaning.rows_raw, "rows_after_cleaning": n, "columns": 13},
        "cleaning": cleaning.to_dict(),
        "missing_values": {c: int(df[c].isna().sum()) for c in REQUIRED_COLUMNS},
        "categoricals": {
            c: df[c].value_counts().to_dict() for c in ["Gender", "PolicyType", "ClaimStatus", "AgeBand"]
        },
        "numeric_summary": df[num_cols].describe().round(2).to_dict(),
        "date_ranges": {
            c: [df[c].min().strftime("%Y-%m-%d"), df[c].max().strftime("%Y-%m-%d")]
            for c in ["PolicyStartDate", "PolicyEndDate", "ClaimDate"]
        },
        "consistency_checks": consistency_checks(df),
        "status_vs_claim_fields": status_vs_claim,
        "findings": _findings(df),
    }
    return to_builtin(report)


def _findings(df: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    n = len(df)

    # F1 - one row per policy => at most one claim per policy
    if df["PolicyNumber"].is_unique and (df["ClaimNumber"] == df["CustomerID"]).all():
        out.append(_finding(
            "ONE_CLAIM_PER_POLICY", "info",
            "Each policy has at most one claim record",
            "PolicyNumber is unique and ClaimNumber is identical to CustomerID on every row, so "
            "ClaimNumber is not an independent claim identifier.",
            "Claim frequency is measured as claiming POLICIES / policies (a claim-incidence rate), "
            "not claims per policy-year. Multiple claims per policy cannot be modelled.",
        ))

    # F2 - Rejected rows carry no claim information
    rej = df[df["ClaimStatus"] == "Rejected"]
    if len(rej) and (rej["ClaimAmount"] == 0).all() and rej["ClaimDate"].isna().all():
        out.append(_finding(
            "REJECTED_IS_EMPTY", "warning",
            "'Rejected' rows have no claim date and zero amount",
            f"All {len(rej):,} Rejected rows have ClaimAmount = 0 and no ClaimDate, so they cannot be "
            "distinguished from 'no claim was made'.",
            "Rejected is treated as 'no payable claim'. Claim frequency is reported on Settled+Pending "
            "(claims with a recorded amount). A rejection rate cannot be reliably computed and is NOT reported as such.",
        ))

    # F3 - Pending amounts
    pend = df[df["ClaimStatus"] == "Pending"]
    if len(pend):
        out.append(_finding(
            "PENDING_AMOUNT", "info",
            "Pending claims have an amount but are unsettled",
            f"{len(pend):,} Pending claims total {pend['ClaimAmount'].sum():,.2f}.",
            "Pending amounts are treated as case-reserve estimates: Incurred = Settled (paid) + Pending (outstanding). "
            "Both 'incurred' and 'paid-only' loss ratios are exposed so the user can see the difference.",
        ))

    # F4 - implausibly high claim incidence => synthetic data
    freq = float(df["IsClaim"].mean())
    lr = float(df["IncurredAmount"].sum() / df["EarnedPremium"].sum())
    if freq > 0.30 or lr > 1.5:
        out.append(_finding(
            "SYNTHETIC_LEVELS", "warning",
            "Claim incidence and loss ratio are far above real-world insurance levels",
            f"{freq:.1%} of policies have a claim and the incurred loss ratio is {lr:.0%}. A viable insurer "
            "typically runs loss ratios well below 100% and far lower claim incidence for most lines.",
            "The data is treated as SYNTHETIC. All outputs are labelled as illustrative; no result is presented "
            "as a real-world pricing indication.",
        ))

    # F5 - policies written over ~1 year => monthly trend is exposure-driven
    span_days = (df["PolicyStartDate"].max() - df["PolicyStartDate"].min()).days
    if span_days > 180:
        out.append(_finding(
            "EXPOSURE_RAMP", "warning",
            "Monthly claim counts are driven by how many policies were in force",
            f"Policies start over a {span_days}-day window and claims occur 1-366 days after start, so raw monthly "
            "claim counts rise and fall with the number of policies in force, not with underlying risk.",
            "The monthly trend chart must show claims per policy in force (or be clearly labelled as raw counts).",
        ))

    # F6 - partially earned premium
    partial = int((df["EarnedFraction"] < 1).sum())
    if partial:
        out.append(_finding(
            "EARNED_PROXY", "info",
            "Earned premium is an estimate",
            f"No earned-premium column exists. {partial:,} policies are still in force at the valuation date.",
            "Earned premium = PremiumAmount x elapsed fraction of the policy term at the valuation date "
            "(pro-rata, daily). Fully expired policies are 100% earned.",
        ))

    # F7 - no relationship between rating variables and claims (synthetic signal)
    corr = df[["Age", "PremiumAmount", "CoverageAmount", "IncurredAmount"]].corr()["IncurredAmount"].drop("IncurredAmount")
    if (corr.abs() < 0.05).all():
        out.append(_finding(
            "NO_SIGNAL", "warning",
            "Rating variables show almost no relationship with claim cost",
            "Correlation of incurred amount with Age, Premium and Coverage is "
            + ", ".join(f"{k}: {v:+.3f}" for k, v in corr.items())
            + ".",
            "Segment differences must be tested before being called 'risk'. Segments are labelled as a rule-based "
            "classification, not as evidence of different underlying risk. Statistically weak differences are flagged.",
        ))
    return out
