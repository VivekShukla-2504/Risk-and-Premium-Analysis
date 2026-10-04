from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from app.dependencies import Scope, get_repo, get_scope, scope_from_spec
from app.schemas.common import AnalyticsResponse
from app.schemas.scenario import ScenarioRequest
from app.services import report_service as RS
from app.services.data_repository import DataRepository
from app.services.filters import FilterSpec, filter_options
from app.services import rate_indication_service as RI
from app.services.scenario_service import ScenarioError, compare_scenarios, compute_scenario
from app.utils.serialization import to_builtin

router = APIRouter(prefix="/analytics", tags=["Analytics"])

COMMON = {422: {"description": "Invalid filter or input"}, 503: {"description": "No data source available"}}
ExportSection = Literal["summary", "policy-types", "age-bands", "gender", "claim-status", "monthly",
                        "risk-segments", "policies", "rate-indication", "full"]


@router.get("/policy-types", response_model=AnalyticsResponse, responses=COMMON,
            summary="Metrics by policy type, with significance tests and actual-vs-expected")
def policy_types(scope: Scope = Depends(get_scope)) -> dict:
    """Frequency, severity, pure premium and loss ratio per policy type, 95% intervals, credibility factor,
    a chi-square test (claim rate) and ANOVA (claim size), and actual vs expected claims against the portfolio rate."""
    return scope.envelope(RS.policy_types_report(scope.df))


@router.get("/age-bands", response_model=AnalyticsResponse, responses=COMMON,
            summary="Metrics by age band (18-25 ... 76+)")
def age_bands(scope: Scope = Depends(get_scope)) -> dict:
    """Same measures as `/policy-types`, by age band. Empty bands are returned with null metrics."""
    return scope.envelope(RS.age_bands_report(scope.df))


@router.get("/claims", response_model=AnalyticsResponse, responses=COMMON,
            summary="Claim status, coverage-vs-claim analysis and claim-to-coverage ratios")
def claims(
    include_points: bool = Query(False, description="Add a deterministic sample of claims for scatter charts"),
    max_points: int = Query(500, ge=1, le=5000, description="Sample size when include_points=true"),
    scope: Scope = Depends(get_scope),
) -> dict:
    """Status breakdown (Settled / Pending / Rejected, with paid and outstanding amounts), coverage bands of 10,000,
    correlations of premium and claim size with coverage, and claim-to-coverage statistics."""
    return scope.envelope(RS.claims_report(scope.df, include_points, max_points))


@router.get("/loss-ratio", response_model=AnalyticsResponse, responses=COMMON, summary="Loss ratio and its drivers")
def loss_ratio(scope: Scope = Depends(get_scope)) -> dict:
    """**Loss ratio = incurred claims / earned premium.** Incurred = Settled + Pending. Also returns the paid-only ratio
    and, for illustration only, the ratio on written premium. Broken down by policy type, age band and gender."""
    return scope.envelope(RS.loss_ratio_report(scope.df))


@router.get("/severity", response_model=AnalyticsResponse, responses=COMMON, summary="Claim severity distribution and breakdowns")
def severity(scope: Scope = Depends(get_scope)) -> dict:
    """**Severity = total claim amount / number of claims.** Mean, median, quantiles, histogram, 95% interval,
    breakdowns by policy type, age band and claim status, and an ANOVA test."""
    return scope.envelope(RS.severity_report(scope.df))


@router.get("/frequency", response_model=AnalyticsResponse, responses=COMMON, summary="Claim frequency with confidence intervals")
def frequency(scope: Scope = Depends(get_scope)) -> dict:
    """**Frequency = claiming policies / policies** (incidence, since each policy has at most one claim), plus the
    exposure-adjusted version per policy-year, with Wilson 95% intervals and chi-square tests."""
    return scope.envelope(RS.frequency_report(scope.df))


@router.get("/monthly-trends", response_model=AnalyticsResponse, responses=COMMON,
            summary="Monthly claims, adjusted for policies in force")
def monthly_trends(scope: Scope = Depends(get_scope)) -> dict:
    """Claims by calendar month beside the exposure (policy-months) in force, giving claims per 100 policy-months.
    Raw counts mostly follow how many policies were active; months with little exposure are flagged."""
    return scope.envelope(RS.monthly_trends_report(scope.df))


@router.get("/risk-segments", response_model=AnalyticsResponse, responses=COMMON,
            summary="Rule-based risk tiers, tested against actual experience")
def risk_segments(scope: Scope = Depends(get_scope)) -> dict:
    """A-priori tiers (Low / Medium / High) from age and coverage rules known before any claim, with actual vs expected
    claims and a significance test, plus descriptive claim-size classes. `data.rules` documents every rule."""
    return scope.envelope(RS.risk_segments_report(scope.df))


def _require_rate_valid_scope(scope: Scope) -> None:
    if not scope.rate_metrics_valid:
        raise HTTPException(
            status_code=422,
            detail="Rate indications require a cohort scope that was not selected by claim outcome. Remove "
                   "claim_status and claim-date filters; they make the baseline experience statistically invalid.",
        )


