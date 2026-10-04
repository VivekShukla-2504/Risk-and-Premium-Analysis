from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas.data_quality import DataQualityResponse
from app.services.data_loader import DataValidationError, load_clean_dataset
from app.services.data_quality import build_audit_report

router = APIRouter(prefix="/data-quality", tags=["Data Quality"])


@lru_cache
def _cached_report() -> dict:
    s = get_settings()
    df, cleaning = load_clean_dataset(s.data_path, s.valuation_date)
    return build_audit_report(df, cleaning)


@router.get(
    "",
    response_model=DataQualityResponse,
    summary="Dataset audit: cleaning actions, consistency checks and analytical findings",
)
def data_quality() -> dict:
    try:
        return _cached_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
