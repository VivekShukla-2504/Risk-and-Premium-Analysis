from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' when data is loaded, otherwise 'degraded'")
    data_loaded: bool
    data_source: str | None = Field(None, description="mongodb | cleaned_csv | raw_csv_pipeline")
    rows: int | None = None
    valuation_date: str | None = Field(None, description="As-of date used for the earned-premium proxy")
    mongodb_configured: bool
    mongodb_error: str | None = Field(None, description="Why MongoDB was skipped, if it was (never contains credentials)")
    error: str | None = None


class ResponseMeta(BaseModel):
    data_source: str | None
    generated_at: datetime
    filters_applied: dict[str, Any] = Field(description="Only the filters actually in force")
    policies_total: int
    policies_in_scope: int
    claims_in_scope: int
    rate_metrics_valid: bool = Field(
        description="False when the filters select on claim outcome (claim_status, or date_basis=claim_date), which "
                    "makes frequency, pure premium and loss ratio statistically meaningless.")
    valuation_date: str | None
    warnings: list[str]
    disclaimer: str


class AnalyticsResponse(BaseModel):
    meta: ResponseMeta
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    detail: str
