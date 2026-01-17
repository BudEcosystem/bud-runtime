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

"""BudPipeline service - proxies requests to the budpipeline orchestration service via Dapr."""

from typing import Any, Dict, List, Optional

from fastapi import status

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.shared.dapr_service import DaprService


logger = logging.get_logger(__name__)

# Dapr app ID for budpipeline service
BUDPIPELINE_APP_ID = app_settings.bud_pipeline_app_id


class BudPipelineService(SessionMixin):
    """Service for communicating with budpipeline via Dapr service invocation.

    This service acts as a proxy layer between budapp and budpipeline,
    handling authentication, error translation, and response enrichment.
    """

    async def validate_dag(self, dag: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a DAG definition without creating it.

        Args:
            dag: The DAG definition to validate

        Returns:
            Validation result with is_valid flag and any errors

        Raises:
            ClientException: If validation request fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="validate",
                method="POST",
                data={"dag": dag},
            )
            return result
        except Exception as e:
            logger.exception("Failed to validate DAG")
            raise ClientException(
                f"Failed to validate DAG: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def create_workflow(
        self,
        dag: Dict[str, Any],
        name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new workflow in budpipeline service.

        Args:
            dag: The DAG definition
            name: Optional workflow name override
            user_id: The ID of the user creating the workflow

        Returns:
            Created workflow data including ID

        Raises:
            ClientException: If creation fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="workflows",
                method="POST",
                data={
                    "dag": dag,
                    "name": name,
                    "created_by": user_id,
                },
            )
            return result
        except Exception as e:
            logger.exception("Failed to create workflow")
            raise ClientException(
                f"Failed to create workflow: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows from budpipeline service.

        Returns:
            List of workflow summaries

        Raises:
            ClientException: If listing fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="workflows",
                method="GET",
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.exception("Failed to list workflows")
            raise ClientException(
                f"Failed to list workflows: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow details including DAG definition.

        Args:
            workflow_id: The workflow ID

        Returns:
            Workflow details with DAG

        Raises:
            ClientException: If workflow not found or request fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"workflows/{workflow_id}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get workflow {workflow_id}")
            raise ClientException(
                f"Failed to get workflow: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def update_workflow(
        self,
        workflow_id: str,
        dag: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a workflow's DAG definition.

        Args:
            workflow_id: The workflow ID to update
            dag: New DAG definition
            name: Optional new name

        Returns:
            Updated workflow data

        Raises:
            ClientException: If update fails
        """
        try:
            data = {}
            if dag is not None:
                data["dag"] = dag
            if name is not None:
                data["name"] = name

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"workflows/{workflow_id}",
                method="PUT",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to update workflow {workflow_id}")
            raise ClientException(
                f"Failed to update workflow: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow.

        Args:
            workflow_id: The workflow ID to delete

        Raises:
            ClientException: If deletion fails
        """
        try:
            await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"workflows/{workflow_id}",
                method="DELETE",
            )
        except Exception as e:
            logger.exception(f"Failed to delete workflow {workflow_id}")
            raise ClientException(
                f"Failed to delete workflow: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def execute_workflow(
        self,
        workflow_id: str,
        params: Optional[Dict[str, Any]] = None,
        callback_topics: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a workflow execution.

        Args:
            workflow_id: The workflow ID to execute
            params: Input parameters for the execution
            callback_topics: Optional list of callback topics for real-time updates (D-004)
            user_id: User ID initiating the execution (for service-to-service auth)

        Returns:
            Execution details including execution_id

        Raises:
            ClientException: If execution start fails
        """
        try:
            data = {
                "workflow_id": workflow_id,
                "params": params or {},
            }
            # Forward callback_topics to budpipeline (T052)
            if callback_topics:
                data["callback_topics"] = callback_topics
            # Pass user_id for downstream service-to-service auth
            if user_id:
                data["user_id"] = user_id
                data["initiator"] = user_id

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="executions",
                method="POST",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to execute workflow {workflow_id}")
            raise ClientException(
                f"Failed to execute workflow: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def list_executions(
        self,
        workflow_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List workflow executions.

        Args:
            workflow_id: Optional filter by workflow ID

        Returns:
            List of execution summaries

        Raises:
            ClientException: If listing fails
        """
        try:
            params = {"workflow_id": workflow_id} if workflow_id else None
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="executions",
                method="GET",
                params=params,
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.exception("Failed to list executions")
            raise ClientException(
                f"Failed to list executions: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def list_executions_paginated(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        initiator: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List workflow executions with filtering and pagination (T059).

        Args:
            workflow_id: Optional filter by workflow ID.
            status: Optional filter by execution status.
            initiator: Optional filter by initiator.
            start_date: Optional filter by created_at >= start_date (ISO format).
            end_date: Optional filter by created_at <= end_date (ISO format).
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Dictionary with executions list and pagination info.

        Raises:
            ClientException: If listing fails.
        """
        try:
            params: Dict[str, Any] = {
                "page": page,
                "page_size": page_size,
            }
            if workflow_id:
                params["workflow_id"] = workflow_id
            if status:
                params["status"] = status
            if initiator:
                params["initiator"] = initiator
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="executions",
                method="GET",
                params=params,
            )
            return result if isinstance(result, dict) else {"executions": [], "pagination": {}}
        except Exception as e:
            logger.exception("Failed to list executions")
            raise ClientException(
                f"Failed to list executions: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Get execution details including step statuses.

        Args:
            execution_id: The execution ID

        Returns:
            Execution details with step statuses

        Raises:
            ClientException: If execution not found or request fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"executions/{execution_id}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get execution {execution_id}")
            raise ClientException(
                f"Failed to get execution: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_execution_progress(self, execution_id: str) -> Dict[str, Any]:
        """Get detailed execution progress including steps, events, and aggregated progress.

        Args:
            execution_id: The execution ID

        Returns:
            Execution progress with steps, recent events, and aggregated progress info

        Raises:
            ClientException: If execution not found or request fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"executions/{execution_id}/progress",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get execution progress {execution_id}")
            raise ClientException(
                f"Failed to get execution progress: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # =========================================================================
    # Schedule Methods
    # =========================================================================

    async def list_schedules(self, workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """List schedules, optionally filtered by workflow_id."""
        try:
            params = {"workflow_id": workflow_id} if workflow_id else None
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="schedules",
                method="GET",
                params=params,
            )
            return result
        except Exception as e:
            logger.exception("Failed to list schedules")
            raise ClientException(
                f"Failed to list schedules: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def create_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new schedule."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="schedules",
                method="POST",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception("Failed to create schedule")
            raise ClientException(
                f"Failed to create schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Get schedule details."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"schedules/{schedule_id}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get schedule {schedule_id}")
            raise ClientException(
                f"Failed to get schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def update_schedule(self, schedule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a schedule."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"schedules/{schedule_id}",
                method="PUT",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to update schedule {schedule_id}")
            raise ClientException(
                f"Failed to update schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a schedule."""
        try:
            await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"schedules/{schedule_id}",
                method="DELETE",
            )
        except Exception as e:
            logger.exception(f"Failed to delete schedule {schedule_id}")
            raise ClientException(
                f"Failed to delete schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def pause_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Pause a schedule."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"schedules/{schedule_id}/pause",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to pause schedule {schedule_id}")
            raise ClientException(
                f"Failed to pause schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def resume_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Resume a paused schedule."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"schedules/{schedule_id}/resume",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to resume schedule {schedule_id}")
            raise ClientException(
                f"Failed to resume schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def trigger_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Trigger a schedule immediately."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"schedules/{schedule_id}/trigger",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to trigger schedule {schedule_id}")
            raise ClientException(
                f"Failed to trigger schedule: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # =========================================================================
    # Webhook Methods
    # =========================================================================

    async def list_webhooks(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List webhooks, optionally filtered by workflow_id."""
        try:
            params = {"workflow_id": workflow_id} if workflow_id else None
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="webhooks",
                method="GET",
                params=params,
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.exception("Failed to list webhooks")
            raise ClientException(
                f"Failed to list webhooks: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def create_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new webhook."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="webhooks",
                method="POST",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception("Failed to create webhook")
            raise ClientException(
                f"Failed to create webhook: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook."""
        try:
            await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"webhooks/{webhook_id}",
                method="DELETE",
            )
        except Exception as e:
            logger.exception(f"Failed to delete webhook {webhook_id}")
            raise ClientException(
                f"Failed to delete webhook: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def rotate_webhook_secret(self, webhook_id: str) -> Dict[str, Any]:
        """Rotate a webhook's secret."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"webhooks/{webhook_id}/rotate-secret",
                method="POST",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to rotate webhook secret {webhook_id}")
            raise ClientException(
                f"Failed to rotate webhook secret: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # =========================================================================
    # Event Trigger Methods
    # =========================================================================

    async def list_event_triggers(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List event triggers, optionally filtered by workflow_id."""
        try:
            params = {"workflow_id": workflow_id} if workflow_id else None
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="event-triggers",
                method="GET",
                params=params,
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.exception("Failed to list event triggers")
            raise ClientException(
                f"Failed to list event triggers: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def create_event_trigger(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event trigger."""
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="event-triggers",
                method="POST",
                data=data,
            )
            return result
        except Exception as e:
            logger.exception("Failed to create event trigger")
            raise ClientException(
                f"Failed to create event trigger: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def delete_event_trigger(self, trigger_id: str) -> None:
        """Delete an event trigger."""
        try:
            await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"event-triggers/{trigger_id}",
                method="DELETE",
            )
        except Exception as e:
            logger.exception(f"Failed to delete event trigger {trigger_id}")
            raise ClientException(
                f"Failed to delete event trigger: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # =========================================================================
    # Actions API Methods (Pluggable Action Architecture)
    # =========================================================================

    async def list_actions(self) -> Dict[str, Any]:
        """List all available pipeline actions with metadata.

        Returns:
            Dictionary with actions list, categories, and total count

        Raises:
            ClientException: If listing fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="actions",
                method="GET",
            )
            return result if isinstance(result, dict) else {"actions": [], "categories": [], "total": 0}
        except Exception as e:
            logger.exception("Failed to list actions")
            raise ClientException(
                f"Failed to list actions: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def get_action(self, action_type: str) -> Dict[str, Any]:
        """Get metadata for a specific action type.

        Args:
            action_type: The action type identifier (e.g., 'log', 'model_add')

        Returns:
            Action metadata including params, outputs, execution mode

        Raises:
            ClientException: If action not found or request fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"actions/{action_type}",
                method="GET",
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get action {action_type}")
            raise ClientException(
                f"Failed to get action: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def validate_action_params(
        self,
        action_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate parameters for an action type.

        Args:
            action_type: The action type to validate against
            params: The parameters to validate

        Returns:
            Validation result with 'valid' bool and 'errors' list

        Raises:
            ClientException: If validation request fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="actions/validate",
                method="POST",
                data={
                    "action_type": action_type,
                    "params": params,
                },
            )
            return result if isinstance(result, dict) else {"valid": False, "errors": ["Validation failed"]}
        except Exception as e:
            logger.exception(f"Failed to validate action params for {action_type}")
            raise ClientException(
                f"Failed to validate action params: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e
