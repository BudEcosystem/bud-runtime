"""Tests for cluster-related workflow handlers.

Tests the ClusterHealthHandler for health check functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from budpipeline.handlers.base import HandlerContext
from budpipeline.handlers.cluster_handlers import ClusterHealthHandler, invoke_dapr_service


@pytest.fixture
def handler() -> ClusterHealthHandler:
    """Create a ClusterHealthHandler instance."""
    return ClusterHealthHandler()


@pytest.fixture
def context() -> HandlerContext:
    """Create a basic handler context."""
    return HandlerContext(
        step_id="health_check",
        execution_id="test-exec-001",
        params={
            "cluster_id": "test-cluster-123",
            "checks": ["nodes", "api"],
        },
        workflow_params={},
        step_outputs={},
    )


class TestClusterHealthHandler:
    """Tests for ClusterHealthHandler."""

    def test_handler_metadata(self, handler: ClusterHealthHandler) -> None:
        """Should have correct metadata."""
        assert handler.action_type == "cluster_health"
        assert handler.name == "Cluster Health Check"
        assert handler.description is not None

    def test_get_required_params(self, handler: ClusterHealthHandler) -> None:
        """Should require cluster_id parameter."""
        required = handler.get_required_params()
        assert "cluster_id" in required

    def test_get_optional_params(self, handler: ClusterHealthHandler) -> None:
        """Should have checks and timeout as optional params."""
        optional = handler.get_optional_params()
        assert "checks" in optional
        assert "timeout_seconds" in optional
        assert isinstance(optional["checks"], list)
        assert "nodes" in optional["checks"]

    def test_get_output_names(self, handler: ClusterHealthHandler) -> None:
        """Should output healthy, status, issues, and details."""
        outputs = handler.get_output_names()
        assert "healthy" in outputs
        assert "status" in outputs
        assert "issues" in outputs
        assert "details" in outputs

    def test_validate_params_missing_cluster_id(self, handler: ClusterHealthHandler) -> None:
        """Should fail validation without cluster_id."""
        errors = handler.validate_params({})
        assert any("cluster_id" in e for e in errors)

    def test_validate_params_valid(self, handler: ClusterHealthHandler) -> None:
        """Should pass validation with cluster_id."""
        errors = handler.validate_params({"cluster_id": "test-cluster"})
        assert len(errors) == 0

    def test_validate_params_invalid_checks(self, handler: ClusterHealthHandler) -> None:
        """Should fail validation with invalid check types."""
        errors = handler.validate_params(
            {
                "cluster_id": "test-cluster",
                "checks": ["nodes", "invalid_check"],
            }
        )
        assert any("checks" in e for e in errors)

    def test_validate_params_checks_not_list(self, handler: ClusterHealthHandler) -> None:
        """Should fail validation if checks is not a list."""
        errors = handler.validate_params(
            {
                "cluster_id": "test-cluster",
                "checks": "nodes",  # Should be a list
            }
        )
        assert any("list" in e for e in errors)

    @pytest.mark.asyncio
    async def test_execute_with_mock_data(
        self, handler: ClusterHealthHandler, context: HandlerContext
    ) -> None:
        """Should execute successfully with mock data."""
        result = await handler.execute(context)

        assert result.success is True
        assert "healthy" in result.outputs
        assert "status" in result.outputs
        assert "issues" in result.outputs
        assert "details" in result.outputs
        assert isinstance(result.outputs["healthy"], bool)
        assert isinstance(result.outputs["issues"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_healthy_status(
        self, handler: ClusterHealthHandler, context: HandlerContext
    ) -> None:
        """Should return healthy status when all checks pass."""
        result = await handler.execute(context)

        # With mock data, all checks should pass
        assert result.outputs["healthy"] is True
        assert result.outputs["status"] == "healthy"
        assert len(result.outputs["issues"]) == 0

    @pytest.mark.asyncio
    async def test_execute_all_checks(self, handler: ClusterHealthHandler) -> None:
        """Should execute all available checks."""
        context = HandlerContext(
            step_id="health_check",
            execution_id="test-exec-002",
            params={
                "cluster_id": "test-cluster-123",
                "checks": ["nodes", "api", "storage", "network", "gpu"],
            },
            workflow_params={},
            step_outputs={},
        )

        result = await handler.execute(context)

        assert result.success is True
        # Details should include all requested checks
        details = result.outputs["details"]
        assert "nodes" in details
        assert "api" in details
        assert "storage" in details
        assert "network" in details
        assert "gpu" in details

    @pytest.mark.asyncio
    async def test_execute_default_checks(self, handler: ClusterHealthHandler) -> None:
        """Should use default checks when not specified."""
        context = HandlerContext(
            step_id="health_check",
            execution_id="test-exec-003",
            params={"cluster_id": "test-cluster-123"},
            workflow_params={},
            step_outputs={},
        )

        result = await handler.execute(context)

        assert result.success is True
        details = result.outputs["details"]
        # Default checks are nodes and api
        assert "nodes" in details
        assert "api" in details

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(self, handler: ClusterHealthHandler) -> None:
        """Should handle timeout errors gracefully."""
        import httpx

        context = HandlerContext(
            step_id="health_check",
            execution_id="test-exec-004",
            params={
                "cluster_id": "test-cluster-123",
                "checks": ["nodes"],
            },
            workflow_params={},
            step_outputs={},
        )

        # Patch to force use of real implementation and simulate timeout
        with patch.object(
            handler, "_perform_health_checks", side_effect=httpx.TimeoutException("Timeout")
        ):
            result = await handler.execute(context)

        assert result.success is False
        assert result.outputs["status"] == "timeout"
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_handles_http_error(self, handler: ClusterHealthHandler) -> None:
        """Should handle HTTP errors gracefully."""
        import httpx

        context = HandlerContext(
            step_id="health_check",
            execution_id="test-exec-005",
            params={
                "cluster_id": "test-cluster-123",
                "checks": ["nodes"],
            },
            workflow_params={},
            step_outputs={},
        )

        # Create mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            handler,
            "_perform_health_checks",
            side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response),
        ):
            result = await handler.execute(context)

        assert result.success is False
        assert result.outputs["status"] == "error"
        assert "500" in result.error

    def test_get_mock_results(self, handler: ClusterHealthHandler) -> None:
        """Should return mock results for specified checks."""
        results = handler._get_mock_results(["nodes", "api"])

        assert "nodes" in results
        assert "api" in results
        assert results["nodes"]["healthy"] is True
        assert results["api"]["healthy"] is True

    def test_get_mock_results_all_checks(self, handler: ClusterHealthHandler) -> None:
        """Should return mock results for all check types."""
        all_checks = ["nodes", "api", "storage", "network", "gpu"]
        results = handler._get_mock_results(all_checks)

        for check in all_checks:
            assert check in results
            assert "healthy" in results[check]
            assert "message" in results[check]


class TestInvokeDaprService:
    """Tests for the invoke_dapr_service helper function."""

    @pytest.mark.asyncio
    async def test_invoke_dapr_service_success(self) -> None:
        """Should successfully invoke a Dapr service."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await invoke_dapr_service(
                app_id="budcluster",
                method_path="cluster/test-123/health",
                method="GET",
            )

        assert result == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_invoke_dapr_service_with_data(self) -> None:
        """Should send data in request body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "ok"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await invoke_dapr_service(
                app_id="budcluster",
                method_path="cluster/test/action",
                method="POST",
                data={"action": "scale"},
            )

            # Verify request was made with data
            mock_client.request.assert_called_once()
            call_kwargs = mock_client.request.call_args.kwargs
            assert call_kwargs["json"] == {"action": "scale"}
