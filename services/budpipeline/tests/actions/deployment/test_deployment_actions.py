"""Tests for deployment actions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from budpipeline.actions.base import ActionContext
from budpipeline.actions.deployment import (
    DeploymentCreateAction,
    DeploymentCreateExecutor,
    DeploymentDeleteAction,
    DeploymentDeleteExecutor,
    DeploymentRateLimitAction,
    DeploymentRateLimitExecutor,
    DeploymentScaleAction,
    DeploymentScaleExecutor,
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
        """Test validation passes with required params for local model."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params(
            {
                "model_id": "model-123",
                "project_id": "proj-123",
                "endpoint_name": "test-endpoint",
                "cluster_id": "cluster-123",
                "hardware_mode": "shared",  # shared mode doesn't require SLO targets
            }
        )
        assert len(errors) == 0

    def test_validate_params_cloud_model(self) -> None:
        """Test validation passes for cloud model with credential_id."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params(
            {
                "model_id": "model-123",
                "project_id": "proj-123",
                "endpoint_name": "test-endpoint",
                "credential_id": "cred-123",  # cloud model uses credential instead of cluster
            }
        )
        assert len(errors) == 0

    def test_validate_params_requires_cluster_or_credential(self) -> None:
        """Test that either cluster_id or credential_id is required."""
        executor = DeploymentCreateExecutor()
        errors = executor.validate_params(
            {
                "model_id": "model-123",
                "project_id": "proj-123",
                "endpoint_name": "test-endpoint",
                # Neither cluster_id nor credential_id provided
            }
        )
        assert len(errors) == 1
        assert "cluster_id" in errors[0] or "credential_id" in errors[0]


class TestDeploymentDeleteAction:
    """Tests for DeploymentDeleteAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentDeleteAction.meta
        assert meta.type == "deployment_delete"
        assert meta.name == "Delete Deployment"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "event_driven"
        assert meta.idempotent is True

    def test_validate_params_missing_endpoint_id(self) -> None:
        """Test validation catches missing endpoint_id."""
        executor = DeploymentDeleteExecutor()
        errors = executor.validate_params({})
        assert any("endpoint_id" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with required params."""
        executor = DeploymentDeleteExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123"})
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful delete execution."""
        executor = DeploymentDeleteExecutor()
        context = make_context(endpoint_id="endpoint-123")

        # Mock the invoke_service method
        context.invoke_service = AsyncMock(
            return_value={"workflow_id": "workflow-123", "status": "started"}
        )

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.outputs["endpoint_id"] == "endpoint-123"


class TestDeploymentScaleAction:
    """Tests for DeploymentScaleAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentScaleAction.meta
        assert meta.type == "deployment_scale"
        assert meta.name == "Scale Deployment"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is True
        assert "budapp" in meta.required_services

    def test_validate_params_missing_endpoint_id(self) -> None:
        """Test validation catches missing endpoint_id."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"target_replicas": 2})
        assert any("endpoint_id" in e for e in errors)

    def test_validate_params_missing_target_replicas(self) -> None:
        """Test validation catches missing target_replicas."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123"})
        assert any("target_replicas" in e for e in errors)

    def test_validate_params_negative_replicas(self) -> None:
        """Test validation catches negative replicas."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123", "target_replicas": -1})
        assert any("non-negative" in e for e in errors)

    def test_validate_params_exceeds_max_replicas(self) -> None:
        """Test validation catches replicas exceeding max."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123", "target_replicas": 101})
        assert any("exceed" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123", "target_replicas": 5})
        assert len(errors) == 0

    def test_validate_params_zero_replicas_valid(self) -> None:
        """Test that zero replicas is valid for scale-down."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123", "target_replicas": 0})
        assert len(errors) == 0

    def test_validate_params_max_replicas_valid(self) -> None:
        """Test that 100 replicas is valid (max)."""
        executor = DeploymentScaleExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123", "target_replicas": 100})
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_scales_deployment_successfully(self) -> None:
        """Test successful scaling with mocked service invocation."""
        executor = DeploymentScaleExecutor()
        context = make_context(endpoint_id="endpoint-123", target_replicas=5)

        # Mock the invoke_service method
        context.invoke_service = AsyncMock(
            side_effect=[
                # First call: GET current autoscale config
                {
                    "budaiscaler_config": {
                        "enabled": True,
                        "minReplicas": 1,
                        "maxReplicas": 10,
                        "scalingStrategy": "metrics_based",
                        "metricsSources": {"cpu": 80},
                    }
                },
                # Second call: PUT updated config
                {"status": "success"},
            ]
        )

        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["endpoint_id"] == "endpoint-123"
        assert result.outputs["target_replicas"] == 5
        assert result.outputs["previous_min_replicas"] == 1
        assert result.outputs["previous_max_replicas"] == 10
        assert result.outputs["scaling_strategy"] == "metrics_based"
        assert "Scaled deployment to 5 replicas" in result.outputs["message"]

        # Verify invoke_service was called twice
        assert context.invoke_service.call_count == 2

        # Verify GET call
        get_call = context.invoke_service.call_args_list[0]
        assert get_call.kwargs["http_method"] == "GET"
        assert "endpoints/endpoint-123/autoscale" in get_call.kwargs["method_path"]

        # Verify PUT call
        put_call = context.invoke_service.call_args_list[1]
        assert put_call.kwargs["http_method"] == "PUT"
        assert "endpoints/endpoint-123/autoscale" in put_call.kwargs["method_path"]
        # Verify the request data has correct min/max replicas
        put_data = put_call.kwargs["data"]
        assert put_data["budaiscaler_specification"]["minReplicas"] == 5
        assert put_data["budaiscaler_specification"]["maxReplicas"] == 5
        # Verify scaling strategy was preserved
        assert put_data["budaiscaler_specification"]["scalingStrategy"] == "metrics_based"

    @pytest.mark.asyncio
    async def test_execute_handles_missing_current_config(self) -> None:
        """Test scaling works when current config cannot be retrieved."""
        executor = DeploymentScaleExecutor()
        context = make_context(endpoint_id="endpoint-123", target_replicas=3)

        # Mock invoke_service: GET fails, PUT succeeds
        context.invoke_service = AsyncMock(
            side_effect=[
                # First call: GET fails
                Exception("Endpoint not found"),
                # Second call: PUT succeeds
                {"status": "success"},
            ]
        )

        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["target_replicas"] == 3
        # Previous config should be None since GET failed
        assert result.outputs["previous_min_replicas"] is None
        assert result.outputs["previous_max_replicas"] is None

    @pytest.mark.asyncio
    async def test_execute_preserves_existing_settings(self) -> None:
        """Test that existing autoscale settings are preserved."""
        executor = DeploymentScaleExecutor()
        context = make_context(endpoint_id="endpoint-123", target_replicas=2)

        # Mock the invoke_service method with rich existing config
        context.invoke_service = AsyncMock(
            side_effect=[
                # GET: rich existing config
                {
                    "budaiscaler_config": {
                        "enabled": True,
                        "minReplicas": 1,
                        "maxReplicas": 10,
                        "scalingStrategy": "gpu_aware",
                        "metricsSources": {"gpu_utilization": 70},
                        "gpuConfig": {"type": "A100", "memory": "80GB"},
                        "behavior": {"scaleDown": {"stabilizationWindowSeconds": 300}},
                    }
                },
                # PUT: success
                {"status": "success"},
            ]
        )

        result = await executor.execute(context)

        assert result.success is True

        # Verify preserved settings in PUT call
        put_call = context.invoke_service.call_args_list[1]
        put_data = put_call.kwargs["data"]["budaiscaler_specification"]

        # Replicas should be updated
        assert put_data["minReplicas"] == 2
        assert put_data["maxReplicas"] == 2

        # These should be preserved
        assert put_data["scalingStrategy"] == "gpu_aware"
        assert put_data["metricsSources"] == {"gpu_utilization": 70}
        assert put_data["gpuConfig"] == {"type": "A100", "memory": "80GB"}
        assert put_data["behavior"] == {"scaleDown": {"stabilizationWindowSeconds": 300}}

    @pytest.mark.asyncio
    async def test_execute_fails_on_put_error(self) -> None:
        """Test scaling fails gracefully when PUT fails."""
        executor = DeploymentScaleExecutor()
        context = make_context(endpoint_id="endpoint-123", target_replicas=5)

        # Mock invoke_service: GET succeeds, PUT fails
        context.invoke_service = AsyncMock(
            side_effect=[
                # First call: GET succeeds
                {"budaiscaler_config": {"minReplicas": 1, "maxReplicas": 10}},
                # Second call: PUT fails
                Exception("Service unavailable"),
            ]
        )

        result = await executor.execute(context)

        assert result.success is False
        assert "Failed to scale deployment" in result.error
        assert result.outputs["success"] is False
        assert result.outputs["endpoint_id"] == "endpoint-123"

    @pytest.mark.asyncio
    async def test_execute_missing_target_replicas(self) -> None:
        """Test scaling fails when target_replicas is missing."""
        executor = DeploymentScaleExecutor()
        context = make_context(endpoint_id="endpoint-123")  # No target_replicas

        result = await executor.execute(context)

        assert result.success is False
        assert "target_replicas is required" in result.error

    @pytest.mark.asyncio
    async def test_execute_scales_to_zero(self) -> None:
        """Test scaling to zero replicas (scale down)."""
        executor = DeploymentScaleExecutor()
        context = make_context(endpoint_id="endpoint-123", target_replicas=0)

        context.invoke_service = AsyncMock(
            side_effect=[
                {"budaiscaler_config": {"minReplicas": 1, "maxReplicas": 5}},
                {"status": "success"},
            ]
        )

        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["target_replicas"] == 0

        # Verify PUT call has 0 replicas
        put_call = context.invoke_service.call_args_list[1]
        put_data = put_call.kwargs["data"]["budaiscaler_specification"]
        assert put_data["minReplicas"] == 0
        assert put_data["maxReplicas"] == 0


