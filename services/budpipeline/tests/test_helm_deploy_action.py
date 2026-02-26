"""Unit tests for the helm_deploy pipeline action.

Tests for HelmDeployExecutor and META metadata:
- META attribute validation (type, category, execution_mode, required_services)
- Parameter validation (cluster_id, chart_ref, chart_ref format)
- execute() — job creation, trigger, outputs, error handling
- on_event() — job_completed, job_failed, unknown event types, output extraction
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from budpipeline.actions.base import (
    ActionContext,
    ActionResult,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    StepStatus,
)
from budpipeline.actions.deployment.helm_deploy import (
    META,
    HelmDeployExecutor,
)

# ============ Fixtures ============


@pytest.fixture
def executor() -> HelmDeployExecutor:
    """Create a fresh HelmDeployExecutor instance."""
    return HelmDeployExecutor()


@pytest.fixture
def make_action_context():
    """Factory for ActionContext with mocked invoke_service."""

    def _make(
        params: dict | None = None,
        step_id: str = "test-step-1",
        execution_id: str | None = None,
    ) -> ActionContext:
        ctx = ActionContext(
            step_id=step_id,
            execution_id=execution_id or str(uuid4()),
            params=params or {},
            workflow_params={},
            step_outputs={},
        )
        ctx.invoke_service = AsyncMock()
        return ctx

    return _make


@pytest.fixture
def make_event_context():
    """Factory for EventContext with test event data."""

    def _make(
        event_data: dict | None = None,
        step_outputs: dict | None = None,
        external_workflow_id: str = "job-123",
    ) -> EventContext:
        return EventContext(
            step_execution_id=uuid4(),
            execution_id=uuid4(),
            external_workflow_id=external_workflow_id,
            event_type=event_data.get("type", "") if event_data else "",
            event_data=event_data or {},
            step_outputs=step_outputs or {},
        )

    return _make


# ============ META Tests ============


class TestMeta:
    """Tests for HelmDeploy META metadata."""

    def test_meta_has_correct_attributes(self):
        """Verify META.type, category, execution_mode, required_services."""
        assert META.type == "helm_deploy"
        assert META.category == "Deployment"
        assert META.execution_mode == ExecutionMode.EVENT_DRIVEN
        assert "budcluster" in META.required_services


# ============ Parameter Validation Tests ============


class TestValidateParams:
    """Tests for HelmDeployExecutor.validate_params()."""

    def test_validate_params_missing_cluster_id(self, executor):
        """validate_params({}) returns errors containing 'cluster_id'."""
        errors = executor.validate_params({})
        assert any("cluster_id" in e for e in errors)

    def test_validate_params_missing_chart_ref(self, executor):
        """validate_params with cluster_id but no chart_ref returns error."""
        errors = executor.validate_params({"cluster_id": "123"})
        assert any("chart_ref" in e for e in errors)

    def test_validate_params_valid(self, executor):
        """validate_params with valid cluster_id and oci:// chart_ref returns no errors."""
        errors = executor.validate_params(
            {
                "cluster_id": "123",
                "chart_ref": "oci://registry.example.com/charts/my-chart",
            }
        )
        assert errors == []

    def test_validate_params_invalid_chart_ref(self, executor):
        """validate_params with chart_ref not starting with a valid prefix returns error."""
        errors = executor.validate_params(
            {
                "cluster_id": "123",
                "chart_ref": "some-random-chart-ref",
            }
        )
        assert len(errors) > 0
        assert any("chart_ref" in e for e in errors)


# ============ execute() Tests ============


