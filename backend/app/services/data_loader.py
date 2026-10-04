"""
Data loading and cleaning.

Every rule here is derived from the dataset audit (see docs/DATA_AUDIT.md) and is
deliberately conservative: rows are only dropped when they are exact duplicates or are
unusable (unparseable/invalid core fields). Suspicious-but-usable rows are kept and
*reported* by the audit service instead of being silently altered.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constants (documented assumptions)
# --------------------------------------------------------------------------- #
REQUIRED_COLUMNS = [
    "PolicyNumber", "CustomerID", "Gender", "Age", "PolicyType",
    "PolicyStartDate", "PolicyEndDate", "PremiumAmount", "CoverageAmount",
    "ClaimNumber", "ClaimDate", "ClaimAmount", "ClaimStatus",
]

DATE_FORMAT = "%d-%m-%Y"  # dataset uses DD-MM-YYYY; parsed strictly, never guessed

# Age bands: edges are (lower-exclusive, upper-inclusive]. Dataset age range is 18-87.
AGE_BAND_EDGES = [17, 25, 35, 45, 55, 65, 75, 200]
AGE_BAND_LABELS = ["18-25", "26-35", "36-45", "46-55", "56-65", "66-75", "76+"]

# How each ClaimStatus is treated in the cost calculations.
#   Settled  -> claim is real, amount is PAID.
#   Pending  -> claim is real, amount is treated as a case-reserve ESTIMATE (outstanding).
#   Rejected -> claim is not payable; contributes 0 to incurred cost.
# "Incurred" = Paid + Outstanding (Settled + Pending). This is a simplification: no IBNR
# (incurred-but-not-reported) provision is possible with this data.
CLAIM_STATUS_TREATMENT = {
    "Settled": {"counts_as_claim": True, "paid": True, "incurred": True},
    "Pending": {"counts_as_claim": True, "paid": False, "incurred": True},
    "Rejected": {"counts_as_claim": False, "paid": False, "incurred": False},
}


class DataValidationError(ValueError):
    """Raised when the input file cannot be used at all (e.g. missing columns)."""


@dataclass
class CleaningReport:
    rows_raw: int = 0
    rows_clean: int = 0
    exact_duplicate_rows_removed: int = 0
    conflicting_policy_rows_removed: int = 0
    rows_dropped_invalid: dict[str, int] = field(default_factory=dict)
    claim_dates_unparseable: int = 0
    unknown_claim_statuses: int = 0
    valuation_date: str = ""
    valuation_date_source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_raw_csv(path: str | Path) -> pd.DataFrame:
    """Read the CSV with everything as text so we control every conversion."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"CSV is missing required columns: {missing}")
    return df[REQUIRED_COLUMNS].copy()


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def clean_data(raw: pd.DataFrame, valuation_date: str | None = None) -> tuple[pd.DataFrame, CleaningReport]:
    """Validate, de-duplicate and enrich the raw data. Returns (clean_df, report)."""
    report = CleaningReport(rows_raw=len(raw))
    df = raw.copy()

    # 1. Trim whitespace in text columns; blank strings become missing.
    for col in ["PolicyNumber", "CustomerID", "Gender", "PolicyType", "ClaimNumber", "ClaimStatus"]:
        df[col] = df[col].str.strip()
    df = df.replace({"": np.nan})

    # 2. Duplicates. Exact duplicate rows are removed. If the same PolicyNumber still
    #    appears with different content, keep the first and report it (cannot know which is right).
    before = len(df)
    df = df.drop_duplicates()
    report.exact_duplicate_rows_removed = before - len(df)
    before = len(df)
    df = df.drop_duplicates(subset="PolicyNumber", keep="first")
    report.conflicting_policy_rows_removed = before - len(df)

    # 3. Numeric validation. Non-numeric text becomes NaN, then rule checks are applied.
    for col in ["Age", "PremiumAmount", "CoverageAmount", "ClaimAmount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 4. Strict date parsing (DD-MM-YYYY). Unparseable policy dates make a row unusable.
    for col in ["PolicyStartDate", "PolicyEndDate", "ClaimDate"]:
        df[col] = pd.to_datetime(df[col], format=DATE_FORMAT, errors="coerce")

    invalid = {
        "missing_or_invalid_age": df["Age"].isna() | (df["Age"] < 0) | (df["Age"] > 120),
        "missing_or_nonpositive_premium": df["PremiumAmount"].isna() | (df["PremiumAmount"] <= 0),
        "missing_or_nonpositive_coverage": df["CoverageAmount"].isna() | (df["CoverageAmount"] <= 0),
        "missing_or_negative_claim_amount": df["ClaimAmount"].isna() | (df["ClaimAmount"] < 0),
        "invalid_policy_dates": df["PolicyStartDate"].isna() | df["PolicyEndDate"].isna()
        | (df["PolicyEndDate"] <= df["PolicyStartDate"]),
        "missing_key_text_fields": df[["PolicyNumber", "PolicyType", "ClaimStatus"]].isna().any(axis=1),
    }
    drop_mask = pd.Series(False, index=df.index)
    for reason, mask in invalid.items():
        report.rows_dropped_invalid[reason] = int(mask.sum())
        drop_mask |= mask
    df = df.loc[~drop_mask].copy()

    # ClaimDate is legitimately blank for policies without a claim. Count only the
    # values that were *present* in the raw file but failed to parse.
    raw_claim_present = raw.loc[df.index, "ClaimDate"].astype("string").str.strip().replace("", pd.NA).notna()
    report.claim_dates_unparseable = int((raw_claim_present & df["ClaimDate"].isna()).sum())

    # 5. Claim status handling.
    known = set(CLAIM_STATUS_TREATMENT)
    report.unknown_claim_statuses = int((~df["ClaimStatus"].isin(known)).sum())

    # 6. Resolve the analysis cut-off before deriving claim experience.
    val_ts, source = _resolve_valuation_date(df, valuation_date)

    # 7. Derived columns used by every later analytics phase.
    df["AgeBand"] = pd.cut(df["Age"], bins=AGE_BAND_EDGES, labels=AGE_BAND_LABELS)
    df = _apply_valuation_date(df, val_ts)

    report.valuation_date = val_ts.strftime("%Y-%m-%d")
    report.valuation_date_source = source
    report.rows_clean = len(df)
    df = df.reset_index(drop=True)
    df.attrs["valuation_date"] = report.valuation_date
    return df, report


def _resolve_valuation_date(df: pd.DataFrame, configured: str | None) -> tuple[pd.Timestamp, str]:
    if configured:
        try:
            val_ts = pd.Timestamp(configured)
            if val_ts.strftime("%Y-%m-%d") != configured:
                raise ValueError
            return val_ts, "configured via VALUATION_DATE"
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"VALUATION_DATE must be YYYY-MM-DD, got {configured!r}") from exc
    if df["ClaimDate"].notna().any():
        return df["ClaimDate"].max(), "latest ClaimDate in the data (data cut-off proxy)"
    return df["PolicyEndDate"].max(), "latest PolicyEndDate (no claim dates available)"


