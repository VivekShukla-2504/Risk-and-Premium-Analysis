"""Baseline experience rate indications by portfolio segment; descriptive, not a forecast."""
from __future__ import annotations

import math

import pandas as pd

from app.services import analytics_service as A
from app.services.data_loader import AGE_BAND_LABELS

DEFAULT_TARGET_LOSS_RATIO_PCT = 65.0
MIN_TARGET_LOSS_RATIO_PCT = 30.0
MAX_TARGET_LOSS_RATIO_PCT = 100.0

FORMULAS = {
    "observed_pure_premium": "incurred claims / policies",
    "credibility_factor": "min(1, sqrt(segment claiming policies / 1,082))",
    "indicated_pure_premium": (
        "credibility factor x segment observed pure premium "
        "+ (1 - credibility factor) x filtered portfolio pure premium"
    ),
    "indicated_earned_premium_per_policy": (
        "indicated pure premium / target loss ratio"
    ),
    "indicated_rate_change_pct": (
        "(indicated earned premium per policy / current earned premium per policy - 1) x 100"
    ),
}

DISCLAIMER = (
    "Descriptive rate indication from synthetic historical experience. It is not a forecast, filed rate, "
    "or production pricing recommendation."
)

NOTES = [
    "Incurred claims are settled paid amounts plus pending outstanding estimates; future claims after the valuation date are excluded.",
    "Earned premium is the project's pro-rata daily proxy as of the configured valuation date.",
    "Credibility uses the project's classical limited-fluctuation claim-count standard of 1,082 claims (90% probability and +/-5% error). "
    "The portfolio experience is the complement; this is a simple internal credibility blend, not a Bühlmann model.",
    "The credibility factor is based on claim count only. It does not model claim severity variance, trend, development, expenses, profit, "
    "tax, reinsurance, capital, or IBNR.",
    "Segment indications are separate comparisons to the current average earned premium per policy. Do not add indications across dimensions.",
    "The filtered-portfolio row is the unblended reference experience; its credibility factor is not applicable.",
    "The data is synthetic, and indicated changes can be extreme or statistically unstable. Review credibility and existing segment tests "
    "before using the figures for decisions.",
]


class RateIndicationError(ValueError):
    """A rate indication request has an invalid target assumption."""


def _validate_target(target_loss_ratio_pct: float) -> float:
    try:
        target = float(target_loss_ratio_pct)
    except (TypeError, ValueError) as exc:
        raise RateIndicationError("target_loss_ratio_pct must be a finite percentage.") from exc
    if not math.isfinite(target) or not MIN_TARGET_LOSS_RATIO_PCT <= target <= MAX_TARGET_LOSS_RATIO_PCT:
        raise RateIndicationError(
            f"target_loss_ratio_pct must be between {MIN_TARGET_LOSS_RATIO_PCT:g} and "
            f"{MAX_TARGET_LOSS_RATIO_PCT:g} (got {target_loss_ratio_pct})."
        )
    return target / 100


