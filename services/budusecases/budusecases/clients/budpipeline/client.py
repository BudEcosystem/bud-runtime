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

"""BudPipeline client for Dapr service invocation."""

import asyncio
import json
import logging

from dapr.clients import DaprClient

from .exceptions import (
    BudPipelineConnectionError,
    BudPipelineError,
    BudPipelineTimeoutError,
    ExecutionNotFoundError,
)

logger = logging.getLogger(__name__)


class BudPipelineClient:
    """Client for communicating with BudPipeline via Dapr service invocation."""

    def __init__(
        self,
        app_id: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the BudPipeline client.

        Args:
            app_id: Dapr app ID for BudPipeline service.
            max_retries: Maximum number of retry attempts.
            retry_delay: Delay between retries in seconds.
        """
        if app_id is None:
            from budusecases.commons.config import app_settings

            app_id = app_settings.budpipeline_app_id

        self.app_id = app_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = DaprClient()

    async def _invoke_method(
        self,
        method_name: str,
        http_verb: str = "GET",
        data: dict | None = None,
    ) -> dict:
        """Invoke a method on BudPipeline with retry logic.

        Args:
            method_name: API method/endpoint to invoke.
            http_verb: HTTP verb (GET, POST, PUT, DELETE).
            data: Optional request body data.

        Returns:
            Response data as dict.

        Raises:
            BudPipelineError: On unrecoverable errors.
        """
        last_error: Exception | None = None

        # Dapr SDK invoke_method expects data as bytes/str, not dict
        serialized_data = json.dumps(data).encode("utf-8") if data is not None else None

        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self._client.invoke_method,
                    app_id=self.app_id,
                    method_name=method_name,
                    http_verb=http_verb,
                    data=serialized_data,
                    content_type="application/json",
                )

                # Handle response status codes
                # status_code may be None for gRPC responses
                status_code = getattr(response, "status_code", 200) or 200

                if status_code == 404:
                    if "executions" in method_name:
                        raise ExecutionNotFoundError(f"Execution not found: {method_name}")
                    raise BudPipelineError(f"Resource not found: {method_name}")

                if status_code >= 500:
                    raise BudPipelineError(f"Server error: {status_code} - {response.json()}")

                return response.json()

            except TimeoutError as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise BudPipelineTimeoutError(f"Request timed out after {self.max_retries} attempts") from e

            except ExecutionNotFoundError:
                # Don't retry on not-found errors
                raise

            except Exception as e:
                # Don't retry on gRPC NOT_FOUND errors
                import grpc

                if isinstance(e, grpc.RpcError) and e.code() == grpc.StatusCode.NOT_FOUND:
                    raise BudPipelineConnectionError(f"Service returned NOT_FOUND: {e}") from e

                last_error = e
                logger.warning(f"Error on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise BudPipelineConnectionError(
                        f"Failed to connect after {self.max_retries} attempts: {e}"
                    ) from e

        raise BudPipelineConnectionError(f"Unexpected error: {last_error}")

    async def create_execution(
        self,
        workflow_id: str,
        params: dict | None = None,
        callback_topics: list[str] | None = None,
    ) -> dict:
        """Create a new pipeline execution for a registered pipeline.

        Args:
            workflow_id: UUID of a pipeline registered in BudPipeline.
            params: Optional execution parameters.
            callback_topics: Optional list of Dapr pub/sub topics for callbacks.

        Returns:
            Created execution response dict.
        """
        data = {
            "workflow_id": workflow_id,
            "params": params or {},
            "callback_topics": callback_topics or [],
        }
        return await self._invoke_method(
            method_name="executions",
            http_verb="POST",
            data=data,
        )

    async def run_ephemeral(
        self,
        pipeline_definition: dict,
        params: dict | None = None,
        callback_topics: list[str] | None = None,
        user_id: str | None = None,
        initiator: str = "budusecases",
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> dict:
        """Execute an inline pipeline definition without registering it.

        Uses POST /executions/run which accepts a full DAG definition
        and executes it as an ephemeral (one-off) pipeline.

        Args:
            pipeline_definition: Complete pipeline DAG dict.
            params: Optional execution parameters.
            callback_topics: Optional list of Dapr pub/sub topics for callbacks.
            user_id: User initiating the execution.
            initiator: Initiator identifier.
            subscriber_ids: Comma-separated user IDs for Novu notifications.
            payload_type: Event type for notification routing.
            notification_workflow_id: budapp workflow ID for linking events.

        Returns:
            Created execution response dict.
        """
        data: dict = {
            "pipeline_definition": pipeline_definition,
            "params": params or {},
            "initiator": initiator,
        }
        if callback_topics:
            data["callback_topics"] = callback_topics
        if user_id:
            data["user_id"] = user_id
        if subscriber_ids:
            data["subscriber_ids"] = subscriber_ids
        if payload_type:
            data["payload_type"] = payload_type
        if notification_workflow_id:
            data["notification_workflow_id"] = notification_workflow_id
        return await self._invoke_method(
            method_name="executions/run",
            http_verb="POST",
            data=data,
        )

    async def get_execution(self, execution_id: str) -> dict:
        """Get a pipeline execution by ID.

        Args:
            execution_id: Execution UUID string.

        Returns:
            Execution response dict.

        Raises:
            ExecutionNotFoundError: If execution not found.
        """
        return await self._invoke_method(
            method_name=f"executions/{execution_id}",
            http_verb="GET",
        )

    async def get_execution_progress(self, execution_id: str) -> dict:
        """Get progress details for a pipeline execution.

        Args:
            execution_id: Execution UUID string.

        Returns:
            Execution progress dict with step-level detail.

        Raises:
            ExecutionNotFoundError: If execution not found.
        """
        return await self._invoke_method(
            method_name=f"executions/{execution_id}/progress?detail=steps",
            http_verb="GET",
        )

    async def cancel_execution(self, execution_id: str) -> dict:
        """Cancel a running pipeline execution.

        Args:
            execution_id: Execution UUID string.

        Returns:
            Cancelled execution response dict.

        Raises:
            ExecutionNotFoundError: If execution not found.
        """
        return await self._invoke_method(
            method_name=f"executions/{execution_id}/cancel",
            http_verb="POST",
        )
