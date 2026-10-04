from fastapi import APIRouter, Depends

from app.schemas.common import HealthResponse
from app.services.data_repository import DataRepository, get_repository

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse, summary="Service and data-source health")
def health(repo: DataRepository = Depends(get_repository)) -> dict:
    """Reports which data source is active (MongoDB, cleaned CSV or raw CSV). Never fails: returns `degraded` if no data."""
    st = repo.status()
    return {"status": "ok" if st["data_loaded"] else "degraded", **st}