def _apply_valuation_date(df: pd.DataFrame, val_ts: pd.Timestamp) -> pd.DataFrame:
    """Recompute every time-dependent derived field on the same as-of date."""
    out = df.copy()
    term_days = (out["PolicyEndDate"] - out["PolicyStartDate"]).dt.days
    elapsed = (val_ts - out["PolicyStartDate"]).dt.days.clip(lower=0)
    observed_by_valuation = out["ClaimDate"].notna() & (out["ClaimDate"] <= val_ts)
    counts = out["ClaimStatus"].map(lambda s: CLAIM_STATUS_TREATMENT.get(s, {}).get("counts_as_claim", False))
    paid = out["ClaimStatus"].map(lambda s: CLAIM_STATUS_TREATMENT.get(s, {}).get("paid", False))
    incurred = out["ClaimStatus"].map(lambda s: CLAIM_STATUS_TREATMENT.get(s, {}).get("incurred", False))
    future_claim = counts.astype(bool) & (out["ClaimAmount"] > 0) & out["ClaimDate"].notna() & (out["ClaimDate"] > val_ts)

    out["TermDays"] = term_days
    out["EarnedFraction"] = (elapsed / term_days).clip(upper=1.0)
    out["EarnedPremium"] = out["PremiumAmount"] * out["EarnedFraction"]
    out["ClaimStatusAsOf"] = out["ClaimStatus"].where(~future_claim, "Not yet occurred as of valuation date")
    out["IsClaim"] = counts.astype(bool) & (out["ClaimAmount"] > 0) & observed_by_valuation
    out["IncurredAmount"] = np.where(incurred.astype(bool) & observed_by_valuation, out["ClaimAmount"], 0.0)
    out["PaidAmount"] = np.where(paid.astype(bool) & observed_by_valuation, out["ClaimAmount"], 0.0)
    out["OutstandingAmount"] = out["IncurredAmount"] - out["PaidAmount"]
    out["ClaimToCoverage"] = np.where(out["IsClaim"], out["IncurredAmount"] / out["CoverageAmount"], 0.0)
    out["ClaimMonth"] = out["ClaimDate"].where(observed_by_valuation).dt.to_period("M").dt.to_timestamp()
    out.attrs["valuation_date"] = val_ts.strftime("%Y-%m-%d")
    return out


