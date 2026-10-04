from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from app.services import analytics_service as A
from app.services import risk_segmentation as R
from app.services import rate_indication_service as RI
from app.services import scenario_service as S
from app.services.data_loader import AGE_BAND_LABELS, CLAIM_STATUS_TREATMENT
from app.services.report_service import DISCLAIMER
from app.utils.serialization import to_builtin

router = APIRouter(prefix="/methodology", tags=["Methodology"])


@router.get("", summary="Metric definitions, rules and assumptions in force", response_model=dict[str, Any])
def methodology() -> dict:
    """Everything the UI needs to explain itself: formula, numerator, denominator, assumptions and limitations of each
    metric, the risk-segmentation rules, claim-status treatment, and the scenario limits, defaults and formulas."""
    return to_builtin({
        "disclaimer": DISCLAIMER,
        "metric_definitions": A.get_metric_definitions(),
        "claim_status_treatment": CLAIM_STATUS_TREATMENT,
        "age_bands": AGE_BAND_LABELS,
        "risk_segmentation_rules": R.RULES,
        "scenario": {
            "disclaimer": S.DISCLAIMER,
            "limits": {k: {"min": lo, "max": hi} for k, (lo, hi) in S.LIMITS.items()},
            "defaults": asdict(S.ScenarioInputs()),
            "formulas": S.FORMULAS,
            "presets": S.PRESETS,
            "preset_note": S.PRESET_NOTE,
        },
        "rate_indication": {
            "disclaimer": RI.DISCLAIMER,
            "default_target_loss_ratio_pct": RI.DEFAULT_TARGET_LOSS_RATIO_PCT,
            "target_loss_ratio_limits_pct": {
                "minimum": RI.MIN_TARGET_LOSS_RATIO_PCT,
                "maximum": RI.MAX_TARGET_LOSS_RATIO_PCT,
            },
            "credibility_standard_claims": A.FULL_CREDIBILITY_CLAIMS,
            "formulas": RI.FORMULAS,
            "assumptions": RI.NOTES,
        },
        "credibility_standard_claims": A.FULL_CREDIBILITY_CLAIMS,
    })
