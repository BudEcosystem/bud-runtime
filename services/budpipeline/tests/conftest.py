"""Pytest configuration and fixtures for budpipeline tests."""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# Import all models to ensure SQLAlchemy relationships are properly registered
# This fixes "expression 'X' failed to locate a name" errors
# Order matters: import base model first, then models with relationships
from budpipeline.commons.database import Base  # noqa: F401
from budpipeline.pipeline.models import (  # noqa: F401
    PipelineDefinition,
    PipelineExecution,
    StepExecution,
)
from budpipeline.progress.models import ProgressEvent  # noqa: F401
from budpipeline.subscriptions.models import ExecutionSubscription  # noqa: F401

# ============ DAG Fixtures ============


@pytest.fixture
def simple_dag() -> dict[str, Any]:
    """Simple single-step DAG for basic tests."""
    return {
        "name": "simple-workflow",
        "version": "1.0",
        "steps": [
            {
                "id": "step1",
                "name": "First Step",
                "action": "internal.test.action",
                "params": {"value": "test"},
            }
        ],
    }


@pytest.fixture
def linear_dag() -> dict[str, Any]:
    """Linear DAG with sequential dependencies: step1 -> step2 -> step3."""
    return {
        "name": "linear-workflow",
        "version": "1.0",
        "parameters": [{"name": "input_value", "type": "string", "required": True}],
        "steps": [
            {
                "id": "step1",
                "name": "First Step",
                "action": "internal.test.action",
                "params": {"value": "{{ params.input_value }}"},
                "outputs": ["result"],
            },
            {
                "id": "step2",
                "name": "Second Step",
                "action": "internal.test.action",
                "depends_on": ["step1"],
                "params": {"input": "{{ steps.step1.outputs.result }}"},
                "outputs": ["result"],
            },
            {
                "id": "step3",
                "name": "Third Step",
                "action": "internal.test.action",
                "depends_on": ["step2"],
                "params": {"input": "{{ steps.step2.outputs.result }}"},
            },
        ],
        "outputs": {
            "final_result": "{{ steps.step3.outputs.result }}",
        },
    }


@pytest.fixture
def parallel_dag() -> dict[str, Any]:
    """DAG with parallel steps: step1 -> (step2a, step2b) -> step3."""
    return {
        "name": "parallel-workflow",
        "version": "1.0",
        "steps": [
            {
                "id": "step1",
                "name": "Initial Step",
                "action": "internal.test.action",
                "params": {},
                "outputs": ["data"],
            },
            {
                "id": "step2a",
                "name": "Parallel Step A",
                "action": "internal.test.action",
                "depends_on": ["step1"],
                "params": {"branch": "a"},
                "outputs": ["result_a"],
            },
            {
                "id": "step2b",
                "name": "Parallel Step B",
                "action": "internal.test.action",
                "depends_on": ["step1"],
                "params": {"branch": "b"},
                "outputs": ["result_b"],
            },
            {
                "id": "step3",
                "name": "Final Step",
                "action": "internal.test.action",
                "depends_on": ["step2a", "step2b"],
                "params": {
                    "result_a": "{{ steps.step2a.outputs.result_a }}",
                    "result_b": "{{ steps.step2b.outputs.result_b }}",
                },
            },
        ],
    }


@pytest.fixture
def diamond_dag() -> dict[str, Any]:
    """Diamond DAG pattern: A -> (B, C) -> D."""
    return {
        "name": "diamond-workflow",
        "version": "1.0",
        "steps": [
            {"id": "A", "name": "Step A", "action": "test.action", "params": {}},
            {
                "id": "B",
                "name": "Step B",
                "action": "test.action",
                "depends_on": ["A"],
                "params": {},
            },
            {
                "id": "C",
                "name": "Step C",
                "action": "test.action",
                "depends_on": ["A"],
                "params": {},
            },
            {
                "id": "D",
                "name": "Step D",
                "action": "test.action",
                "depends_on": ["B", "C"],
                "params": {},
            },
        ],
    }


@pytest.fixture
def cyclic_dag() -> dict[str, Any]:
    """Invalid DAG with cyclic dependency: A -> B -> C -> A."""
    return {
        "name": "cyclic-workflow",
        "version": "1.0",
        "steps": [
            {
                "id": "A",
                "name": "Step A",
                "action": "test.action",
                "depends_on": ["C"],
                "params": {},
            },
            {
                "id": "B",
                "name": "Step B",
                "action": "test.action",
                "depends_on": ["A"],
                "params": {},
            },
            {
                "id": "C",
                "name": "Step C",
                "action": "test.action",
                "depends_on": ["B"],
                "params": {},
            },
        ],
    }


@pytest.fixture
def conditional_dag() -> dict[str, Any]:
    """DAG with conditional execution."""
    return {
        "name": "conditional-workflow",
        "version": "1.0",
        "parameters": [{"name": "skip_optional", "type": "boolean", "default": False}],
        "steps": [
            {
                "id": "step1",
                "name": "Check Step",
                "action": "internal.test.action",
                "params": {},
                "outputs": ["should_continue"],
            },
            {
                "id": "step2",
                "name": "Optional Step",
                "action": "internal.test.action",
                "depends_on": ["step1"],
                "condition": "{{ steps.step1.outputs.should_continue == true }}",
                "params": {},
            },
            {
                "id": "step3",
                "name": "Always Step",
                "action": "internal.test.action",
                "depends_on": ["step1"],
                "params": {},
            },
        ],
    }


