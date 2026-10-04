import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import analytics, dashboard, data_quality, health, methodology
from app.services.data_repository import DataUnavailableError, get_repository

logger = logging.getLogger("insurance_analytics")

DESCRIPTION = """
Educational insurance risk analytics API built on **synthetic** policy and claim data.

Uses traditional actuarial measures (claim frequency, severity, pure premium, loss ratio) with pandas/NumPy only -
no machine learning. Results are **descriptive and scenario-based, never predictions**, and this is not production
actuarial software.

**Filters** (all GET endpoints): `policy_type`, `gender`, `age_band`, `claim_status`, `start_date`, `end_date`,
`date_basis`. Every response carries `meta` with the filters applied, warnings and `rate_metrics_valid`.

**Data source:** MongoDB if configured and reachable, otherwise the cleaned CSV (see `/api/health`).
"""

TAGS = [
    {"name": "System", "description": "Health and data-source status."},
    {"name": "Dashboard", "description": "KPI cards and filter options."},
    {"name": "Analytics", "description": "Segment analytics, scenarios and exports."},
    {"name": "Methodology", "description": "Formulas, assumptions and limitations of every metric."},
    {"name": "Data Quality", "description": "Dataset audit findings and cleaning actions."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    status = get_repository().status()           # warm the cache; never prevents start-up
    if status["data_loaded"]:
        logger.info("Data ready: %s rows from %s", status["rows"], status["data_source"])
    else:
        logger.error("Data not available at start-up: %s", status["error"])
    yield


app = FastAPI(title="Insurance Risk & Premium Analytics API", version="0.3.0", description=DESCRIPTION,
              openapi_tags=TAGS, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(DataUnavailableError)
async def data_unavailable_handler(_request: Request, exc: DataUnavailableError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Check the server log."})


for router in (health.router, dashboard.router, analytics.router, methodology.router, data_quality.router):
    app.include_router(router, prefix="/api")
