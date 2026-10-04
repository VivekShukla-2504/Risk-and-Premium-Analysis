"""
Rule-based risk segmentation.

Two deliberately separate views, to avoid circular reasoning (data leakage):

1. A-PRIORI RISK TIERS use only attributes known BEFORE any claim (age, policy type, coverage).
   The points are conventional underwriting assumptions, NOT estimated from this data. We then test
   whether observed claims actually follow the tiers (actual vs expected). With this synthetic dataset they do not,
   and the output says so.

2. CLAIM-EXPERIENCE CLASSES describe what happened (no claim / claim size relative to cover). They use the claim
   outcome, so they are descriptive only and must never be used to "predict" claims.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services import analytics_service as A
from app.services.statistics import segment_significance, z_test_vs_expected

# ---- a-priori rule parameters (documented assumptions) -----------------------------------
AGE_YOUNG_BELOW = 25          # ages 18-24
AGE_OLD_FROM = 70             # ages 70+
AGE_NOT_A_FACTOR = {"Home"}   # property cover is not conventionally rated on policyholder age
COVERAGE_HIGH_FROM = 85_000   # roughly the top quartile of sums insured
TIERS = {0: "Low", 1: "Medium", 2: "High"}
TIER_ORDER = list(TIERS.values())

# ---- claim-size classes (claim as a share of the policy's coverage) -----------------------
SIZE_EDGES = [0.02, 0.05, 0.10]
CLASS_ORDER = ["No payable claim", "Claim <2% of cover", "Claim 2-5% of cover",
               "Claim 5-10% of cover", "Claim >=10% of cover"]

RULES = {
    "a_priori_tiers": {
        "purpose": "Group policies by characteristics known at inception, then test whether claims follow the grouping.",
        "points": [
            {"factor": "Age", "condition": f"age < {AGE_YOUNG_BELOW} or age >= {AGE_OLD_FROM} (not applied to Home)",
             "points": 1, "rationale": "Conventional assumption that very young and older policyholders carry higher claim propensity."},
            {"factor": "Coverage amount", "condition": f"coverage >= {COVERAGE_HIGH_FROM:,}", "points": 1,
             "rationale": "Larger sums insured allow larger losses (a severity exposure, not a frequency driver)."},
        ],
        "tiers": {"Low": "0 points", "Medium": "1 point", "High": "2 points"},
        "policy_type": "Policy type is NOT scored: no basis exists to rank unrelated product lines by claim propensity. "
                       "It is analysed as its own dimension.",
        "caveat": "Points are underwriting conventions, not estimated from data. A 'High' tier is only a statement about "
                  "the rule; the actual-vs-expected table shows whether experience supports it.",
    },
    "claim_experience_classes": {
        "purpose": "Describe observed claim size relative to cover.",
        "classes": CLASS_ORDER,
        "caveat": "Uses the claim outcome, so it is descriptive only and not a rating factor.",
    },
}


def assign_apriori_tier(df: pd.DataFrame) -> pd.Series:
    age_pts = (((df["Age"] < AGE_YOUNG_BELOW) | (df["Age"] >= AGE_OLD_FROM))
               & ~df["PolicyType"].isin(AGE_NOT_A_FACTOR)).astype(int)
    cov_pts = (df["CoverageAmount"] >= COVERAGE_HIGH_FROM).astype(int)
    return (age_pts + cov_pts).map(TIERS)


def assign_claim_class(df: pd.DataFrame) -> pd.Series:
    r = df["ClaimToCoverage"]
    conditions = [~df["IsClaim"], r < SIZE_EDGES[0], r < SIZE_EDGES[1], r < SIZE_EDGES[2]]
    return pd.Series(np.select(conditions, CLASS_ORDER[:4], default=CLASS_ORDER[4]), index=df.index)


def actual_vs_expected(seg_result: dict) -> list[dict]:
    """
    Expected = segment policies x PORTFOLIO rate (i.e. 'if this segment behaved like the whole portfolio').
    Reported for claim counts and claim cost; significance from a z-test on claim counts.
    """
    segs = seg_result["segments"]
    tot_n = sum(s["policies"] for s in segs)
    tot_cost = sum(s["total_claim_amount"] for s in segs)
    port_rate = seg_result["portfolio_claim_frequency"]
    port_cost_per_policy = tot_cost / tot_n if tot_n else None
    rows = []
    for s in segs:
        z = z_test_vs_expected(s["claiming_policies"], s["policies"], port_rate)
        exp_cost = None if port_cost_per_policy is None else s["policies"] * port_cost_per_policy
        rows.append({
            "segment": s["segment"], "policies": s["policies"],
            "actual_claims": s["claiming_policies"], "expected_claims": z["expected_claims"],
            "actual_to_expected_claims": z["actual_to_expected"], "z_score": z["z_score"],
            "p_value": z["p_value"], "significant_at_5pct": z["significant_at_5pct"],
            "actual_claim_cost": s["total_claim_amount"],
            "expected_claim_cost": None if exp_cost is None else round(exp_cost, 2),
            "actual_to_expected_cost": None if not exp_cost else round(s["total_claim_amount"] / exp_cost, 6),
        })
    return rows


def risk_segments(df: pd.DataFrame) -> dict:
    work = df.assign(RiskTier=assign_apriori_tier(df), ClaimClass=assign_claim_class(df))

    tiers = A.segment_analytics(work, "RiskTier", order=TIER_ORDER)
    tier_tests = segment_significance(work, "RiskTier", order=TIER_ORDER)
    ave = actual_vs_expected(tiers)

    classes = A.segment_analytics(work, "ClaimClass", order=CLASS_ORDER)
    class_rows = [{
        "class": s["segment"], "policies": s["policies"], "share_of_policies": s["share_of_policies"],
        "total_claim_amount": s["total_claim_amount"], "share_of_claim_amount": s["share_of_claim_amount"],
        "average_claim_amount": s["claim_severity"], "settled_claims": s["settled_claims"],
        "pending_claims": s["pending_claims"],
    } for s in classes["segments"]]

    freq_p = tier_tests["claim_frequency"]
    supported = bool(freq_p.get("computable") and freq_p.get("significant_at_5pct"))
    return {
        "rules": RULES,
        "a_priori_tiers": tiers["segments"],
        "portfolio_claim_frequency": tiers["portfolio_claim_frequency"],
        "tier_significance": tier_tests,
        "actual_vs_expected": ave,
        "tiers_supported_by_experience": supported,
        "conclusion": (
            "Observed claim frequency differs between a-priori tiers by more than chance would explain."
            if supported else
            "Observed claim experience does NOT significantly differ between the a-priori tiers, so the tiers are "
            "a rule-based classification only and should not be read as evidence of different underlying risk."),
        "claim_experience_classes": class_rows,
        "notes": tiers["notes"],
    }