class TestExecute:
    """Tests for HelmDeployExecutor.execute()."""

    @pytest.mark.asyncio
    async def test_execute_creates_job_and_triggers(self, executor, make_action_context):
        """Execute creates a job via POST /jobs and triggers via POST /jobs/{id}/execute."""
        ctx = make_action_context(
            params={
                "cluster_id": "cluster-abc",
                "chart_ref": "oci://registry.example.com/charts/my-chart",
                "namespace": "production",
            }
        )

        # First call (POST /jobs) returns {id: "job-123"}
        # Second call (POST /jobs/job-123/execute) returns {}
        ctx.invoke_service.side_effect = [
            {"id": "job-123"},
            {},
        ]

        result = await executor.execute(ctx)

        # Verify two invoke_service calls were made
        assert ctx.invoke_service.call_count == 2

        # First call: create job
        first_call = ctx.invoke_service.call_args_list[0]
        assert (
            first_call.kwargs.get("method_path") == "job"
            or first_call[1].get("method_path") == "job"
        )
        assert first_call.kwargs.get("http_method", "POST") == "POST"

        # Second call: trigger execution
        second_call = ctx.invoke_service.call_args_list[1]
        second_method_path = second_call.kwargs.get("method_path") or second_call[1].get(
            "method_path", ""
        )
        assert "job/job-123/execute" in second_method_path

        # Result should indicate awaiting event
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.awaiting_event is True
        assert result.external_workflow_id == "job-123"

    @pytest.mark.asyncio
    async def test_execute_returns_correct_outputs(self, executor, make_action_context):
        """Execute returns outputs with job_id, namespace, release_name, status."""
        ctx = make_action_context(
            params={
                "cluster_id": "cluster-abc",
                "chart_ref": "oci://registry.example.com/charts/my-chart",
                "release_name": "my-release",
                "namespace": "staging",
            }
        )
        ctx.invoke_service.side_effect = [
            {"id": "job-456"},
            {},
        ]

        result = await executor.execute(ctx)

        assert result.outputs["job_id"] == "job-456"
        assert result.outputs["namespace"] == "staging"
        assert result.outputs["release_name"] == "my-release"
        assert result.outputs["status"] == "deploying"

    @pytest.mark.asyncio
    async def test_execute_failure_returns_error(self, executor, make_action_context):
        """When invoke_service raises, execute returns ActionResult(success=False)."""
        ctx = make_action_context(
            params={
                "cluster_id": "cluster-abc",
                "chart_ref": "oci://registry.example.com/charts/my-chart",
            }
        )
        ctx.invoke_service.side_effect = Exception("connection refused")

        result = await executor.execute(ctx)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert result.error is not None
        assert "Failed to deploy Helm chart" in result.error
        assert result.outputs["status"] == "failed"


# ============ on_event() Tests ============


class TestOnEvent:
    """Tests for HelmDeployExecutor.on_event()."""

    @pytest.mark.asyncio
    async def test_on_event_job_completed(self, executor, make_event_context):
        """job_completed event returns EventResult(action=COMPLETE, status=COMPLETED)."""
        ctx = make_event_context(
            event_data={
                "type": "job_completed",
                "payload": {"message": "all resources deployed"},
                "result": {},
            },
            step_outputs={
                "release_name": "my-release",
                "namespace": "production",
            },
            external_workflow_id="job-789",
        )

        result = await executor.on_event(ctx)

        assert isinstance(result, EventResult)
        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["status"] == "completed"
        assert result.outputs["job_id"] == "job-789"
        assert result.outputs["release_name"] == "my-release"
        assert result.outputs["namespace"] == "production"

    @pytest.mark.asyncio
    async def test_on_event_job_failed(self, executor, make_event_context):
        """job_failed event returns EventResult(action=COMPLETE, status=FAILED)."""
        ctx = make_event_context(
            event_data={
                "type": "job_failed",
                "payload": {"error": "timeout"},
            },
            step_outputs={
                "release_name": "my-release",
                "namespace": "default",
            },
            external_workflow_id="job-fail-1",
        )

        result = await executor.on_event(ctx)

        assert isinstance(result, EventResult)
        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.FAILED
        assert result.error is not None
        assert result.outputs["status"] == "failed"
        assert result.outputs["job_id"] == "job-fail-1"

    @pytest.mark.asyncio
    async def test_on_event_unknown_type_ignored(self, executor, make_event_context):
        """Unknown event type returns EventResult(action=IGNORE)."""
        ctx = make_event_context(
            event_data={
                "type": "unknown",
                "payload": {},
            },
        )

        result = await executor.on_event(ctx)

        assert isinstance(result, EventResult)
        assert result.action == EventAction.IGNORE

    @pytest.mark.asyncio
    async def test_on_event_extracts_endpoint_url(self, executor, make_event_context):
        """job_completed event with nested result.endpoint_url extracts it to outputs."""
        ctx = make_event_context(
            event_data={
                "type": "job_completed",
                "payload": {},
                "result": {
                    "endpoint_url": "https://my-service.example.com",
                    "services": [
                        {"name": "my-svc", "type": "ClusterIP", "port": 8080},
                    ],
                },
            },
            step_outputs={
                "release_name": "my-release",
                "namespace": "production",
            },
            external_workflow_id="job-endpoint-1",
        )

        result = await executor.on_event(ctx)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["endpoint_url"] == "https://my-service.example.com"
        assert result.outputs["services"] == [
            {"name": "my-svc", "type": "ClusterIP", "port": 8080},
        ]