def load_clean_dataset(path: str | Path, valuation_date: str | None = None) -> tuple[pd.DataFrame, CleaningReport]:
    """Convenience wrapper used by routes and scripts."""
    return clean_data(load_raw_csv(path), valuation_date)


CLEANED_DATE_COLUMNS = ["PolicyStartDate", "PolicyEndDate", "ClaimDate", "ClaimMonth"]
CLEANED_REQUIRED_COLUMNS = REQUIRED_COLUMNS + [
    "AgeBand", "IsClaim", "IncurredAmount", "PaidAmount", "OutstandingAmount",
    "ClaimToCoverage", "ClaimMonth", "TermDays", "EarnedFraction", "EarnedPremium",
]
_CLEANED_NUMERIC = ["Age", "PremiumAmount", "CoverageAmount", "ClaimAmount", "IncurredAmount", "PaidAmount",
                    "OutstandingAmount", "ClaimToCoverage", "TermDays", "EarnedFraction", "EarnedPremium"]


def normalize_cleaned_frame(df: pd.DataFrame, valuation_date: str | None = None) -> pd.DataFrame:
    """
    Give a cleaned-data frame (from CSV or MongoDB) the exact types the analytics service expects.
    Raises DataValidationError if the derived columns are missing.
    """
    missing = [c for c in CLEANED_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"Cleaned data is missing columns: {missing}. Re-run scripts/audit_dataset.py --save-clean")
    out = df[CLEANED_REQUIRED_COLUMNS].copy()
    for col in CLEANED_DATE_COLUMNS:
        out[col] = pd.to_datetime(out[col], errors="coerce")
    for col in _CLEANED_NUMERIC:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if out[_CLEANED_NUMERIC].isna().any().any():
        raise DataValidationError("Cleaned data contains non-numeric values in numeric columns")
    out["AgeBand"] = pd.Categorical(out["AgeBand"], categories=AGE_BAND_LABELS, ordered=True)
    out["IsClaim"] = out["IsClaim"].astype(str).str.lower().isin(["true", "1"])
    out = out.reset_index(drop=True)
    val_ts, _ = _resolve_valuation_date(out, valuation_date)
    return _apply_valuation_date(out, val_ts)


def read_cleaned_csv(path: str | Path, valuation_date: str | None = None) -> pd.DataFrame:
    """Read backend/data/cleaned_insurance_data.csv back with correct types (ISO dates)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cleaned data file not found: {path}")
    return normalize_cleaned_frame(pd.read_csv(path), valuation_date)
