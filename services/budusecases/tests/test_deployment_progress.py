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

"""Tests for the deployment progress endpoint and synthesize logic.

Covers:
- GET /deployments/{id}/progress route
- DeploymentOrchestrationService.get_deployment_progress()
- DeploymentOrchestrationService._synthesize_progress()
- DeploymentProgressResponseSchema validation
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus
from budusecases.deployments.schemas import (
    AggregatedProgressSchema,
    DeploymentProgressResponseSchema,
    StepProgressSchema,
)
from budusecases.deployments.services import DeploymentOrchestrationService


def _make_service(session=None):
    """Create a DeploymentOrchestrationService with mocked BudClusterClient."""
    if session is None:
        session = MagicMock()
    with patch("budusecases.deployments.services.BudClusterClient"):
        return DeploymentOrchestrationService(session=session)


# ======================================================================
# Helpers
# ======================================================================


def _make_component(
    name: str,
    component_type: str = "model",
    status: ComponentDeploymentStatus = ComponentDeploymentStatus.PENDING,
    endpoint_url: str | None = None,
    error_message: str | None = None,
):
    """Create a mock component deployment."""
    comp = MagicMock()
    comp.id = uuid4()
    comp.component_name = name
    comp.component_type = component_type
    comp.selected_component = f"{name}-default"
    comp.status = status
    comp.endpoint_url = endpoint_url
    comp.error_message = error_message
    comp.job_id = None
    comp.created_at = MagicMock(isoformat=MagicMock(return_value="2026-02-06T00:00:00Z"))
    comp.updated_at = MagicMock(isoformat=MagicMock(return_value="2026-02-06T00:00:00Z"))
    return comp


def _make_deployment(
    status: DeploymentStatus = DeploymentStatus.DEPLOYING,
    components: list | None = None,
    pipeline_execution_id: str | None = None,
):
    """Create a mock deployment."""
    deployment = MagicMock()
    deployment.id = uuid4()
    deployment.name = "test-deployment"
    deployment.status = status
    deployment.pipeline_execution_id = pipeline_execution_id
    deployment.component_deployments = components or []
    deployment.parameters = {}
    deployment.user_id = uuid4()
    deployment.cluster_id = uuid4()
    deployment.template_id = uuid4()
    return deployment


# ======================================================================
# _synthesize_progress tests
# ======================================================================


class TestSynthesizeProgress:
    """Test the _synthesize_progress method."""

    def _get_service(self):
        return _make_service()

    def test_all_pending_components(self):
        """All pending -> 0% progress, no current step."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.PENDING),
                _make_component("embedder", status=ComponentDeploymentStatus.PENDING),
            ]
        )

        result = service._synthesize_progress(deployment)

        assert result["aggregated_progress"]["overall_progress"] == "0"
        assert result["aggregated_progress"]["completed_steps"] == 0
        assert result["aggregated_progress"]["total_steps"] == 2
        assert result["aggregated_progress"]["current_step"] is None

    def test_mixed_statuses(self):
        """One RUNNING, one DEPLOYING, one PENDING -> 33% progress."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.RUNNING),
                _make_component("embedder", status=ComponentDeploymentStatus.DEPLOYING),
                _make_component("vector_db", status=ComponentDeploymentStatus.PENDING),
            ]
        )

        result = service._synthesize_progress(deployment)

        assert result["aggregated_progress"]["overall_progress"] == "33"
        assert result["aggregated_progress"]["completed_steps"] == 1
        assert result["aggregated_progress"]["total_steps"] == 3
        assert result["aggregated_progress"]["current_step"] == "deploy_embedder"

    def test_all_completed(self):
        """All RUNNING -> 100% progress."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.RUNNING),
                _make_component("embedder", status=ComponentDeploymentStatus.RUNNING),
            ]
        )

        result = service._synthesize_progress(deployment)

        assert result["aggregated_progress"]["overall_progress"] == "100"
        assert result["aggregated_progress"]["completed_steps"] == 2
        assert result["aggregated_progress"]["total_steps"] == 2
        assert result["aggregated_progress"]["current_step"] is None

    def test_failed_component_counts_as_completed(self):
        """FAILED is a terminal status and counts toward completed count."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component(
                    "llm",
                    status=ComponentDeploymentStatus.FAILED,
                    error_message="Chart not found",
                ),
                _make_component("embedder", status=ComponentDeploymentStatus.PENDING),
            ]
        )

        result = service._synthesize_progress(deployment)

        assert result["aggregated_progress"]["overall_progress"] == "50"
        assert result["aggregated_progress"]["completed_steps"] == 1

    def test_stopped_component_counts_as_completed(self):
        """STOPPED is a terminal status and counts toward completed count."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.STOPPED),
                _make_component("embedder", status=ComponentDeploymentStatus.STOPPED),
            ]
        )

        result = service._synthesize_progress(deployment)

        assert result["aggregated_progress"]["overall_progress"] == "100"
        assert result["aggregated_progress"]["completed_steps"] == 2

    def test_identifies_current_step(self):
        """Current step is the first DEPLOYING component."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.RUNNING),
                _make_component("embedder", status=ComponentDeploymentStatus.DEPLOYING),
                _make_component("vector_db", status=ComponentDeploymentStatus.DEPLOYING),
            ]
        )

        result = service._synthesize_progress(deployment)

        # First DEPLOYING component
        assert result["aggregated_progress"]["current_step"] == "deploy_embedder"

    def test_step_status_mapping(self):
        """Component statuses are correctly mapped to pipeline step statuses."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component("a", status=ComponentDeploymentStatus.PENDING),
                _make_component("b", status=ComponentDeploymentStatus.DEPLOYING),
                _make_component("c", status=ComponentDeploymentStatus.RUNNING),
                _make_component("d", status=ComponentDeploymentStatus.FAILED),
                _make_component("e", status=ComponentDeploymentStatus.STOPPED),
            ]
        )

        result = service._synthesize_progress(deployment)
        steps = result["steps"]

        assert steps[0]["status"] == "pending"
        assert steps[0]["step_name"] == "deploy_a"
        assert steps[1]["status"] == "running"
        assert steps[2]["status"] == "completed"
        assert steps[3]["status"] == "failed"
        assert steps[4]["status"] == "cancelled"

    def test_endpoint_url_in_outputs(self):
        """Endpoint URL is included in step outputs when present."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component(
                    "llm",
                    status=ComponentDeploymentStatus.RUNNING,
                    endpoint_url="https://llm.cluster.local:8080",
                ),
            ]
        )

        result = service._synthesize_progress(deployment)
        step = result["steps"][0]

        assert step["outputs"] == {"endpoint_url": "https://llm.cluster.local:8080"}

    def test_error_message_in_step(self):
        """Error message is included in step when present."""
        service = self._get_service()
        deployment = _make_deployment(
            components=[
                _make_component(
                    "helm_app",
                    component_type="helm",
                    status=ComponentDeploymentStatus.FAILED,
                    error_message="OCI registry unreachable",
                ),
            ]
        )

        result = service._synthesize_progress(deployment)
        step = result["steps"][0]

        assert step["error_message"] == "OCI registry unreachable"

    def test_empty_components(self):
        """Deployment with no components -> 0% progress, 0 steps."""
        service = self._get_service()
        deployment = _make_deployment(components=[])

        result = service._synthesize_progress(deployment)

        assert result["aggregated_progress"]["overall_progress"] == "0"
        assert result["aggregated_progress"]["completed_steps"] == 0
        assert result["aggregated_progress"]["total_steps"] == 0
        assert result["steps"] == []

    def test_execution_field_uses_pipeline_execution_id(self):
        """Execution dict uses pipeline_execution_id when present."""
        service = self._get_service()
        exec_id = "pipeline-exec-123"
        deployment = _make_deployment(
            pipeline_execution_id=exec_id,
            components=[_make_component("llm", status=ComponentDeploymentStatus.RUNNING)],
        )

        result = service._synthesize_progress(deployment)

        assert result["execution"]["id"] == exec_id

    def test_execution_field_fallback_to_deployment_id(self):
        """Execution dict falls back to deployment ID when no pipeline ID."""
        service = self._get_service()
        deployment = _make_deployment(
            pipeline_execution_id=None,
            components=[_make_component("llm", status=ComponentDeploymentStatus.PENDING)],
        )

        result = service._synthesize_progress(deployment)

        assert result["execution"]["id"] == str(deployment.id)


# ======================================================================
# get_deployment_progress tests
# ======================================================================


class TestGetDeploymentProgress:
    """Test the get_deployment_progress service method."""

    @pytest.mark.asyncio
    async def test_returns_pipeline_progress_when_available(self):
        """When deployment has pipeline_execution_id, returns BudPipeline progress."""
        service = _make_service()

        deployment = _make_deployment(pipeline_execution_id="exec-42")
        service._get_deployment = MagicMock(return_value=deployment)

        pipeline_response = {
            "execution": {"id": "exec-42", "status": "running", "progress_percentage": "60"},
            "steps": [],
            "recent_events": [],
            "aggregated_progress": {
                "overall_progress": "60",
                "eta_seconds": 120,
                "completed_steps": 3,
                "total_steps": 5,
                "current_step": "deploy_vector_db",
            },
        }

        with patch("budusecases.deployments.services.BudPipelineClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get_execution_progress = AsyncMock(return_value=pipeline_response)

            result = await service.get_deployment_progress(deployment.id)

        assert result == pipeline_response

    @pytest.mark.asyncio
    async def test_falls_back_to_synthesize_on_pipeline_error(self):
        """When BudPipeline call fails, falls back to synthesized progress."""
        service = _make_service()

        deployment = _make_deployment(
            pipeline_execution_id="exec-42",
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.RUNNING),
                _make_component("embedder", status=ComponentDeploymentStatus.DEPLOYING),
            ],
        )
        service._get_deployment = MagicMock(return_value=deployment)

        with patch("budusecases.deployments.services.BudPipelineClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get_execution_progress = AsyncMock(side_effect=Exception("Connection refused"))

            result = await service.get_deployment_progress(deployment.id)

        # Should fall back to synthesized progress
        assert result["aggregated_progress"]["total_steps"] == 2
        assert result["aggregated_progress"]["completed_steps"] == 1

    @pytest.mark.asyncio
    async def test_synthesizes_for_legacy_deployment(self):
        """Legacy deployment (no pipeline_execution_id) uses synthesized progress."""
        service = _make_service()

        deployment = _make_deployment(
            pipeline_execution_id=None,
            components=[
                _make_component("llm", status=ComponentDeploymentStatus.RUNNING),
            ],
        )
        service._get_deployment = MagicMock(return_value=deployment)

        result = await service.get_deployment_progress(deployment.id)

        assert result["aggregated_progress"]["overall_progress"] == "100"
        assert result["aggregated_progress"]["completed_steps"] == 1

    @pytest.mark.asyncio
    async def test_raises_deployment_not_found(self):
        """Raises DeploymentNotFoundError when deployment doesn't exist."""
        service = _make_service()
        service._get_deployment = MagicMock(return_value=None)

        from budusecases.deployments.exceptions import DeploymentNotFoundError

        with pytest.raises(DeploymentNotFoundError):
            await service.get_deployment_progress(uuid4())


