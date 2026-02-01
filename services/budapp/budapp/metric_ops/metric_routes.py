#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""The metric ops package, containing essential business logic, services, and routing configurations for the metric ops."""

from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import BlockingRuleStatus, BlockingRuleType
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.models import User as UserModel
from budapp.user_ops.schemas import User

from .schemas import (
    # New aggregated metrics schemas
    AggregatedMetricsRequest,
    AggregatedMetricsResponse,
    # Gateway Analytics schemas
    BlockingRule,
    BlockingRuleCreate,
    BlockingRuleDeleteResponse,
    BlockingRuleListResponse,
    BlockingRuleResponse,
    BlockingRulesStatsOverviewResponse,
    BlockingRuleSyncRequest,
    BlockingRuleUpdate,
    BlockingStatsResponse,
    ClientAnalyticsResponse,
    DashboardStatsResponse,
    GatewayAnalyticsRequest,
    GatewayAnalyticsResponse,
    GeographicalStatsResponse,
    GeographicDataRequest,
    GeographicDataResponse,
    InferenceDetailResponse,
    InferenceFeedbackResponse,
    InferenceListRequest,
    InferenceListResponse,
    LatencyDistributionRequest,
    LatencyDistributionResponse,
    PromptDistributionRequest,
    PromptDistributionResponse,
    TimeSeriesRequest,
    TimeSeriesResponse,
    TopRoutesResponse,
)
from .services import (
    BlockingRulesService,
    BudMetricService,
    GatewayAnalyticsService,
    MetricService,
)


logger = logging.get_logger(__name__)

metric_router = APIRouter(prefix="/metrics", tags=["metric"])


@metric_router.post(
    "/analytics",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "description": "Analytics response from metrics service",
        },
    },
    description="Proxy endpoint for analytics requests to the observability/analytics endpoint",
)
async def analytics_proxy(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request_body: Dict[str, Any],
):
    """Proxy analytics requests to the observability/analytics endpoint.

    This endpoint forwards the request body to the metrics service
    and enriches the response with names for project, model, and endpoint IDs.
    """
    try:
        response_data = await BudMetricService(session).proxy_analytics_request(request_body)
        return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to proxy analytics request: {e}")
        error_response = ErrorResponse(code=e.status_code, message=e.message)
        return JSONResponse(content=error_response.model_dump(mode="json"), status_code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to proxy analytics request: {e}")
        error_response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to proxy analytics request"
        )
        return JSONResponse(
            content=error_response.model_dump(mode="json"), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@metric_router.get(
    "/count",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": DashboardStatsResponse,
            "description": "Successfully retrieved dashboard statistics",
        },
    },
    description="Retrieve the dashboard statistics, including counts for models, projects, endpoints, and clusters.",
)
async def get_dashboard_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> DashboardStatsResponse:
    """Retrieves the dashboard statistics, including counts for models, projects, endpoints, and clusters.

    Args:
        current_user (User): The current authenticated user making the request.
        session (Session): The database session used for querying data.

    Returns:
        DashboardStatsResponse: An object containing aggregated statistics for the dashboard,
        such as model counts, project counts, endpoint counts, and cluster counts.
    """
    try:
        return await MetricService(session).get_dashboard_stats(current_user.id)
    except ClientException as e:
        logger.exception(f"Failed to fetch dashboard statistics: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to fetch dashboard statistics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to fetch dashboard statistics"
        ).to_http_response()


