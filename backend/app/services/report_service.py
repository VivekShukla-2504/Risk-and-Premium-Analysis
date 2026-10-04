"""
One pure function per API endpoint: DataFrame in, JSON-safe dict out.

Keeping these separate from the FastAPI routes means every number the API returns can be unit-tested
without a web server, and the routes stay a few lines each.
"""
from __future__ import annotations

import datetime as dt
import io
import math

import numpy as np
import pandas as pd

from app.services import analytics_service as A
from app.services import risk_segmentation as R
from app.services import rate_indication_service as RI
from app.services.data_loader import AGE_BAND_LABELS
from app.services.filters import FilterSpec
from app.services.statistics import segment_significance
from app.utils.serialization import to_builtin

DISCLAIMER = ("Educational analytics on SYNTHETIC data. Descriptive results, not predictions or pricing advice; "
              "not production actuarial software.")
COVERAGE_BAND_WIDTH = 10_000

# (key, label, metric, format, note, rate_metric)
# rate_metric = True when the value becomes meaningless if the scope was chosen on claim outcome
KPI_SPEC = [
    ("total_policies", "Total Policies", "policies", "integer", "Unique policies after removing duplicate rows.", False),
    ("total_premium", "Total Premium", "total_premium", "currency", "Written (full-term) premium.", False),
    ("total_coverage", "Total Coverage", "total_coverage", "currency", "Sum of policy coverage limits.", False),
    ("total_claims", "Total Claims", "claiming_policies", "integer", "Policies with a payable claim (Settled + Pending).", False),
    ("total_claim_amount", "Total Claim Amount", "total_claim_amount", "currency", "Incurred = Settled paid + Pending outstanding.", False),
    ("loss_ratio", "Loss Ratio", "loss_ratio", "percent", "Incurred claims / earned premium (pro-rata proxy).", True),
    ("average_claim_severity", "Average Claim Severity", "claim_severity", "currency", "Total claim amount / number of claims.", False),
    ("claim_frequency", "Claim Frequency", "claim_frequency", "percent", "Claiming policies / policies.", True),
]


# --------------------------------------------------------------------------- #
# Envelope
# --------------------------------------------------------------------------- #
def build_meta(*, source: str | None, spec: FilterSpec, full_df: pd.DataFrame, scoped_df: pd.DataFrame,
               warnings: list[str], rate_metrics_valid: bool) -> dict:
    return {
        "data_source": source,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "filters_applied": spec.applied(),
        "policies_total": int(len(full_df)),
        "policies_in_scope": int(len(scoped_df)),
        "claims_in_scope": int(scoped_df["IsClaim"].sum()),
        "rate_metrics_valid": bool(rate_metrics_valid),
        "valuation_date": full_df.attrs.get("valuation_date"),
        "warnings": list(warnings),
        "disclaimer": DISCLAIMER,
    }


def _segment_block(df: pd.DataFrame, column: str, order: list | None = None) -> dict:
    seg = A.segment_analytics(df, column, order=order)
    seg["statistical_tests"] = segment_significance(df, column, order=order)
    seg["actual_vs_expected"] = R.actual_vs_expected(seg)
    return seg


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def dashboard_summary(df: pd.DataFrame, options: dict) -> dict:
    summary = A.portfolio_summary(df)
    m = summary["metrics"]
    kpis = [{"key": key, "label": label, "value": m[src], "format": fmt, "note": note, "rate_metric": rate}
            for key, label, src, fmt, note, rate in KPI_SPEC]
    return to_builtin({
        "kpis": kpis,
        "secondary_metrics": {k: m[k] for k in (
            "total_earned_premium", "total_paid_amount", "total_outstanding_amount", "average_premium",
            "average_coverage", "pure_premium", "paid_loss_ratio", "claim_to_coverage_ratio",
            "claim_to_coverage_aggregate", "coverage_utilization", "exposure_policy_years",
            "claim_frequency_per_exposure_year")},
        "confidence_intervals_95": summary["confidence_intervals_95"],
        "basis": summary["basis"],
        "definitions": {src: A.METRIC_DEFINITIONS[src] for _, _, src, _, _, _ in KPI_SPEC},
        "filter_options": options,
    })


