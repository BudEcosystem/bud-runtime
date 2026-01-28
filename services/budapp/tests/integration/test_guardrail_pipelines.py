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

"""Integration tests for guardrail pipeline functionality.

Tests the pipeline integration methods in GuardrailDeploymentWorkflowService
with mocked external services (BudPipelineService, DaprService).
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session


class TestGuardrailModelOnboardingPipeline:
    """Tests for trigger_model_onboarding pipeline integration."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance with mock session."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.fixture
    def sample_models(self):
        """Provide sample models for onboarding."""
        return [
            {
                "rule_id": str(uuid4()),
                "model_uri": "microsoft/deberta-v3-base",
                "model_provider_type": "hugging_face",
            },
            {
                "rule_id": str(uuid4()),
                "model_uri": "sentence-transformers/all-MiniLM-L6-v2",
                "model_provider_type": "hugging_face",
            },
        ]

    @pytest.mark.asyncio
    async def test_trigger_model_onboarding_creates_dag(self, service, sample_models):
        """Test that trigger_model_onboarding creates correct DAG structure."""
        credential_id = uuid4()
        user_id = uuid4()
        execution_id = str(uuid4())

        with patch.object(
            service,
            "session",
            MagicMock(),
        ):
            with patch("budapp.guardrails.services.BudPipelineService") as MockPipelineService:
                mock_pipeline = AsyncMock()
                mock_pipeline.run_ephemeral_execution = AsyncMock(return_value={"execution_id": execution_id})
                MockPipelineService.return_value = mock_pipeline

                result = await service.trigger_model_onboarding(
                    models=sample_models,
                    credential_id=credential_id,
                    user_id=user_id,
                    callback_topics=["test-topic"],
                )

                # Verify result
                assert result["execution_id"] == execution_id
                assert result["total_models"] == 2
                assert "step_mapping" in result

                # Verify DAG was created correctly
                mock_pipeline.run_ephemeral_execution.assert_called_once()
                call_args = mock_pipeline.run_ephemeral_execution.call_args

                dag = call_args.kwargs["pipeline_definition"]
                assert dag["name"] == "guardrail-model-onboarding"
                assert len(dag["steps"]) == 2

                # Verify step structure
                for step in dag["steps"]:
                    assert step["action"] == "model_add"
                    assert "uri" in step["params"]
                    assert step["depends_on"] == []  # Parallel execution

    @pytest.mark.asyncio
    async def test_trigger_model_onboarding_empty_list(self, service):
        """Test that empty model list returns early without calling pipeline."""
        result = await service.trigger_model_onboarding(models=[])

        assert result["execution_id"] is None
        assert result["message"] == "No models to onboard"

    @pytest.mark.asyncio
    async def test_trigger_model_onboarding_with_callback_topics(self, service, sample_models):
        """Test that callback topics are passed to pipeline execution."""
        execution_id = str(uuid4())
        callback_topics = ["topic1", "topic2"]

        with patch.object(service, "session", MagicMock()):
            with patch("budapp.guardrails.services.BudPipelineService") as MockPipelineService:
                mock_pipeline = AsyncMock()
                mock_pipeline.run_ephemeral_execution = AsyncMock(return_value={"execution_id": execution_id})
                MockPipelineService.return_value = mock_pipeline

                await service.trigger_model_onboarding(
                    models=sample_models,
                    callback_topics=callback_topics,
                )

                call_args = mock_pipeline.run_ephemeral_execution.call_args
                assert call_args.kwargs["callback_topics"] == callback_topics


