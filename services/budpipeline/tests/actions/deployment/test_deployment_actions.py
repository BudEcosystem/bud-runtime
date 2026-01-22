"""Tests for deployment actions."""

from __future__ import annotations

import pytest

from budpipeline.actions.base import ActionContext
from budpipeline.actions.deployment import (
    DeploymentAutoscaleAction,
    DeploymentAutoscaleExecutor,
    DeploymentCreateAction,
    DeploymentCreateExecutor,
    DeploymentDeleteAction,
    DeploymentDeleteExecutor,
    DeploymentRateLimitAction,
    DeploymentRateLimitExecutor,
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


class TestDeploymentCreateAction:
    """Tests for DeploymentCreateAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentCreateAction.meta
        assert meta.type == "deployment_create"
        assert meta.name == "Deploy Model"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "event_driven"
        assert meta.idempotent is False
        assert "budapp" in meta.required_services

    def test_validate_params_missing_model_id(self) -> None:
        """Test validation catches missing model_id."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params({"project_id": "proj-123", "endpoint_name": "test-ep"})
        assert any("model_id" in e for e in errors)

    def test_validate_params_missing_project_id(self) -> None:
        """Test validation catches missing project_id."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params({"model_id": "model-123", "endpoint_name": "test-ep"})
        assert any("project_id" in e for e in errors)

    def test_validate_params_missing_endpoint_name(self) -> None:
        """Test validation catches missing endpoint_name."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params({"model_id": "model-123", "project_id": "proj-123"})
        assert any("endpoint_name" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with required params."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params(
            {
                "model_id": "model-123",
                "project_id": "proj-123",
                "endpoint_name": "test-endpoint",
            }
        )
        assert len(errors) == 0

    def test_validate_params_cluster_optional(self) -> None:
        """Test that cluster_id is optional (for cloud models)."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params(
            {
                "model_id": "model-123",
                "project_id": "proj-123",
                "endpoint_name": "test-endpoint",
                # cluster_id intentionally omitted
            }
        )
        assert len(errors) == 0


class TestDeploymentDeleteAction:
    """Tests for DeploymentDeleteAction (placeholder)."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentDeleteAction.meta
        assert meta.type == "deployment_delete"
        assert meta.name == "Delete Deployment"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "event_driven"
        assert meta.idempotent is True

    def test_validate_params_missing_deployment_id(self) -> None:
        """Test validation catches missing deployment_id."""
        executor = DeploymentDeleteExecutor()
        errors = executor.validate_params({})
        assert any("deployment_id" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with required params."""
        executor = DeploymentDeleteExecutor()
        errors = executor.validate_params({"deployment_id": "deploy-123"})
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_returns_not_implemented(self) -> None:
        """Test that execute returns not implemented error."""
        executor = DeploymentDeleteExecutor()
        context = make_context(deployment_id="deploy-123")

        result = await executor.execute(context)

        assert result.success is False
        assert "not yet implemented" in result.error.lower()


class TestDeploymentAutoscaleAction:
    """Tests for DeploymentAutoscaleAction (placeholder)."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentAutoscaleAction.meta
        assert meta.type == "deployment_autoscale"
        assert meta.name == "Configure Autoscaling"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is True

    def test_validate_params_missing_deployment_id(self) -> None:
        """Test validation catches missing deployment_id."""
        executor = DeploymentAutoscaleExecutor()
        errors = executor.validate_params({})
        assert any("deployment_id" in e for e in errors)

    def test_validate_params_invalid_min_max(self) -> None:
        """Test validation catches min > max replicas."""
        executor = DeploymentAutoscaleExecutor()
        errors = executor.validate_params(
            {"deployment_id": "deploy-123", "min_replicas": 10, "max_replicas": 5}
        )
        assert any("min_replicas" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = DeploymentAutoscaleExecutor()
        errors = executor.validate_params(
            {"deployment_id": "deploy-123", "min_replicas": 1, "max_replicas": 10}
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_returns_not_implemented(self) -> None:
        """Test that execute returns not implemented error."""
        executor = DeploymentAutoscaleExecutor()
        context = make_context(deployment_id="deploy-123")

        result = await executor.execute(context)

        assert result.success is False
        assert "not yet implemented" in result.error.lower()


class TestDeploymentRateLimitAction:
    """Tests for DeploymentRateLimitAction (placeholder)."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentRateLimitAction.meta
        assert meta.type == "deployment_ratelimit"
        assert meta.name == "Configure Rate Limiting"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is True

    def test_validate_params_missing_deployment_id(self) -> None:
        """Test validation catches missing deployment_id."""
        executor = DeploymentRateLimitExecutor()
        errors = executor.validate_params({"requests_per_second": 100})
        assert any("deployment_id" in e for e in errors)

    def test_validate_params_invalid_rps(self) -> None:
        """Test validation catches non-positive requests_per_second."""
        executor = DeploymentRateLimitExecutor()
        errors = executor.validate_params({"deployment_id": "deploy-123", "requests_per_second": 0})
        assert any("requests_per_second" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = DeploymentRateLimitExecutor()
        errors = executor.validate_params(
            {"deployment_id": "deploy-123", "requests_per_second": 100}
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_returns_not_implemented(self) -> None:
        """Test that execute returns not implemented error."""
        executor = DeploymentRateLimitExecutor()
        context = make_context(deployment_id="deploy-123", requests_per_second=100)

        result = await executor.execute(context)

        assert result.success is False
        assert "not yet implemented" in result.error.lower()


class TestDeploymentActionsRegistration:
    """Tests for action registration."""

    def test_all_actions_have_executor_class(self) -> None:
        """Test all deployment actions have executor_class defined."""
        assert hasattr(DeploymentCreateAction, "executor_class")
        assert hasattr(DeploymentDeleteAction, "executor_class")
        assert hasattr(DeploymentAutoscaleAction, "executor_class")
        assert hasattr(DeploymentRateLimitAction, "executor_class")

    def test_all_actions_have_meta(self) -> None:
        """Test all deployment actions have meta defined."""
        assert hasattr(DeploymentCreateAction, "meta")
        assert hasattr(DeploymentDeleteAction, "meta")
        assert hasattr(DeploymentAutoscaleAction, "meta")
        assert hasattr(DeploymentRateLimitAction, "meta")

    def test_executor_classes_are_correct_type(self) -> None:
        """Test executor classes are subclasses of BaseActionExecutor."""
        from budpipeline.actions.base import BaseActionExecutor

        assert issubclass(DeploymentCreateExecutor, BaseActionExecutor)
        assert issubclass(DeploymentDeleteExecutor, BaseActionExecutor)
        assert issubclass(DeploymentAutoscaleExecutor, BaseActionExecutor)
        assert issubclass(DeploymentRateLimitExecutor, BaseActionExecutor)

    def test_unique_action_types(self) -> None:
        """Test all actions have unique type identifiers."""
        types = [
            DeploymentCreateAction.meta.type,
            DeploymentDeleteAction.meta.type,
            DeploymentAutoscaleAction.meta.type,
            DeploymentRateLimitAction.meta.type,
        ]
        assert len(types) == len(set(types))
