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

"""Gateway analytics services for proxying and filtering requests to budmetrics."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import BlockingRuleStatus, BlockingRuleType
from ..commons.db_utils import SessionMixin
from ..commons.exceptions import ClientException
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..model_ops.models import Model
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from ..shared.redis_service import RedisService
from ..user_ops.models import User as UserModel
from .crud import BlockingRuleDataManager
from .models import GatewayBlockingRule
from .schemas import (
    AutoBlockingConfig,
    BlockingRule,
    BlockingRuleCreate,
    BlockingRuleListResponse,
    BlockingRuleResponse,
    BlockingRuleUpdate,
    BlockingStatsResponse,
    ClientAnalyticsResponse,
    GatewayAnalyticsRequest,
    GatewayAnalyticsResponse,
    GeographicalStatsResponse,
    TopRoutesResponse,
)


logger = logging.get_logger(__name__)


class GatewayAnalyticsService(SessionMixin):
    """Service for handling gateway analytics operations."""

    def __init__(self, session: Session, user: UserModel):
        """Initialize the service with database session and user context.

        Args:
            session: Database session
            user: Current authenticated user
        """
        super().__init__(session)
        self.user = user

    async def _get_user_accessible_projects(self) -> List[UUID]:
        """Get list of project IDs accessible by the current user.

        Returns:
            List of project UUIDs the user has access to
        """
        project_data_manager = ProjectDataManager(self.session)
        projects = await project_data_manager.get_projects_by_user(self.user.id)
        return [project.id for project in projects]

    async def _proxy_to_budmetrics(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Proxy request to budmetrics service via Dapr.

        Args:
            endpoint: The budmetrics endpoint to call (e.g., "/gateway/analytics")
            method: HTTP method (GET or POST)
            json_data: JSON body for POST requests
            params: Query parameters for GET requests

        Returns:
            Response data from budmetrics

        Raises:
            ClientException: If the request fails
        """
        # Construct the Dapr invocation URL
        url = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method{endpoint}"

        logger.debug(f"Proxying {method} request to budmetrics: {url}")
        if json_data:
            logger.debug(f"Request body: {json_data}")
        if params:
            logger.debug(f"Query params: {params}")

        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {"url": url}
                if method == "POST" and json_data:
                    kwargs["json"] = json_data
                elif method == "GET" and params:
                    kwargs["params"] = params

                async with session.request(method, **kwargs) as response:
                    response_data = await response.json()

                    if response.status != status.HTTP_200_OK:
                        logger.error(f"Budmetrics request failed: {response.status} {response_data}")
                        raise ClientException(
                            response_data.get("message", "Analytics request failed"),
                            status_code=response.status,
                        )

                    return response_data

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to proxy request to budmetrics: {e}")
            raise ClientException(
                "Failed to connect to analytics service",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e

    async def _enrich_with_names(self, data: Dict[str, Any]) -> None:
        """Enrich response data with names for project, model, and endpoint IDs.

        Args:
            data: Response data to enrich in-place
        """
        try:
            # Collect all unique IDs
            project_ids = set()
            model_ids = set()
            endpoint_ids = set()

            # Helper function to extract IDs from items
            def extract_ids(items: List[Dict[str, Any]]) -> None:
                for item in items:
                    if isinstance(item, dict):
                        if project_id := item.get("project_id"):
                            project_ids.add(project_id)
                        if model_id := item.get("model_id"):
                            model_ids.add(model_id)
                        if endpoint_id := item.get("endpoint_id"):
                            endpoint_ids.add(endpoint_id)

            # Extract IDs based on response structure
            if "items" in data:
                items = data["items"]
                if isinstance(items, list):
                    # Check if items contain time buckets (for analytics response)
                    if items and isinstance(items[0], dict) and "items" in items[0]:
                        for bucket in items:
                            extract_ids(bucket.get("items", []))
                    else:
                        # Direct items list
                        extract_ids(items)

            # Fetch names for all IDs
            project_names = {}
            model_names = {}
            endpoint_names = {}

            if project_ids:
            if project_ids:
                stmt = select(ProjectModel).where(ProjectModel.id.in_(list(project_ids)))
                result = await self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}

            if model_ids:
                stmt = select(Model).where(Model.id.in_(list(model_ids)))
                result = await self.session.execute(stmt)
                models = result.scalars().all()
                model_names = {str(m.id): m.name for m in models}

            if endpoint_ids:
                stmt = select(EndpointModel).where(EndpointModel.id.in_(list(endpoint_ids)))
                result = await self.session.execute(stmt)
                endpoints = result.scalars().all()
                endpoint_names = {str(e.id): e.name for e in endpoints}

            # Helper function to add names to items
            def add_names(items: List[Dict[str, Any]]) -> None:
                for item in items:
                    if isinstance(item, dict):
                        if project_id := item.get("project_id"):
                            item["project_name"] = project_names.get(str(project_id), "Unknown")
                        if model_id := item.get("model_id"):
                            item["model_name"] = model_names.get(str(model_id), "Unknown")
                        if endpoint_id := item.get("endpoint_id"):
                            item["endpoint_name"] = endpoint_names.get(str(endpoint_id), "Unknown")

            # Add names based on response structure
            if "items" in data:
                items = data["items"]
                if isinstance(items, list):
                    if items and isinstance(items[0], dict) and "items" in items[0]:
                        for bucket in items:
                            add_names(bucket.get("items", []))
                    else:
                        add_names(items)

        except Exception as e:
            logger.warning(f"Failed to enrich response with names: {e}")
            # Don't fail the entire request if enrichment fails

    async def query_analytics(self, request: GatewayAnalyticsRequest) -> GatewayAnalyticsResponse:
        """Query gateway analytics with user context filtering.

        Args:
            request: Analytics query request

        Returns:
            Gateway analytics response with enriched data
        """
        # If no project IDs specified, use user's accessible projects
        if not request.project_ids:
            request.project_ids = await self._get_user_accessible_projects()

        # Prepare request body for budmetrics
        budmetrics_request = {
            "project_ids": [str(pid) for pid in request.project_ids] if request.project_ids else None,
            "model_ids": [str(mid) for mid in request.model_ids] if request.model_ids else None,
            "endpoint_ids": [str(eid) for eid in request.endpoint_ids] if request.endpoint_ids else None,
            "start_time": request.start_time.isoformat(),
            "end_time": request.end_time.isoformat(),
            "time_bucket": request.time_bucket,
            "metrics": request.metrics,
            "group_by": request.group_by,
            "filters": request.filters,
        }

        # Remove None values
        budmetrics_request = {k: v for k, v in budmetrics_request.items() if v is not None}

        # Proxy to budmetrics
        response_data = await self._proxy_to_budmetrics(
            "/gateway/analytics",
            method="POST",
            json_data=budmetrics_request,
        )

        # Enrich with names
        await self._enrich_with_names(response_data)

        return GatewayAnalyticsResponse(**response_data)

    async def get_geographical_stats(
        self,
        start_time: datetime,
        end_time: datetime,
        project_ids: Optional[List[UUID]] = None,
    ) -> GeographicalStatsResponse:
        """Get geographical distribution statistics.

        Args:
            start_time: Start time for the query
            end_time: End time for the query
            project_ids: Optional list of project IDs to filter by

        Returns:
            Geographical statistics response
        """
        # If no project IDs specified, use user's accessible projects
        if not project_ids:
            project_ids = await self._get_user_accessible_projects()

        # Prepare query parameters
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        if project_ids:
            params["project_ids"] = ",".join(str(pid) for pid in project_ids)

        # Proxy to budmetrics
        response_data = await self._proxy_to_budmetrics(
            "/gateway/geographical-stats",
            method="GET",
            params=params,
        )

        return GeographicalStatsResponse(**response_data)

    async def get_blocking_stats(
        self,
        start_time: datetime,
        end_time: datetime,
        project_ids: Optional[List[UUID]] = None,
    ) -> BlockingStatsResponse:
        """Get blocking statistics for security analysis.

        Args:
            start_time: Start time for the query
            end_time: End time for the query
            project_ids: Optional list of project IDs to filter by

        Returns:
            Blocking statistics response
        """
        # If no project IDs specified, use user's accessible projects
        if not project_ids:
            project_ids = await self._get_user_accessible_projects()

        # Prepare query parameters
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        if project_ids:
            params["project_ids"] = ",".join(str(pid) for pid in project_ids)

        # Proxy to budmetrics
        response_data = await self._proxy_to_budmetrics(
            "/gateway/blocking-stats",
            method="GET",
            params=params,
        )

        # Enrich with project names
        await self._enrich_with_names(response_data)

        return BlockingStatsResponse(**response_data)

    async def get_top_routes(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10,
        project_ids: Optional[List[UUID]] = None,
    ) -> TopRoutesResponse:
        """Get top API routes by request count.

        Args:
            start_time: Start time for the query
            end_time: End time for the query
            limit: Maximum number of routes to return
            project_ids: Optional list of project IDs to filter by

        Returns:
            Top routes response
        """
        # If no project IDs specified, use user's accessible projects
        if not project_ids:
            project_ids = await self._get_user_accessible_projects()

        # Prepare query parameters
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "limit": limit,
        }
        if project_ids:
            params["project_ids"] = ",".join(str(pid) for pid in project_ids)

        # Proxy to budmetrics
        response_data = await self._proxy_to_budmetrics(
            "/gateway/top-routes",
            method="GET",
            params=params,
        )

        # Enrich with names
        await self._enrich_with_names(response_data)

        return TopRoutesResponse(**response_data)

    async def get_client_analytics(
        self,
        start_time: datetime,
        end_time: datetime,
        project_ids: Optional[List[UUID]] = None,
    ) -> ClientAnalyticsResponse:
        """Get client-level analytics.

        Args:
            start_time: Start time for the query
            end_time: End time for the query
            project_ids: Optional list of project IDs to filter by

        Returns:
            Client analytics response
        """
        # If no project IDs specified, use user's accessible projects
        if not project_ids:
            project_ids = await self._get_user_accessible_projects()

        # Prepare query parameters
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        if project_ids:
            params["project_ids"] = ",".join(str(pid) for pid in project_ids)

        # Proxy to budmetrics
        response_data = await self._proxy_to_budmetrics(
            "/gateway/client-analytics",
            method="GET",
            params=params,
        )

        return ClientAnalyticsResponse(**response_data)