@router.get("/rate-indication", response_model=AnalyticsResponse, responses=COMMON,
            summary="Credibility-weighted rate adequacy indication by portfolio segment")
def rate_indication(
    target_loss_ratio_pct: float = Query(
        RI.DEFAULT_TARGET_LOSS_RATIO_PCT,
        ge=RI.MIN_TARGET_LOSS_RATIO_PCT,
        le=RI.MAX_TARGET_LOSS_RATIO_PCT,
        description="Target incurred loss ratio, in percent (30 to 100).",
    ),
    scope: Scope = Depends(get_scope),
) -> dict:
    """
    Baseline experience indication, not a what-if scenario. Segment pure premium is credibility-weighted toward
    the filtered portfolio using min(1, sqrt(segment claims / 1,082)); required earned premium per policy is
    indicated pure premium / target loss ratio. Rate indication compares that amount with current earned premium
    per policy. Claim-outcome-selected scopes are rejected.
    """
    _require_rate_valid_scope(scope)
    try:
        result = RI.rate_indication_report(scope.df, target_loss_ratio_pct)
    except RI.RateIndicationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return scope.envelope(result)


def _scenario_response(body: ScenarioRequest, repo: DataRepository, compute) -> dict:
    spec = body.filters.to_spec() if body.filters else FilterSpec()
    scope = scope_from_spec(repo, spec)
    if not scope.rate_metrics_valid:
        raise HTTPException(
            status_code=422,
            detail="Scenarios require a cohort scope that was not selected by claim outcome. Remove claim_status "
                   "and claim-date filters; they make baseline frequency and loss ratio statistically invalid.",
        )
    try:
        result = compute(scope.df, body.to_inputs())
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return scope.envelope(to_builtin(result))


@router.post("/scenario", response_model=AnalyticsResponse, summary="Scenario and sensitivity analysis (one scenario in depth)",
             responses={422: {"description": "Invalid assumptions, filters, or no claims in scope"}, 503: COMMON[503]})
def scenario(body: ScenarioRequest, repo: DataRepository = Depends(get_repo)) -> dict:
    """
    What-if analysis on the observed portfolio. **Not a prediction.**

    `expected claim cost = policies x frequency x severity`, with frequency, severity and inflation adjustments applied
    multiplicatively, and `loss ratio = expected claim cost / adjusted earned premium`.
    Returns base vs scenario, an illustrative underwriting margin, premium needed for a target loss ratio,
    a 5x5 sensitivity grid and an unranked comparison of equal one-at-a-time assumption shocks.
    """
    return _scenario_response(body, repo, compute_scenario)


@router.post("/scenario/compare", response_model=AnalyticsResponse,
             summary="Compare Baseline, Optimistic, Stress and Custom scenarios",
             responses={422: {"description": "Invalid assumptions, filters, or no claims in scope"}, 503: COMMON[503]})
def scenario_compare(body: ScenarioRequest, repo: DataRepository = Depends(get_repo)) -> dict:
    """
    Runs four scenarios on the same portfolio: **Baseline** (no change), **Optimistic** and **Stress** (fixed, illustrative
    assumptions) and **Custom** (the adjustments in the request body). Each scenario returns the baseline claim cost,
    adjusted frequency, severity, expected claim cost, premium and loss ratio, plus a step-by-step explanation with the
    numbers substituted in. **Scenario analysis, not a prediction.**
    """
    return _scenario_response(body, repo, compare_scenarios)


@router.get("/export", summary="Download an analytical report as CSV or JSON",
            responses={200: {"content": {"text/csv": {}, "application/json": {}}}, **COMMON})
def export(
    section: ExportSection = Query("summary", description="Which report section to export"),
    fmt: Literal["csv", "json"] = Query("csv", alias="format", description="csv (single table) or json (includes meta, assumptions)"),
    target_loss_ratio_pct: float = Query(
        RI.DEFAULT_TARGET_LOSS_RATIO_PCT,
        ge=RI.MIN_TARGET_LOSS_RATIO_PCT,
        le=RI.MAX_TARGET_LOSS_RATIO_PCT,
        description="Target loss ratio used for section=rate-indication, in percent.",
    ),
    scope: Scope = Depends(get_scope),
):
    """CSV contains one flat table; JSON also carries filters, warnings and assumptions. `section=full` is JSON only."""
    if section == "full" and fmt == "csv":
        raise HTTPException(status_code=422, detail="section=full is only available as JSON")
    if section == "rate-indication":
        _require_rate_valid_scope(scope)
    headers = {"Content-Disposition": f'attachment; filename="{RS.export_filename(section, fmt)}"'}
    if fmt == "csv":
        return Response(
            content=RS.to_csv(RS.export_table(scope.df, section, target_loss_ratio_pct)),
            media_type="text/csv",
            headers=headers,
        )
    payload = scope.envelope(
        RS.export_json_payload(scope.df, section, filter_options(scope.full_df), target_loss_ratio_pct)
    )
    payload["section"] = section
    return JSONResponse(content=to_builtin(payload), headers=headers)