class TestDeploymentRateLimitAction:
    """Tests for DeploymentRateLimitAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = DeploymentRateLimitAction.meta
        assert meta.type == "deployment_ratelimit"
        assert meta.name == "Configure Rate Limiting"
        assert meta.category == "Deployment"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is True

    def test_validate_params_missing_endpoint_id(self) -> None:
        """Test validation catches missing endpoint_id."""
        executor = DeploymentRateLimitExecutor()
        errors = executor.validate_params({"requests_per_second": 100})
        assert any("endpoint_id" in e for e in errors)

    def test_validate_params_invalid_rps(self) -> None:
        """Test validation catches non-positive requests_per_second."""
        executor = DeploymentRateLimitExecutor()
        errors = executor.validate_params({"endpoint_id": "endpoint-123", "requests_per_second": 0})
        assert any("requests_per_second" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = DeploymentRateLimitExecutor()
        errors = executor.validate_params(
            {"endpoint_id": "endpoint-123", "requests_per_second": 100}
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful rate limit configuration."""
        executor = DeploymentRateLimitExecutor()
        context = make_context(endpoint_id="endpoint-123", requests_per_second=100)

        # Mock the invoke_service method
        context.invoke_service = AsyncMock(
            return_value={"status": "success", "rate_limit_config": {"requests_per_second": 100}}
        )

        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["endpoint_id"] == "endpoint-123"


