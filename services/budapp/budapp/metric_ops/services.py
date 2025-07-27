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

from typing import Dict
from uuid import UUID

import aiohttp
from fastapi import status

from budapp.commons import logging
from budapp.commons.config import app_settings
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
)
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..model_ops.crud import ModelDataManager
from ..model_ops.models import Model
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from .schemas import DashboardStatsResponse


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
                    raise ClientException(
                        response_data.get("message", "Analytics request failed"), status_code=response.status
                    )

                # Enrich response with names
                await self._enrich_response_with_names(response_data)

                return response_data
        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to proxy analytics request: {e}")
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
                        item["endpoint_name"] = endpoint_names.get(str(endpoint_id), "Unknown")

        except Exception as e:
            logger.warning(f"Failed to enrich response with names: {e}")
            # Don't fail the entire request if enrichment fails


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