def _row(
    sums: dict,
    *,
    name: str,
    dimension: str,
    portfolio_pure_premium: float | None,
    target_loss_ratio: float,
    overall: bool = False,
) -> dict:
    policies = sums["policies"]
    claims = sums["claims"]
    incurred = sums["incurred"]
    earned = sums["earned"]
    observed_pure_premium = None if policies == 0 else incurred / policies
    current_earned_premium_per_policy = None if policies == 0 else earned / policies
    observed_loss_ratio = None if earned <= 0 else incurred / earned
    credibility = None if overall else min(1.0, math.sqrt(claims / A.FULL_CREDIBILITY_CLAIMS))
    indication_available = False
    reason = None
    indicated_pure_premium = None
    required_earned_premium_per_policy = None
    indicated_rate_change_pct = None

    if policies == 0:
        reason = "No policies are available in this group."
    elif portfolio_pure_premium is None:
        indication_available = False
        reason = "No payable claims are available in the filtered portfolio to establish an experience basis."
    else:
        group_pure_premium = observed_pure_premium or 0.0
        indicated_pure_premium = (
            group_pure_premium if overall
            else credibility * group_pure_premium + (1 - credibility) * portfolio_pure_premium
        )
        required_earned_premium_per_policy = indicated_pure_premium / target_loss_ratio
        if current_earned_premium_per_policy is None or current_earned_premium_per_policy <= 0:
            reason = "Current earned premium per policy is zero, so a percentage rate change is undefined."
        else:
            indication_available = True
            indicated_rate_change_pct = (required_earned_premium_per_policy / current_earned_premium_per_policy - 1) * 100

    return {
        "dimension": dimension,
        "segment": name,
        "policies": policies,
        "claiming_policies": claims,
        "incurred_claims": round(incurred, 2),
        "earned_premium": round(earned, 2),
        "observed_loss_ratio": None if observed_loss_ratio is None else round(observed_loss_ratio, 6),
        "observed_pure_premium_per_policy": (
            None if observed_pure_premium is None else round(observed_pure_premium, 2)
        ),
        "credibility_factor": None if credibility is None else round(credibility, 6),
        "credibility_factor_note": (
            "Unblended filtered-portfolio reference; credibility factor is not applicable."
            if overall else "Segment claim-count credibility blended with filtered-portfolio pure premium."
        ),
        "indicated_pure_premium_per_policy": (
            None if indicated_pure_premium is None else round(indicated_pure_premium, 2)
        ),
        "current_earned_premium_per_policy": (
            None if current_earned_premium_per_policy is None else round(current_earned_premium_per_policy, 2)
        ),
        "indicated_earned_premium_per_policy": (
            None if required_earned_premium_per_policy is None else round(required_earned_premium_per_policy, 2)
        ),
        "indicated_rate_change_pct": (
            None if indicated_rate_change_pct is None else round(indicated_rate_change_pct, 2)
        ),
        "indication_available": indication_available,
        "unavailable_reason": reason,
    }


def rate_indication_report(df: pd.DataFrame, target_loss_ratio_pct: float = DEFAULT_TARGET_LOSS_RATIO_PCT) -> dict:
    """Build overall and credibility-weighted indications by policy type, age band and gender."""
    target = _validate_target(target_loss_ratio_pct)
    total = A._sums(df)
    portfolio_pure_premium = (
        None if total["policies"] == 0 or total["claims"] == 0
        else total["incurred"] / total["policies"]
    )

    overall = None
    dimensions: dict[str, list[dict]] = {
        "by_policy_type": [],
        "by_age_band": [],
        "by_gender": [],
    }
    if total["policies"]:
        overall = _row(
            total,
            name="Filtered portfolio",
            dimension="portfolio",
            portfolio_pure_premium=portfolio_pure_premium,
            target_loss_ratio=target,
            overall=True,
        )
        for key, column, order in (
            ("by_policy_type", "PolicyType", None),
            ("by_age_band", "AgeBand", AGE_BAND_LABELS),
            ("by_gender", "Gender", None),
        ):
            segments = A.segment_analytics(df, column, order=order)["segments"]
            dimensions[key] = [
                _row(
                    {
                        "policies": segment["policies"],
                        "claims": segment["claiming_policies"],
                        "incurred": segment["total_claim_amount"],
                        "earned": segment["total_earned_premium"],
                    },
                    name=str(segment["segment"]),
                    dimension=column,
                    portfolio_pure_premium=portfolio_pure_premium,
                    target_loss_ratio=target,
                )
                for segment in segments
                if segment["policies"] > 0
            ]

    return {
        "available": bool(overall and overall["indication_available"]),
        "unavailable_reason": (
            overall["unavailable_reason"] if overall and not overall["indication_available"]
            else "No policies are available in the filtered portfolio." if overall is None
            else None
        ),
        "overall": overall,
        **dimensions,
        "assumptions": {
            "target_loss_ratio_pct": round(target * 100, 2),
            "credibility_standard_claims": A.FULL_CREDIBILITY_CLAIMS,
            "credibility_standard_basis": "Classical limited-fluctuation standard: 90% probability and +/-5% error.",
            "portfolio_prior": "The experience pure premium of the filtered portfolio.",
            "indication_basis": "Incurred claims and earned premium per policy, both evaluated as of the valuation date.",
        },
        "formulas": FORMULAS,
        "disclaimer": DISCLAIMER,
        "notes": NOTES,
    }