class TestDeploymentActionsRegistration:
    """Tests for action registration."""

    def test_all_actions_have_executor_class(self) -> None:
        """Test all deployment actions have executor_class defined."""
        assert hasattr(DeploymentCreateAction, "executor_class")
        assert hasattr(DeploymentDeleteAction, "executor_class")
        assert hasattr(DeploymentScaleAction, "executor_class")
        assert hasattr(DeploymentRateLimitAction, "executor_class")

    def test_all_actions_have_meta(self) -> None:
        """Test all deployment actions have meta defined."""
        assert hasattr(DeploymentCreateAction, "meta")
        assert hasattr(DeploymentDeleteAction, "meta")
        assert hasattr(DeploymentScaleAction, "meta")
        assert hasattr(DeploymentRateLimitAction, "meta")

    def test_executor_classes_are_correct_type(self) -> None:
        """Test executor classes are subclasses of BaseActionExecutor."""
        from budpipeline.actions.base import BaseActionExecutor

        assert issubclass(DeploymentCreateExecutor, BaseActionExecutor)
        assert issubclass(DeploymentDeleteExecutor, BaseActionExecutor)
        assert issubclass(DeploymentScaleExecutor, BaseActionExecutor)
        assert issubclass(DeploymentRateLimitExecutor, BaseActionExecutor)

    def test_unique_action_types(self) -> None:
        """Test all actions have unique type identifiers."""
        types = [
            DeploymentCreateAction.meta.type,
            DeploymentDeleteAction.meta.type,
            DeploymentScaleAction.meta.type,
            DeploymentRateLimitAction.meta.type,
        ]
        assert len(types) == len(set(types))
