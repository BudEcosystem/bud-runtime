"""Cluster-related workflow handlers.

Provides handlers for cluster health checks and operations via Dapr
service invocation to budcluster.
"""

import logging
from typing import Any

import httpx

from budpipeline.commons.config import settings
from budpipeline.handlers.base import BaseHandler, HandlerContext, HandlerResult
from budpipeline.handlers.registry import register_handler

logger = logging.getLogger(__name__)


async def invoke_dapr_service(
    app_id: str,
    method_path: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Invoke a Dapr-enabled service via the Dapr sidecar.

    Args:
        app_id: The Dapr app ID of the target service
        method_path: The method/endpoint path to invoke
        method: The HTTP method (GET, POST, PUT, DELETE)
        data: JSON data for request body
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        Response from the target service

    Raises:
        httpx.HTTPError: If the request fails
    """
    url = f"{settings.dapr_http_endpoint}/v1.0/invoke/{app_id}/method/{method_path}"

    headers = {}
    if settings.dapr_api_token:
        headers["dapr-api-token"] = settings.dapr_api_token

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method=method,
            url=url,
            json=data,
            params=params,
            headers=headers if headers else None,
        )
        response.raise_for_status()
        return response.json()


@register_handler("cluster_health")
class ClusterHealthHandler(BaseHandler):
    """Handler for performing cluster health checks.

    Invokes the budcluster service to run health diagnostics on a Kubernetes
    cluster, checking nodes, API server, storage, network, and GPU drivers.
    """

    action_type = "cluster_health"
    name = "Cluster Health Check"
    description = "Performs comprehensive health checks on a Kubernetes cluster"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return ["cluster_id"]

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "checks": ["nodes", "api", "storage", "network", "gpu"],
            "timeout_seconds": 30,
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return ["healthy", "status", "issues", "details"]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters.

        Args:
            params: Parameters to validate

        Returns:
            List of validation error messages
        """
        errors = []

        if "cluster_id" not in params or not params.get("cluster_id"):
            errors.append("cluster_id is required")

        checks = params.get("checks")
        if checks is not None:
            valid_checks = {"nodes", "api", "storage", "network", "gpu"}
            if not isinstance(checks, list):
                errors.append("checks must be a list")
            elif not all(c in valid_checks for c in checks):
                errors.append(f"checks must be from: {valid_checks}")

        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute cluster health check.

        Args:
            context: Execution context with parameters

        Returns:
            HandlerResult with health check outputs
        """
        cluster_id = context.params.get("cluster_id")
        checks = context.params.get("checks", ["nodes", "api"])
        timeout = context.params.get("timeout_seconds", 30)

        logger.info(
            f"[{context.step_id}] Running health check on cluster {cluster_id}"
            f" with checks: {checks}"
        )

        try:
            results = await self._perform_health_checks(
                cluster_id=cluster_id,
                checks=checks,
                timeout=timeout,
            )

            # Aggregate results
            healthy = all(r.get("healthy", False) for r in results.values())
            issues = [
                r.get("message", f"Check {k} failed")
                for k, r in results.items()
                if not r.get("healthy", False)
            ]

            status = "healthy" if healthy else "degraded"
            if not results:
                status = "unknown"
                healthy = False
                issues = ["No health check results returned"]

            logger.info(
                f"[{context.step_id}] Cluster {cluster_id} health: {status} ({len(issues)} issues)"
            )

            return HandlerResult(
                success=True,
                outputs={
                    "healthy": healthy,
                    "status": status,
                    "issues": issues,
                    "details": results,
                },
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Health check HTTP error: {e.response.status_code}"
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "healthy": False,
                    "status": "error",
                    "issues": [error_msg],
                    "details": {},
                },
                error=error_msg,
            )

        except httpx.TimeoutException:
            error_msg = f"Health check timed out after {timeout}s"
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "healthy": False,
                    "status": "timeout",
                    "issues": [error_msg],
                    "details": {},
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            logger.exception(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "healthy": False,
                    "status": "error",
                    "issues": [error_msg],
                    "details": {},
                },
                error=error_msg,
            )

    async def _perform_health_checks(
        self,
        cluster_id: str,
        checks: list[str],
        timeout: int,
    ) -> dict[str, Any]:
        """Perform health checks by calling budcluster service.

        This method invokes the budcluster service via Dapr to perform
        the actual health checks on the cluster.

        Args:
            cluster_id: The cluster ID to check
            checks: List of checks to perform
            timeout: Timeout in seconds

        Returns:
            Dict mapping check names to results
        """
        # Use real budcluster endpoint for health checks
        use_mock = False

        if use_mock:
            logger.info(f"Using mock health check data for cluster {cluster_id}")
            return self._get_mock_results(checks)

        # Call budcluster via Dapr
        response = await invoke_dapr_service(
            app_id=settings.budcluster_app_id,
            method_path=f"cluster/{cluster_id}/health",
            method="GET",
            params={"checks": ",".join(checks)},
            timeout=timeout,
        )
        # Extract health data from response (budcluster wraps in 'data' field)
        return response.get("data", response)

    def _get_mock_results(self, checks: list[str]) -> dict[str, Any]:
        """Get mock health check results for testing.

        Args:
            checks: List of checks to mock

        Returns:
            Dict mapping check names to mock results
        """
        mock_data = {
            "nodes": {
                "healthy": True,
                "message": "All nodes ready",
                "count": 3,
                "ready": 3,
            },
            "api": {
                "healthy": True,
                "message": "API server responding",
                "latency_ms": 12,
            },
            "storage": {
                "healthy": True,
                "message": "PVCs bound",
                "pvc_count": 5,
                "bound_count": 5,
            },
            "network": {
                "healthy": True,
                "message": "Network policies active",
                "policies_count": 2,
            },
            "gpu": {
                "healthy": True,
                "message": "GPU drivers detected",
                "gpu_nodes": 2,
                "driver_version": "535.104.05",
            },
        }
        return {k: mock_data.get(k, {"healthy": True, "message": "OK"}) for k in checks}