@metric_router.post(
    "/inferences/list",
    response_model=InferenceListResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": InferenceListResponse,
            "description": "Successfully retrieved inference list",
        },
    },
    description="List inference requests with pagination and filtering",
)
async def list_inferences(
    request: InferenceListRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InferenceListResponse:
    """List inference requests with pagination, filtering, and access control.

    This endpoint proxies to budmetrics and enriches the response with
    project, endpoint, and model names.

    Args:
        request (InferenceListRequest): The list request parameters.
        current_user (User): The current authenticated user making the request.
        session (Session): The database session used for querying data.

    Returns:
        InferenceListResponse: Paginated list of inference requests.
    """
    try:
        return await BudMetricService(session).list_inferences(request, current_user)
    except ClientException as e:
        logger.exception(f"Failed to list inferences: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list inferences: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list inferences"
        ).to_http_response()


@metric_router.get(
    "/inferences/{inference_id}",
    response_model=InferenceDetailResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Inference not found",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to this inference",
        },
        status.HTTP_200_OK: {
            "model": InferenceDetailResponse,
            "description": "Successfully retrieved inference details",
        },
    },
    description="Get complete details for a single inference",
)
async def get_inference_details(
    inference_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InferenceDetailResponse:
    """Get complete details for a single inference with access control.

    Args:
        inference_id (UUID): The ID of the inference to retrieve.
        current_user (User): The current authenticated user making the request.
        session (Session): The database session used for querying data.

    Returns:
        InferenceDetailResponse: Complete inference details.
    """
    try:
        return await BudMetricService(session).get_inference_details(str(inference_id), current_user)
    except ClientException as e:
        logger.exception(f"Failed to get inference details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get inference details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get inference details"
        ).to_http_response()


@metric_router.get(
    "/inferences/{inference_id}/feedback",
    response_model=InferenceFeedbackResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Inference not found",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to this inference",
        },
        status.HTTP_200_OK: {
            "model": InferenceFeedbackResponse,
            "description": "Successfully retrieved inference feedback",
        },
    },
    description="Get all feedback associated with an inference",
)
async def get_inference_feedback(
    inference_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InferenceFeedbackResponse:
    """Get all feedback associated with an inference with access control.

    Args:
        inference_id (UUID): The ID of the inference.
        current_user (User): The current authenticated user making the request.
        session (Session): The database session used for querying data.

    Returns:
        InferenceFeedbackResponse: Aggregated feedback data.
    """
    try:
        return await BudMetricService(session).get_inference_feedback(str(inference_id), current_user)
    except ClientException as e:
        logger.exception(f"Failed to get inference feedback: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get inference feedback: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get inference feedback"
        ).to_http_response()


# Gateway Analytics Routes


@metric_router.post(
    "/gateway/analytics",
    response_model=GatewayAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Query gateway analytics",
    description="Query comprehensive gateway analytics with filtering by projects, models, and endpoints",
)
async def query_gateway_analytics(
    request: GatewayAnalyticsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> GatewayAnalyticsResponse:
    """Query gateway analytics with user context filtering.

    This endpoint provides comprehensive analytics data including:
    - Request counts and error rates
    - Response time metrics (average, p95, p99)
    - Token usage and cost analysis
    - Time-series data with configurable bucketing

    The results are automatically filtered based on the user's project access.
    """
    service = GatewayAnalyticsService(session, current_user)
    return await service.query_analytics(request)


@metric_router.get(
    "/gateway/geographical-stats",
    response_model=GeographicalStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get geographical distribution statistics",
    description="Get statistics on the geographical distribution of API requests",
)
async def get_geographical_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: datetime = Query(
        default_factory=lambda: datetime.utcnow() - timedelta(days=7),
        description="Start time for the query (defaults to 7 days ago)",
    ),
    end_time: datetime = Query(
        default_factory=datetime.utcnow,
        description="End time for the query (defaults to now)",
    ),
    project_ids: Optional[List[UUID]] = Query(
        None,
        description="List of project IDs to filter by (defaults to user's accessible projects)",
    ),
) -> GeographicalStatsResponse:
    """Get geographical distribution of API requests.

    Returns statistics grouped by country, region, and city including:
    - Request counts per location
    - Error counts per location
    - Average response times by geography
    """
    service = GatewayAnalyticsService(session, current_user)
    return await service.get_geographical_stats(start_time, end_time, project_ids)


@metric_router.get(
    "/gateway/blocking-stats",
    response_model=BlockingStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get blocking statistics",
    description="Get statistics on blocked requests for security analysis",
)
async def get_blocking_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: datetime = Query(
        default_factory=lambda: datetime.utcnow() - timedelta(days=7),
        description="Start time for the query (defaults to 7 days ago)",
    ),
    end_time: datetime = Query(
        default_factory=datetime.utcnow,
        description="End time for the query (defaults to now)",
    ),
    project_ids: Optional[List[UUID]] = Query(
        None,
        description="List of project IDs to filter by (defaults to user's accessible projects)",
    ),
) -> BlockingStatsResponse:
    """Get statistics on blocked requests.

    Returns information about:
    - Blocked IP addresses
    - Reasons for blocking
    - Block counts and patterns
    - Associated projects
    """
    service = GatewayAnalyticsService(session, current_user)
    return await service.get_blocking_stats(start_time, end_time, project_ids)


