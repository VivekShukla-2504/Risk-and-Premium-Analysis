from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.common import ResponseMeta


class KPI(BaseModel):
    key: str
    label: str
    value: float | int | None
    format: Literal["integer", "currency", "percent"]
    note: str
    rate_metric: bool = False  # True: meaningless when scope is chosen on claim outcome (see meta.rate_metrics_valid)


class DashboardSummaryData(BaseModel):
    kpis: list[KPI]
    secondary_metrics: dict[str, float | int | None]
    confidence_intervals_95: dict[str, Any]
    basis: dict[str, Any]
    definitions: dict[str, dict[str, str]]
    filter_options: dict[str, Any]


class DashboardSummaryResponse(BaseModel):
    meta: ResponseMeta
    data: DashboardSummaryData