# ======================================================================
# Schema validation tests
# ======================================================================


class TestDeploymentProgressSchemas:
    """Test DeploymentProgressResponseSchema and sub-schemas."""

    def test_full_response_schema_validates(self):
        """A complete progress response is valid."""
        data = {
            "execution": {"id": "abc-123", "status": "running", "progress_percentage": "50"},
            "steps": [
                {
                    "step_name": "deploy_llm",
                    "status": "completed",
                    "sequence_number": 0,
                },
            ],
            "recent_events": [],
            "aggregated_progress": {
                "overall_progress": "50",
                "completed_steps": 1,
                "total_steps": 2,
            },
        }
        schema = DeploymentProgressResponseSchema(**data)
        assert schema.execution["id"] == "abc-123"
        assert len(schema.steps) == 1
        assert schema.aggregated_progress.overall_progress == "50"

    def test_step_progress_schema_defaults(self):
        """StepProgressSchema has sensible defaults."""
        step = StepProgressSchema(step_name="deploy_llm", status="pending")
        assert step.id == ""
        assert step.progress_percentage == "0"
        assert step.awaiting_event is False
        assert step.outputs is None
        assert step.error_message is None

    def test_aggregated_progress_defaults(self):
        """AggregatedProgressSchema has sensible defaults."""
        agg = AggregatedProgressSchema()
        assert agg.overall_progress == "0"
        assert agg.eta_seconds is None
        assert agg.completed_steps == 0
        assert agg.total_steps == 0
        assert agg.current_step is None

    def test_response_schema_with_empty_steps(self):
        """Response with no steps is valid."""
        data = {
            "execution": {"id": "abc", "status": "pending", "progress_percentage": "0"},
            "steps": [],
            "recent_events": [],
            "aggregated_progress": {
                "overall_progress": "0",
                "completed_steps": 0,
                "total_steps": 0,
            },
        }
        schema = DeploymentProgressResponseSchema(**data)
        assert len(schema.steps) == 0
