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

"""BudUseCases service - proxies requests to the budusecases service via Dapr."""

import json
from typing import Any, Dict, Optional

from fastapi import status

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.shared.dapr_service import DaprService
from budapp.shared.redis_service import RedisService


logger = logging.get_logger(__name__)

# Dapr app ID for budusecases service
BUDUSECASES_APP_ID = app_settings.bud_usecases_app_id


class BudUseCasesService(SessionMixin):
    """Service for communicating with budusecases via Dapr service invocation."""

    # =========================================================================
    # Template Methods
    # =========================================================================

    async def list_templates(
        self,
        params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List templates with optional filtering."""
        try:
            headers: Dict[str, str] = {}
            if user_id:
                headers["X-User-ID"] = user_id
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path="api/v1/templates",
                method="GET",
                params=params,
                headers=headers,
            )
            return result
        except Exception as e:
            logger.exception("Failed to list templates")
            raise ClientException(
                f"Failed to list templates: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_template(self, template_id: str) -> Dict[str, Any]:
        """Get a template by ID."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/templates/{template_id}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get template {template_id}")
            raise ClientException(
                f"Failed to get template: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_template_by_name(self, name: str) -> Dict[str, Any]:
        """Get a template by name."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/templates/by-name/{name}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get template by name {name}")
            raise ClientException(
                f"Failed to get template by name: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def create_template(
        self,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a custom template."""
        try:
            headers: Dict[str, str] = {}
            if user_id:
                headers["X-User-ID"] = user_id
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path="api/v1/templates",
                method="POST",
                data=data,
                headers=headers,
            )
            return result
        except Exception as e:
            logger.exception("Failed to create template")
            raise ClientException(
                f"Failed to create template: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def update_template(self, template_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a template."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/templates/{template_id}",
                method="PUT",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to update template {template_id}")
            raise ClientException(
                f"Failed to update template: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def delete_template(self, template_id: str) -> None:
        """Delete a template."""
        try:
            await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/templates/{template_id}",
                method="DELETE",
            )
        except Exception as e:
            logger.exception(f"Failed to delete template {template_id}")
            raise ClientException(
                f"Failed to delete template: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def sync_templates(self) -> Dict[str, Any]:
        """Sync templates from YAML files."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path="api/v1/templates/sync",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception("Failed to sync templates")
            raise ClientException(
                f"Failed to sync templates: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # =========================================================================
    # Deployment Methods
    # =========================================================================

    async def list_deployments(
        self,
        params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List deployments with optional filtering."""
        try:
            headers: Dict[str, str] = {}
            if user_id:
                headers["X-User-ID"] = user_id
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path="api/v1/deployments",
                method="GET",
                params=params,
                headers=headers,
            )
            return result
        except Exception as e:
            logger.exception("Failed to list deployments")
            raise ClientException(
                f"Failed to list deployments: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Get a deployment by ID."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get deployment {deployment_id}")
            raise ClientException(
                f"Failed to get deployment: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def create_deployment(
        self,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new deployment.

        Args:
            data: Deployment creation payload.
            user_id: User ID forwarded via X-User-ID header to budusecases.
            project_id: Project ID forwarded via X-Project-ID header to budusecases.
        """
        try:
            headers: Dict[str, str] = {}
            if user_id:
                headers["X-User-ID"] = user_id
            if project_id:
                headers["X-Project-ID"] = project_id
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path="api/v1/deployments",
                method="POST",
                data=data,
                headers=headers,
            )
            return result
        except Exception as e:
            logger.exception("Failed to create deployment")
            raise ClientException(
                f"Failed to create deployment: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def start_deployment(
        self,
        deployment_id: str,
        notification_workflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a deployment.

        Args:
            deployment_id: The deployment ID to start.
            notification_workflow_id: Optional budapp workflow ID for real-time notifications.
        """
        try:
            headers: Dict[str, str] = {}
            if notification_workflow_id:
                headers["X-Notification-Workflow-ID"] = notification_workflow_id
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}/start",
                method="POST",
                headers=headers,
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to start deployment {deployment_id}")
            raise ClientException(
                f"Failed to start deployment: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def stop_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Stop a deployment."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}/stop",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to stop deployment {deployment_id}")
            raise ClientException(
                f"Failed to stop deployment: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def delete_deployment(self, deployment_id: str) -> None:
        """Delete a deployment."""
        try:
            await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}",
                method="DELETE",
            )
        except Exception as e:
            logger.exception(f"Failed to delete deployment {deployment_id}")
            raise ClientException(
                f"Failed to delete deployment: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def sync_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """Sync deployment status from BudCluster."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}/sync",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to sync deployment status {deployment_id}")
            raise ClientException(
                f"Failed to sync deployment status: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def retry_gateway_route(self, deployment_id: str) -> Dict[str, Any]:
        """Retry HTTPRoute creation for a deployment missing a gateway URL."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}/retry-gateway",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to retry gateway route for {deployment_id}")
            raise ClientException(
                f"Failed to retry gateway route: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_deployment_progress(self, deployment_id: str) -> Dict[str, Any]:
        """Get deployment progress from pipeline execution."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDUSECASES_APP_ID,
                method_path=f"api/v1/deployments/{deployment_id}/progress",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get deployment progress {deployment_id}")
            raise ClientException(
                f"Failed to get deployment progress: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # =========================================================================
    # Deployment Route Publishing (Redis for budgateway)
    # =========================================================================

    async def publish_deployment_route(
        self,
        deployment_id: str,
        project_id: str,
        gateway_url: str,
    ) -> None:
        """Publish deployment route to Redis for budgateway.

        Follows the same pattern as model endpoint publishing:
        endpoint_ops/services.py -> RedisService().set("model_table:{id}", ...)

        Args:
            deployment_id: The deployment ID to publish a route for.
            project_id: The project ID owning the deployment.
            gateway_url: The ingress URL for the deployment.
        """
        route_data = {
            "deployment_id": deployment_id,
            "project_id": project_id,
            "ingress_url": gateway_url,
            "status": "active",
        }
        redis_service = RedisService()
        await redis_service.set(
            f"deployment_route:{deployment_id}",
            json.dumps(route_data),
        )
        logger.info(f"Published deployment route for {deployment_id}")

    async def delete_deployment_route(self, deployment_id: str) -> None:
        """Delete deployment route from Redis.

        Called when a deployment is stopped or deleted.

        Args:
            deployment_id: The deployment ID whose route should be removed.
        """
        redis_service = RedisService()
        await redis_service.delete(f"deployment_route:{deployment_id}")
        logger.info(f"Deleted deployment route for {deployment_id}")