@metric_router.get(
    "/gateway/blocking-rules-stats",
    response_model=BlockingRulesStatsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get blocking rules overview statistics",
    description="Get overview statistics for blocking rules dashboard cards including rule counts and block statistics",
)
async def get_blocking_rules_stats_overview(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: Optional[datetime] = Query(
        None,
        description="Start time for time-based statistics (defaults to 7 days ago)",
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="End time for time-based statistics (defaults to now)",
    ),
) -> BlockingRulesStatsOverviewResponse:
    """Get overview statistics for blocking rules dashboard.

    Returns statistics including:
    - Total rules count
    - Active/inactive/expired rules count
    - Total blocks today and this week
    - Top blocked IPs and countries
    - Blocks by rule type
    """
    service = BlockingRulesService(session, current_user)
    return await service.get_blocking_rules_stats_overview(start_time, end_time)


@metric_router.get(
    "/gateway/blocking-dashboard-stats",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get blocking rules dashboard statistics",
    description="Get real-time dashboard statistics for blocking rules, querying PostgreSQL for rule counts and ClickHouse for block counts",
)
async def get_blocking_dashboard_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: Optional[datetime] = Query(
        None,
        description="Start time for block statistics (defaults to 7 days ago)",
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="End time for block statistics (defaults to now)",
    ),
) -> Dict[str, Any]:
    """Get real-time dashboard statistics for blocking rules.

    Returns statistics including:
    - Rule counts from PostgreSQL (total, active, inactive, expired)
    - Block counts from ClickHouse (today, this week)
    - No duplicate data storage - always fresh from source
    """
    service = BlockingRulesService(session, current_user)
    return await service.get_blocking_dashboard_stats(start_time, end_time)


@metric_router.get(
    "/gateway/top-routes",
    response_model=TopRoutesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get top API routes",
    description="Get the most frequently accessed API routes with performance metrics",
)
async def get_top_routes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: datetime = Query(
        default_factory=lambda: datetime.utcnow() - timedelta(days=7),
        description="Start time for the query (defaults to 7 days ago)",
    ),
    end_time: datetime = Query(
        default_factory=datetime.utcnow,
        description="End time for the query (defaults to now)",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of routes to return",
    ),
    project_ids: Optional[List[UUID]] = Query(
        None,
        description="List of project IDs to filter by (defaults to user's accessible projects)",
    ),
) -> TopRoutesResponse:
    """Get top API routes by request count.

    Returns the most accessed routes with:
    - Request and error counts
    - Response time metrics (average, p95, p99)
    - Error rates
    - Associated projects, models, and endpoints
    """
    service = GatewayAnalyticsService(session, current_user)
    return await service.get_top_routes(start_time, end_time, limit, project_ids)


@metric_router.get(
    "/gateway/client-analytics",
    response_model=ClientAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get client analytics",
    description="Get analytics data grouped by client/user",
)
async def get_client_analytics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: datetime = Query(
        default_factory=lambda: datetime.utcnow() - timedelta(days=7),
        description="Start time for the query (defaults to 7 days ago)",
    ),
    end_time: datetime = Query(
        default_factory=datetime.utcnow,
        description="End time for the query (defaults to now)",
    ),
    project_ids: Optional[List[UUID]] = Query(
        None,
        description="List of project IDs to filter by (defaults to user's accessible projects)",
    ),
) -> ClientAnalyticsResponse:
    """Get analytics data grouped by client.

    Returns per-client statistics including:
    - Request and error counts
    - Average response times
    - Token usage and costs
    - Last activity time
    - Associated projects and models
    """
    service = GatewayAnalyticsService(session, current_user)
    return await service.get_client_analytics(start_time, end_time, project_ids)