class TestGuardrailDeploymentPipeline:
    """Tests for trigger_deployment pipeline integration."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance with mock session."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.fixture
    def sample_models_for_deployment(self):
        """Provide sample models for deployment."""
        return [
            {
                "model_id": str(uuid4()),
                "model_name": "deberta-classifier",
                "deployment_config": {
                    "replica": 1,
                    "tensor_parallelism": 1,
                    "max_model_len": 4096,
                },
            },
            {
                "model_id": str(uuid4()),
                "model_name": "minilm-embeddings",
                "deployment_config": {
                    "replica": 2,
                    "tensor_parallelism": 2,
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_trigger_deployment_creates_dag(self, service, sample_models_for_deployment):
        """Test that trigger_deployment creates correct DAG structure."""
        cluster_id = uuid4()
        project_id = uuid4()
        user_id = uuid4()
        execution_id = str(uuid4())

        with patch.object(service, "session", MagicMock()):
            with patch("budapp.guardrails.services.BudPipelineService") as MockPipelineService:
                mock_pipeline = AsyncMock()
                mock_pipeline.run_ephemeral_execution = AsyncMock(return_value={"execution_id": execution_id})
                MockPipelineService.return_value = mock_pipeline

                result = await service.trigger_deployment(
                    models=sample_models_for_deployment,
                    cluster_id=cluster_id,
                    project_id=project_id,
                    user_id=user_id,
                )

                # Verify result
                assert result["execution_id"] == execution_id
                assert result["total_models"] == 2
                assert result["cluster_id"] == str(cluster_id)

                # Verify DAG structure
                call_args = mock_pipeline.run_ephemeral_execution.call_args
                dag = call_args.kwargs["pipeline_definition"]
                assert dag["name"] == "guardrail-model-deployment"
                assert len(dag["steps"]) == 2

                # Verify deployment steps
                for step in dag["steps"]:
                    assert step["action"] == "deployment_create"
                    assert "model_id" in step["params"]
                    assert "cluster_id" in step["params"]
                    assert "project_id" in step["params"]

    @pytest.mark.asyncio
    async def test_trigger_deployment_empty_list(self, service):
        """Test that empty model list returns early."""
        result = await service.trigger_deployment(
            models=[],
            cluster_id=uuid4(),
            project_id=uuid4(),
        )

        assert result["execution_id"] is None
        assert result["message"] == "No models to deploy"

    @pytest.mark.asyncio
    async def test_trigger_deployment_preserves_config(self, service, sample_models_for_deployment):
        """Test that deployment config is passed correctly to DAG steps."""
        cluster_id = uuid4()
        project_id = uuid4()
        execution_id = str(uuid4())

        with patch.object(service, "session", MagicMock()):
            with patch("budapp.guardrails.services.BudPipelineService") as MockPipelineService:
                mock_pipeline = AsyncMock()
                mock_pipeline.run_ephemeral_execution = AsyncMock(return_value={"execution_id": execution_id})
                MockPipelineService.return_value = mock_pipeline

                await service.trigger_deployment(
                    models=sample_models_for_deployment,
                    cluster_id=cluster_id,
                    project_id=project_id,
                )

                call_args = mock_pipeline.run_ephemeral_execution.call_args
                dag = call_args.kwargs["pipeline_definition"]

                # Check first model config
                step0 = dag["steps"][0]
                assert step0["params"]["replica"] == 1
                assert step0["params"]["tp"] == 1
                assert step0["params"]["max_model_len"] == 4096

                # Check second model config
                step1 = dag["steps"][1]
                assert step1["params"]["replica"] == 2
                assert step1["params"]["tp"] == 2


class TestGuardrailSimulationPipeline:
    """Tests for trigger_simulation pipeline integration."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance with mock session."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.fixture
    def sample_models_for_simulation(self):
        """Provide sample models for simulation."""
        return [
            {
                "model_id": str(uuid4()),
                "model_uri": "microsoft/deberta-v3-base",
                "deployment_config": {
                    "input_tokens": 512,
                    "output_tokens": 64,
                    "concurrency": 5,
                },
            },
            {
                "model_id": str(uuid4()),
                "model_uri": "sentence-transformers/all-MiniLM-L6-v2",
                "deployment_config": {
                    "input_tokens": 256,
                    "output_tokens": 32,
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_trigger_simulation_calls_budsim(self, service, sample_models_for_simulation):
        """Test that trigger_simulation calls budsim for each model."""
        workflow_ids = [str(uuid4()), str(uuid4())]

        with patch("budapp.guardrails.services.DaprService") as MockDaprService:
            # Mock successful simulation responses
            MockDaprService.invoke_service = AsyncMock(
                side_effect=[
                    {"workflow_id": workflow_ids[0]},
                    {"workflow_id": workflow_ids[1]},
                ]
            )

            result = await service.trigger_simulation(
                models=sample_models_for_simulation,
                hardware_mode="dedicated",
            )

            # Verify result
            assert result["total_models"] == 2
            assert result["successful"] == 2
            assert result["failed"] == 0
            assert len(result["workflow_ids"]) == 2
            assert result["workflow_ids"] == workflow_ids

            # Verify DaprService was called for each model
            assert MockDaprService.invoke_service.call_count == 2

    @pytest.mark.asyncio
    async def test_trigger_simulation_empty_list(self, service):
        """Test that empty model list returns early."""
        result = await service.trigger_simulation(models=[])

        assert len(result["workflow_ids"]) == 0
        assert result["message"] == "No models to simulate"

    @pytest.mark.asyncio
    async def test_trigger_simulation_partial_failure(self, service, sample_models_for_simulation):
        """Test handling of partial simulation failures."""
        workflow_id = str(uuid4())

        with patch("budapp.guardrails.services.DaprService") as MockDaprService:
            # First succeeds, second fails
            MockDaprService.invoke_service = AsyncMock(
                side_effect=[
                    {"workflow_id": workflow_id},
                    Exception("Simulation failed"),
                ]
            )

            result = await service.trigger_simulation(
                models=sample_models_for_simulation,
            )

            # Verify partial results
            assert result["successful"] == 1
            assert result["failed"] == 1
            assert len(result["workflow_ids"]) == 1

            # Check results array for failure info
            failed_result = [r for r in result["results"] if r["status"] == "failed"]
            assert len(failed_result) == 1
            assert "error" in failed_result[0]

    @pytest.mark.asyncio
    async def test_trigger_simulation_uses_deployment_config(self, service, sample_models_for_simulation):
        """Test that deployment config is passed to budsim."""
        workflow_id = str(uuid4())

        with patch("budapp.guardrails.services.DaprService") as MockDaprService:
            MockDaprService.invoke_service = AsyncMock(return_value={"workflow_id": workflow_id})

            await service.trigger_simulation(
                models=[sample_models_for_simulation[0]],
                hardware_mode="shared",
            )

            # Verify call parameters
            call_args = MockDaprService.invoke_service.call_args
            call_data = call_args.kwargs["data"]

            assert call_data["input_tokens"] == 512
            assert call_data["output_tokens"] == 64
            assert call_data["concurrency"] == 5
            assert call_data["hardware_mode"] == "shared"


class TestPipelineExecutionProgress:
    """Tests for get_pipeline_execution_progress."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance with mock session."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.mark.asyncio
    async def test_get_execution_progress(self, service):
        """Test retrieving pipeline execution progress."""
        execution_id = str(uuid4())
        progress_data = {
            "execution_id": execution_id,
            "status": "running",
            "progress_percentage": 50,
            "steps": [
                {"id": "step1", "status": "completed"},
                {"id": "step2", "status": "running"},
            ],
        }

        with patch.object(service, "session", MagicMock()):
            with patch("budapp.guardrails.services.BudPipelineService") as MockPipelineService:
                mock_pipeline = AsyncMock()
                mock_pipeline.get_execution_progress = AsyncMock(return_value=progress_data)
                MockPipelineService.return_value = mock_pipeline

                result = await service.get_pipeline_execution_progress(execution_id)

                assert result["execution_id"] == execution_id
                assert result["status"] == "running"
                assert result["progress_percentage"] == 50
                mock_pipeline.get_execution_progress.assert_called_once_with(execution_id)
