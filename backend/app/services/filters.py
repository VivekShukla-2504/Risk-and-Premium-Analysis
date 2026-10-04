"""
Dashboard filters.

Date-range semantics matter statistically:
  * date_basis = "policy_start" (default): keep policies that STARTED in the range, together with all of their
    claims. Frequency, loss ratio and pure premium stay valid (a cohort view).
  * date_basis = "claim_date": keep only policies whose CLAIM falls in the range. Policies without a claim have
    no ClaimDate, so they vanish and rate metrics (frequency, loss ratio, pure premium) are no longer valid.
    Use it for amounts and trends only.
Filtering on ClaimStatus also selects on the outcome and invalidates rate metrics. Both cases are flagged.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass

import pandas as pd

from app.services.data_loader import AGE_BAND_LABELS, CLAIM_STATUS_TREATMENT

DATE_BASES = ("policy_start", "claim_date")
MIN_CLAIMS_FOR_STABLE_RESULTS = 30  # rule of thumb for this project, not an actuarial standard


class FilterValidationError(ValueError):
    """A filter value is not valid for this dataset."""


@dataclass(frozen=True)
class FilterSpec:
    policy_type: str | None = None
    gender: str | None = None
    age_band: str | None = None
    claim_status: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    date_basis: str = "policy_start"

    def applied(self) -> dict:
        """Only the filters actually in force (JSON-friendly)."""
        out = {}
        for k, v in asdict(self).items():
            if k == "date_basis":
                if self.start_date or self.end_date:
                    out[k] = v
            elif v is not None:
                out[k] = v.isoformat() if isinstance(v, dt.date) else v
        return out


def _match(value: str | None, allowed: list[str], label: str) -> str | None:
    if value is None:
        return None
    lookup = {a.lower(): a for a in allowed}
    hit = lookup.get(str(value).strip().lower())
    if hit is None:
        raise FilterValidationError(f"Invalid {label} '{value}'. Allowed values: {sorted(allowed)}")
    return hit


def resolve_filters(df: pd.DataFrame, spec: FilterSpec) -> FilterSpec:
    """Validate a spec against the dataset and normalise capitalisation."""
    if spec.date_basis not in DATE_BASES:
        raise FilterValidationError(f"Invalid date_basis '{spec.date_basis}'. Allowed values: {list(DATE_BASES)}")
    if spec.start_date and spec.end_date and spec.start_date > spec.end_date:
        raise FilterValidationError("start_date must be on or before end_date")
    return FilterSpec(
        policy_type=_match(spec.policy_type, df["PolicyType"].dropna().unique().tolist(), "policy_type"),
        gender=_match(spec.gender, df["Gender"].dropna().unique().tolist(), "gender"),
        age_band=_match(spec.age_band, AGE_BAND_LABELS, "age_band"),
        claim_status=_match(spec.claim_status, list(CLAIM_STATUS_TREATMENT), "claim_status"),
        start_date=spec.start_date, end_date=spec.end_date, date_basis=spec.date_basis,
    )


def apply_filters(df: pd.DataFrame, spec: FilterSpec) -> tuple[pd.DataFrame, list[str], bool]:
    """
    Returns (filtered_df, warnings, rate_metrics_valid).
    ``spec`` should already have been through ``resolve_filters``.
    """
    mask = pd.Series(True, index=df.index)
    if spec.policy_type:
        mask &= df["PolicyType"] == spec.policy_type
    if spec.gender:
        mask &= df["Gender"] == spec.gender
    if spec.age_band:
        mask &= df["AgeBand"].astype(str) == spec.age_band
    if spec.claim_status:
        status_col = "ClaimStatusAsOf" if "ClaimStatusAsOf" in df.columns else "ClaimStatus"
        mask &= df[status_col] == spec.claim_status

    date_col = "PolicyStartDate" if spec.date_basis == "policy_start" else "ClaimDate"
    if spec.start_date:
        mask &= df[date_col] >= pd.Timestamp(spec.start_date)
    if spec.end_date:
        mask &= df[date_col] <= pd.Timestamp(spec.end_date)
    if (spec.start_date or spec.end_date) and spec.date_basis == "claim_date":
        mask &= df["ClaimDate"].notna()

    out = df[mask].copy()
    out.attrs = dict(df.attrs)

    warnings: list[str] = []
    valid = True
    if spec.claim_status:
        valid = False
        warnings.append(
            "Filtering by claim_status selects policies on their claim outcome, so claim frequency, pure premium and "
            "loss ratio are not meaningful for this subset (e.g. 'Settled' only gives 100% frequency).")
    if (spec.start_date or spec.end_date) and spec.date_basis == "claim_date":
        valid = False
        warnings.append(
            "date_basis=claim_date keeps only policies with a claim in the range; policies without claims are "
            "excluded, so frequency, pure premium and loss ratio are not meaningful. Use for amounts and trends only.")
    if len(out) == 0:
        warnings.append("No policies match the selected filters.")
    elif int(out["IsClaim"].sum()) < MIN_CLAIMS_FOR_STABLE_RESULTS:
        warnings.append(
            f"Fewer than {MIN_CLAIMS_FOR_STABLE_RESULTS} claims in scope: results are statistically unreliable.")
    return out, warnings, valid


def filter_options(df: pd.DataFrame) -> dict:
    """Values for the dashboard's filter controls (computed from the unfiltered data)."""
    def rng(col):
        s = df[col].dropna()
        return None if s.empty else [s.min().strftime("%Y-%m-%d"), s.max().strftime("%Y-%m-%d")]
    return {
        "policy_type": sorted(df["PolicyType"].dropna().unique().tolist()),
        "gender": sorted(df["Gender"].dropna().unique().tolist()),
        "age_band": list(AGE_BAND_LABELS),
        "claim_status": list(CLAIM_STATUS_TREATMENT),
        "date_basis": list(DATE_BASES),
        "policy_start_date_range": rng("PolicyStartDate"),
        "claim_date_range": rng("ClaimDate"),
    }
