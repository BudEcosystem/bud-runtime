"""Action execution context definitions.

This module defines the context objects passed to action executors
during execution and event handling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx


@dataclass
class ActionContext:
    """Context passed to action execute() method.

    Contains all information needed to execute an action,
    including parameters, workflow state, and service invocation helpers.
    """

    step_id: str
    execution_id: str
    params: dict[str, Any]
    workflow_params: dict[str, Any]
    step_outputs: dict[str, dict[str, Any]]
    timeout_seconds: int | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # Internal: HTTP client for service invocation
    _http_client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def invoke_service(
        self,
        app_id: str,
        method_path: str,
        data: dict[str, Any] | None = None,
        http_method: str = "POST",
        params: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        """Invoke another service via Dapr service invocation.

        Args:
            app_id: Target service app ID (e.g., "budapp", "budcluster")
            method_path: HTTP method path (e.g., "models/add" or "/models/add")
            data: Request body data (for POST/PUT/PATCH)
            http_method: HTTP method (GET, POST, PUT, DELETE)
            params: URL query parameters
            timeout_seconds: Request timeout in seconds

        Returns:
            Response data as dictionary

        Raises:
            httpx.HTTPStatusError: On non-2xx response
        """
        dapr_endpoint = os.environ.get("DAPR_HTTP_ENDPOINT", "http://localhost:3500")

        # Ensure method_path starts with /
        if not method_path.startswith("/"):
            method_path = f"/{method_path}"

        url = f"{dapr_endpoint}/v1.0/invoke/{app_id}/method{method_path}"

        headers = {
            "Content-Type": "application/json",
        }

        # Add dapr-api-token for Dapr sidecar authentication
        # (required when target app has dapr.io/app-token-secret configured)
        dapr_token = os.environ.get("DAPR_API_TOKEN") or os.environ.get("APP_API_TOKEN")
        if dapr_token:
            headers["dapr-api-token"] = dapr_token

        # Use provided client or create a temporary one
        client = self._http_client
        should_close = client is None
        if should_close:
            client = httpx.AsyncClient()

        try:
            if http_method.upper() == "GET":
                response = await client.get(
                    url, headers=headers, params=params, timeout=timeout_seconds
                )
            elif http_method.upper() == "DELETE":
                response = await client.delete(
                    url, headers=headers, params=params, timeout=timeout_seconds
                )
            else:
                response = await client.request(
                    method=http_method.upper(),
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout_seconds,
                )

            response.raise_for_status()
            return response.json() if response.content else {}
        finally:
            # Only close client if we created it
            if should_close:
                await client.aclose()

    def get_step_output(self, step_id: str, output_name: str) -> Any:
        """Get an output value from a previous step.

        Args:
            step_id: The step ID to get output from
            output_name: The output field name

        Returns:
            The output value, or None if not found
        """
        step_outputs = self.step_outputs.get(step_id, {})
        return step_outputs.get(output_name)


@dataclass
class EventContext:
    """Context passed to action on_event() method.

    Contains information about an incoming event and the
    current state of the waiting step.
    """

    step_execution_id: UUID
    execution_id: UUID
    external_workflow_id: str
    event_type: str
    event_data: dict[str, Any]
    step_outputs: dict[str, Any]  # Outputs from initial execute() call

    def get_event_field(self, *path: str, default: Any = None) -> Any:
        """Get a field from event data by path.

        Args:
            *path: Path segments to traverse (e.g., "result", "status")
            default: Default value if path not found

        Returns:
            The value at the path, or default if not found
        """
        current = self.event_data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
