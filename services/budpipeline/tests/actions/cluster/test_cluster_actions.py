"""Tests for cluster actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from budpipeline.actions.base import ActionContext
from budpipeline.actions.cluster import (
    ClusterHealthAction,
    ClusterHealthExecutor,
)


def make_context(**params) -> ActionContext:
    """Create a test ActionContext."""
    return ActionContext(
        step_id="test_step",
        execution_id="test_execution",
        params=params,
        workflow_params={},
        step_outputs={},
    )


class TestClusterHealthAction:
    """Tests for ClusterHealthAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = ClusterHealthAction.meta
        assert meta.type == "cluster_health"
        assert meta.name == "Cluster Health Check"
        assert meta.category == "Cluster Operations"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is True

    def test_validate_params_missing_cluster_id(self) -> None:
        """Test validation catches missing cluster_id."""
        executor = ClusterHealthExecutor()
        errors = executor.validate_params({})
        assert any("cluster_id" in e for e in errors)

    def test_validate_params_invalid_checks(self) -> None:
        """Test validation catches invalid check types."""
        executor = ClusterHealthExecutor()
        errors = executor.validate_params(
            {"cluster_id": "cluster-123", "checks": ["invalid_check"]}
        )
        assert any("checks" in e for e in errors)

    def test_validate_params_checks_not_list(self) -> None:
        """Test validation catches non-list checks."""
        executor = ClusterHealthExecutor()
        errors = executor.validate_params({"cluster_id": "cluster-123", "checks": "nodes"})
        assert any("list" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = ClusterHealthExecutor()
        errors = executor.validate_params({"cluster_id": "cluster-123", "checks": ["nodes", "api"]})
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful health check execution."""
        executor = ClusterHealthExecutor()
        context = make_context(cluster_id="cluster-123", checks=["nodes", "api"])

        with patch.object(
            context,
            "invoke_service",
            new_callable=AsyncMock,
            return_value={
                "health": {
                    "nodes": {"healthy": True, "message": "All nodes ready"},
                    "api": {"healthy": True, "message": "API server responding"},
                }
            },
        ):
            result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["healthy"] is True
        assert result.outputs["status"] == "healthy"
        assert len(result.outputs["issues"]) == 0

    @pytest.mark.asyncio
    async def test_execute_degraded(self) -> None:
        """Test degraded health check result."""
        executor = ClusterHealthExecutor()
        context = make_context(cluster_id="cluster-123", checks=["nodes", "api"])

        with patch.object(
            context,
            "invoke_service",
            new_callable=AsyncMock,
            return_value={
                "health": {
                    "nodes": {"healthy": False, "message": "2 nodes not ready"},
                    "api": {"healthy": True, "message": "API server responding"},
                }
            },
        ):
            result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["healthy"] is False
        assert result.outputs["status"] == "degraded"
        assert len(result.outputs["issues"]) > 0

    @pytest.mark.asyncio
    async def test_execute_api_error(self) -> None:
        """Test health check API error handling."""
        executor = ClusterHealthExecutor()
        context = make_context(cluster_id="cluster-123")

        with patch.object(
            context,
            "invoke_service",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            result = await executor.execute(context)

        # Should still succeed but with degraded results
        assert result.success is True
        assert result.outputs["healthy"] is False


class TestClusterActionsRegistration:
    """Tests for action registration."""

    def test_health_action_has_executor_class(self) -> None:
        """Test cluster health action has executor_class defined."""
        assert hasattr(ClusterHealthAction, "executor_class")

    def test_health_action_has_meta(self) -> None:
        """Test cluster health action has meta defined."""
        assert hasattr(ClusterHealthAction, "meta")

    def test_executor_class_is_correct_type(self) -> None:
        """Test executor class is subclass of BaseActionExecutor."""
        from budpipeline.actions.base import BaseActionExecutor

        assert issubclass(ClusterHealthExecutor, BaseActionExecutor)