# Blocking Rules Management Routes


@metric_router.post(
    "/gateway/blocking-rules",
    response_model=BlockingRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a blocking rule",
    description="Create a new blocking rule (global, model-specific, or project-specific)",
)
async def create_blocking_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_data: BlockingRuleCreate,
    project_id: Optional[UUID] = Query(None, description="Project ID for project-specific rules"),
) -> BlockingRuleResponse:
    """Create a new blocking rule.

    Rule scopes:
    - Global: No project_id, no model_name - applies to entire gateway
    - Model-specific: model_name set - applies to specific model
    - Project-specific: project_id set - applies to specific project (legacy)

    Rule types:
    - IP_BLOCKING: Block specific IP addresses or ranges
    - COUNTRY_BLOCKING: Block traffic from specific countries
    - USER_AGENT_BLOCKING: Block based on user agent patterns
    - RATE_BASED_BLOCKING: Block based on request rate thresholds

    Configuration examples:
    - IP blocking: {"ip_addresses": ["192.168.1.1", "10.0.0.0/24"]}
    - Country blocking: {"countries": ["CN", "RU"]}
    - User agent blocking: {"patterns": ["bot", "crawler"]}
    - Rate-based blocking: {"threshold": 100, "window_seconds": 60}
    """
    service = BlockingRulesService(session, current_user)
    rule = await service.create_blocking_rule(project_id, rule_data)
    return BlockingRuleResponse(message="Blocking rule created successfully", data=rule)


@metric_router.get(
    "/gateway/blocking-rules",
    response_model=BlockingRuleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List blocking rules",
    description="List blocking rules with filtering options",
)
async def list_blocking_rules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    rule_type: Optional[BlockingRuleType] = Query(None, description="Filter by rule type"),
    status: Optional[BlockingRuleStatus] = Query(None, description="Filter by status"),
    endpoint_id: Optional[UUID] = Query(None, description="Filter by endpoint ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> BlockingRuleListResponse:
    """List blocking rules accessible to the user.

    Results are automatically filtered based on the user's project access.
    """
    service = BlockingRulesService(session, current_user)
    return await service.list_blocking_rules(
        project_id=project_id,
        rule_type=rule_type,
        status=status,
        endpoint_id=endpoint_id,
        page=page,
        page_size=page_size,
    )


@metric_router.get(
    "/gateway/blocking-rules/{rule_id}",
    response_model=BlockingRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a blocking rule",
    description="Get details of a specific blocking rule",
)
async def get_blocking_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_id: UUID,
) -> BlockingRuleResponse:
    """Get a specific blocking rule by ID.

    The user must have access to the project that owns the rule.
    """
    service = BlockingRulesService(session, current_user)
    rule = await service.get_blocking_rule(rule_id)
    return BlockingRuleResponse(message="Blocking rule retrieved successfully", data=rule)


@metric_router.put(
    "/gateway/blocking-rules/{rule_id}",
    response_model=BlockingRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a blocking rule",
    description="Update an existing blocking rule",
)
async def update_blocking_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_id: UUID,
    update_data: BlockingRuleUpdate,
) -> BlockingRuleResponse:
    """Update a blocking rule.

    Only the fields provided in the update data will be modified.
    The user must have access to the project that owns the rule.
    """
    service = BlockingRulesService(session, current_user)
    rule = await service.update_blocking_rule(rule_id, update_data)
    return BlockingRuleResponse(message="Blocking rule updated successfully", data=rule)


@metric_router.delete(
    "/gateway/blocking-rules/{rule_id}",
    response_model=BlockingRuleDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a blocking rule",
    description="Delete a blocking rule",
)
async def delete_blocking_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_id: UUID,
) -> BlockingRuleDeleteResponse:
    """Delete a blocking rule.

    The rule will be removed from both the database and Redis cache.
    The user must have access to the project that owns the rule.
    """
    service = BlockingRulesService(session, current_user)
    await service.delete_blocking_rule(rule_id)
    return BlockingRuleDeleteResponse(message="Blocking rule deleted successfully", id=rule_id)