class BlockingRulesService(SessionMixin):
    """Service for managing gateway blocking rules."""

    def __init__(self, session: Session, user: UserModel):
        """Initialize the service with database session and user context.

        Args:
            session: Database session
            user: Current authenticated user
        """
        super().__init__(session)
        self.user = user
        self.redis_service = RedisService()
        self.data_manager = BlockingRuleDataManager(session)

    async def _get_user_accessible_projects(self) -> List[UUID]:
        """Get list of project IDs accessible by the current user.

        Returns:
            List of project UUIDs the user has access to
        """
        project_data_manager = ProjectDataManager(self.session)
        projects = await project_data_manager.get_projects_by_user(self.user.id)
        return [project.id for project in projects]

    async def _validate_project_access(self, project_id: UUID) -> None:
        """Validate user has access to the project.

        Args:
            project_id: Project ID to check

        Raises:
            ClientException: If user doesn't have access
        """
        accessible_projects = await self._get_user_accessible_projects()
        if project_id not in accessible_projects:
            raise ClientException(
                "You don't have access to this project",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    async def _validate_rule_config(self, rule_type: BlockingRuleType, rule_config: Dict[str, Any]) -> None:
        """Validate rule configuration based on rule type.

        Args:
            rule_type: Type of blocking rule
            rule_config: Rule configuration

        Raises:
            ClientException: If configuration is invalid
        """
        if rule_type == BlockingRuleType.IP_BLOCKING:
            if "ip_addresses" not in rule_config or not isinstance(rule_config["ip_addresses"], list):
                raise ClientException(
                    "IP blocking rules must have 'ip_addresses' list in config",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        elif rule_type == BlockingRuleType.COUNTRY_BLOCKING:
            if "countries" not in rule_config or not isinstance(rule_config["countries"], list):
                raise ClientException(
                    "Country blocking rules must have 'countries' list in config",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        elif rule_type == BlockingRuleType.USER_AGENT_BLOCKING:
            if "patterns" not in rule_config or not isinstance(rule_config["patterns"], list):
                raise ClientException(
                    "User agent blocking rules must have 'patterns' list in config",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        elif rule_type == BlockingRuleType.RATE_BASED_BLOCKING:
            required_fields = ["threshold", "window_seconds"]
            for field in required_fields:
                if field not in rule_config:
                    raise ClientException(
                        f"Rate-based blocking rules must have '{field}' in config",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

    async def _sync_rule_to_redis(self, rule: GatewayBlockingRule) -> None:
        """Sync a single rule to Redis for real-time access.

        Args:
            rule: Blocking rule to sync
        """
        # Create Redis key for the rule
        redis_key = f"blocking_rule:{rule.project_id}:{rule.id}"

        # Prepare rule data for Redis
        rule_data = {
            "id": str(rule.id),
            "project_id": str(rule.project_id),
            "endpoint_id": str(rule.endpoint_id) if rule.endpoint_id else None,
            "rule_type": rule.rule_type,
            "rule_config": rule.rule_config,
            "priority": rule.priority,
            "status": rule.status,
        }

        # Store in Redis with 24-hour expiry
        await self.redis_service.set(redis_key, json.dumps(rule_data), ttl=86400)

        # Also add to project's rule set for quick lookup
        project_rules_key = f"project_blocking_rules:{rule.project_id}"
        await self.redis_service.sadd(project_rules_key, str(rule.id))

    async def _remove_rule_from_redis(self, rule: GatewayBlockingRule) -> None:
        """Remove a rule from Redis.

        Args:
            rule: Blocking rule to remove
        """
        redis_key = f"blocking_rule:{rule.project_id}:{rule.id}"
        await self.redis_service.delete(redis_key)

        # Remove from project's rule set
        project_rules_key = f"project_blocking_rules:{rule.project_id}"
        await self.redis_service.srem(project_rules_key, str(rule.id))

    async def create_blocking_rule(
        self,
        project_id: UUID,
        rule_data: BlockingRuleCreate,
    ) -> BlockingRule:
        """Create a new blocking rule.

        Args:
            project_id: Project ID
            rule_data: Rule creation data

        Returns:
            Created blocking rule
        """
        # Validate project access
        await self._validate_project_access(project_id)

        # Validate rule configuration
        await self._validate_rule_config(rule_data.rule_type, rule_data.rule_config)

        # Check if rule name already exists
        name_exists = await self.data_manager.check_rule_name_exists(project_id, rule_data.name)
        if name_exists:
            raise ClientException(
                f"A rule with name '{rule_data.name}' already exists in this project",
                status_code=status.HTTP_409_CONFLICT,
            )

        # Create the rule
        db_rule = await self.data_manager.create_blocking_rule(
            project_id=project_id,
            user_id=self.user.id,
            rule_data=rule_data,
        )

        # Sync to Redis for real-time access
        await self._sync_rule_to_redis(db_rule)

        # Convert to response schema
        return BlockingRule.model_validate(db_rule)

    async def get_blocking_rule(self, rule_id: UUID) -> BlockingRule:
        """Get a specific blocking rule.

        Args:
            rule_id: Rule ID

        Returns:
            Blocking rule details

        Raises:
            ClientException: If rule not found or access denied
        """
        accessible_projects = await self._get_user_accessible_projects()

        rule = await self.data_manager.get_blocking_rule(rule_id, accessible_projects)
        if not rule:
            raise ClientException(
                "Blocking rule not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Enrich with names
        response = BlockingRule.model_validate(rule)
        if rule.project:
            response.project_name = rule.project.name
        if rule.endpoint:
            response.endpoint_name = rule.endpoint.name
        if rule.created_user:
            response.created_by_name = rule.created_user.name

        return response

    async def list_blocking_rules(
        self,
        project_id: Optional[UUID] = None,
        rule_type: Optional[BlockingRuleType] = None,
        status: Optional[BlockingRuleStatus] = None,
        endpoint_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BlockingRuleListResponse:
        """List blocking rules with filters.

        Args:
            project_id: Optional specific project ID
            rule_type: Optional rule type filter
            status: Optional status filter
            endpoint_id: Optional endpoint ID filter
            page: Page number
            page_size: Items per page

        Returns:
            List of blocking rules
        """
        # Get accessible projects
        accessible_projects = await self._get_user_accessible_projects()

        # If specific project requested, validate access
        if project_id:
            if project_id not in accessible_projects:
                raise ClientException(
                    "You don't have access to this project",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            project_ids = [project_id]
        else:
            project_ids = accessible_projects

        # Get rules
        rules, total = await self.data_manager.list_blocking_rules(
            project_ids=project_ids,
            rule_type=rule_type,
            status=status,
            endpoint_id=endpoint_id,
            page=page,
            page_size=page_size,
        )

        # Convert to response schema with enriched data
        items = []
        for rule in rules:
            item = BlockingRule.model_validate(rule)
            if rule.project:
                item.project_name = rule.project.name
            if rule.endpoint:
                item.endpoint_name = rule.endpoint.name
            if rule.created_user:
                item.created_by_name = rule.created_user.name
            items.append(item)

        return BlockingRuleListResponse(
            success=True,
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_blocking_rule(
        self,
        rule_id: UUID,
        update_data: BlockingRuleUpdate,
    ) -> BlockingRule:
        """Update a blocking rule.

        Args:
            rule_id: Rule ID
            update_data: Update data

        Returns:
            Updated blocking rule

        Raises:
            ClientException: If rule not found or access denied
        """
        accessible_projects = await self._get_user_accessible_projects()

        # Get existing rule to check access
        existing_rule = await self.data_manager.get_blocking_rule(rule_id, accessible_projects)
        if not existing_rule:
            raise ClientException(
                "Blocking rule not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # If updating rule config, validate it
        if update_data.rule_config is not None:
            await self._validate_rule_config(existing_rule.rule_type, update_data.rule_config)

        # If updating name, check uniqueness
        if update_data.name is not None and update_data.name != existing_rule.name:
            name_exists = await self.data_manager.check_rule_name_exists(
                existing_rule.project_id,
                update_data.name,
                exclude_id=rule_id,
            )
            if name_exists:
                raise ClientException(
                    f"A rule with name '{update_data.name}' already exists in this project",
                    status_code=status.HTTP_409_CONFLICT,
                )

        # Update the rule
        updated_rule = await self.data_manager.update_blocking_rule(
            rule_id=rule_id,
            update_data=update_data,
            project_ids=accessible_projects,
        )

        # Sync to Redis
        if updated_rule.status == BlockingRuleStatus.ACTIVE:
            await self._sync_rule_to_redis(updated_rule)
        else:
            await self._remove_rule_from_redis(updated_rule)

        # Convert to response schema
        response = BlockingRule.model_validate(updated_rule)
        if updated_rule.project:
            response.project_name = updated_rule.project.name
        if updated_rule.endpoint:
            response.endpoint_name = updated_rule.endpoint.name
        if updated_rule.created_user:
            response.created_by_name = updated_rule.created_user.name

        return response

    async def delete_blocking_rule(self, rule_id: UUID) -> bool:
        """Delete a blocking rule.

        Args:
            rule_id: Rule ID

        Returns:
            True if deleted

        Raises:
            ClientException: If rule not found or access denied
        """
        accessible_projects = await self._get_user_accessible_projects()

        # Get rule to remove from Redis
        rule = await self.data_manager.get_blocking_rule(rule_id, accessible_projects)
        if not rule:
            raise ClientException(
                "Blocking rule not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Delete from database
        deleted = await self.data_manager.delete_blocking_rule(rule_id, accessible_projects)

        if deleted:
            # Remove from Redis
            await self._remove_rule_from_redis(rule)

        return deleted

    async def sync_blocking_rules(self, project_ids: Optional[List[UUID]] = None) -> Dict[str, Any]:
        """Sync blocking rules to Redis for real-time access.

        Args:
            project_ids: Optional list of project IDs to sync

        Returns:
            Sync summary
        """
        # If no specific projects, use user's accessible projects
        if not project_ids:
            project_ids = await self._get_user_accessible_projects()
        else:
            # Validate access to specified projects
            accessible_projects = await self._get_user_accessible_projects()
            for project_id in project_ids:
                if project_id not in accessible_projects:
                    raise ClientException(
                        f"You don't have access to project {project_id}",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

        # Get all active rules for these projects
        rules = await self.data_manager.get_active_rules_for_sync(project_ids)

        # Sync each rule to Redis
        synced_count = 0
        for rule in rules:
            await self._sync_rule_to_redis(rule)
            synced_count += 1

        logger.info(f"Synced {synced_count} blocking rules to Redis for projects {project_ids}")

        return {
            "synced_rules": synced_count,
            "project_ids": [str(pid) for pid in project_ids],
        }

    async def create_auto_blocking_rule(
        self,
        project_id: UUID,
        ip_address: str,
        reason: str,
        duration_minutes: int = 1440,
    ) -> BlockingRule:
        """Create an automatic blocking rule based on analytics.

        Args:
            project_id: Project ID
            ip_address: IP address to block
            reason: Reason for blocking
            duration_minutes: How long to block (default 24 hours)

        Returns:
            Created blocking rule
        """
        # Create rule data
        rule_data = BlockingRuleCreate(
            name=f"Auto-block: {ip_address}",
            description=f"Automatically blocked due to: {reason}",
            rule_type=BlockingRuleType.IP_BLOCKING,
            rule_config={"ip_addresses": [ip_address]},
            reason=reason,
            priority=100,  # High priority for auto-blocks
        )

        # Create the rule
        db_rule = await self.data_manager.create_blocking_rule(
            project_id=project_id,
            user_id=self.user.id,
            rule_data=rule_data,
        )

        # Sync to Redis with expiry
        await self._sync_rule_to_redis(db_rule)

        # Schedule automatic removal after duration
        # This would typically be done via a background task or workflow
        logger.info(
            f"Created auto-blocking rule for IP {ip_address} in project {project_id}, "
            f"expires in {duration_minutes} minutes"
        )

        return BlockingRule.model_validate(db_rule)
