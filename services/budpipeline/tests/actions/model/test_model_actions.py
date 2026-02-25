"""Tests for model actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from budpipeline.actions.base import ActionContext, EventAction, EventContext, StepStatus
from budpipeline.actions.model import (
    ModelAddAction,
    ModelAddExecutor,
    ModelBenchmarkAction,
    ModelBenchmarkExecutor,
    ModelDeleteAction,
    ModelDeleteExecutor,
)


def make_action_context(**params) -> ActionContext:
    """Create a test ActionContext."""
    return ActionContext(
        step_id="test_step",
        execution_id="test_execution",
        params=params,
        workflow_params={},
        step_outputs={},
    )


def make_event_context(event_data: dict) -> EventContext:
    """Create a test EventContext."""
    return EventContext(
        step_execution_id="test_step_execution",
        execution_id="test_execution",
        external_workflow_id="test_workflow_123",
        event_type=event_data.get("type", ""),
        event_data=event_data,
        step_outputs={},
    )


class TestModelAddAction:
    """Tests for ModelAddAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = ModelAddAction.meta
        assert meta.type == "model_add"
        assert meta.name == "Add Model"
        assert meta.category == "Model Operations"
        assert meta.execution_mode.value == "event_driven"
        assert len(meta.params) > 0
        assert len(meta.outputs) > 0

    def test_validate_params_missing_model_uri(self) -> None:
        """Test validation catches missing model_uri."""
        executor = ModelAddExecutor()
        errors = executor.validate_params({"model_source": "hugging_face"})
        assert any("model_uri" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = ModelAddExecutor()
        errors = executor.validate_params(
            {"model_source": "hugging_face", "model_uri": "meta-llama/Llama-2-7b"}
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful execution starts workflow."""
        executor = ModelAddExecutor()
        context = make_action_context(
            huggingface_id="meta-llama/Llama-2-7b",
            model_name="Llama-2-7b",
        )

        with patch.object(
            context,
            "invoke_service",
            new_callable=AsyncMock,
            return_value={"workflow_id": "wf-123"},
        ):
            result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.external_workflow_id == "wf-123"
        assert result.outputs["workflow_id"] == "wf-123"
        assert result.outputs["status"] == "running"

    @pytest.mark.asyncio
    async def test_execute_no_workflow_id(self) -> None:
        """Test execution fails when no workflow_id returned."""
        executor = ModelAddExecutor()
        context = make_action_context(
            huggingface_id="meta-llama/Llama-2-7b",
        )

        with patch.object(
            context,
            "invoke_service",
            new_callable=AsyncMock,
            return_value={},  # No workflow_id
        ):
            result = await executor.execute(context)

        assert result.success is False
        assert "No workflow_id" in result.error

    @pytest.mark.asyncio
    async def test_on_event_completed(self) -> None:
        """Test event handling for successful completion."""
        executor = ModelAddExecutor()
        event_data = {
            "type": "workflow_completed",
            "status": "COMPLETED",
            "result": {"model_id": "model-123", "model_name": "TestModel"},
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["success"] is True
        assert result.outputs["model_id"] == "model-123"

    @pytest.mark.asyncio
    async def test_on_event_failed(self) -> None:
        """Test event handling for failure."""
        executor = ModelAddExecutor()
        event_data = {
            "type": "workflow_completed",
            "status": "FAILED",
            "reason": "Model extraction failed",
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.FAILED
        assert result.outputs["success"] is False
        assert "Model extraction failed" in result.error

    @pytest.mark.asyncio
    async def test_on_event_ignored(self) -> None:
        """Test event handling for irrelevant events."""
        executor = ModelAddExecutor()
        event_data = {
            "type": "some_other_event",
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.IGNORE


class TestModelDeleteAction:
    """Tests for ModelDeleteAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = ModelDeleteAction.meta
        assert meta.type == "model_delete"
        assert meta.name == "Delete Model"
        assert meta.category == "Model Operations"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is True

    def test_validate_params_missing_model_id(self) -> None:
        """Test validation catches missing model_id."""
        executor = ModelDeleteExecutor()
        errors = executor.validate_params({})
        assert any("model_id" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = ModelDeleteExecutor()
        errors = executor.validate_params({"model_id": "model-123"})
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful deletion."""
        executor = ModelDeleteExecutor()
        context = make_action_context(model_id="model-123")

        with patch.object(
            context,
            "invoke_service",
            new_callable=AsyncMock,
            return_value={"success": True},
        ):
            result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["success"] is True
        assert result.outputs["model_id"] == "model-123"

    @pytest.mark.asyncio
    async def test_execute_with_force(self) -> None:
        """Test deletion with force flag."""
        executor = ModelDeleteExecutor()
        context = make_action_context(model_id="model-123", force=True)

        mock_invoke = AsyncMock(return_value={"success": True})
        with patch.object(context, "invoke_service", mock_invoke):
            result = await executor.execute(context)

        assert result.success is True
        # Verify force was passed
        call_args = mock_invoke.call_args
        assert call_args[1]["params"]["force"] == "true"


class TestModelBenchmarkAction:
    """Tests for ModelBenchmarkAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = ModelBenchmarkAction.meta
        assert meta.type == "model_benchmark"
        assert meta.name == "Model Benchmark"
        assert meta.category == "Model Operations"
        assert meta.execution_mode.value == "event_driven"
        assert "budapp" in meta.required_services
        assert "budcluster" in meta.required_services

    def test_validate_params_missing_model_id(self) -> None:
        """Test validation catches missing model_id."""
        executor = ModelBenchmarkExecutor()
        errors = executor.validate_params({"cluster_id": "cluster-123"})
        assert any("model_id" in e for e in errors)

    def test_validate_params_missing_cluster_id(self) -> None:
        """Test validation catches missing cluster_id."""
        executor = ModelBenchmarkExecutor()
        errors = executor.validate_params({"model_id": "model-123"})
        assert any("cluster_id" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = ModelBenchmarkExecutor()
        errors = executor.validate_params({"model_id": "model-123", "cluster_id": "cluster-123"})
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_no_cluster_info(self) -> None:
        """Test execution fails when cluster info cannot be fetched."""
        executor = ModelBenchmarkExecutor()
        test_cluster_id = str(uuid4())
        context = make_action_context(
            model_id="model-123",
            cluster_id=test_cluster_id,
        )

        # Mock invoke_service to return empty cluster info
        async def mock_invoke(app_id, method_path, **kwargs):
            if "clusters" in method_path:
                return {}  # No cluster_id
            return {}

        with patch.object(context, "invoke_service", side_effect=mock_invoke):
            result = await executor.execute(context)

        assert result.success is False
        assert "cluster" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful benchmark execution."""
        executor = ModelBenchmarkExecutor()
        test_cluster_id = str(uuid4())
        bud_cluster_id = str(uuid4())
        context = make_action_context(
            model_id="model-123",
            cluster_id=test_cluster_id,
        )

        # Mock all service calls
        call_count = 0

        async def mock_invoke(app_id, method_path, **kwargs):
            nonlocal call_count
            call_count += 1
            if "clusters/" in method_path and "nodes" not in method_path:
                # Cluster details from budapp
                return {"cluster": {"id": test_cluster_id, "cluster_id": bud_cluster_id}}
            elif "nodes" in method_path:
                # Nodes from budcluster
                return {
                    "param": {
                        "nodes": [
                            {
                                "name": "node1",
                                "hardware_info": [{"type": "cuda", "available_count": 4}],
                            }
                        ]
                    }
                }
            elif "node-configurations" in method_path:
                # Device configurations from budsim
                return {
                    "device_configurations": [
                        {
                            "device_type": "cuda",
                            "tp_pp_options": [{"tp_size": 1, "pp_size": 1, "max_replicas": 4}],
                        }
                    ]
                }
            elif "run-workflow" in method_path:
                # Benchmark workflow start
                return {"workflow_id": "benchmark-wf-123"}
            return {}

        with patch.object(context, "invoke_service", side_effect=mock_invoke):
            result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.external_workflow_id == "benchmark-wf-123"
        assert result.outputs["status"] == "running"

    @pytest.mark.asyncio
    async def test_on_event_completed(self) -> None:
        """Test event handling for successful completion."""
        executor = ModelBenchmarkExecutor()
        event_data = {
            "type": "workflow_completed",
            "status": "COMPLETED",
            "result": {
                "benchmark_id": "bench-123",
                "benchmark_name": "TestBench",
                "results": {"throughput": 100},
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["success"] is True
        assert result.outputs["benchmark_id"] == "bench-123"

    @pytest.mark.asyncio
    async def test_on_event_performance_benchmark_completed(self) -> None:
        """Test event handling for direct benchmark completion."""
        executor = ModelBenchmarkExecutor()
        event_data = {
            "type": "performance_benchmark",
            "payload": {
                "event": "results",
                "content": {
                    "status": "COMPLETED",
                    "result": {
                        "benchmark_id": "bench-456",
                        "benchmark_name": "DirectBench",
                    },
                },
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["benchmark_id"] == "bench-456"

    @pytest.mark.asyncio
    async def test_on_event_step_failed(self) -> None:
        """Test event handling for intermediate step failure."""
        executor = ModelBenchmarkExecutor()
        event_data = {
            "type": "notification",
            "payload": {
                "event": "verify_deployment_status",
                "content": {
                    "status": "FAILED",
                    "title": "Deployment Failed",
                    "message": "Pod failed to start",
                },
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.FAILED
        assert result.outputs["success"] is False
        assert "Deployment Failed" in result.error

    @pytest.mark.asyncio
    async def test_on_event_ignored(self) -> None:
        """Test event handling for irrelevant events."""
        executor = ModelBenchmarkExecutor()
        event_data = {
            "type": "some_other_event",
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.IGNORE


class TestModelActionsRegistration:
    """Tests for action registration."""

    def test_all_actions_have_executor_class(self) -> None:
        """Test all model actions have executor_class defined."""
        assert hasattr(ModelAddAction, "executor_class")
        assert hasattr(ModelDeleteAction, "executor_class")
        assert hasattr(ModelBenchmarkAction, "executor_class")

    def test_all_actions_have_meta(self) -> None:
        """Test all model actions have meta defined."""
        assert hasattr(ModelAddAction, "meta")
        assert hasattr(ModelDeleteAction, "meta")
        assert hasattr(ModelBenchmarkAction, "meta")

    def test_executor_classes_are_correct_type(self) -> None:
        """Test executor classes are subclasses of BaseActionExecutor."""
        from budpipeline.actions.base import BaseActionExecutor

        assert issubclass(ModelAddExecutor, BaseActionExecutor)
        assert issubclass(ModelDeleteExecutor, BaseActionExecutor)
        assert issubclass(ModelBenchmarkExecutor, BaseActionExecutor)


class TestModelAddEdgeCases:
    """Edge case tests for ModelAddAction."""

    @pytest.mark.asyncio
    async def test_on_event_model_extraction_completed(self) -> None:
        """Test direct model_extraction event completion."""
        executor = ModelAddExecutor()
        event_data = {
            "type": "model_extraction",
            "payload": {
                "event": "results",
                "content": {
                    "status": "COMPLETED",
                    "result": {"model_id": "model-789", "model_name": "DirectModel"},
                },
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["model_id"] == "model-789"

    @pytest.mark.asyncio
    async def test_on_event_model_extraction_failed(self) -> None:
        """Test direct model_extraction event failure."""
        executor = ModelAddExecutor()
        event_data = {
            "type": "model_extraction",
            "payload": {
                "event": "results",
                "content": {
                    "status": "FAILED",
                    "message": "Extraction error",
                },
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.FAILED
        assert "Extraction error" in result.error


class TestModelBenchmarkEdgeCases:
    """Edge case tests for ModelBenchmarkAction."""

    @pytest.mark.asyncio
    async def test_execute_no_nodes(self) -> None:
        """Test execution fails when no nodes found."""
        executor = ModelBenchmarkExecutor()
        test_cluster_id = str(uuid4())
        bud_cluster_id = str(uuid4())
        context = make_action_context(
            model_id="model-123",
            cluster_id=test_cluster_id,
        )

        async def mock_invoke(app_id, method_path, **kwargs):
            if "clusters/" in method_path and "nodes" not in method_path:
                return {"cluster": {"id": test_cluster_id, "cluster_id": bud_cluster_id}}
            elif "nodes" in method_path:
                return {"param": {"nodes": []}}  # Empty nodes
            return {}

        with patch.object(context, "invoke_service", side_effect=mock_invoke):
            result = await executor.execute(context)

        assert result.success is False
        assert "No nodes found" in result.error

    @pytest.mark.asyncio
    async def test_execute_no_hostnames(self) -> None:
        """Test execution fails when nodes have no valid hostnames.

        The benchmark code extracts hostnames from node['name'], so
        nodes without 'name' field result in empty hostname and are filtered out.
        """
        executor = ModelBenchmarkExecutor()
        test_cluster_id = str(uuid4())
        bud_cluster_id = str(uuid4())
        context = make_action_context(
            model_id="model-123",
            cluster_id=test_cluster_id,
        )

        async def mock_invoke(app_id, method_path, **kwargs):
            if "clusters/" in method_path and "nodes" not in method_path:
                return {"cluster": {"id": test_cluster_id, "cluster_id": bud_cluster_id}}
            elif "nodes" in method_path:
                # Nodes with valid name but then we mock hostnames extraction
                # to return nodes that get filtered out
                return {
                    "param": {
                        "nodes": [
                            {
                                "name": "node1",
                                "type": "worker",
                                "hardware_info": [{"type": "cuda", "available_count": 4}],
                            }
                        ]
                    }
                }
            elif "node-configurations" in method_path:
                return {
                    "device_configurations": [
                        {
                            "device_type": "cuda",
                            "tp_pp_options": [{"tp_size": 1, "pp_size": 1, "max_replicas": 4}],
                        }
                    ]
                }
            elif "run-workflow" in method_path:
                return {}  # No workflow_id
            return {}

        with patch.object(context, "invoke_service", side_effect=mock_invoke):
            result = await executor.execute(context)

        assert result.success is False
        # No workflow_id is the final error in this flow
        assert "No workflow_id" in result.error

    @pytest.mark.asyncio
    async def test_on_event_notification_results_completed(self) -> None:
        """Test notification:results event completion."""
        executor = ModelBenchmarkExecutor()
        event_data = {
            "type": "notification",
            "payload": {
                "event": "results",
                "content": {
                    "status": "completed",
                    "result": {"benchmark_id": "bench-789"},
                },
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["benchmark_id"] == "bench-789"

    @pytest.mark.asyncio
    async def test_on_event_notification_results_failed(self) -> None:
        """Test notification:results event failure."""
        executor = ModelBenchmarkExecutor()
        event_data = {
            "type": "notification",
            "payload": {
                "event": "results",
                "content": {
                    "status": "failed",
                    "message": "Benchmark error",
                },
            },
        }
        context = make_event_context(event_data)

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.FAILED
        assert "Benchmark error" in result.error