@metric_router.post(
    "/gateway/blocking-rules/sync",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync blocking rules to Redis",
    description="Sync blocking rules to Redis for real-time access by the gateway",
)
async def sync_blocking_rules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    sync_request: BlockingRuleSyncRequest,
) -> SuccessResponse:
    """Sync blocking rules to Redis for real-time access.

    This endpoint ensures that all active blocking rules are available
    in Redis for the gateway to enforce in real-time.
    """
    service = BlockingRulesService(session, current_user)
    result = await service.sync_blocking_rules(sync_request.project_ids)
    return SuccessResponse(
        success=True,
        message=f"Successfully synced {result['synced_rules']} rules to Redis",
    )


@metric_router.post(
    "/gateway/blocking-rules/sync-stats",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync blocking rule statistics from ClickHouse",
    description="Sync blocking rule match counts and last matched timestamps from ClickHouse to PostgreSQL",
)
async def sync_blocking_rule_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> SuccessResponse:
    """Sync blocking rule statistics from ClickHouse to PostgreSQL.

    This endpoint triggers a manual sync of blocking rule match counts
    and last matched timestamps from ClickHouse event data to PostgreSQL.
    """
    service = MetricService(session)
    result = await service.sync_blocking_rule_stats_from_clickhouse()

    # Check if sync was successful
    if "error" in result:
        return SuccessResponse(
            message=f"Sync failed: {result['error']}. Updated {result.get('updated_rules', 0)} rules."
        )
    else:
        return SuccessResponse(message=f"Successfully synced statistics for {result.get('updated_rules', 0)} rules")


# New Aggregated Metrics Proxy Endpoints


@metric_router.post(
    "/aggregated",
    response_model=AggregatedMetricsResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": AggregatedMetricsResponse,
            "description": "Successfully retrieved aggregated metrics",
        },
    },
    description="Get aggregated metrics with server-side calculations and user access control",
)
async def get_aggregated_metrics(
    request: AggregatedMetricsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> AggregatedMetricsResponse:
    """Get aggregated metrics with server-side calculations and access control.

    This endpoint provides pre-aggregated metrics calculated directly in ClickHouse for
    high performance. The request is automatically filtered to only include data from
    projects the user has access to.

    Supported metrics include:
    - total_requests: Total number of requests
    - success_rate: Success rate percentage
    - avg_latency, p95_latency, p99_latency: Latency percentiles
    - total_tokens, avg_tokens: Token usage metrics
    - total_cost, avg_cost: Cost metrics
    - ttft_avg, ttft_p95, ttft_p99: Time to first token metrics
    - cache_hit_rate: Cache performance
    - throughput_avg: Request throughput
    - error_rate: Error rate percentage
    - unique_users: Number of unique users

    Args:
        request: Aggregated metrics request parameters
        current_user: The current authenticated user making the request
        session: The database session used for querying data

    Returns:
        AggregatedMetricsResponse: Aggregated metrics with enriched entity names
    """
    try:
        response_data = await BudMetricService(session).proxy_aggregated_metrics(
            request.model_dump(mode="json"), current_user
        )
        return AggregatedMetricsResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get aggregated metrics: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get aggregated metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get aggregated metrics"
        ).to_http_response()


@metric_router.post(
    "/time-series",
    response_model=TimeSeriesResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": TimeSeriesResponse,
            "description": "Successfully retrieved time-series data",
        },
    },
    description="Get time-series metrics data for chart visualization with user access control",
)
async def get_time_series_metrics(
    request: TimeSeriesRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> TimeSeriesResponse:
    """Get time-series metrics data for chart visualization with access control.

    This endpoint provides time-bucketed metrics data optimized for charts and graphs.
    Uses efficient ClickHouse time bucketing functions and supports gap filling for
    smooth visualizations. The request is automatically filtered to only include data
    from projects the user has access to.

    Supported intervals:
    - 1m, 5m, 15m, 30m: Minute-based intervals
    - 1h, 6h, 12h: Hour-based intervals
    - 1d: Daily intervals
    - 1w: Weekly intervals

    Supported metrics:
    - requests: Number of requests per interval
    - success_rate: Success rate percentage
    - avg_latency, p95_latency, p99_latency: Latency metrics
    - tokens: Token usage per interval
    - cost: Cost per interval
    - ttft_avg: Average time to first token
    - cache_hit_rate: Cache hit rate percentage
    - throughput: Request throughput
    - error_rate: Error rate percentage

    Args:
        request: Time-series request parameters
        current_user: The current authenticated user making the request
        session: The database session used for querying data

    Returns:
        TimeSeriesResponse: Time-series data with enriched entity names
    """
    try:
        response_data = await BudMetricService(session).proxy_time_series_metrics(
            request.model_dump(mode="json"), current_user
        )
        return TimeSeriesResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get time-series metrics: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get time-series metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get time-series metrics"
        ).to_http_response()


