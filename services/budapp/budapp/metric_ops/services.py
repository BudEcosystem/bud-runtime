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

"""The metric ops services. Contains business logic for metric ops."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import aiohttp
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import BlockingRuleStatus, BlockingRuleType
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException

from ..cluster_ops.crud import ClusterDataManager
from ..cluster_ops.models import Cluster as ClusterModel
from ..commons.constants import (
    ClusterStatusEnum,
    EndpointStatusEnum,
    ModelProviderTypeEnum,
    ModelStatusEnum,
    ProjectStatusEnum,
    UserTypeEnum,
)
from ..endpoint_ops.crud import AdapterDataManager, EndpointDataManager
from ..endpoint_ops.models import Adapter as AdapterModel
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..model_ops.crud import ModelDataManager
from ..model_ops.models import Model
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from ..project_ops.services import ProjectService
from ..shared.redis_service import RedisService
from ..user_ops.models import User as UserModel
from ..user_ops.schemas import User
from .crud import BlockingRuleDataManager
from .models import GatewayBlockingRule
from .schemas import (
    # New aggregated metrics schemas
    AggregatedMetricsRequest,
    AggregatedMetricsResponse,
    # Gateway Analytics schemas
    AutoBlockingConfig,
    BlockingRule,
    BlockingRuleCreate,
    BlockingRuleListResponse,
    BlockingRuleResponse,
    BlockingRulesStatsOverviewResponse,
    BlockingRuleUpdate,
    BlockingStats,
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
    InferenceListItem,
    InferenceListRequest,
    InferenceListResponse,
    TimeSeriesRequest,
    TimeSeriesResponse,
    TopRoutesResponse,
)


logger = logging.get_logger(__name__)


class BudMetricService(SessionMixin):
    """Bud Metric service."""

    async def proxy_analytics_request(self, request_body: Dict) -> Dict:
        """Proxy analytics request to the observability endpoint and enrich with names."""
        analytics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/analytics"

        logger.debug(f"Proxying analytics request to bud_metrics: {request_body}")

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    analytics_endpoint,
                    json=request_body,
                ) as response,
            ):
                response_data = await response.json()

                # Return the response as-is, including the status code
                if response.status != status.HTTP_200_OK:
                    logger.error(f"Analytics request failed: {response.status} {response_data}")
                    raise ClientException("Analytics request failed", status_code=response.status)

                # Enrich response with names
                await self._enrich_response_with_names(response_data)

                return response_data
        except ClientException:
            raise
        except Exception as e:
            logger.exception("Failed to proxy analytics request")
            raise ClientException(
                "Failed to proxy analytics request", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _enrich_response_with_names(self, response_data: Dict) -> None:
        """Enrich the response data with names for project, model, and endpoint IDs."""
        try:
            from sqlalchemy import select

            # Validate response_data is a dictionary
            if not isinstance(response_data, dict):
                logger.warning(f"Response data is not a dictionary: {type(response_data)}")
                return

            # Collect all unique IDs from the response
            project_ids = set()
            model_ids = set()
            endpoint_ids = set()

            # Extract IDs from the response structure
            items_list = response_data.get("items", [])
            if not items_list:
                return

            for time_bucket in items_list:
                if not isinstance(time_bucket, dict):
                    continue

                bucket_items = time_bucket.get("items", [])
                for item in bucket_items:
                    if not isinstance(item, dict):
                        continue

                    # Extract IDs if they exist
                    if project_id := item.get("project_id"):
                        project_ids.add(project_id)
                    if model_id := item.get("model_id"):
                        model_ids.add(model_id)
                    if endpoint_id := item.get("endpoint_id"):
                        endpoint_ids.add(endpoint_id)

            # Fetch names for all IDs
            project_names = {}
            model_names = {}
            endpoint_names = {}
            adapter_names = {}

            if project_ids:
                # Query projects
                stmt = select(ProjectModel).where(ProjectModel.id.in_(list(project_ids)))
                result = self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}

            if model_ids:
                # Query models
                stmt = select(Model).where(Model.id.in_(list(model_ids)))
                result = self.session.execute(stmt)
                models = result.scalars().all()
                model_names = {str(m.id): m.name for m in models}

            if endpoint_ids:
                # Query endpoints
                stmt = select(EndpointModel).where(EndpointModel.id.in_(list(endpoint_ids)))
                result = self.session.execute(stmt)
                endpoints = result.scalars().all()
                endpoint_names = {str(e.id): e.name for e in endpoints}

                # Check for adapters: any endpoint_ids not found might be adapter IDs
                found_endpoint_ids = set(endpoint_names.keys())
                missing_ids = {str(eid) for eid in endpoint_ids} - found_endpoint_ids
                if missing_ids:
                    stmt = select(AdapterModel).where(AdapterModel.id.in_([UUID(mid) for mid in missing_ids]))
                    result = self.session.execute(stmt)
                    adapters = result.scalars().all()
                    adapter_names.update({str(a.id): a.name for a in adapters})

            # Add names to the response items
            for time_bucket in items_list:
                if not isinstance(time_bucket, dict):
                    continue

                bucket_items = time_bucket.get("items", [])
                for item in bucket_items:
                    if not isinstance(item, dict):
                        continue

                    # Add names for each ID type
                    if project_id := item.get("project_id"):
                        item["project_name"] = project_names.get(str(project_id), "Unknown")
                    if model_id := item.get("model_id"):
                        item["model_name"] = model_names.get(str(model_id), "Unknown")
                    if endpoint_id := item.get("endpoint_id"):
                        endpoint_id_str = str(endpoint_id)
                        if endpoint_name := endpoint_names.get(endpoint_id_str):
                            item["endpoint_name"] = endpoint_name
                        elif adapter_name := adapter_names.get(endpoint_id_str):
                            item["endpoint_name"] = adapter_name
                            item["adapter_name"] = adapter_name
                            item["is_adapter"] = True
                        else:
                            item["endpoint_name"] = "Unknown"

        except Exception as e:
            logger.warning(f"Failed to enrich response with names: {e}")
            # Don't fail the entire request if enrichment fails

    async def list_inferences(self, request: InferenceListRequest, current_user: User) -> InferenceListResponse:
        """List inference requests with access control and enrichment.

        Args:
            request: The inference list request parameters
            current_user: The authenticated user

        Returns:
            InferenceListResponse with enriched data
        """
        from ..commons.constants import UserTypeEnum

        # Check user access to the specified project if filtered
        if request.project_id:
            # Verify user has access to the project
            project = await ProjectDataManager(self.session).retrieve_project_by_fields(
                {"id": request.project_id}, missing_ok=True
            )
            if not project:
                raise ClientException("Project not found", status_code=status.HTTP_404_NOT_FOUND)

            # Check if user is member of the project
            project_service = ProjectService(self.session)
            try:
                await project_service.check_project_membership(request.project_id, current_user.id)
            except HTTPException as e:
                raise ClientException("Access denied: User is not a member of the project", status_code=e.status_code)

        # Prepare request data with CLIENT-specific filtering
        request_data = request.model_dump(mode="json")

        # For CLIENT users, we need to filter by api_key_project_id instead of project_id
        if current_user.user_type == UserTypeEnum.CLIENT:
            # Ensure filters dictionary exists
            if request_data.get("filters") is None:
                request_data["filters"] = {}

            # Determine the api_key_project_id value(s) to filter by
            if request.project_id:
                # Convert project_id filter to api_key_project_id for CLIENT users
                # Always use a list for consistency
                api_key_project_id_value = [str(request.project_id)]
            else:
                # If no project_id provided, restrict to user's accessible api_key_project_ids
                project_service = ProjectService(self.session)
                user_projects, _ = await project_service.get_all_active_projects(
                    current_user, offset=0, limit=1000, filters={}, order_by=[], search=False
                )
                api_key_project_id_value = [str(project.project.id) for project in user_projects]

            # Apply the api_key_project_id filter and remove the project_id from top-level
            # Only add the filter if there are actually projects to filter by
            if api_key_project_id_value:
                request_data["filters"]["api_key_project_id"] = api_key_project_id_value
            request_data.pop("project_id", None)

            # Log the request data for debugging
            logger.info(f"CLIENT user inference request - api_key_project_id filter: {api_key_project_id_value}")
        else:
            # For ADMIN users, ensure filters dictionary exists if we need it
            if request_data.get("filters") is None:
                request_data["filters"] = {}

            # Log the request data for debugging
            logger.info(
                f"ADMIN user inference request - project_id: {request.project_id}, filters: {request_data.get('filters', {})}"
            )

        # Proxy request to budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/inferences/list"

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    metrics_endpoint,
                    json=request_data,
                ) as response,
            ):
                response_data = await response.json()

                if response.status != status.HTTP_200_OK:
                    logger.error(f"Inference list request failed: status={response.status}, response={response_data}")
                    error_detail = response_data.get("detail", "Failed to list inferences")

                    # Handle validation errors from budmetrics
                    if isinstance(error_detail, list) and len(error_detail) > 0:
                        # Extract the first error message
                        first_error = error_detail[0]
                        if isinstance(first_error, dict):
                            error_message = first_error.get("msg", "Validation error")
                            # Add more context if available
                            if "loc" in first_error:
                                field = ".".join(str(x) for x in first_error["loc"] if x != "body")
                                error_message = f"{field}: {error_message}"
                        else:
                            error_message = str(error_detail)
                    elif isinstance(error_detail, str):
                        error_message = error_detail
                    else:
                        error_message = "Failed to list inferences"

                    raise ClientException(
                        error_message,
                        status_code=response.status,
                    )

                # Enrich response with names
                await self._enrich_inference_list(response_data, current_user)

                # Add required message field for SuccessResponse
                if "message" not in response_data:
                    response_data["message"] = "Successfully retrieved inference list"

                # Convert to response model
                return InferenceListResponse(**response_data)

        except ClientException:
            raise
        except Exception as e:
            logger.exception("Failed to list inferences")
            raise ClientException(
                "Failed to list inferences", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def get_inference_details(self, inference_id: str, current_user: User) -> InferenceDetailResponse:
        """Get inference details with access control and enrichment.

        Args:
            inference_id: The inference ID
            current_user: The authenticated user

        Returns:
            InferenceDetailResponse with enriched data
        """
        # First get the inference details from budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/inferences/{inference_id}"

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(metrics_endpoint) as response,
            ):
                response_data = await response.json()

                if response.status == status.HTTP_404_NOT_FOUND:
                    raise ClientException("Inference not found", status_code=status.HTTP_404_NOT_FOUND)

                if response.status != status.HTTP_200_OK:
                    logger.error(f"Get inference request failed: {response.status}")
                    raise ClientException(
                        "Failed to get inference details",
                        status_code=response.status,
                    )

                # Check user access to the project
                # Import UserTypeEnum for user type checking
                from ..commons.constants import UserTypeEnum

                # For CLIENT users, check api_key_project_id; for others, check project_id
                if current_user.user_type == UserTypeEnum.CLIENT:
                    project_id = response_data.get("api_key_project_id")
                else:
                    project_id = response_data.get("project_id")

                if project_id:
                    project = await ProjectDataManager(self.session).retrieve_project_by_fields(
                        {"id": UUID(project_id)}, missing_ok=True
                    )
                    if not project:
                        raise ClientException("Access denied", status_code=status.HTTP_403_FORBIDDEN)

                    # Check if user is member of the project

                    project_service = ProjectService(self.session)
                    try:
                        await project_service.check_project_membership(UUID(project_id), current_user.id)
                    except HTTPException as e:
                        raise ClientException(
                            "Access denied: User is not a member of the project", status_code=e.status_code
                        )

                # Enrich response with names
                await self._enrich_inference_detail(response_data, current_user)

                logger.info(f"Response data: {response_data}")

                # Add required message field for SuccessResponse
                if "message" not in response_data:
                    response_data["message"] = "Successfully retrieved inference details"

                # Parse gateway_request and gateway_response from JSON strings if present
                if "gateway_request" in response_data and response_data["gateway_request"]:
                    try:
                        response_data["gateway_request"] = json.loads(response_data["gateway_request"])
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, set to None (schema expects Dict or None)
                        response_data["gateway_request"] = None

                if "gateway_response" in response_data and response_data["gateway_response"]:
                    try:
                        response_data["gateway_response"] = json.loads(response_data["gateway_response"])
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, set to None (schema expects Dict or None)
                        response_data["gateway_response"] = None

                # Convert to response model - extra fields will be ignored due to extra="ignore" in model config
                return InferenceDetailResponse(**response_data)

        except ClientException:
            raise
        except Exception as e:
            logger.exception("Failed to get inference details")
            raise ClientException(
                "Failed to get inference details", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def get_inference_feedback(self, inference_id: str, current_user: User) -> InferenceFeedbackResponse:
        """Get inference feedback with access control.

        Args:
            inference_id: The inference ID
            current_user: The authenticated user

        Returns:
            InferenceFeedbackResponse
        """
        # First verify the inference exists and user has access
        # This will raise appropriate exceptions if not found or no access
        await self.get_inference_details(inference_id, current_user)

        # Now get the feedback from budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/inferences/{inference_id}/feedback"

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(metrics_endpoint) as response,
            ):
                response_data = await response.json()

                if response.status != status.HTTP_200_OK:
                    logger.error(f"Get feedback request failed: {response.status}")
                    raise ClientException(
                        "Failed to get inference feedback",
                        status_code=response.status,
                    )

                # Add required message field for SuccessResponse
                if "message" not in response_data:
                    response_data["message"] = "Successfully retrieved inference feedback"

                # Convert to response model
                return InferenceFeedbackResponse(**response_data)

        except ClientException:
            raise
        except Exception as e:
            logger.exception("Failed to get inference feedback")
            raise ClientException(
                "Failed to get inference feedback", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _enrich_inference_list(self, response_data: Dict, current_user: User) -> None:
        """Enrich inference list with project, endpoint, and model names."""
        from ..commons.constants import UserTypeEnum

        try:
            items = response_data.get("items", [])
            if not items:
                return

            # Collect unique IDs
            project_ids: Set[UUID] = set()
            api_key_project_ids: Set[UUID] = set()  # For CLIENT users
            model_ids: Set[UUID] = set()
            endpoint_ids: Set[UUID] = set()

            # Determine which project ID field to use based on user type
            is_client = current_user.user_type == UserTypeEnum.CLIENT

            for item in items:
                # For CLIENT users, get project ID from api_key_project_id field
                # For ADMIN users, use the regular project_id field
                if is_client:
                    # CLIENT users: project name should come from api_key_project_id
                    if api_key_project_id := item.get("api_key_project_id"):
                        api_key_project_ids.add(UUID(api_key_project_id))
                else:
                    # ADMIN users: use regular project_id
                    if project_id := item.get("project_id"):
                        project_ids.add(UUID(project_id))

                if endpoint_id := item.get("endpoint_id"):
                    endpoint_ids.add(UUID(endpoint_id))
                if model_id := item.get("model_id"):
                    model_ids.add(UUID(model_id))

            # Fetch names for all IDs
            project_names = {}
            endpoint_names = {}
            adapter_names = {}
            model_names = {}

            # Fetch project names based on user type
            if is_client and api_key_project_ids:
                # For CLIENT users, fetch projects using api_key_project_ids
                from sqlalchemy import select

                stmt = select(ProjectModel).where(ProjectModel.id.in_(list(api_key_project_ids)))
                result = self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}
            elif not is_client and project_ids:
                # For ADMIN users, fetch projects using regular project_ids
                from sqlalchemy import select

                stmt = select(ProjectModel).where(ProjectModel.id.in_(list(project_ids)))
                result = self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}

            if endpoint_ids:
                # Query endpoints (including all statuses, even deleted)
                from sqlalchemy import select

                stmt = select(EndpointModel).where(EndpointModel.id.in_(list(endpoint_ids)))
                result = self.session.execute(stmt)
                endpoints = result.scalars().all()
                endpoint_names = {str(e.id): e.name for e in endpoints}

                # Check for adapters: any endpoint_ids not found might be adapter IDs
                # (endpoint_id field can hold either endpoint or adapter UUID)
                found_endpoint_ids = set(endpoint_names.keys())
                # Convert endpoint_ids (Set[UUID]) to strings for comparison with found_endpoint_ids (Set[str])
                missing_ids = {str(eid) for eid in endpoint_ids} - found_endpoint_ids
                if missing_ids:
                    stmt = select(AdapterModel).where(AdapterModel.id.in_([UUID(mid) for mid in missing_ids]))
                    result = self.session.execute(stmt)
                    adapters = result.scalars().all()
                    adapter_names.update({str(a.id): a.name for a in adapters})

            if model_ids:
                # Query models (including all statuses, even deleted)
                from sqlalchemy import select

                stmt = select(Model).where(Model.id.in_(list(model_ids)))
                result = self.session.execute(stmt)
                models = result.scalars().all()
                model_names = {str(m.id): m.name for m in models}

            # Add names to the response items
            for item in items:
                if is_client:
                    # For CLIENT users, use api_key_project_id to get project name
                    if api_key_project_id := item.get("api_key_project_id"):
                        item["project_name"] = project_names.get(str(api_key_project_id))
                else:
                    # For ADMIN users, use regular project_id
                    if project_id := item.get("project_id"):
                        item["project_name"] = project_names.get(str(project_id))

                if endpoint_id := item.get("endpoint_id"):
                    endpoint_id_str = str(endpoint_id)
                    if endpoint_name := endpoint_names.get(endpoint_id_str):
                        item["endpoint_name"] = endpoint_name
                    elif adapter_name := adapter_names.get(endpoint_id_str):
                        # endpoint_id is actually an adapter ID
                        item["endpoint_name"] = adapter_name
                        item["adapter_name"] = adapter_name
                        item["is_adapter"] = True
                if model_id := item.get("model_id"):
                    item["model_display_name"] = model_names.get(str(model_id))

        except Exception as e:
            logger.warning(f"Failed to enrich inference list: {e}")

    def _get_country_name(self, country_code: str) -> str:
        """Get human-readable country name from country code."""
        # Common country codes mapping
        country_map = {
            "US": "United States",
            "CA": "Canada",
            "GB": "United Kingdom",
            "DE": "Germany",
            "FR": "France",
            "JP": "Japan",
            "CN": "China",
            "IN": "India",
            "BR": "Brazil",
            "AU": "Australia",
            "NL": "Netherlands",
            "SE": "Sweden",
            "NO": "Norway",
            "DK": "Denmark",
            "FI": "Finland",
            "CH": "Switzerland",
            "AT": "Austria",
            "BE": "Belgium",
            "IT": "Italy",
            "ES": "Spain",
            "PT": "Portugal",
            "PL": "Poland",
            "CZ": "Czech Republic",
            "HU": "Hungary",
            "RO": "Romania",
            "BG": "Bulgaria",
            "GR": "Greece",
            "TR": "Turkey",
            "RU": "Russia",
            "KR": "South Korea",
            "SG": "Singapore",
            "HK": "Hong Kong",
            "TW": "Taiwan",
            "TH": "Thailand",
            "MY": "Malaysia",
            "ID": "Indonesia",
            "PH": "Philippines",
            "VN": "Vietnam",
            "ZA": "South Africa",
            "EG": "Egypt",
            "IL": "Israel",
            "SA": "Saudi Arabia",
            "AE": "United Arab Emirates",
            "MX": "Mexico",
            "AR": "Argentina",
            "CO": "Colombia",
            "CL": "Chile",
            "PE": "Peru",
            "NZ": "New Zealand",
        }
        return country_map.get(country_code.upper(), country_code)

    async def _enrich_inference_detail(self, response_data: Dict, current_user: User) -> None:
        """Enrich inference detail with project, endpoint, and model names."""
        from ..commons.constants import UserTypeEnum

        try:
            # Determine which project ID field to use based on user type
            is_client = current_user.user_type == UserTypeEnum.CLIENT

            # Get the IDs from response
            # For CLIENT users, use api_key_project_id for project name
            # For ADMIN users, use regular project_id
            project_id = response_data.get("api_key_project_id") if is_client else response_data.get("project_id")

            endpoint_id = response_data.get("endpoint_id")
            model_id = response_data.get("model_id")

            # Fetch names
            if project_id:
                project = await ProjectDataManager(self.session).retrieve_project_by_fields(
                    {"id": UUID(project_id)}, missing_ok=True
                )
                if project:
                    response_data["project_name"] = project.name

            if endpoint_id:
                endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                    EndpointModel, {"id": UUID(endpoint_id)}, missing_ok=True
                )
                if endpoint:
                    response_data["endpoint_name"] = endpoint.name
                else:
                    # endpoint_id might be an adapter ID - check Adapter table
                    adapter = await AdapterDataManager(self.session).retrieve_by_fields(
                        AdapterModel, {"id": UUID(endpoint_id)}, missing_ok=True
                    )
                    if adapter:
                        response_data["endpoint_name"] = adapter.name
                        response_data["adapter_name"] = adapter.name
                        response_data["is_adapter"] = True

            if model_id:
                model = await ModelDataManager(self.session).retrieve_by_fields(
                    Model, {"id": UUID(model_id)}, missing_ok=True
                )
                if model:
                    response_data["model_display_name"] = model.name

            # Enrich gateway metadata with country names
            if gateway_metadata := response_data.get("gateway_metadata"):
                if isinstance(gateway_metadata, dict):
                    if country_code := gateway_metadata.get("country_code"):
                        gateway_metadata["country_name"] = self._get_country_name(country_code)

        except Exception as e:
            logger.warning(f"Failed to enrich inference detail: {e}")

    async def proxy_aggregated_metrics(self, request_body: Dict[str, Any], current_user: User) -> Dict[str, Any]:
        """Proxy aggregated metrics request to budmetrics with access control and enrichment."""
        # Apply user's project access restrictions
        try:
            await self._apply_user_project_filter(request_body, current_user)
        except Exception as e:
            logger.warning(f"Failed to apply project filter, proceeding without: {e}")

        # Proxy to budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/metrics/aggregated"

        # Try with filters first, then without if it fails
        for attempt, try_without_filters in enumerate([False, True]):
            try:
                request_to_send = request_body.copy()
                if try_without_filters and attempt > 0:
                    # Remove filters that might be causing validation issues
                    request_to_send.pop("filters", None)
                    logger.info("Retrying aggregated metrics request without filters")

                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        metrics_endpoint,
                        json=request_to_send,
                    ) as response,
                ):
                    response_data = await response.json()

                    if response.status == status.HTTP_200_OK:
                        # Success! Enrich and return
                        await self._enrich_aggregated_metrics_response(response_data)

                        # Add required message field
                        if "message" not in response_data:
                            response_data["message"] = "Successfully retrieved aggregated metrics"

                        return response_data
                    else:
                        logger.error(f"Aggregated metrics request failed: {response.status}")
                        if attempt == 0:  # Try again without filters
                            continue
                        else:
                            raise ClientException(
                                "Failed to get aggregated metrics",
                                status_code=response.status,
                            )

            except ClientException:
                if attempt == 0:  # Try again without filters
                    continue
                else:
                    raise
            except Exception as e:
                if attempt == 0:  # Try again without filters
                    logger.warning(f"First attempt failed, retrying without filters: {e}")
                    continue
                else:
                    logger.exception("Failed to proxy aggregated metrics request")
                    raise ClientException(
                        "Failed to proxy aggregated metrics request", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    ) from e

        # This shouldn't be reached, but just in case
        raise ClientException(
            "Failed to get aggregated metrics after retries", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    async def proxy_time_series_metrics(self, request_body: Dict[str, Any], current_user: User) -> Dict[str, Any]:
        """Proxy time-series metrics request to budmetrics with access control and enrichment."""
        # Apply user's project access restrictions
        try:
            await self._apply_user_project_filter(request_body, current_user)
        except Exception as e:
            logger.warning(f"Failed to apply project filter, proceeding without: {e}")

        # Proxy to budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/metrics/time-series"

        # Try with filters first, then without if it fails
        for attempt, try_without_filters in enumerate([False, True]):
            try:
                request_to_send = request_body.copy()
                if try_without_filters and attempt > 0:
                    # Remove filters and grouping that might be causing SQL issues
                    request_to_send.pop("filters", None)
                    request_to_send.pop("group_by", None)
                    logger.info("Retrying time-series metrics request without filters/grouping")

                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        metrics_endpoint,
                        json=request_to_send,
                    ) as response,
                ):
                    response_data = await response.json()

                    if response.status == status.HTTP_200_OK:
                        # Success! Enrich and return
                        await self._enrich_time_series_response(response_data)

                        # Add required message field
                        if "message" not in response_data:
                            response_data["message"] = "Successfully retrieved time-series data"

                        return response_data
                    else:
                        logger.error(f"Time-series metrics request failed: {response.status}")
                        if attempt == 0:  # Try again without filters
                            continue
                        else:
                            raise ClientException(
                                "Failed to get time-series metrics",
                                status_code=response.status,
                            )

            except ClientException:
                if attempt == 0:  # Try again without filters
                    continue
                else:
                    raise
            except Exception as e:
                if attempt == 0:  # Try again without filters
                    logger.warning(f"First attempt failed, retrying without filters/grouping: {e}")
                    continue
                else:
                    logger.exception("Failed to proxy time-series metrics request")
                    raise ClientException(
                        "Failed to proxy time-series metrics request",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    ) from e

        # This shouldn't be reached, but just in case
        raise ClientException(
            "Failed to get time-series metrics after retries", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    async def proxy_geographic_metrics(self, request_params: Dict[str, Any], current_user: User) -> Dict[str, Any]:
        """Proxy geographic metrics request to budmetrics with access control and enrichment."""
        # Convert GET params to POST body format
        from_date = request_params.get("from_date")
        to_date = request_params.get("to_date")
        group_by = request_params.get("group_by", "country")
        limit = int(request_params.get("limit", 50))

        # Build request body with filters
        request_body = {
            "from_date": from_date,
            "to_date": to_date,
            "group_by": group_by,
            "limit": limit,
            "filters": {},
        }

        # Apply user's project access restrictions
        await self._apply_user_project_filter(request_body, current_user)

        # Proxy to budmetrics using POST endpoint
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/metrics/geography"

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    metrics_endpoint,
                    json=request_body,
                ) as response,
            ):
                response_data = await response.json()

                if response.status != status.HTTP_200_OK:
                    logger.error(f"Geographic metrics request failed: {response.status}")
                    raise ClientException(
                        "Failed to get geographic metrics",
                        status_code=response.status,
                    )

                # Enrich response with names (if needed)
                await self._enrich_geographic_response(response_data)

                # Add required message field
                if "message" not in response_data:
                    response_data["message"] = "Successfully retrieved geographic data"

                return response_data

        except ClientException:
            raise
        except Exception as e:
            logger.exception("Failed to proxy geographic metrics request")
            raise ClientException(
                "Failed to proxy geographic metrics request", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _apply_user_project_filter(self, request_body: Dict[str, Any], current_user: User) -> None:
        """Apply user's project access restrictions to the request body."""
        try:
            # Import UserTypeEnum for user type checking
            from ..commons.constants import UserTypeEnum

            # Check if user is a CLIENT and apply appropriate filtering
            if current_user.user_type == UserTypeEnum.CLIENT:
                # For CLIENT users, filter by api_key_project_id instead of project_id
                # Get user's accessible projects
                project_service = ProjectService(self.session)
                # Get all projects the user has access to
                user_projects, _ = await project_service.get_all_active_projects(
                    current_user, offset=0, limit=1000, filters={}, order_by=[], search=False
                )
                user_project_ids = [str(project.project.id) for project in user_projects]

                # Get existing filters or create new ones
                filters = request_body.get("filters", {})

                # For CLIENT users, use api_key_project_id instead of project_id
                filter_field = "api_key_project_id"
                old_filter_field = "project_id"
                if old_filter_field in filters:
                    filters[filter_field] = filters.pop(old_filter_field)

                # If api_key_project_id filter exists, intersect with user's accessible projects
                if filter_field in filters:
                    existing_project_ids = filters[filter_field]
                    if isinstance(existing_project_ids, list):
                        # Keep only projects that user has access to
                        accessible_ids = [pid for pid in existing_project_ids if str(pid) in user_project_ids]
                        if not accessible_ids:
                            # User has no access to any of the requested projects
                            raise ClientException(
                                "Access denied to requested projects", status_code=status.HTTP_403_FORBIDDEN
                            )
                        filters[filter_field] = accessible_ids
                    else:
                        # Single project ID
                        if str(existing_project_ids) not in user_project_ids:
                            raise ClientException(
                                "Access denied to requested project", status_code=status.HTTP_403_FORBIDDEN
                            )
                        filters[filter_field] = existing_project_ids
                else:
                    # No api_key_project_id filter specified, apply user's projects
                    filters[filter_field] = user_project_ids

                request_body["filters"] = filters
            else:
                # For ADMIN users, keep the existing project_id filtering logic
                # Get user's accessible projects
                project_service = ProjectService(self.session)
                # Get all projects the user has access to
                user_projects, _ = await project_service.get_all_active_projects(
                    current_user, offset=0, limit=1000, filters={}, order_by=[], search=False
                )
                user_project_ids = [str(project.project.id) for project in user_projects]

                # Get existing filters or create new ones
                filters = request_body.get("filters", {})

                # If project_id filter exists, intersect with user's accessible projects
                if "project_id" in filters:
                    existing_project_ids = filters["project_id"]
                    if isinstance(existing_project_ids, list):
                        # Keep only projects that user has access to
                        accessible_ids = [pid for pid in existing_project_ids if str(pid) in user_project_ids]
                        if not accessible_ids:
                            # User has no access to any of the requested projects
                            raise ClientException(
                                "Access denied to requested projects", status_code=status.HTTP_403_FORBIDDEN
                            )
                        filters["project_id"] = accessible_ids
                    else:
                        # Single project ID
                        if str(existing_project_ids) not in user_project_ids:
                            raise ClientException(
                                "Access denied to requested project", status_code=status.HTTP_403_FORBIDDEN
                            )
                else:
                    # No project filter specified, apply user's projects
                    filters["project_id"] = user_project_ids

                request_body["filters"] = filters

        except ClientException:
            raise
        except Exception as e:
            logger.warning(f"Failed to apply user project filter: {e}")
            # Fallback: restrict to user's projects only
            from ..commons.constants import UserTypeEnum

            project_service = ProjectService(self.session)
            user_projects, _ = await project_service.get_all_active_projects(
                current_user, offset=0, limit=1000, filters={}, order_by=[], search=False
            )
            user_project_ids = [str(project.project.id) for project in user_projects]

            filters = request_body.get("filters", {})
            # Use appropriate filter field based on user type
            if current_user.user_type == UserTypeEnum.CLIENT:
                filters["api_key_project_id"] = user_project_ids
            else:
                filters["project_id"] = user_project_ids
            request_body["filters"] = filters

    async def _apply_user_project_filter_params(self, request_params: Dict[str, Any], current_user: User) -> None:
        """Apply user's project access restrictions to GET request parameters."""
        try:
            # Import UserTypeEnum for user type checking
            from ..commons.constants import UserTypeEnum

            # Get user's accessible projects
            project_service = ProjectService(self.session)
            # Get all projects the user has access to
            user_projects, _ = await project_service.get_all_active_projects(
                current_user, offset=0, limit=1000, filters={}, order_by=[], search=False
            )
            user_project_ids = [str(project.project.id) for project in user_projects]

            # Check if user is a CLIENT and apply appropriate filtering
            if current_user.user_type == UserTypeEnum.CLIENT:
                # For CLIENT users, convert project_id to api_key_project_id parameter
                if "project_id" in request_params:
                    # Move project_id to api_key_project_id for CLIENT users
                    request_params["api_key_project_id"] = request_params.pop("project_id")

                # If api_key_project_id parameter exists, intersect with user's accessible projects
                if "api_key_project_id" in request_params:
                    existing_project_id = request_params["api_key_project_id"]
                    # Check if user has access to this project
                    if str(existing_project_id) not in user_project_ids:
                        raise ClientException(
                            "Access denied to requested project", status_code=status.HTTP_403_FORBIDDEN
                        )
                    # Keep the api_key_project_id as is
                elif "project_ids" not in request_params:
                    # No project filter specified, for CLIENT users set api_key_project_id
                    # NOTE: This method is for GET requests which have limitations with lists
                    # For POST requests, use _apply_user_project_filter which sends all project IDs
                    # Here we can only send the first project due to GET parameter constraints
                    if user_project_ids:
                        request_params["api_key_project_id"] = user_project_ids[0]
            else:
                # For non-CLIENT users, use regular project_id filtering
                # If project_ids parameter exists, intersect with user's accessible projects
                if "project_ids" in request_params:
                    existing_project_ids = request_params["project_ids"]
                    if isinstance(existing_project_ids, str):
                        # Convert comma-separated string to list
                        existing_project_ids = existing_project_ids.split(",")

                    # Keep only projects that user has access to
                    accessible_ids = [pid for pid in existing_project_ids if str(pid) in user_project_ids]
                    if not accessible_ids:
                        # User has no access to any of the requested projects
                        raise ClientException(
                            "Access denied to requested projects", status_code=status.HTTP_403_FORBIDDEN
                        )
                    request_params["project_ids"] = ",".join(accessible_ids)
                elif "project_id" in request_params:
                    # Single project_id parameter
                    if str(request_params["project_id"]) not in user_project_ids:
                        raise ClientException(
                            "Access denied to requested project", status_code=status.HTTP_403_FORBIDDEN
                        )
                else:
                    # No project filter specified, apply user's projects
                    request_params["project_ids"] = ",".join(user_project_ids)

        except ClientException:
            raise
        except Exception as e:
            logger.warning(f"Failed to apply user project filter: {e}")
            # Fallback: restrict to user's projects only

            project_service = ProjectService(self.session)
            user_projects, _ = await project_service.get_all_active_projects(
                current_user, offset=0, limit=1000, filters={}, order_by=[], search=False
            )
            user_project_ids = [str(project.project.id) for project in user_projects]
            request_params["project_ids"] = ",".join(user_project_ids)
        finally:
            # For CLIENT users, rename project_ids to api_key_project_id
            if current_user.user_type == UserTypeEnum.CLIENT and "project_ids" in request_params:
                request_params["api_key_project_id"] = request_params["project_ids"]
                del request_params["project_ids"]

    async def _enrich_aggregated_metrics_response(self, response_data: Dict[str, Any]) -> None:
        """Enrich aggregated metrics response with entity names."""
        try:
            # Collect unique IDs from all groups
            project_ids = set()
            model_ids = set()
            endpoint_ids = set()

            groups = response_data.get("groups", [])
            summary_group = response_data.get("summary", {})

            for group in groups:
                if project_id := group.get("project_id"):
                    project_ids.add(str(project_id))
                # Also handle api_key_project_id (points to project table)
                if api_key_project_id := group.get("api_key_project_id"):
                    project_ids.add(str(api_key_project_id))
                if model_id := group.get("model_id"):
                    model_ids.add(str(model_id))
                if endpoint_id := group.get("endpoint_id"):
                    endpoint_ids.add(str(endpoint_id))

            # Also check summary if it contains grouping info
            if isinstance(summary_group, dict):
                if project_id := summary_group.get("project_id"):
                    project_ids.add(str(project_id))
                if api_key_project_id := summary_group.get("api_key_project_id"):
                    project_ids.add(str(api_key_project_id))
                if model_id := summary_group.get("model_id"):
                    model_ids.add(str(model_id))
                if endpoint_id := summary_group.get("endpoint_id"):
                    endpoint_ids.add(str(endpoint_id))

            # Fetch entity names
            project_names = {}
            model_names = {}
            endpoint_names = {}

            if project_ids:
                stmt = select(ProjectModel).where(ProjectModel.id.in_(list(project_ids)))
                result = self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}

            if model_ids:
                stmt = select(Model).where(Model.id.in_(list(model_ids)))
                result = self.session.execute(stmt)
                models = result.scalars().all()
                model_names = {str(m.id): m.name for m in models}

            if endpoint_ids:
                stmt = select(EndpointModel).where(EndpointModel.id.in_(list(endpoint_ids)))
                result = self.session.execute(stmt)
                endpoints = result.scalars().all()
                endpoint_names = {str(e.id): e.name for e in endpoints}

            # Add names to groups
            for group in groups:
                if project_id := group.get("project_id"):
                    group["project_name"] = project_names.get(str(project_id))
                # Handle api_key_project_id - add the project name as api_key_project_name
                if api_key_project_id := group.get("api_key_project_id"):
                    group["api_key_project_name"] = project_names.get(str(api_key_project_id))
                if model_id := group.get("model_id"):
                    group["model_name"] = model_names.get(str(model_id))
                if endpoint_id := group.get("endpoint_id"):
                    group["endpoint_name"] = endpoint_names.get(str(endpoint_id))

        except Exception as e:
            logger.warning(f"Failed to enrich aggregated metrics response: {e}")

    async def _enrich_time_series_response(self, response_data: Dict[str, Any]) -> None:
        """Enrich time-series response with entity names."""
        try:
            groups = response_data.get("groups", [])

            # Collect unique IDs from all groups
            project_ids = set()
            model_ids = set()
            endpoint_ids = set()

            for _idx, group in enumerate(groups):
                if project_id := group.get("project_id"):
                    project_ids.add(str(project_id))
                # Also handle api_key_project_id (points to project table)
                if api_key_project_id := group.get("api_key_project_id"):
                    project_ids.add(str(api_key_project_id))
                if model_id := group.get("model_id"):
                    model_ids.add(str(model_id))
                if endpoint_id := group.get("endpoint_id"):
                    endpoint_ids.add(str(endpoint_id))

            # Fetch entity names
            project_names = {}
            model_names = {}
            endpoint_names = {}

            if project_ids:
                stmt = select(ProjectModel).where(ProjectModel.id.in_(list(project_ids)))
                result = self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}

            if model_ids:
                stmt = select(Model).where(Model.id.in_(list(model_ids)))
                result = self.session.execute(stmt)
                models = result.scalars().all()
                model_names = {str(m.id): m.name for m in models}

            if endpoint_ids:
                stmt = select(EndpointModel).where(EndpointModel.id.in_(list(endpoint_ids)))
                result = self.session.execute(stmt)
                endpoints = result.scalars().all()
                endpoint_names = {str(e.id): e.name for e in endpoints}

            # Add names to groups
            for _idx, group in enumerate(groups):
                if project_id := group.get("project_id"):
                    name = project_names.get(str(project_id))
                    group["project_name"] = name

                # Handle api_key_project_id - add the project name as api_key_project_name
                if api_key_project_id := group.get("api_key_project_id"):
                    name = project_names.get(str(api_key_project_id))
                    group["api_key_project_name"] = name

                if model_id := group.get("model_id"):
                    group["model_name"] = model_names.get(str(model_id))
                if endpoint_id := group.get("endpoint_id"):
                    group["endpoint_name"] = endpoint_names.get(str(endpoint_id))

        except Exception as e:
            logger.warning(f"Failed to enrich time-series response: {e}")

    async def _enrich_geographic_response(self, response_data: Dict[str, Any]) -> None:
        """Enrich geographic response with additional data if needed."""
        try:
            # Geographic response typically doesn't need entity name enrichment
            # since it's grouped by geographic location, but we could add
            # country name enrichment from country codes if needed
            locations = response_data.get("locations", [])

            for location in locations:
                if country_code := location.get("country_code"):
                    if not location.get("country_name"):
                        location["country_name"] = self._get_country_name(country_code)

        except Exception as e:
            logger.warning(f"Failed to enrich geographic response: {e}")

    async def proxy_latency_distribution_metrics(
        self, request_body: Dict[str, Any], current_user: User
    ) -> Dict[str, Any]:
        """Proxy latency distribution metrics request to budmetrics with access control and enrichment."""
        # Apply user's project access restrictions
        try:
            await self._apply_user_project_filter(request_body, current_user)
        except Exception as e:
            logger.warning(f"Failed to apply project filter, proceeding without: {e}")

        # Proxy to budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/metrics/latency-distribution"

        # Try with filters first, then without if it fails
        for attempt, try_without_filters in enumerate([False, True]):
            try:
                request_to_send = request_body.copy()
                if try_without_filters and attempt > 0:
                    # Remove filters that might be causing validation issues
                    request_to_send.pop("filters", None)
                    logger.info("Retrying latency distribution metrics request without filters")

                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        metrics_endpoint,
                        json=request_to_send,
                    ) as response,
                ):
                    response_data = await response.json()

                    if response.status == status.HTTP_200_OK:
                        # Success! Enrich and return
                        await self._enrich_latency_distribution_response(response_data)

                        # Add required message field
                        if "message" not in response_data:
                            response_data["message"] = "Successfully retrieved latency distribution"

                        return response_data
                    else:
                        logger.error(f"Latency distribution metrics request failed: {response.status}")
                        if attempt == 0:  # Try again without filters
                            continue
                        else:
                            raise ClientException(
                                "Failed to get latency distribution metrics",
                                status_code=response.status,
                            )

            except ClientException:
                if attempt == 0:  # Try again without filters
                    continue
                else:
                    raise
            except Exception as e:
                if attempt == 0:  # Try again without filters
                    logger.warning(f"First attempt failed, retrying without filters: {e}")
                    continue
                else:
                    logger.exception("Failed to proxy latency distribution metrics request")
                    raise ClientException(
                        "Failed to proxy latency distribution metrics request",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    ) from e

        # This shouldn't be reached, but just in case
        raise ClientException(
            "Failed to get latency distribution metrics after retries",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    async def _enrich_latency_distribution_response(self, response_data: Dict[str, Any]) -> None:
        """Enrich latency distribution response with entity names."""
        try:
            from sqlalchemy import select

            groups = response_data.get("groups", [])

            # Collect all unique IDs from the response
            project_ids = set()
            model_ids = set()
            endpoint_ids = set()

            for _idx, group in enumerate(groups):
                if project_id := group.get("project_id"):
                    project_ids.add(str(project_id))
                # Also handle api_key_project_id (points to project table)
                if api_key_project_id := group.get("api_key_project_id"):
                    project_ids.add(str(api_key_project_id))
                if model_id := group.get("model_id"):
                    model_ids.add(str(model_id))
                if endpoint_id := group.get("endpoint_id"):
                    endpoint_ids.add(str(endpoint_id))

            # Fetch names in batches for efficiency
            project_names = {}
            model_names = {}
            endpoint_names = {}

            if project_ids:
                stmt = select(ProjectModel).where(ProjectModel.id.in_([UUID(pid) for pid in project_ids]))
                result = self.session.execute(stmt)
                projects = result.scalars().all()
                project_names = {str(p.id): p.name for p in projects}

            if model_ids:
                stmt = select(Model).where(Model.id.in_([UUID(mid) for mid in model_ids]))
                result = self.session.execute(stmt)
                models = result.scalars().all()
                model_names = {str(m.id): m.name for m in models}

            if endpoint_ids:
                stmt = select(EndpointModel).where(EndpointModel.id.in_([UUID(eid) for eid in endpoint_ids]))
                result = self.session.execute(stmt)
                endpoints = result.scalars().all()
                endpoint_names = {str(e.id): e.name for e in endpoints}

            # Add names to groups
            for group in groups:
                if project_id := group.get("project_id"):
                    group["project_name"] = project_names.get(str(project_id), group.get("project_name"))
                # Handle api_key_project_id - add the project name as api_key_project_name
                if api_key_project_id := group.get("api_key_project_id"):
                    group["api_key_project_name"] = project_names.get(
                        str(api_key_project_id), group.get("api_key_project_name")
                    )
                if model_id := group.get("model_id"):
                    # Preserve original model_name if enrichment fails
                    enriched_name = model_names.get(str(model_id))
                    if enriched_name:
                        group["model_name"] = enriched_name
                    # Otherwise keep the existing model_name (even if it's a UUID)
                if endpoint_id := group.get("endpoint_id"):
                    group["endpoint_name"] = endpoint_names.get(str(endpoint_id), group.get("endpoint_name"))

        except Exception as e:
            logger.warning(f"Failed to enrich latency distribution response: {e}")

    async def proxy_prompt_distribution_metrics(
        self, request_body: Dict[str, Any], current_user: User
    ) -> Dict[str, Any]:
        """Proxy prompt distribution metrics request to budmetrics with access control."""
        # Apply user's project access restrictions
        try:
            await self._apply_user_project_filter(request_body, current_user)
        except Exception as e:
            logger.warning(f"Failed to apply project filter, proceeding without: {e}")

        # Proxy to budmetrics
        metrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/metrics/distribution"

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(metrics_endpoint, json=request_body) as response,
            ):
                response_data = await response.json()

                if response.status == status.HTTP_200_OK:
                    if "message" not in response_data:
                        response_data["message"] = "Successfully retrieved prompt distribution"
                    return response_data
                else:
                    logger.error(f"Prompt distribution request failed: {response.status}")
                    raise ClientException(
                        "Failed to get prompt distribution metrics",
                        status_code=response.status,
                    )

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to proxy prompt distribution metrics: {e}")
            raise ClientException(
                "Failed to get prompt distribution metrics",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e


class MetricService(SessionMixin):
    """Metric service."""

    async def get_dashboard_stats(self, user_id: UUID) -> DashboardStatsResponse:
        """Fetch dashboard statistics for the given user."""
        db_total_model_count = await ModelDataManager(self.session).get_count_by_fields(
            Model, fields={"status": ModelStatusEnum.ACTIVE}
        )
        db_cloud_model_count = await ModelDataManager(self.session).get_count_by_fields(
            Model,
            fields={
                "status": ModelStatusEnum.ACTIVE,
                "provider_type": ModelProviderTypeEnum.CLOUD_MODEL,
            },
        )
        db_local_model_count = await ModelDataManager(self.session).get_count_by_fields(
            Model,
            fields={"status": ModelStatusEnum.ACTIVE},
            exclude_fields={"provider_type": ModelProviderTypeEnum.CLOUD_MODEL},
        )
        db_total_endpoint_count = await EndpointDataManager(self.session).get_count_by_fields(
            EndpointModel, fields={}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )
        db_running_endpoint_count = await EndpointDataManager(self.session).get_count_by_fields(
            EndpointModel, fields={"status": EndpointStatusEnum.RUNNING}
        )

        db_total_clusters = await ClusterDataManager(self.session).get_count_by_fields(
            ClusterModel, fields={}, exclude_fields={"status": ClusterStatusEnum.DELETED}
        )

        _, db_inactive_clusters = await ClusterDataManager(self.session).get_inactive_clusters()

        db_project_count = await ProjectDataManager(self.session).get_count_by_fields(
            ProjectModel, fields={"status": ProjectStatusEnum.ACTIVE}
        )

        db_total_project_users = ProjectDataManager(self.session).get_unique_user_count_in_all_projects()

        db_dashboard_stats = {
            "total_model_count": db_total_model_count,
            "cloud_model_count": db_cloud_model_count,
            "local_model_count": db_local_model_count,
            "total_projects": db_project_count,
            "total_project_users": db_total_project_users,
            "total_endpoints_count": db_total_endpoint_count,
            "running_endpoints_count": db_running_endpoint_count,
            "total_clusters": db_total_clusters,
            "inactive_clusters": db_inactive_clusters,
        }

        db_dashboard_stats = DashboardStatsResponse(
            code=status.HTTP_200_OK,
            object="dashboard.count",
            message="Successfully fetched dashboard count statistics",
            **db_dashboard_stats,
        )

        return db_dashboard_stats

    async def sync_blocking_rule_stats_from_clickhouse(self) -> Dict[str, Any]:
        """Sync blocking rule match counts from ClickHouse to PostgreSQL.

        This method retrieves the latest block counts from budmetrics ClickHouse
        and updates the match_count and last_matched_at fields in PostgreSQL.

        Returns:
            Dictionary with sync summary
        """
        logger.info("Starting blocking rule stats sync from ClickHouse")

        try:
            # Call budmetrics to get rule stats from ClickHouse
            budmetrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/gateway/blocking-stats"

            # Get stats for the last 24 hours
            from datetime import datetime, timedelta

            to_date = datetime.now()
            from_date = to_date - timedelta(days=1)

            params = {"from_date": from_date.isoformat(), "to_date": to_date.isoformat()}

            logger.debug(f"Calling budmetrics endpoint: {budmetrics_endpoint}")
            logger.debug(f"Request params: {params}")

            # Make HTTP GET request to budmetrics via Dapr
            async with aiohttp.ClientSession() as session:
                async with session.get(budmetrics_endpoint, params=params) as response:
                    if response.status == 200:
                        stats_data = await response.json()
                        logger.debug(f"Received stats data: {stats_data}")
                    else:
                        error_text = await response.text()
                        logger.error(f"BudMetrics API error {response.status}: {error_text}")
                        return {"error": f"BudMetrics API returned {response.status}", "updated_rules": 0}

            # Process the stats and update PostgreSQL
            if not stats_data:
                logger.warning("No stats data received from budmetrics")
                return {"message": "No stats data received", "updated_rules": 0}

            logger.debug(f"Processing stats data: blocked_by_rule={stats_data.get('blocked_by_rule', {})}")

            # Get all rules from PostgreSQL to sync their stats
            updated_rules = 0
            rule_data_manager = BlockingRuleDataManager(self.session)
            all_rules = await rule_data_manager.get_all_blocking_rules()

            # Get the blocked_by_rule mapping (rule_name -> count)
            blocked_by_rule = stats_data.get("blocked_by_rule", {})

            # Update each rule's statistics based on rule name match
            for rule in all_rules:
                try:
                    rule_name = rule.name
                    new_block_count = blocked_by_rule.get(rule_name, 0)

                    # Only update if there are new blocks or if we need to reset to 0
                    current_count = rule.match_count or 0

                    if new_block_count > current_count:
                        # There are new blocks - update with new count and current time
                        update_data = {
                            "match_count": new_block_count,
                            "last_matched_at": datetime.now(),  # Use current time as last match
                        }

                        result = await rule_data_manager.update_blocking_rule_stats(rule.id, update_data)
                        if result:
                            updated_rules += 1
                            logger.debug(f"Updated rule '{rule_name}': {current_count} -> {new_block_count} blocks")
                    elif new_block_count == 0 and current_count > 0:
                        # Reset count to 0 if no blocks in current period
                        update_data = {"match_count": 0}

                        result = await rule_data_manager.update_blocking_rule_stats(rule.id, update_data)
                        if result:
                            updated_rules += 1
                            logger.debug(f"Reset rule '{rule_name}' count to 0")
                    else:
                        logger.debug(f"Rule '{rule_name}' count unchanged: {current_count}")

                except Exception as e:
                    logger.warning(f"Error updating rule {rule.id} ({rule.name}): {e}")
                    continue

            logger.info(f"Blocking rule stats sync completed: {updated_rules} rules updated")
            return {
                "success": True,
                "updated_rules": updated_rules,
                "total_stats_received": len(stats_data.get("rules", [])),
                "sync_time": datetime.now().isoformat(),
            }

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during stats sync: {e}")
            return {"error": f"HTTP error: {str(e)}", "updated_rules": 0}
        except Exception as e:
            logger.error(f"Unexpected error during stats sync: {e}")
            return {"error": f"Unexpected error: {str(e)}", "updated_rules": 0}


# Gateway Analytics Services


class GatewayAnalyticsService(SessionMixin):
    """Service for handling gateway analytics operations."""

    def __init__(self, session: Session, user: User):
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
        # Get all projects the user participates in
        result = await project_data_manager.get_all_participated_projects(
            user_id=self.user.id,
            offset=0,
            limit=1000,  # Get all projects, adjust if needed
        )
        projects = result.get("projects", []) if isinstance(result, dict) else []
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
            adapter_names = {}

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

                # Check for adapters: any endpoint_ids not found might be adapter IDs
                found_endpoint_ids = set(endpoint_names.keys())
                missing_ids = {str(eid) for eid in endpoint_ids} - found_endpoint_ids
                if missing_ids:
                    stmt = select(AdapterModel).where(AdapterModel.id.in_([UUID(mid) for mid in missing_ids]))
                    result = await self.session.execute(stmt)
                    adapters = result.scalars().all()
                    adapter_names.update({str(a.id): a.name for a in adapters})

            # Helper function to add names to items
            def add_names(items: List[Dict[str, Any]]) -> None:
                for item in items:
                    if isinstance(item, dict):
                        if project_id := item.get("project_id"):
                            item["project_name"] = project_names.get(str(project_id), "Unknown")
                        if model_id := item.get("model_id"):
                            item["model_name"] = model_names.get(str(model_id), "Unknown")
                        if endpoint_id := item.get("endpoint_id"):
                            endpoint_id_str = str(endpoint_id)
                            if endpoint_name := endpoint_names.get(endpoint_id_str):
                                item["endpoint_name"] = endpoint_name
                            elif adapter_name := adapter_names.get(endpoint_id_str):
                                item["endpoint_name"] = adapter_name
                                item["adapter_name"] = adapter_name
                                item["is_adapter"] = True
                            else:
                                item["endpoint_name"] = "Unknown"

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
        from ..commons.constants import UserTypeEnum

        # If no project IDs specified, use user's accessible projects
        if not request.project_ids:
            request.project_ids = await self._get_user_accessible_projects()

        # Prepare request body for budmetrics
        budmetrics_request = {
            "model_ids": [str(mid) for mid in request.model_ids] if request.model_ids else None,
            "endpoint_ids": [str(eid) for eid in request.endpoint_ids] if request.endpoint_ids else None,
            "start_time": request.start_time.isoformat(),
            "end_time": request.end_time.isoformat(),
            "time_bucket": request.time_bucket,
            "metrics": request.metrics,
            "group_by": request.group_by,
            "filters": request.filters or {},
        }

        # For CLIENT users, use api_key_project_id; for others, use project_id
        if self.user.user_type == UserTypeEnum.CLIENT:
            budmetrics_request["filters"]["api_key_project_id"] = (
                [str(pid) for pid in request.project_ids] if request.project_ids else None
            )
        else:
            budmetrics_request["filters"]["project_id"] = (
                [str(pid) for pid in request.project_ids] if request.project_ids else None
            )

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

        # Get blocking rules from database
        from sqlalchemy import and_, func, select

        from budapp.metric_ops.models import GatewayBlockingRule

        stmt = (
            select(
                GatewayBlockingRule.created_at.label("timestamp"),
                GatewayBlockingRule.rule_config.label("rule_config"),
                GatewayBlockingRule.rule_type.label("reason"),
                func.count(GatewayBlockingRule.id).label("block_count"),
                GatewayBlockingRule.project_id,
            )
            .where(
                and_(
                    GatewayBlockingRule.project_id.in_(project_ids) if project_ids else True,
                    GatewayBlockingRule.created_at >= start_time,
                    GatewayBlockingRule.created_at <= end_time,
                    GatewayBlockingRule.status == "active",
                )
            )
            .group_by(
                GatewayBlockingRule.created_at,
                GatewayBlockingRule.rule_config,
                GatewayBlockingRule.rule_type,
                GatewayBlockingRule.project_id,
            )
            .order_by(GatewayBlockingRule.created_at.desc())
        )

        result = self.session.execute(stmt)
        rows = result.fetchall()

        # Format response
        items = []
        unique_ips = set()
        total_events = 0

        for row in rows:
            # Extract IP address from rule_config if available
            ip_address = "N/A"
            if row.rule_config and isinstance(row.rule_config, dict):
                if "ip_addresses" in row.rule_config:
                    ip_list = row.rule_config.get("ip_addresses", [])
                    ip_address = ip_list[0] if ip_list else "N/A"
                elif "ip" in row.rule_config:
                    ip_address = row.rule_config.get("ip", "N/A")

            items.append(
                BlockingStats(
                    timestamp=row.timestamp,
                    ip_address=ip_address,
                    reason=f"Rule type: {row.reason}",
                    block_count=row.block_count,
                    project_id=row.project_id,
                )
            )
            unique_ips.add(ip_address)
            total_events += row.block_count

        # Enrich with project names
        if items:
            project_ids_to_enrich = list({item.project_id for item in items if item.project_id})
            if project_ids_to_enrich:
                from budapp.project_ops.models import Project

                projects_stmt = select(Project.id, Project.name).where(Project.id.in_(project_ids_to_enrich))
                projects_result = self.session.execute(projects_stmt)
                project_map = {str(p.id): p.name for p in projects_result}

                for item in items:
                    if item.project_id:
                        item.project_name = project_map.get(str(item.project_id))

        return BlockingStatsResponse(
            items=items,
            total_blocked_ips=len(unique_ips),
            total_block_events=total_events,
            message="Blocking statistics retrieved successfully",
        )

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

    def __init__(self, session: Session, user: User):
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
        # Get all projects the user participates in
        result = await project_data_manager.get_all_participated_projects(
            user_id=self.user.id,
            offset=0,
            limit=1000,  # Get all projects, adjust if needed
        )
        projects = result.get("projects", []) if isinstance(result, dict) else []
        return [project.id for project in projects]

    async def _get_real_time_rule_blocks(
        self, rule_names: List[str], rule_name_to_id: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get real-time block counts for specific rules from ClickHouse via budmetrics.

        Args:
            rule_names: List of rule names to get block counts for
            rule_name_to_id: Mapping of rule names to rule IDs

        Returns:
            Dictionary mapping rule_id -> {total_blocks: int, last_block_time: datetime}
        """
        if not rule_names:
            return {}

        try:
            # Use the existing blocking-stats endpoint with a long time range to get all blocks
            budmetrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/gateway/blocking-stats"

            # Get blocks from last 30 days to capture most activity
            from datetime import datetime, timedelta

            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)

            params = {
                "from_date": start_time.isoformat(),
                "to_date": end_time.isoformat(),
            }

            import aiohttp

            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(budmetrics_endpoint, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Budmetrics response for rule blocks: {data}")

                        # Process the response to extract per-rule statistics
                        rule_stats = {}

                        # Initialize all requested rules with zero counts (using rule IDs)
                        rule_stats = {}
                        for rule_name in rule_names:
                            rule_id = rule_name_to_id[rule_name]
                            rule_stats[rule_id] = {"total_blocks": 0, "last_block_time": None}

                        # Parse blocked_by_rule data (which uses rule names)
                        blocked_by_rule = data.get("blocked_by_rule", {})
                        logger.info(f"blocked_by_rule data: {blocked_by_rule}")
                        logger.info(f"Looking for rule_names: {rule_names}")
                        logger.info(f"rule_name_to_id mapping: {rule_name_to_id}")

                        for rule_name, count in blocked_by_rule.items():
                            logger.info(f"Processing rule_name: {rule_name}, count: {count}")
                            if rule_name in rule_name_to_id:
                                rule_id = rule_name_to_id[rule_name]
                                rule_stats[rule_id]["total_blocks"] = count
                                logger.info(f"Updated rule {rule_name} (ID: {rule_id}) with count {count}")

                        logger.info(f"Final rule_stats: {rule_stats}")
                        return rule_stats
                    else:
                        logger.warning(f"Failed to fetch block counts from budmetrics: {response.status}")
                        response_text = await response.text()
                        logger.warning(f"Response body: {response_text}")
                        return {
                            rule_name_to_id[name]: {"total_blocks": 0, "last_block_time": None} for name in rule_names
                        }

        except Exception as e:
            logger.error(f"Error fetching real-time rule block counts: {e}")
            # Fallback: return empty counts for all rules
            return {rule_name_to_id[name]: {"total_blocks": 0, "last_block_time": None} for name in rule_names}

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
        # Determine Redis key based on rule scope
        if rule.endpoint_id:
            # Endpoint-specific rule
            redis_key = f"blocking_rules:endpoint:{rule.endpoint_id}"
        elif not rule.project_id:
            # Global rule
            redis_key = "blocking_rules:global"
        else:
            # Legacy project-specific rule (for backwards compatibility)
            redis_key = f"blocking_rule:{rule.project_id}:{rule.id}"

        # Prepare rule data for Redis
        rule_data = {
            "id": str(rule.id),
            "project_id": str(rule.project_id) if rule.project_id else None,
            "endpoint_id": str(rule.endpoint_id) if rule.endpoint_id else None,
            "rule_type": rule.rule_type.name,  # Use enum name for SCREAMING_SNAKE_CASE
            "name": rule.name,  # Required field for Rust BlockingRule struct
            "config": rule.rule_config,  # Rust expects 'config' not 'rule_config'
            "priority": rule.priority,
            "status": rule.status.name,  # Use enum name for SCREAMING_SNAKE_CASE
            "action": "block",  # Default action for blocking rules
            "expires_at": None,  # Currently not used but expected by Rust struct
            "reason": rule.reason,  # Include reason in the main rule data
        }

        # Store rule reason separately for gateway blocking middleware access
        if rule.reason:
            reason_key = f"blocking_rule_reason:{rule.name}"
            await self.redis_service.set(reason_key, rule.reason, ex=86400)
            logger.debug(f"Stored rule reason in Redis: {reason_key} = {rule.reason}")

        # For global and endpoint rules, we need to get all rules and update as a list
        if rule.endpoint_id or not rule.project_id:
            # Get existing rules
            existing_data = await self.redis_service.get(redis_key)
            existing_rules = json.loads(existing_data) if existing_data else []

            # Remove any existing rule with same ID
            existing_rules = [r for r in existing_rules if r.get("id") != str(rule.id)]

            # Add new/updated rule
            existing_rules.append(rule_data)

            # Store back in Redis (ex=86400 is 24 hours in seconds)
            await self.redis_service.set(redis_key, json.dumps(existing_rules), ex=86400)
        else:
            # Legacy single rule storage (ex=86400 is 24 hours in seconds)
            await self.redis_service.set(redis_key, json.dumps(rule_data), ex=86400)

            # Also add to project's rule set for quick lookup
            project_rules_key = f"project_blocking_rules:{rule.project_id}"
            await self.redis_service.sadd(project_rules_key, str(rule.id))

    async def _remove_rule_from_redis(self, rule: GatewayBlockingRule) -> None:
        """Remove a rule from Redis.

        Args:
            rule: Blocking rule to remove
        """
        # Determine Redis key based on rule scope
        if rule.endpoint_id:
            # Endpoint-specific rule
            redis_key = f"blocking_rules:endpoint:{rule.endpoint_id}"
        elif not rule.project_id:
            # Global rule
            redis_key = "blocking_rules:global"
        else:
            # Legacy project-specific rule
            redis_key = f"blocking_rule:{rule.project_id}:{rule.id}"

        # Remove rule reason from Redis
        reason_key = f"blocking_rule_reason:{rule.name}"
        await self.redis_service.delete(reason_key)
        logger.debug(f"Removed rule reason from Redis: {reason_key}")

        # For global and endpoint rules, we need to update the list
        if rule.endpoint_id or not rule.project_id:
            # Get existing rules
            existing_data = await self.redis_service.get(redis_key)
            existing_rules = json.loads(existing_data) if existing_data else []

            # Remove the rule
            existing_rules = [r for r in existing_rules if r.get("id") != str(rule.id)]

            # Store back in Redis (or delete if empty)
            if existing_rules:
                await self.redis_service.set(redis_key, json.dumps(existing_rules), ex=86400)
            else:
                await self.redis_service.delete(redis_key)
        else:
            # Legacy single rule removal
            await self.redis_service.delete(redis_key)

            # Remove from project's rule set
            project_rules_key = f"project_blocking_rules:{rule.project_id}"
            await self.redis_service.srem(project_rules_key, str(rule.id))

    async def create_blocking_rule(
        self,
        project_id: Optional[UUID],
        rule_data: BlockingRuleCreate,
    ) -> BlockingRule:
        """Create a new blocking rule.

        Args:
            project_id: Optional Project ID (None for global rules)
            rule_data: Rule creation data

        Returns:
            Created blocking rule
        """
        # Validate project access if project_id provided
        if project_id:
            await self._validate_project_access(project_id)
        elif not rule_data.model_name:
            # Global rules require admin privileges
            if not self.user.is_superuser:
                raise ClientException(
                    "Only administrators can create global blocking rules",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        # Validate rule configuration
        await self._validate_rule_config(rule_data.rule_type, rule_data.rule_config)

        # Check if rule name already exists in the same scope
        if rule_data.model_name:
            # Check for model-specific rule name conflict
            name_exists = await self.data_manager.check_model_rule_name_exists(rule_data.model_name, rule_data.name)
            if name_exists:
                raise ClientException(
                    f"A rule with name '{rule_data.name}' already exists for model '{rule_data.model_name}'",
                    status_code=status.HTTP_409_CONFLICT,
                )
        elif project_id:
            # Check for project-specific rule name conflict
            name_exists = await self.data_manager.check_rule_name_exists(project_id, rule_data.name)
            if name_exists:
                raise ClientException(
                    f"A rule with name '{rule_data.name}' already exists in this project",
                    status_code=status.HTTP_409_CONFLICT,
                )
        else:
            # Check for global rule name conflict
            name_exists = await self.data_manager.check_global_rule_name_exists(rule_data.name)
            if name_exists:
                raise ClientException(
                    f"A global rule with name '{rule_data.name}' already exists",
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
        # Create a dictionary with all required fields
        rule_dict = {
            "id": db_rule.id,
            "name": db_rule.name,
            "description": db_rule.description,
            "rule_type": db_rule.rule_type,
            "rule_config": db_rule.rule_config,
            "status": db_rule.status,
            "reason": db_rule.reason,
            "priority": db_rule.priority,
            "project_id": db_rule.project_id,
            "model_name": db_rule.model_name,
            "endpoint_id": db_rule.endpoint_id,
            "created_by": db_rule.created_by,
            "match_count": db_rule.match_count,
            "last_matched_at": db_rule.last_matched_at,
            "created_at": db_rule.created_at,
            "updated_at": db_rule.modified_at,  # Schema will map this via validation_alias
        }
        return BlockingRule.model_validate(rule_dict)

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

        # Get rules (no sync needed - block counts will come from ClickHouse directly)
        rules, total = await self.data_manager.list_blocking_rules(
            project_ids=project_ids,
            rule_type=rule_type,
            status=status,
            endpoint_id=endpoint_id,
            page=page,
            page_size=page_size,
        )

        # Convert to response schema with enriched real-time data
        items = []

        # Get real-time block counts for all rules from ClickHouse using rule names
        rule_name_to_id = {rule.name: str(rule.id) for rule in rules}
        rule_block_counts = await self._get_real_time_rule_blocks(list(rule_name_to_id.keys()), rule_name_to_id)

        for rule in rules:
            item = BlockingRule.model_validate(rule)
            if rule.project:
                item.project_name = rule.project.name
            if rule.endpoint:
                item.endpoint_name = rule.endpoint.name
            if rule.created_user:
                item.created_by_name = rule.created_user.name

            # Use real-time block counts from ClickHouse instead of stale PostgreSQL data
            rule_id_str = str(rule.id)
            if rule_id_str in rule_block_counts:
                block_data = rule_block_counts[rule_id_str]
                item.match_count = block_data.get("total_blocks", 0)
                item.last_matched_at = block_data.get("last_block_time")
            else:
                # No blocks found for this rule
                item.match_count = 0
                item.last_matched_at = None

            items.append(item)

        return BlockingRuleListResponse(
            message="Blocking rules retrieved successfully",
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_blocking_rules_stats_overview(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> BlockingRulesStatsOverviewResponse:
        """Get blocking rules overview statistics for dashboard cards.

        Args:
            start_time: Start time for time-based statistics (defaults to 7 days ago)
            end_time: End time for time-based statistics (defaults to now)

        Returns:
            BlockingRulesStatsOverviewResponse with dashboard statistics
        """
        from datetime import datetime, timedelta

        from ..commons.constants import BlockingRuleStatus
        from .schemas import BlockingRulesStatsOverviewResponse

        # Default time range to last 7 days if not provided
        if not start_time:
            start_time = datetime.now() - timedelta(days=7)
        if not end_time:
            end_time = datetime.now()

        # Get accessible projects
        accessible_projects = await self._get_user_accessible_projects()

        # Get rule counts from database
        from sqlalchemy import and_, func, select

        from .models import GatewayBlockingRule

        # Query rules for user's accessible projects

        # Total rules count
        total_rules_result = await self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(GatewayBlockingRule.project_id.in_(accessible_projects))
        )
        total_rules = total_rules_result.scalar() or 0

        # Active rules count
        active_rules_result = await self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(
                and_(
                    GatewayBlockingRule.project_id.in_(accessible_projects),
                    GatewayBlockingRule.status == BlockingRuleStatus.ACTIVE,
                )
            )
        )
        active_rules = active_rules_result.scalar() or 0

        # Inactive rules count
        inactive_rules_result = await self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(
                and_(
                    GatewayBlockingRule.project_id.in_(accessible_projects),
                    GatewayBlockingRule.status == BlockingRuleStatus.INACTIVE,
                )
            )
        )
        inactive_rules = inactive_rules_result.scalar() or 0

        # Expired rules count
        expired_rules_result = await self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(
                and_(
                    GatewayBlockingRule.project_id.in_(accessible_projects),
                    GatewayBlockingRule.status == BlockingRuleStatus.EXPIRED,
                )
            )
        )
        expired_rules = expired_rules_result.scalar() or 0

        # Get block counts from ClickHouse via budmetrics
        total_blocks_today = 0
        total_blocks_week = 0
        top_blocked_ips = []
        top_blocked_countries = []
        blocks_by_type = {}
        blocks_timeline = []

        try:
            # Sync latest stats first
            await self.sync_blocking_rule_stats_from_clickhouse()

            # Get blocks for today (last 24 hours)
            today_start = datetime.now() - timedelta(hours=24)
            today_params = {
                "from_date": today_start,
                "to_date": datetime.now(),
            }

            budmetrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/gateway/blocking-stats"

            async with aiohttp.ClientSession() as client_session:
                # Get today's stats
                async with client_session.get(budmetrics_endpoint, params=today_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_blocks_today = data.get("total_blocked", 0)

                # Get week's stats
                week_params = {
                    "from_date": start_time,
                    "to_date": end_time,
                }
                async with client_session.get(budmetrics_endpoint, params=week_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_blocks_week = data.get("total_blocked", 0)
                        top_blocked_ips = data.get("top_blocked_ips", [])[:5]  # Top 5
                        # Extract more detailed stats if available
                        blocked_by_reason = data.get("blocked_by_reason", {})
                        blocks_by_type = blocked_by_reason  # Map to rule types

        except Exception as e:
            logger.warning(f"Failed to get blocking statistics from ClickHouse: {e}")

        return BlockingRulesStatsOverviewResponse(
            message="Blocking rules statistics retrieved successfully",
            total_rules=total_rules,
            active_rules=active_rules,
            inactive_rules=inactive_rules,
            expired_rules=expired_rules,
            total_blocks_today=total_blocks_today,
            total_blocks_week=total_blocks_week,
            top_blocked_ips=top_blocked_ips,
            top_blocked_countries=top_blocked_countries,
            blocks_by_type=blocks_by_type,
            blocks_timeline=blocks_timeline,
        )

    async def get_blocking_dashboard_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get blocking rules dashboard statistics directly from source databases.

        This method queries PostgreSQL for rule counts and ClickHouse for block counts
        without storing duplicate data in PostgreSQL.

        Args:
            start_time: Start time for block statistics (defaults to 24 hours ago for today)
            end_time: End time for block statistics (defaults to now)

        Returns:
            Dictionary with dashboard statistics
        """
        from datetime import datetime, timedelta

        from ..commons.constants import BlockingRuleStatus

        # Get accessible projects
        accessible_projects = await self._get_user_accessible_projects()

        # Get rule counts from PostgreSQL (configuration data only)
        from sqlalchemy import and_, func, or_, select

        from .models import GatewayBlockingRule

        # Build filter: include global rules (project_id IS NULL) + rules for accessible projects
        rule_filter = GatewayBlockingRule.project_id.is_(None)  # Global rules
        if accessible_projects:
            # Add project-specific rules for accessible projects
            rule_filter = or_(rule_filter, GatewayBlockingRule.project_id.in_(accessible_projects))

        # Total rules count (global + project-specific for accessible projects)
        total_rules_result = self.session.execute(select(func.count(GatewayBlockingRule.id)).where(rule_filter))
        total_rules = total_rules_result.scalar() or 0

        # Active rules count
        active_rules_result = self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(
                and_(rule_filter, GatewayBlockingRule.status == BlockingRuleStatus.ACTIVE)
            )
        )
        active_rules = active_rules_result.scalar() or 0

        # Inactive rules count
        inactive_rules_result = self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(
                and_(rule_filter, GatewayBlockingRule.status == BlockingRuleStatus.INACTIVE)
            )
        )
        inactive_rules = inactive_rules_result.scalar() or 0

        # Expired rules count
        expired_rules_result = self.session.execute(
            select(func.count(GatewayBlockingRule.id)).where(
                and_(rule_filter, GatewayBlockingRule.status == BlockingRuleStatus.EXPIRED)
            )
        )
        expired_rules = expired_rules_result.scalar() or 0

        # Get block counts directly from ClickHouse via budmetrics
        total_blocks_today = 0
        total_blocks_week = 0

        try:
            # Get current date for proper day boundaries
            now = datetime.now()

            # Get blocks for today (current calendar day: 00:00 to now)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_params = {
                "from_date": today_start.isoformat(),
                "to_date": now.isoformat(),
            }

            # Get blocks for the week (last 7 calendar days including today)
            week_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
            week_params = {
                "from_date": week_start.isoformat(),
                "to_date": now.isoformat(),
            }

            budmetrics_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/gateway/blocking-stats"

            import aiohttp

            async with aiohttp.ClientSession() as client_session:
                # Get today's blocks
                async with client_session.get(budmetrics_endpoint, params=today_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_blocks_today = data.get("total_blocked", 0)

                # Get week's blocks
                async with client_session.get(budmetrics_endpoint, params=week_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_blocks_week = data.get("total_blocked", 0)

        except Exception as e:
            logger.warning(f"Failed to get blocking statistics from ClickHouse: {e}")
            # Return zeros if ClickHouse is not available
            total_blocks_today = 0
            total_blocks_week = 0

        return {
            "total_rules": total_rules,
            "active_rules": active_rules,
            "inactive_rules": inactive_rules,
            "expired_rules": expired_rules,
            "total_blocks_today": total_blocks_today,
            "total_blocks_week": total_blocks_week,
            "top_blocked_ips": [],
            "top_blocked_countries": [],
            "blocks_by_type": {},
            "blocks_timeline": [],
        }

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
