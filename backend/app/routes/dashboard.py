from fastapi import APIRouter, Depends

from app.dependencies import Scope, get_scope
from app.schemas.dashboard import DashboardSummaryResponse
from app.services import report_service as RS
from app.services.filters import filter_options

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary", response_model=DashboardSummaryResponse,
    summary="KPI cards, confidence intervals and filter options",
    responses={422: {"description": "Invalid filter value"}, 503: {"description": "No data source available"}},
)
def dashboard_summary(scope: Scope = Depends(get_scope)) -> dict:
    """
    The eight headline KPIs for the selected portfolio slice, each with label, format and a one-line definition.

    * **Claim frequency** = claiming policies / policies
    * **Claim severity** = total claim amount / number of claims
    * **Loss ratio** = incurred claims / earned premium (pro-rata proxy)

    `meta.rate_metrics_valid` is `false` when the filters make rate metrics meaningless.
    `data.filter_options` lists the values available for every filter (from the unfiltered data).
    """
    return scope.envelope(RS.dashboard_summary(scope.df, filter_options(scope.full_df)))