@pytest.fixture
def complex_dag() -> dict[str, Any]:
    """Complex DAG with multiple features."""
    return {
        "name": "complex-workflow",
        "version": "1.0",
        "description": "Complex workflow for testing",
        "parameters": [
            {"name": "model_uri", "type": "string", "required": True},
            {"name": "cluster_id", "type": "string", "required": True},
            {"name": "replicas", "type": "integer", "required": False, "default": 1},
        ],
        "settings": {
            "timeout_seconds": 3600,
            "fail_fast": True,
            "max_parallel_steps": 5,
        },
        "steps": [
            {
                "id": "onboard",
                "name": "Onboard Model",
                "action": "internal.model.onboard",
                "params": {"model_uri": "{{ params.model_uri }}"},
                "outputs": ["model_id"],
                "timeout_seconds": 600,
            },
            {
                "id": "simulate",
                "name": "Run Simulation",
                "action": "internal.budsim.simulate",
                "depends_on": ["onboard"],
                "params": {
                    "model_id": "{{ steps.onboard.outputs.model_id }}",
                    "cluster_id": "{{ params.cluster_id }}",
                },
                "outputs": ["recommended_config"],
                "on_failure": "continue",
            },
            {
                "id": "deploy",
                "name": "Deploy Model",
                "action": "internal.deployment.deploy",
                "depends_on": ["onboard"],
                "params": {
                    "model_id": "{{ steps.onboard.outputs.model_id }}",
                    "cluster_id": "{{ params.cluster_id }}",
                    "replicas": "{{ params.replicas }}",
                },
                "outputs": ["endpoint_url"],
                "retry": {"max_attempts": 2, "backoff_seconds": 30},
            },
            {
                "id": "notify",
                "name": "Send Notification",
                "action": "internal.notify.send",
                "depends_on": ["deploy"],
                "params": {"message": "Deployed {{ steps.onboard.outputs.model_id }}"},
                "on_failure": "continue",
            },
        ],
        "outputs": {
            "endpoint_url": "{{ steps.deploy.outputs.endpoint_url }}",
            "model_id": "{{ steps.onboard.outputs.model_id }}",
        },
    }


# ============ Mock Fixtures ============


@pytest.fixture
def mock_dapr_client() -> AsyncMock:
    """Mock Dapr client for service invocation."""
    client = AsyncMock()
    client.invoke.return_value = {"status": "success", "result": "test"}
    return client


@pytest.fixture
def mock_state_store() -> AsyncMock:
    """Mock Dapr state store."""
    store = AsyncMock()
    store.get.return_value = None
    store.save.return_value = None
    store.delete.return_value = None
    return store


@pytest.fixture
def mock_pubsub() -> AsyncMock:
    """Mock Dapr pub/sub."""
    pubsub = AsyncMock()
    pubsub.publish.return_value = None
    return pubsub


@pytest.fixture
def execution_id() -> str:
    """Generate a random execution ID."""
    return str(uuid4())


@pytest.fixture
def workflow_params() -> dict[str, Any]:
    """Sample workflow parameters."""
    return {
        "model_uri": "meta-llama/Llama-2-7b",
        "cluster_id": "cluster-123",
        "replicas": 2,
    }


@pytest.fixture
def step_outputs() -> dict[str, dict[str, Any]]:
    """Sample step outputs for parameter resolution tests."""
    return {
        "step1": {"result": "value1", "count": 10},
        "step2": {"result": "value2", "items": ["a", "b", "c"]},
        "onboard": {"model_id": "model-abc-123"},
        "simulate": {"recommended_config": {"replicas": 3, "memory": "16Gi"}},
    }


# ============ Test Utilities ============


@pytest.fixture
def make_step():
    """Factory for creating step definitions."""

    def _make_step(
        step_id: str,
        action: str = "test.action",
        depends_on: list[str] | None = None,
        params: dict | None = None,
        outputs: list[str] | None = None,
        condition: str | None = None,
        on_failure: str = "fail",
    ) -> dict[str, Any]:
        step = {
            "id": step_id,
            "name": f"Step {step_id}",
            "action": action,
            "params": params or {},
        }
        if depends_on:
            step["depends_on"] = depends_on
        if outputs:
            step["outputs"] = outputs
        if condition:
            step["condition"] = condition
        if on_failure != "fail":
            step["on_failure"] = on_failure
        return step

    return _make_step


@pytest.fixture
def make_dag(make_step):
    """Factory for creating DAG definitions."""

    def _make_dag(
        name: str = "test-workflow",
        steps: list[dict] | None = None,
        parameters: list[dict] | None = None,
        settings: dict | None = None,
    ) -> dict[str, Any]:
        dag = {
            "name": name,
            "version": "1.0",
            "steps": steps or [make_step("step1")],
        }
        if parameters:
            dag["parameters"] = parameters
        if settings:
            dag["settings"] = settings
        return dag

    return _make_dag