# --------------------------------------------------------------------------- #
# Segment endpoints
# --------------------------------------------------------------------------- #
def policy_types_report(df: pd.DataFrame) -> dict:
    return to_builtin(_segment_block(df, "PolicyType"))


def age_bands_report(df: pd.DataFrame) -> dict:
    return to_builtin(_segment_block(df, "AgeBand", order=AGE_BAND_LABELS))


# --------------------------------------------------------------------------- #
# Claims (status + coverage analysis)
# --------------------------------------------------------------------------- #
def _coverage_band_labels(df: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    lo = int(math.floor(df["CoverageAmount"].min() / COVERAGE_BAND_WIDTH) * COVERAGE_BAND_WIDTH)
    hi = int(math.ceil(df["CoverageAmount"].max() / COVERAGE_BAND_WIDTH) * COVERAGE_BAND_WIDTH)
    if hi == lo:
        hi = lo + COVERAGE_BAND_WIDTH
    edges = list(range(lo, hi + 1, COVERAGE_BAND_WIDTH))
    labels = [f"{a // 1000}k-{b // 1000}k" for a, b in zip(edges[:-1], edges[1:])]
    cut = pd.cut(df["CoverageAmount"], bins=edges, labels=labels, include_lowest=True)
    return cut.astype(str), labels


def _corr(x: pd.Series, y: pd.Series) -> dict:
    n = int(len(x))
    if n < 3 or x.std() == 0 or y.std() == 0:
        return {"n": n, "pearson_r": None, "distinguishable_from_zero": None}
    r = float(np.corrcoef(x, y)[0, 1])
    return {"n": n, "pearson_r": round(r, 4), "distinguishable_from_zero": bool(abs(r) > 1.96 / math.sqrt(n)),
            "rule": "|r| > 1.96 / sqrt(n) (approximate 5% significance)"}


def claims_report(df: pd.DataFrame, include_points: bool = False, max_points: int = 500) -> dict:
    out = {"claim_status": A.claim_status_analytics(df)}

    if len(df):
        bands, labels = _coverage_band_labels(df)
        cov = A.segment_analytics(df.assign(CoverageBand=bands), "CoverageBand", order=labels)
        cov["segments"] = [s for s in cov["segments"] if s["policies"] > 0]
        out["coverage_bands"] = {
            "band_width": COVERAGE_BAND_WIDTH,
            "bands": [{
                "band": s["segment"], "policies": s["policies"], "average_coverage": s["average_coverage"],
                "average_premium": s["average_premium"], "claim_frequency": s["claim_frequency"],
                "average_claim_amount": s["claim_severity"],
                "average_claim_to_coverage": s["claim_to_coverage_ratio"],
                "total_claim_amount": s["total_claim_amount"],
            } for s in cov["segments"]],
            "note": "Coverage bands of 10,000. Use average_premium vs average_coverage for the premium/coverage view and "
                    "average_claim_amount vs average_coverage for the claim/coverage view.",
        }
    else:
        out["coverage_bands"] = {"band_width": COVERAGE_BAND_WIDTH, "bands": [], "note": "No policies in scope."}

    claims = df[df["IsClaim"]]
    out["correlations"] = {
        "premium_vs_coverage": _corr(df["PremiumAmount"], df["CoverageAmount"]),
        "claim_amount_vs_coverage": _corr(claims["IncurredAmount"], claims["CoverageAmount"]),
        "note": "Correlation measures linear association only; |r| near 0 means coverage tells us nothing about premium "
                "or claim size in this data.",
    }
    ctc = claims["ClaimToCoverage"]
    out["claim_to_coverage"] = {
        "claims": int(len(claims)),
        "mean": None if ctc.empty else round(float(ctc.mean()), 6),
        "median": None if ctc.empty else round(float(ctc.median()), 6),
        "max": None if ctc.empty else round(float(ctc.max()), 6),
        "claims_exceeding_coverage": int((claims["IncurredAmount"] > claims["CoverageAmount"]).sum()),
        "definition": A.METRIC_DEFINITIONS["claim_to_coverage_ratio"],
    }
    if include_points:
        pts = claims if len(claims) <= max_points else claims.sample(n=max_points, random_state=42)
        out["points"] = {
            "note": f"Deterministic random sample of up to {max_points} claims (seed 42) for scatter charts.",
            "claims": pts[["PolicyNumber", "PolicyType", "CoverageAmount", "PremiumAmount", "IncurredAmount"]]
            .rename(columns={"IncurredAmount": "ClaimAmount"}).to_dict(orient="records"),
        }
    return to_builtin(out)


# --------------------------------------------------------------------------- #
# Loss ratio / severity / frequency
# --------------------------------------------------------------------------- #
def loss_ratio_report(df: pd.DataFrame) -> dict:
    m = A.portfolio_summary(df)["metrics"]
    written_basis = None
    if m["total_premium"]:
        written_basis = round(m["total_claim_amount"] / m["total_premium"], 6)

    def by(column, order=None):
        return [{"segment": s["segment"], "policies": s["policies"], "total_claim_amount": s["total_claim_amount"],
                 "total_earned_premium": s["total_earned_premium"], "loss_ratio": s["loss_ratio"],
                 "paid_loss_ratio": s["paid_loss_ratio"], "credibility_z": s["credibility_z"]}
                for s in A.segment_analytics(df, column, order=order)["segments"]]

    return to_builtin({
        "portfolio": {
            "loss_ratio": m["loss_ratio"], "paid_loss_ratio": m["paid_loss_ratio"],
            "loss_ratio_on_written_premium": written_basis,
            "total_claim_amount": m["total_claim_amount"], "total_paid_amount": m["total_paid_amount"],
            "total_outstanding_amount": m["total_outstanding_amount"],
            "total_earned_premium": m["total_earned_premium"], "total_premium": m["total_premium"],
        },
        "by_policy_type": by("PolicyType"),
        "by_age_band": by("AgeBand", AGE_BAND_LABELS),
        "by_gender": by("Gender"),
        "definitions": {k: A.METRIC_DEFINITIONS[k] for k in ("loss_ratio", "paid_loss_ratio", "total_earned_premium")},
        "notes": [
            "Headline loss ratio = incurred (Settled + Pending) / earned premium proxy. Paid-only is a lower bound.",
            "'loss_ratio_on_written_premium' is shown only to illustrate why written premium is the wrong denominator.",
            "Values far above 100% are a feature of the synthetic data, not a real-world result.",
            "Differences between segments are mostly random variation here; see the statistical tests on /policy-types and /age-bands.",
        ],
    })


def _severity_stats(values: pd.Series) -> dict:
    v = values.dropna()
    n = int(len(v))
    if n == 0:
        return {"claims": 0, "mean": None, "median": None, "std": None, "cv": None, "min": None, "max": None,
                "ci_95_low": None, "ci_95_high": None}
    mean = float(v.mean())
    std = float(v.std(ddof=1)) if n > 1 else None
    half = None if std is None else 1.96 * std / math.sqrt(n)
    return {"claims": n, "mean": round(mean, 2), "median": round(float(v.median()), 2),
            "std": None if std is None else round(std, 2), "cv": None if not std or mean == 0 else round(std / mean, 4),
            "min": round(float(v.min()), 2), "max": round(float(v.max()), 2),
            "ci_95_low": None if half is None else round(mean - half, 2),
            "ci_95_high": None if half is None else round(mean + half, 2)}


def severity_report(df: pd.DataFrame, bins: int = 10) -> dict:
    claims = df[df["IsClaim"]]
    amounts = claims["IncurredAmount"]

    def by(column, order=None):
        keys = order if order is not None else sorted(claims[column].dropna().unique().tolist())
        return [{"segment": k, **_severity_stats(claims.loc[claims[column] == k, "IncurredAmount"])} for k in keys]

    hist = []
    if len(amounts) > 0 and amounts.max() > amounts.min():
        counts, edges = np.histogram(amounts, bins=bins)
        hist = [{"from": round(float(edges[i]), 2), "to": round(float(edges[i + 1]), 2), "claims": int(counts[i])}
                for i in range(len(counts))]
    quantiles = {} if amounts.empty else {f"p{int(q * 100)}": round(float(amounts.quantile(q)), 2)
                                          for q in (0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)}
    return to_builtin({
        "overall": _severity_stats(amounts),
        "quantiles": quantiles,
        "histogram": hist,
        "by_policy_type": by("PolicyType"),
        "by_age_band": by("AgeBand", AGE_BAND_LABELS),
        "by_claim_status": by("ClaimStatus", ["Settled", "Pending"]),
        "statistical_tests": {"policy_type": segment_significance(df, "PolicyType")["claim_severity"],
                              "age_band": segment_significance(df, "AgeBand", AGE_BAND_LABELS)["claim_severity"]},
        "definition": A.METRIC_DEFINITIONS["claim_severity"],
        "notes": [
            "Severity is computed over claims only (policies without a claim are excluded).",
            "Pending claims are included at their recorded (estimated) amount; 'by_claim_status' separates them.",
            "Claim sizes here are bounded and roughly uniform, with no heavy tail, unlike typical real insurance losses.",
        ],
    })


def frequency_report(df: pd.DataFrame) -> dict:
    summary = A.portfolio_summary(df)
    m = summary["metrics"]

    def by(column, order=None):
        seg = A.segment_analytics(df, column, order=order)
        return {"dimension": column, "segments": [{
            "segment": s["segment"], "policies": s["policies"], "claiming_policies": s["claiming_policies"],
            "claim_frequency": s["claim_frequency"], "ci_95_low": s["claim_frequency_ci_low"],
            "ci_95_high": s["claim_frequency_ci_high"],
            "claim_frequency_per_exposure_year": s["claim_frequency_per_exposure_year"],
            "frequency_index_vs_portfolio": s["frequency_index_vs_portfolio"],
            "ci_includes_portfolio": s["frequency_ci_includes_portfolio"],
            "credibility_z": s["credibility_z"],
        } for s in seg["segments"]], "test": segment_significance(df, column, order=order)["claim_frequency"]}

    return to_builtin({
        "overall": {
            "policies": m["policies"], "claiming_policies": m["claiming_policies"],
            "claim_frequency": m["claim_frequency"],
            "ci_95": summary["confidence_intervals_95"]["claim_frequency"],
            "exposure_policy_years": m["exposure_policy_years"],
            "claim_frequency_per_exposure_year": m["claim_frequency_per_exposure_year"],
        },
        "by_policy_type": by("PolicyType"),
        "by_age_band": by("AgeBand", AGE_BAND_LABELS),
        "by_gender": by("Gender"),
        "definitions": {k: A.METRIC_DEFINITIONS[k] for k in ("claim_frequency", "claim_frequency_per_exposure_year", "exposure_policy_years")},
        "notes": [
            "Frequency is an incidence rate: at most one claim per policy exists in this data.",
            "Rejected policies carry no claim record, so they are counted as 'no claim' and no rejection rate is reported.",
        ],
    })


# --------------------------------------------------------------------------- #
# Monthly trends and risk segments
# --------------------------------------------------------------------------- #
def monthly_trends_report(df: pd.DataFrame) -> dict:
    res = A.monthly_claim_analytics(df)
    reliable = [r for r in res["months"] if not r["low_exposure"] and r["claims_per_100_policy_months"] is not None]
    if reliable:
        rates = np.array([r["claims_per_100_policy_months"] for r in reliable])
        counts = np.array([r["claims"] for r in reliable], dtype=float)
        res["summary"] = {
            "months_total": len(res["months"]), "months_with_adequate_exposure": len(reliable),
            "mean_claims_per_100_policy_months": round(float(rates.mean()), 4),
            "coefficient_of_variation_exposure_adjusted": round(float(rates.std() / rates.mean()), 4),
            "coefficient_of_variation_raw_counts": None if counts.mean() == 0 else round(float(counts.std() / counts.mean()), 4),
            "interpretation": "A much lower variation after exposure adjustment means the swings in raw monthly counts "
                              "come mainly from how many policies were in force, not from changing risk.",
        }
    else:
        res["summary"] = None
    return to_builtin(res)


def risk_segments_report(df: pd.DataFrame) -> dict:
    return to_builtin(R.risk_segments(df))


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
EXPORT_SECTIONS = ("summary", "policy-types", "age-bands", "gender", "claim-status", "monthly", "risk-segments",
                   "policies", "rate-indication", "full")


def _flatten(rows: list[dict]) -> pd.DataFrame:
    flat = pd.json_normalize(rows, sep=".")
    return flat


def export_table(
    df: pd.DataFrame,
    section: str,
    target_loss_ratio_pct: float = RI.DEFAULT_TARGET_LOSS_RATIO_PCT,
) -> pd.DataFrame:
    """Tabular form of a section (used for CSV)."""
    if section == "summary":
        m = A.portfolio_summary(df)["metrics"]
        return pd.DataFrame([{"metric": k, "value": v, "name": A.METRIC_DEFINITIONS[k]["name"],
                              "formula": A.METRIC_DEFINITIONS[k]["formula"]} for k, v in m.items()])
    if section == "policy-types":
        return _flatten(A.segment_analytics(df, "PolicyType")["segments"])
    if section == "age-bands":
        return _flatten(A.segment_analytics(df, "AgeBand", order=AGE_BAND_LABELS)["segments"])
    if section == "gender":
        return _flatten(A.segment_analytics(df, "Gender")["segments"])
    if section == "claim-status":
        rows = A.claim_status_analytics(df)["statuses"]
        return _flatten([{k: v for k, v in r.items() if k != "treatment"} | {f"treatment.{k}": v for k, v in r["treatment"].items()}
                         for r in rows])
    if section == "monthly":
        return _flatten(A.monthly_claim_analytics(df)["months"])
    if section == "risk-segments":
        return _flatten(R.risk_segments(df)["a_priori_tiers"])
    if section == "rate-indication":
        report = RI.rate_indication_report(df, target_loss_ratio_pct)
        rows = []
        if report["overall"] is not None:
            rows.append(report["overall"])
        for dimension in ("by_policy_type", "by_age_band", "by_gender"):
            rows.extend(report[dimension])
        table = pd.DataFrame(rows)
        table["target_loss_ratio_pct"] = report["assumptions"]["target_loss_ratio_pct"]
        table["credibility_standard_claims"] = report["assumptions"]["credibility_standard_claims"]
        table["indicated_rate_change_formula"] = report["formulas"]["indicated_rate_change_pct"]
        return table
    if section == "policies":
        cols = ["PolicyNumber", "Gender", "Age", "AgeBand", "PolicyType", "PolicyStartDate", "PolicyEndDate",
                "PremiumAmount", "EarnedPremium", "CoverageAmount", "ClaimDate", "ClaimStatus", "IsClaim",
                "IncurredAmount", "PaidAmount", "OutstandingAmount", "ClaimToCoverage"]
        out = df[cols].copy()
        out["AgeBand"] = out["AgeBand"].astype(str)
        for c in ("PolicyStartDate", "PolicyEndDate", "ClaimDate"):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
        return out
    raise ValueError(f"Section '{section}' has no tabular form")


def _csv_safe(value):
    """Neutralise spreadsheet formula injection in text cells (=, +, -, @ prefixes)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def to_csv(table: pd.DataFrame) -> str:
    safe = table.copy()
    for col in safe.columns:
        if safe[col].dtype == object or str(safe[col].dtype).startswith("str"):
            safe[col] = safe[col].map(_csv_safe)
    buf = io.StringIO()
    safe.to_csv(buf, index=False)
    return buf.getvalue()


def full_report(df: pd.DataFrame, options: dict) -> dict:
    return to_builtin({
        "summary": dashboard_summary(df, options),
        "policy_types": policy_types_report(df),
        "age_bands": age_bands_report(df),
        "claims": claims_report(df),
        "loss_ratio": loss_ratio_report(df),
        "severity": severity_report(df),
        "frequency": frequency_report(df),
        "monthly_trends": monthly_trends_report(df),
        "risk_segments": risk_segments_report(df),
        "rate_indication": RI.rate_indication_report(df),
        "metric_definitions": A.get_metric_definitions(),
    })


def export_json_payload(
    df: pd.DataFrame,
    section: str,
    options: dict,
    target_loss_ratio_pct: float = RI.DEFAULT_TARGET_LOSS_RATIO_PCT,
) -> dict | list:
    if section == "full":
        return full_report(df, options)
    if section == "summary":
        return to_builtin(A.portfolio_summary(df))
    if section == "rate-indication":
        return to_builtin(RI.rate_indication_report(df, target_loss_ratio_pct))
    table = export_table(df, section, target_loss_ratio_pct)
    return to_builtin(table.where(table.notna(), None).to_dict(orient="records"))


def export_filename(section: str, fmt: str, today: dt.date | None = None) -> str:
    d = (today or dt.date.today()).strftime("%Y%m%d")
    return f"insurance_{section.replace('-', '_')}_{d}.{fmt}"
