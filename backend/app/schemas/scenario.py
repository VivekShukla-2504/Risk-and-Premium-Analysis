from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.filters import FilterSpec
from app.services.scenario_service import LIMITS, ScenarioInputs


class FilterParams(BaseModel):
    """Same filters as the GET endpoints' query parameters."""
    model_config = ConfigDict(extra="forbid")

    policy_type: str | None = Field(None, examples=["Auto"])
    gender: str | None = Field(None, examples=["Female"])
    age_band: Literal["18-25", "26-35", "36-45", "46-55", "56-65", "66-75", "76+"] | None = None
    claim_status: Literal["Settled", "Pending", "Rejected"] | None = None
    start_date: date | None = Field(None, description="YYYY-MM-DD")
    end_date: date | None = Field(None, description="YYYY-MM-DD")
    date_basis: Literal["policy_start", "claim_date"] = "policy_start"

    @model_validator(mode="after")
    def _check_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self

    def to_spec(self) -> FilterSpec:
        return FilterSpec(**self.model_dump())


def _pct(name: str, default: float, description: str):
    lo, hi = LIMITS[name]
    return Field(default, ge=lo, le=hi, allow_inf_nan=False, description=f"{description} (allowed {lo:g} to {hi:g})")


class ScenarioRequest(BaseModel):
    """What-if assumptions, in percent. All changes are relative to the observed portfolio experience."""
    model_config = ConfigDict(extra="forbid")

    frequency_change_pct: float = _pct("frequency_change_pct", 0.0, "Change in claim frequency, %")
    severity_change_pct: float = _pct("severity_change_pct", 0.0, "Change in average claim severity, %")
    inflation_pct: float = _pct("inflation_pct", 0.0, "Claim-cost inflation applied on top of severity, %")
    premium_adjustment_pct: float = _pct("premium_adjustment_pct", 0.0, "Change in earned premium (rate change), %")
    expense_ratio_pct: float = _pct("expense_ratio_pct", 25.0, "ASSUMED expenses as % of premium")
    target_loss_ratio_pct: float = _pct("target_loss_ratio_pct", 65.0, "Loss ratio the premium-needed calculation aims for, %")
    filters: FilterParams | None = Field(None, description="Optional portfolio subset to run the scenario on")

    def to_inputs(self) -> ScenarioInputs:
        return ScenarioInputs(
            frequency_change_pct=self.frequency_change_pct, severity_change_pct=self.severity_change_pct,
            inflation_pct=self.inflation_pct, premium_adjustment_pct=self.premium_adjustment_pct,
            expense_ratio_pct=self.expense_ratio_pct, target_loss_ratio_pct=self.target_loss_ratio_pct)