@metric_router.get(
    "/geography",
    response_model=GeographicDataResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": GeographicDataResponse,
            "description": "Successfully retrieved geographic distribution data",
        },
    },
    description="Get geographic distribution of API requests with user access control",
)
async def get_geographic_distribution(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    group_by: str = Query("country", description="Group by: country, region, city"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of locations to return"),
    project_ids: Optional[str] = Query(
        None, description="Comma-separated list of project IDs to filter by (optional - defaults to user's projects)"
    ),
) -> GeographicDataResponse:
    """Get geographic distribution of API requests with access control.

    Returns statistics grouped by country, region, or city including:
    - Request counts per location
    - Success rates per location
    - Average response times by geography
    - Number of unique users per location
    - Percentage breakdown of total requests

    The request is automatically filtered to only include data from projects
    the user has access to. If specific project IDs are provided, they are
    validated against the user's accessible projects.

    Args:
        current_user: The current authenticated user making the request
        session: The database session used for querying data
        from_date: Start date for the analysis
        to_date: End date for the analysis (defaults to current time)
        group_by: Geographic grouping level (country, region, city)
        limit: Maximum number of locations to return (1-1000)
        project_ids: Optional comma-separated project IDs to filter by

    Returns:
        GeographicDataResponse: Geographic distribution data with enriched information
    """
    try:
        # Prepare request parameters
        request_params = {
            "from_date": from_date.isoformat(),
            "group_by": group_by,
            "limit": limit,
        }

        if to_date:
            request_params["to_date"] = to_date.isoformat()

        if project_ids:
            request_params["project_ids"] = project_ids

        response_data = await BudMetricService(session).proxy_geographic_metrics(request_params, current_user)
        return GeographicDataResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get geographic distribution: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get geographic distribution: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get geographic distribution"
        ).to_http_response()


@metric_router.post(
    "/observability/metrics/aggregated",
    response_model=AggregatedMetricsResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": AggregatedMetricsResponse,
            "description": "Successfully retrieved aggregated metrics data",
        },
    },
    description="Get aggregated metrics with user access control",
)
async def get_aggregated_metrics(
    request: AggregatedMetricsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> AggregatedMetricsResponse:
    """Get aggregated metrics with user access control.

    This endpoint proxies to the budmetrics service and automatically filters
    results based on the user's project access permissions.
    """
    try:
        response_data = await BudMetricService(session).proxy_aggregated_metrics(
            request.model_dump(mode="json"), current_user
        )
        return AggregatedMetricsResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get aggregated metrics: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get aggregated metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get aggregated metrics"
        ).to_http_response()


@metric_router.post(
    "/observability/metrics/time-series",
    response_model=TimeSeriesResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": TimeSeriesResponse,
            "description": "Successfully retrieved time series data",
        },
    },
    description="Get time series metrics with user access control",
)
async def get_time_series_metrics(
    request: TimeSeriesRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> TimeSeriesResponse:
    """Get time series metrics with user access control.

    This endpoint proxies to the budmetrics service and automatically filters
    results based on the user's project access permissions.
    """
    try:
        response_data = await BudMetricService(session).proxy_time_series_metrics(
            request.model_dump(mode="json"), current_user
        )
        return TimeSeriesResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get time series metrics: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get time series metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get time series metrics"
        ).to_http_response()


