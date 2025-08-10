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

"""Gateway analytics API routes."""

from datetime import datetime, timedelta
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from ..commons.constants import BlockingRuleStatus, BlockingRuleType
from ..commons.db_utils import get_db
from ..commons.dependencies import AccessHelper, get_access
from ..commons.schemas import SuccessResponse
from .schemas import (
    BlockingRule,
    BlockingRuleCreate,
    BlockingRuleDeleteResponse,
    BlockingRuleListResponse,
    BlockingRuleResponse,
    BlockingRuleSyncRequest,
    BlockingRuleUpdate,
    BlockingStatsResponse,
    ClientAnalyticsResponse,
    GatewayAnalyticsRequest,
    GatewayAnalyticsResponse,
    GeographicalStatsResponse,
    TopRoutesResponse,
)
from .services import BlockingRulesService, GatewayAnalyticsService


gateway_analytics_router = APIRouter(
    prefix="/api/v1/gateway",
    tags=["gateway-analytics"],
    dependencies=[Depends(get_db)],
)


@gateway_analytics_router.post(
    "/analytics",
    response_model=GatewayAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Query gateway analytics",
    description="Query comprehensive gateway analytics with filtering by projects, models, and endpoints",
)
async def query_gateway_analytics(
    request: GatewayAnalyticsRequest,
    access_helper: AccessHelper = Depends(get_access),
) -> GatewayAnalyticsResponse:
    """Query gateway analytics with user context filtering.

    This endpoint provides comprehensive analytics data including:
    - Request counts and error rates
    - Response time metrics (average, p95, p99)
    - Token usage and cost analysis
    - Time-series data with configurable bucketing

    The results are automatically filtered based on the user's project access.
    """
    service = GatewayAnalyticsService(access_helper.session, access_helper.user)
    return await service.query_analytics(request)


@gateway_analytics_router.get(
    "/geographical-stats",
    response_model=GeographicalStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get geographical distribution statistics",
    description="Get statistics on the geographical distribution of API requests",
)
async def get_geographical_stats(
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
    access_helper: AccessHelper = Depends(get_access),
) -> GeographicalStatsResponse:
    """Get geographical distribution of API requests.

    Returns statistics grouped by country, region, and city including:
    - Request counts per location
    - Error counts per location
    - Average response times by geography
    """
    service = GatewayAnalyticsService(access_helper.session, access_helper.user)
    return await service.get_geographical_stats(start_time, end_time, project_ids)


@gateway_analytics_router.get(
    "/blocking-stats",
    response_model=BlockingStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get blocking statistics",
    description="Get statistics on blocked requests for security analysis",
)
async def get_blocking_stats(
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
    access_helper: AccessHelper = Depends(get_access),
) -> BlockingStatsResponse:
    """Get statistics on blocked requests.

    Returns information about:
    - Blocked IP addresses
    - Reasons for blocking
    - Block counts and patterns
    - Associated projects
    """
    service = GatewayAnalyticsService(access_helper.session, access_helper.user)
    return await service.get_blocking_stats(start_time, end_time, project_ids)


@gateway_analytics_router.get(
    "/top-routes",
    response_model=TopRoutesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get top API routes",
    description="Get the most frequently accessed API routes with performance metrics",
)
async def get_top_routes(
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
    access_helper: AccessHelper = Depends(get_access),
) -> TopRoutesResponse:
    """Get top API routes by request count.

    Returns the most accessed routes with:
    - Request and error counts
    - Response time metrics (average, p95, p99)
    - Error rates
    - Associated projects, models, and endpoints
    """
    service = GatewayAnalyticsService(access_helper.session, access_helper.user)
    return await service.get_top_routes(start_time, end_time, limit, project_ids)


@gateway_analytics_router.get(
    "/client-analytics",
    response_model=ClientAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get client analytics",
    description="Get analytics data grouped by client/user",
)
async def get_client_analytics(
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
    access_helper: AccessHelper = Depends(get_access),
) -> ClientAnalyticsResponse:
    """Get analytics data grouped by client.

    Returns per-client statistics including:
    - Request and error counts
    - Average response times
    - Token usage and costs
    - Last activity time
    - Associated projects and models
    """
    service = GatewayAnalyticsService(access_helper.session, access_helper.user)
    return await service.get_client_analytics(start_time, end_time, project_ids)


