"""FastAPI dependencies: data access, filter parsing/validation and the filtered 'scope' every endpoint works on."""
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import Depends, HTTPException, Query

from app.services import report_service as RS
from app.services.data_repository import DataRepository, DataUnavailableError, get_repository
from app.services.filters import FilterSpec, FilterValidationError, apply_filters, resolve_filters

AgeBandLiteral = Literal["18-25", "26-35", "36-45", "46-55", "56-65", "66-75", "76+"]
ClaimStatusLiteral = Literal["Settled", "Pending", "Rejected"]
DateBasisLiteral = Literal["policy_start", "claim_date"]


@dataclass
class Scope:
    repo: DataRepository
    full_df: pd.DataFrame
    df: pd.DataFrame
    spec: FilterSpec
    warnings: list[str]
    rate_metrics_valid: bool

    def envelope(self, data) -> dict:
        meta = RS.build_meta(source=self.repo.source, spec=self.spec, full_df=self.full_df, scoped_df=self.df,
                             warnings=self.warnings, rate_metrics_valid=self.rate_metrics_valid)
        return {"meta": meta, "data": data}


def get_repo(repo: DataRepository = Depends(get_repository)) -> DataRepository:
    try:
        repo.load()
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return repo


def get_filter_spec(
    policy_type: str | None = Query(None, description="e.g. Auto, Health, Home, Life, Travel (case-insensitive)"),
    gender: str | None = Query(None, description="e.g. Male, Female (case-insensitive)"),
    age_band: AgeBandLiteral | None = Query(None, description="Age band"),
    claim_status: ClaimStatusLiteral | None = Query(
        None, description="Selecting on claim outcome makes frequency/loss-ratio metrics invalid (flagged in meta)."),
    start_date: date | None = Query(None, description="Inclusive, YYYY-MM-DD"),
    end_date: date | None = Query(None, description="Inclusive, YYYY-MM-DD"),
    date_basis: DateBasisLiteral = Query(
        "policy_start", description="Which date the range applies to: policy start (whole cohort, default) or claim date."),
) -> FilterSpec:
    return FilterSpec(policy_type=policy_type, gender=gender, age_band=age_band, claim_status=claim_status,
                      start_date=start_date, end_date=end_date, date_basis=date_basis)


def scope_from_spec(repo: DataRepository, spec: FilterSpec) -> Scope:
    full = repo.df
    try:
        resolved = resolve_filters(full, spec)
    except FilterValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scoped, warnings, valid = apply_filters(full, resolved)
    return Scope(repo=repo, full_df=full, df=scoped, spec=resolved, warnings=warnings, rate_metrics_valid=valid)


def get_scope(spec: FilterSpec = Depends(get_filter_spec), repo: DataRepository = Depends(get_repo)) -> Scope:
    return scope_from_spec(repo, spec)