@metric_router.get(
    "/observability/metrics/geography",
    response_model=GeographicDataResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": GeographicDataResponse,
            "description": "Successfully retrieved geographic data",
        },
    },
    description="Get geographic distribution metrics with user access control",
)
async def get_geographic_metrics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    from_date: datetime = Query(..., description="Start date for the query range"),
    to_date: Optional[datetime] = Query(None, description="End date for the query range"),
) -> GeographicDataResponse:
    """Get geographic distribution metrics with user access control.

    This endpoint proxies to the budmetrics service and automatically filters
    results based on the user's project access permissions.
    """
    try:
        # Prepare request parameters
        params = {"from_date": from_date.isoformat(), "to_date": to_date.isoformat() if to_date else None}

        response_data = await BudMetricService(session).proxy_geographic_metrics(params, current_user)
        return GeographicDataResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get geographic metrics: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get geographic metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get geographic metrics"
        ).to_http_response()


@metric_router.post(
    "/latency-distribution",
    response_model=LatencyDistributionResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": LatencyDistributionResponse,
            "description": "Successfully retrieved latency distribution data",
        },
    },
    description="Get latency distribution analysis with server-side calculations and user access control",
)
async def get_latency_distribution(
    request: LatencyDistributionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> LatencyDistributionResponse:
    """Get latency distribution analysis with server-side calculations and access control.

    This endpoint provides latency distribution analysis calculated directly in ClickHouse for
    high performance. The request is automatically filtered to only include data from
    projects the user has access to.

    Default latency buckets:
    - 0-100ms: Very fast responses
    - 100-500ms: Fast responses
    - 500ms-1s: Moderate responses
    - 1-2s: Slow responses
    - 2-5s: Very slow responses
    - 5-10s: Extremely slow responses
    - >10s: Timeout-prone responses

    Features:
    - Custom latency bucket definitions
    - Grouping by model, project, endpoint, or user
    - Automatic access control filtering
    - Percentage and count statistics
    - Average latency within each bucket

    Args:
        request: Latency distribution request parameters
        current_user: The current authenticated user making the request
        session: The database session used for querying data

    Returns:
        LatencyDistributionResponse: Latency distribution data with enriched information
    """
    try:
        response_data = await BudMetricService(session).proxy_latency_distribution_metrics(
            request.model_dump(mode="json"), current_user
        )
        return LatencyDistributionResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get latency distribution: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get latency distribution: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get latency distribution"
        ).to_http_response()


@metric_router.post(
    "/distribution",
    response_model=PromptDistributionResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access denied to requested projects",
        },
        status.HTTP_200_OK: {
            "model": PromptDistributionResponse,
            "description": "Successfully retrieved prompt distribution data",
        },
    },
    description="Get prompt distribution analysis with access control",
)
async def get_prompt_distribution(
    request: PromptDistributionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> PromptDistributionResponse:
    """Get prompt distribution analysis with access control.

    Supports bucketing by concurrency, input_tokens, or output_tokens (X-axis)
    and metrics like total_duration_ms, ttft_ms, response_time_ms, throughput_per_user (Y-axis).
    """
    try:
        response_data = await BudMetricService(session).proxy_prompt_distribution_metrics(
            request.model_dump(mode="json"), current_user
        )
        return PromptDistributionResponse(**response_data)
    except ClientException as e:
        logger.exception(f"Failed to get prompt distribution: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get prompt distribution: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get prompt distribution"
        ).to_http_response()


@metric_router.get("/sync-stats")
async def get_hybrid_sync_stats(
    current_user: Annotated[dict, Depends(get_current_active_user)],
) -> Dict[str, Any]:
    """Get hybrid metrics sync task statistics.

    This endpoint returns statistics about the hybrid sync task that combines
    credential usage sync and user usage sync.

    Args:
        current_user: The current authenticated user

    Returns:
        Dict containing sync task statistics
    """
    try:
        from budapp.metric_ops.hybrid_sync import get_hybrid_sync_stats

        stats = get_hybrid_sync_stats()
        return {"success": True, "data": stats, "message": "Hybrid sync statistics retrieved successfully"}
    except Exception as e:
        logger.exception(f"Failed to get hybrid sync stats: {e}")
        return {"success": False, "message": f"Failed to get sync statistics: {str(e)}"}