# Blocking Rules Management Endpoints


@gateway_analytics_router.post(
    "/blocking-rules",
    response_model=BlockingRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a blocking rule",
    description="Create a new blocking rule for a project",
)
async def create_blocking_rule(
    project_id: UUID,
    rule_data: BlockingRuleCreate,
    access_helper: AccessHelper = Depends(get_access),
) -> BlockingRuleResponse:
    """Create a new blocking rule.

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
    service = BlockingRulesService(access_helper.session, access_helper.user)
    rule = await service.create_blocking_rule(project_id, rule_data)
    return BlockingRuleResponse(success=True, data=rule)


@gateway_analytics_router.get(
    "/blocking-rules",
    response_model=BlockingRuleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List blocking rules",
    description="List blocking rules with filtering options",
)
async def list_blocking_rules(
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    rule_type: Optional[BlockingRuleType] = Query(None, description="Filter by rule type"),
    status: Optional[BlockingRuleStatus] = Query(None, description="Filter by status"),
    endpoint_id: Optional[UUID] = Query(None, description="Filter by endpoint ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    access_helper: AccessHelper = Depends(get_access),
) -> BlockingRuleListResponse:
    """List blocking rules accessible to the user.

    Results are automatically filtered based on the user's project access.
    """
    service = BlockingRulesService(access_helper.session, access_helper.user)
    return await service.list_blocking_rules(
        project_id=project_id,
        rule_type=rule_type,
        status=status,
        endpoint_id=endpoint_id,
        page=page,
        page_size=page_size,
    )


@gateway_analytics_router.get(
    "/blocking-rules/{rule_id}",
    response_model=BlockingRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a blocking rule",
    description="Get details of a specific blocking rule",
)
async def get_blocking_rule(
    rule_id: UUID,
    access_helper: AccessHelper = Depends(get_access),
) -> BlockingRuleResponse:
    """Get a specific blocking rule by ID.

    The user must have access to the project that owns the rule.
    """
    service = BlockingRulesService(access_helper.session, access_helper.user)
    rule = await service.get_blocking_rule(rule_id)
    return BlockingRuleResponse(success=True, data=rule)


@gateway_analytics_router.put(
    "/blocking-rules/{rule_id}",
    response_model=BlockingRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a blocking rule",
    description="Update an existing blocking rule",
)
async def update_blocking_rule(
    rule_id: UUID,
    update_data: BlockingRuleUpdate,
    access_helper: AccessHelper = Depends(get_access),
) -> BlockingRuleResponse:
    """Update a blocking rule.

    Only the fields provided in the update data will be modified.
    The user must have access to the project that owns the rule.
    """
    service = BlockingRulesService(access_helper.session, access_helper.user)
    rule = await service.update_blocking_rule(rule_id, update_data)
    return BlockingRuleResponse(success=True, data=rule)


@gateway_analytics_router.delete(
    "/blocking-rules/{rule_id}",
    response_model=BlockingRuleDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a blocking rule",
    description="Delete a blocking rule",
)
async def delete_blocking_rule(
    rule_id: UUID,
    access_helper: AccessHelper = Depends(get_access),
) -> BlockingRuleDeleteResponse:
    """Delete a blocking rule.

    The rule will be removed from both the database and Redis cache.
    The user must have access to the project that owns the rule.
    """
    service = BlockingRulesService(access_helper.session, access_helper.user)
    await service.delete_blocking_rule(rule_id)
    return BlockingRuleDeleteResponse(success=True, id=rule_id)


@gateway_analytics_router.post(
    "/blocking-rules/sync",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync blocking rules to Redis",
    description="Sync blocking rules to Redis for real-time access by the gateway",
)
async def sync_blocking_rules(
    sync_request: BlockingRuleSyncRequest,
    access_helper: AccessHelper = Depends(get_access),
) -> SuccessResponse:
    """Sync blocking rules to Redis for real-time access.

    This endpoint ensures that all active blocking rules are available
    in Redis for the gateway to enforce in real-time.
    """
    service = BlockingRulesService(access_helper.session, access_helper.user)
    result = await service.sync_blocking_rules(sync_request.project_ids)
    return SuccessResponse(
        success=True,
        message=f"Successfully synced {result['synced_rules']} rules to Redis",
    )
