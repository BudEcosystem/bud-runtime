"""Gateway Analytics Routes for budmetrics service."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from budmicroframe.commons.middleware import CurrentUserProjectMiddleware
from budmicroframe.commons.schemas import ErrorResponse, Response
from fastapi import APIRouter, Depends, Query

from budmetrics.gateway_analytics.schemas import (
    GatewayAnalyticsRequest,
)
from budmetrics.gateway_analytics.services import GatewayAnalyticsService


gateway_analytics_router = APIRouter(prefix="/gateway", tags=["Gateway Analytics"])

# Initialize service
service = GatewayAnalyticsService()


@gateway_analytics_router.post("/analytics", tags=["Gateway Analytics"])
async def get_gateway_analytics(
    request: GatewayAnalyticsRequest,
    current_user: dict = Depends(CurrentUserProjectMiddleware.get_request_context),
) -> Response:
    """Get gateway analytics metrics.

    Supports various metrics including:
    - Request counts and rates
    - Performance metrics (response times)
    - Geographical distribution
    - Device/Browser/OS distribution
    - Bot traffic analysis
    - Bandwidth usage
    - Status code distribution
    """
    try:
        # Add user context if not specified
        if request.project_id is None and current_user.get("project_id"):
            request.project_id = UUID(current_user["project_id"])

        response = await service.get_gateway_metrics(request)
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch gateway analytics: {str(e)}",
        )
        return error_response.to_http_response()


@gateway_analytics_router.get("/geographical-stats", tags=["Gateway Analytics"])
async def get_geographical_stats(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    current_user: dict = Depends(CurrentUserProjectMiddleware.get_request_context),
) -> Response:
    """Get geographical distribution statistics.

    Returns:
    - Country-wise request distribution
    - City-wise request distribution
    - Heatmap data for visualization
    """
    try:
        # Use current user's project if not specified
        if project_id is None and current_user.get("project_id"):
            project_id = UUID(current_user["project_id"])

        response = await service.get_geographical_stats(from_date=from_date, to_date=to_date, project_id=project_id)
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch geographical stats: {str(e)}",
        )
        return error_response.to_http_response()


@gateway_analytics_router.get("/blocking-stats", tags=["Gateway Analytics"])
async def get_blocking_stats(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    current_user: dict = Depends(CurrentUserProjectMiddleware.get_request_context),
) -> Response:
    """Get blocking rule statistics.

    Returns:
    - Total blocked requests
    - Block rate
    - Breakdown by blocking rule
    - Top blocked IPs
    - Time series of blocked requests
    """
    try:
        # Use current user's project if not specified
        if project_id is None and current_user.get("project_id"):
            project_id = UUID(current_user["project_id"])

        response = await service.get_blocking_stats(from_date=from_date, to_date=to_date, project_id=project_id)
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch blocking stats: {str(e)}",
        )
        return error_response.to_http_response()


@gateway_analytics_router.get("/top-routes", tags=["Gateway Analytics"])
async def get_top_routes(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    limit: Annotated[int, Query(description="Number of top routes to return")] = 10,
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    current_user: dict = Depends(CurrentUserProjectMiddleware.get_request_context),
) -> Response:
    """Get top API routes by request count.

    Returns:
    - Top routes by request count
    - Average response time per route
    - Error rate per route
    """
    try:
        # Use current user's project if not specified
        if project_id is None and current_user.get("project_id"):
            project_id = UUID(current_user["project_id"])

        response = await service.get_top_routes(
            from_date=from_date, to_date=to_date, limit=limit, project_id=project_id
        )
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch top routes: {str(e)}",
        )
        return error_response.to_http_response()


@gateway_analytics_router.get("/client-analytics", tags=["Gateway Analytics"])
async def get_client_analytics(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    group_by: Annotated[str, Query(description="Group by: device_type, browser, os")] = "device_type",
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    current_user: dict = Depends(CurrentUserProjectMiddleware.get_request_context),
) -> Response:
    """Get client analytics (device, browser, OS distribution).

    Returns distribution based on the specified grouping.
    """
    try:
        # Use current user's project if not specified
        if project_id is None and current_user.get("project_id"):
            project_id = UUID(current_user["project_id"])

        response = await service.get_client_analytics(
            from_date=from_date, to_date=to_date, group_by=group_by, project_id=project_id
        )
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch client analytics: {str(e)}",
        )
        return error_response.to_http_response()
