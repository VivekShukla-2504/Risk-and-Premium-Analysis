from typing import Any

from pydantic import BaseModel


class Finding(BaseModel):
    id: str
    severity: str  # info | warning
    title: str
    detail: str
    decision: str


class DataQualityResponse(BaseModel):
    shape: dict[str, int]
    cleaning: dict[str, Any]
    missing_values: dict[str, int]
    categoricals: dict[str, dict[str, int]]
    numeric_summary: dict[str, dict[str, float]]
    date_ranges: dict[str, list[str]]
    consistency_checks: dict[str, int]
    status_vs_claim_fields: list[dict[str, Any]]
    findings: list[Finding]
