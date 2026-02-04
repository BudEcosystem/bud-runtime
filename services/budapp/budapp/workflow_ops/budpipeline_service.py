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

    async def create_pipeline(
        self,
        dag: Dict[str, Any],
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        system_owned: bool = False,
    ) -> Dict[str, Any]:
        """Create a new pipeline in budpipeline service.

        Args:
            dag: The DAG definition
            name: Optional pipeline name override
            user_id: The ID of the user creating the pipeline
            system_owned: True if this is a system-owned pipeline visible to all users

        Returns:
            Created pipeline data including ID

        Raises:
            ClientException: If creation fails
        """
        try:
            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="pipelines",
                method="POST",
                data={
                    "dag": dag,
                    "name": name,
                    "user_id": user_id,
                    "system_owned": system_owned,
                },
            )
            return result
        except ClientException:
            # Re-raise ClientException as-is to preserve status code
            raise
        except Exception as e:
            logger.exception("Failed to create pipeline")
            raise ClientException(
                f"Failed to create pipeline: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # Backwards compatibility alias
    async def create_workflow(
        self,
        dag: Dict[str, Any],
        name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deprecated: Use create_pipeline() instead."""
        return await self.create_pipeline(dag=dag, name=name, user_id=user_id)

    async def list_pipelines(
        self,
        user_id: Optional[str] = None,
        include_system: bool = False,
    ) -> List[Dict[str, Any]]:
        """List pipelines from budpipeline service.

        Args:
            user_id: Filter by user ID (if provided via X-User-ID header)
            include_system: Include system-owned pipelines in results

        Returns:
            List of pipeline summaries

        Raises:
            ClientException: If listing fails
        """
        try:
            # Convert boolean to lowercase string for aiohttp query params
            params: Dict[str, Any] = {"include_system": str(include_system).lower()}
            headers = {}
            if user_id:
                headers["X-User-ID"] = user_id

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="pipelines",
                method="GET",
                params=params,
                headers=headers,
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.exception("Failed to list pipelines")
            raise ClientException(
                f"Failed to list pipelines: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # Backwards compatibility alias
    async def list_workflows(self) -> List[Dict[str, Any]]:
        """Deprecated: Use list_pipelines() instead."""
        return await self.list_pipelines()

    async def get_pipeline(
        self,
        pipeline_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get pipeline details including DAG definition.

        Args:
            pipeline_id: The pipeline ID
            user_id: User ID for permission check (optional)

        Returns:
            Pipeline details with DAG

        Raises:
            ClientException: If pipeline not found or request fails
        """
        try:
            headers = {}
            if user_id:
                headers["X-User-ID"] = user_id

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"pipelines/{pipeline_id}",
                method="GET",
                headers=headers,
            )
            return result
        except Exception as e:
            logger.exception(f"Failed to get pipeline {pipeline_id}")
            raise ClientException(
                f"Failed to get pipeline: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # Backwards compatibility alias
    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Deprecated: Use get_pipeline() instead."""
        return await self.get_pipeline(pipeline_id=workflow_id)

    async def update_pipeline(
        self,
        pipeline_id: str,
        dag: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a pipeline's DAG definition.

        Args:
            pipeline_id: The pipeline ID to update
            dag: New DAG definition
            name: Optional new name
            user_id: User ID for permission check (optional)

        Returns:
            Updated pipeline data

        Raises:
            ClientException: If update fails
        """
        try:
            data = {}
            if dag is not None:
                data["dag"] = dag
            if name is not None:
                data["name"] = name

            headers = {}
            if user_id:
                headers["X-User-ID"] = user_id

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"pipelines/{pipeline_id}",
                method="PUT",
                data=data,
                headers=headers,
            )
            return result
        except ClientException:
            # Re-raise ClientException as-is to preserve status code
            raise
        except Exception as e:
            logger.exception(f"Failed to update pipeline {pipeline_id}")
            raise ClientException(
                f"Failed to update pipeline: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # Backwards compatibility alias
    async def update_workflow(
        self,
        workflow_id: str,
        dag: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deprecated: Use update_pipeline() instead."""
        return await self.update_pipeline(pipeline_id=workflow_id, dag=dag, name=name)

    async def delete_pipeline(
        self,
        pipeline_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Delete a pipeline.

        Args:
            pipeline_id: The pipeline ID to delete
            user_id: User ID for permission check (optional)

        Raises:
            ClientException: If deletion fails
        """
        try:
            headers = {}
            if user_id:
                headers["X-User-ID"] = user_id

            await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path=f"pipelines/{pipeline_id}",
                method="DELETE",
                headers=headers,
            )
        except Exception as e:
            logger.exception(f"Failed to delete pipeline {pipeline_id}")
            raise ClientException(
                f"Failed to delete pipeline: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # Backwards compatibility alias
    async def delete_workflow(self, workflow_id: str) -> None:
        """Deprecated: Use delete_pipeline() instead."""
        return await self.delete_pipeline(pipeline_id=workflow_id)

    async def execute_pipeline(
        self,
        pipeline_id: str,
        params: Optional[Dict[str, Any]] = None,
        callback_topics: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a pipeline execution.

        Args:
            pipeline_id: The pipeline ID to execute
            params: Input parameters for the execution
            callback_topics: Optional list of callback topics for real-time updates
            user_id: User ID initiating the execution

        Returns:
            Execution details including execution_id

        Raises:
            ClientException: If execution start fails
        """
        try:
            data = {
                "workflow_id": pipeline_id,  # Keep as workflow_id for API compatibility
                "params": params or {},
            }
            if callback_topics:
                data["callback_topics"] = callback_topics
            if user_id:
                data["user_id"] = user_id
                data["initiator"] = user_id

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="executions",
                method="POST",
                data=data,
            )

            # Check for error response from budpipeline
            if isinstance(result, dict):
                # Handle ErrorResponse format: {"object": "error", "code": N, "message": "..."}
                if result.get("object") == "error" and "message" in result:
                    error_msg = result["message"]
                    # Validate error_code is an integer to prevent FastAPI crash
                    try:
                        error_code = int(result.get("code", 500))
                    except (ValueError, TypeError):
                        error_code = 500
                    raise ClientException(
                        error_msg,
                        status_code=error_code,
                    )
                # Handle HTTPException format: {"detail": ...}
                if "detail" in result:
                    detail = result["detail"]
                    # Handle structured validation error (400) - has "error" and "errors" keys
                    if isinstance(detail, dict) and "error" in detail:
                        error_msg = detail.get("error", "Pipeline execution failed")
                        errors = detail.get("errors", [])
                        if errors:
                            error_details = ", ".join(map(str, errors))
                            error_msg = f"{error_msg}: {error_details}"
                        raise ClientException(
                            error_msg,
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                    # Handle generic error (500) - detail is a string or unstructured dict
                    else:
                        error_msg = str(detail) if isinstance(detail, str) else "Pipeline execution failed"
                        raise ClientException(
                            error_msg,
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

            return result
        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to execute pipeline {pipeline_id}")
            raise ClientException(
                f"Failed to execute pipeline: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    # Backwards compatibility alias
    async def execute_workflow(
        self,
        workflow_id: str,
        params: Optional[Dict[str, Any]] = None,
        callback_topics: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deprecated: Use execute_pipeline() instead."""
        return await self.execute_pipeline(
            pipeline_id=workflow_id,
            params=params,
            callback_topics=callback_topics,
            user_id=user_id,
        )

    async def run_ephemeral_execution(
        self,
        pipeline_definition: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
        callback_topics: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline inline without saving the pipeline definition.

        This allows executing a pipeline definition without registering it
        in the database. The execution is tracked but the pipeline itself
        is NOT saved.

        Args:
            pipeline_definition: Complete pipeline DAG definition to execute
            params: Input parameters for the execution
            callback_topics: Optional list of callback topics for real-time updates
            user_id: User ID initiating the execution

        Returns:
            Execution details including execution_id

        Raises:
            ClientException: If execution fails
        """
        try:
            data = {
                "pipeline_definition": pipeline_definition,
                "params": params or {},
            }
            if callback_topics:
                data["callback_topics"] = callback_topics
            if user_id:
                data["user_id"] = user_id
                data["initiator"] = user_id

            logger.debug(
                "Sending ephemeral execution request",
                pipeline_name=pipeline_definition.get("name"),
                step_count=len(pipeline_definition.get("steps", [])),
            )

            result = await DaprService.invoke_service(
                app_id=BUDPIPELINE_APP_ID,
                method_path="executions/run",
                method="POST",
                data=data,
            )

            # Check if the response is an error response
            if isinstance(result, dict) and ("error" in result or "errors" in result):
                error_msg = result.get("error", "Unknown error")
                errors = result.get("errors", [])
                logger.error(
                    "Ephemeral execution failed with validation errors",
                    error=error_msg,
                    errors=errors,
                    pipeline_name=pipeline_definition.get("name"),
                )
                raise ClientException(
                    f"Pipeline validation failed: {error_msg}. Errors: {errors}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            return result
        except ClientException:
            raise
        except Exception as e:
            logger.exception("Failed to run ephemeral execution")
            raise ClientException(
                f"Failed to run ephemeral execution: {str(e)}",
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
