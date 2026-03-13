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

"""Integration tests for model-only deployment via BudPipeline path.

Verifies backward compatibility: a simple model-only template still works
correctly when routed through BudPipeline orchestration instead of the legacy
direct-job path.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budusecases.deployments.dag_builder import build_deployment_dag
from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus
from budusecases.events.pipeline_listener import handle_pipeline_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model_only_template() -> dict[str, Any]:
    """Return a minimal model-only template dict."""
    return {
        "components": [
            {
                "name": "llm",
                "type": "model",
                "required": True,
                "default_component": "llama-3-8b",
            },
        ],
        "deployment_order": ["llm"],
        "parameters": {},
    }


def _make_mock_template() -> MagicMock:
    """Return a MagicMock that mimics a Template ORM instance."""
    template = MagicMock()
    template.id = uuid4()
    template.deployment_order = ["llm"]
    template.parameters = {}

    comp = MagicMock()
    comp.name = "llm"
    comp.component_type = "model"
    comp.default_component = "llama-3-8b"
    comp.chart = None  # model components have no chart

    template.components = [comp]
    return template


def _make_mock_component(
    component_name: str = "llm",
    component_type: str = "model",
    status: ComponentDeploymentStatus = ComponentDeploymentStatus.PENDING,
) -> MagicMock:
    """Return a MagicMock that mimics a ComponentDeployment ORM instance."""
    comp = MagicMock()
    comp.id = uuid4()
    comp.component_name = component_name
    comp.component_type = component_type
    comp.selected_component = "llama-3-8b"
    comp.status = status
    comp.config = {}
    comp.endpoint_url = None
    comp.error_message = None
    comp.job_id = None
    return comp


def _make_mock_deployment(
    status: DeploymentStatus = DeploymentStatus.PENDING,
    pipeline_execution_id: str | None = None,
    components: list[MagicMock] | None = None,
) -> MagicMock:
    """Return a MagicMock that mimics a UseCaseDeployment ORM instance."""
    deployment = MagicMock()
    deployment.id = uuid4()
    deployment.name = "test-model-deployment"
    deployment.template_id = uuid4()
    deployment.cluster_id = uuid4()
    deployment.user_id = uuid4()
    deployment.status = status
    deployment.parameters = {}
    deployment.pipeline_execution_id = pipeline_execution_id
    deployment.component_deployments = components or [_make_mock_component()]
    return deployment


# ============================================================================
# Test 1: Model-only DAG structure
# ============================================================================


class TestModelOnlyDagStructure:
    """Verify DAG structure produced by a model-only template."""

    def test_dag_has_correct_step_sequence(self) -> None:
        """DAG must contain cluster_health -> deploy_llm -> notify_complete."""
        deployment_id = str(uuid4())
        template = _make_model_only_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name="test-model",
            cluster_id=str(uuid4()),
            user_id=str(uuid4()),
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        step_names = [s["name"] for s in dag["steps"]]
        assert step_names == ["cluster_health", "deploy_llm", "notify_complete"]

    def test_deploy_llm_uses_deployment_create_action(self) -> None:
        """Model components must use 'deployment_create', not 'helm_deploy'."""
        template = _make_model_only_template()

        dag = build_deployment_dag(
            deployment_id=str(uuid4()),
            deployment_name="test-model",
            cluster_id=str(uuid4()),
            user_id=str(uuid4()),
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        deploy_llm_step = dag["steps"][1]
        assert deploy_llm_step["name"] == "deploy_llm"
        assert deploy_llm_step["action"] == "deployment_create"
        assert deploy_llm_step["action"] != "helm_deploy"

    def test_deploy_llm_depends_on_cluster_health(self) -> None:
        """deploy_llm must depend on cluster_health."""
        template = _make_model_only_template()

        dag = build_deployment_dag(
            deployment_id=str(uuid4()),
            deployment_name="test-model",
            cluster_id=str(uuid4()),
            user_id=str(uuid4()),
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        deploy_llm_step = dag["steps"][1]
        assert deploy_llm_step["depends_on"] == ["cluster_health"]

    def test_deploy_llm_params_contain_model_id(self) -> None:
        """deploy_llm step must pass the selected model_id in its params."""
        template = _make_model_only_template()

        dag = build_deployment_dag(
            deployment_id=str(uuid4()),
            deployment_name="test-model",
            cluster_id=str(uuid4()),
            user_id=str(uuid4()),
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        deploy_llm_step = dag["steps"][1]
        assert deploy_llm_step["params"]["model_id"] == "llama-3-8b"

    def test_notify_complete_depends_on_deploy_llm(self) -> None:
        """notify_complete must depend on deploy_llm."""
        template = _make_model_only_template()

        dag = build_deployment_dag(
            deployment_id=str(uuid4()),
            deployment_name="test-model",
            cluster_id=str(uuid4()),
            user_id=str(uuid4()),
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        notify_step = dag["steps"][2]
        assert notify_step["depends_on"] == ["deploy_llm"]


# ============================================================================
# Test 2: Start deployment creates pipeline execution
# ============================================================================


class TestStartDeploymentCreatesPipelineExecution:
    """Verify start_deployment routes through BudPipeline when the flag is on."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.fixture
    def mock_pipeline_client(self) -> AsyncMock:
        client = AsyncMock()
        client.create_execution.return_value = {"execution_id": "exec-123"}
        return client

    @pytest.fixture
    def mock_template(self) -> MagicMock:
        return _make_mock_template()

    @pytest.fixture
    def mock_deployment(self) -> MagicMock:
        return _make_mock_deployment(status=DeploymentStatus.PENDING)

    @pytest.mark.asyncio
    async def test_create_execution_called(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
        mock_template: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """BudPipelineClient.create_execution() must be called."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
            patch(
                "budusecases.deployments.services.app_settings",
            ) as mock_settings,
        ):
            mock_settings.use_pipeline_orchestration = True

            service = DeploymentOrchestrationService(session=mock_session)

            # Mock internal lookups
            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.template_manager.get_template = MagicMock(return_value=mock_template)
            service.deployment_manager.update_deployment_pipeline_execution = MagicMock()
            service.deployment_manager.update_deployment_status = MagicMock()
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.start_deployment(mock_deployment.id)

            mock_pipeline_client.create_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_execution_id_stored(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
        mock_template: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """Deployment record must have pipeline_execution_id set to 'exec-123'."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
            patch(
                "budusecases.deployments.services.app_settings",
            ) as mock_settings,
        ):
            mock_settings.use_pipeline_orchestration = True

            service = DeploymentOrchestrationService(session=mock_session)

            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.template_manager.get_template = MagicMock(return_value=mock_template)
            service.deployment_manager.update_deployment_pipeline_execution = MagicMock()
            service.deployment_manager.update_deployment_status = MagicMock()
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.start_deployment(mock_deployment.id)

            service.deployment_manager.update_deployment_pipeline_execution.assert_called_once_with(
                deployment_id=mock_deployment.id,
                execution_id="exec-123",
            )

    @pytest.mark.asyncio
    async def test_deployment_status_set_to_deploying(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
        mock_template: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """Deployment status must transition to DEPLOYING."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
            patch(
                "budusecases.deployments.services.app_settings",
            ) as mock_settings,
        ):
            mock_settings.use_pipeline_orchestration = True

            service = DeploymentOrchestrationService(session=mock_session)

            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.template_manager.get_template = MagicMock(return_value=mock_template)
            service.deployment_manager.update_deployment_pipeline_execution = MagicMock()
            service.deployment_manager.update_deployment_status = MagicMock()
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.start_deployment(mock_deployment.id)

            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.DEPLOYING,
            )

    @pytest.mark.asyncio
    async def test_component_statuses_set_to_deploying(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
        mock_template: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """All component statuses must transition to DEPLOYING."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
            patch(
                "budusecases.deployments.services.app_settings",
            ) as mock_settings,
        ):
            mock_settings.use_pipeline_orchestration = True

            service = DeploymentOrchestrationService(session=mock_session)

            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.template_manager.get_template = MagicMock(return_value=mock_template)
            service.deployment_manager.update_deployment_pipeline_execution = MagicMock()
            service.deployment_manager.update_deployment_status = MagicMock()
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.start_deployment(mock_deployment.id)

            # One component in mock_deployment
            component = mock_deployment.component_deployments[0]
            service.deployment_manager.update_component_deployment_status.assert_called_once_with(
                component_id=component.id,
                status=ComponentDeploymentStatus.DEPLOYING,
            )


# ============================================================================
# Test 3: Pipeline event flow (step + execution completion)
# ============================================================================


class TestPipelineEventFlow:
    """Verify that pipeline callback events update component and deployment statuses."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.fixture
    def mock_component(self) -> MagicMock:
        return _make_mock_component(
            status=ComponentDeploymentStatus.DEPLOYING,
        )

    @pytest.fixture
    def mock_deployment(self, mock_component: MagicMock) -> MagicMock:
        return _make_mock_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-123",
            components=[mock_component],
        )

    @pytest.mark.asyncio
    async def test_step_completed_updates_component_to_running(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        mock_component: MagicMock,
    ) -> None:
        """A step_completed event for deploy_llm sets the component to RUNNING."""
        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment
            manager_instance.update_component_deployment_status = MagicMock()
            manager_instance.update_component_deployment_job = MagicMock()

            event_data = {
                "type": "step_completed",
                "execution_id": "exec-123",
                "data": {
                    "step_name": "deploy_llm",
                    "outputs": {},
                },
            }

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_called_once_with(
                component_id=mock_component.id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=None,
                error_message=None,
            )

    @pytest.mark.asyncio
    async def test_workflow_completed_updates_deployment_to_running(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """A workflow_completed event sets the deployment to RUNNING."""
        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment
            manager_instance.update_deployment_status = MagicMock()

            event_data = {
                "type": "workflow_completed",
                "execution_id": "exec-123",
                "data": {
                    "success": True,
                },
            }

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.RUNNING,
                error_message=None,
            )

    @pytest.mark.asyncio
    async def test_step_then_execution_flow(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        mock_component: MagicMock,
    ) -> None:
        """Full flow: step_completed then workflow_completed produce correct final state."""
        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment
            manager_instance.update_component_deployment_status = MagicMock()
            manager_instance.update_component_deployment_job = MagicMock()
            manager_instance.update_deployment_status = MagicMock()

            # Step 1: step_completed for deploy_llm
            step_event = {
                "type": "step_completed",
                "execution_id": "exec-123",
                "data": {
                    "step_name": "deploy_llm",
                    "outputs": {},
                },
            }
            await handle_pipeline_event(step_event, mock_session)

            # Verify component was set to RUNNING
            manager_instance.update_component_deployment_status.assert_called_with(
                component_id=mock_component.id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=None,
                error_message=None,
            )

            # Step 2: workflow_completed
            exec_event = {
                "type": "workflow_completed",
                "execution_id": "exec-123",
                "data": {
                    "success": True,
                },
            }
            await handle_pipeline_event(exec_event, mock_session)

            # Verify deployment was set to RUNNING
            manager_instance.update_deployment_status.assert_called_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.RUNNING,
                error_message=None,
            )

    @pytest.mark.asyncio
    async def test_step_completed_with_endpoint_url(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        mock_component: MagicMock,
    ) -> None:
        """step_completed event with endpoint_url in outputs propagates it to the component."""
        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment
            manager_instance.update_component_deployment_status = MagicMock()
            manager_instance.update_component_deployment_job = MagicMock()

            event_data = {
                "type": "step_completed",
                "execution_id": "exec-123",
                "data": {
                    "step_name": "deploy_llm",
                    "outputs": {
                        "endpoint_url": "http://llm-service:8080/v1",
                    },
                },
            }

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_called_once_with(
                component_id=mock_component.id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url="http://llm-service:8080/v1",
                error_message=None,
            )

    @pytest.mark.asyncio
    async def test_non_deploy_step_event_ignored(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """Events for non-deploy steps (e.g. cluster_health) must not update components."""
        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment
            manager_instance.update_component_deployment_status = MagicMock()

            event_data = {
                "type": "step_completed",
                "execution_id": "exec-123",
                "data": {
                    "step_name": "cluster_health",
                    "outputs": {},
                },
            }

            await handle_pipeline_event(event_data, mock_session)

            # cluster_health is not a deploy step, so no component update
            manager_instance.update_component_deployment_status.assert_not_called()


# ============================================================================
# Test 4: Pipeline sync status
# ============================================================================


class TestPipelineSyncStatus:
    """Verify sync_deployment_status uses the pipeline path when pipeline_execution_id is set."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.fixture
    def mock_pipeline_client(self) -> AsyncMock:
        client = AsyncMock()
        client.get_execution_progress.return_value = {
            "execution": {
                "id": "exec-123",
                "status": "running",
            },
            "steps": [
                {
                    "name": "cluster_health",
                    "status": "completed",
                },
                {
                    "name": "deploy_llm",
                    "status": "running",
                },
            ],
        }
        return client

    @pytest.mark.asyncio
    async def test_sync_calls_get_execution_progress(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
    ) -> None:
        """sync_deployment_status must call get_execution_progress for pipeline deployments."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        mock_component = _make_mock_component(
            status=ComponentDeploymentStatus.DEPLOYING,
        )
        mock_deployment = _make_mock_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-123",
            components=[mock_component],
        )

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            service = DeploymentOrchestrationService(session=mock_session)
            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.sync_deployment_status(mock_deployment.id)

            mock_pipeline_client.get_execution_progress.assert_called_once_with("exec-123")

    @pytest.mark.asyncio
    async def test_sync_does_not_call_budcluster(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
    ) -> None:
        """sync_deployment_status must NOT call BudCluster get_job for pipeline deployments."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        mock_component = _make_mock_component(
            status=ComponentDeploymentStatus.DEPLOYING,
        )
        mock_deployment = _make_mock_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-123",
            components=[mock_component],
        )

        mock_budcluster_client = AsyncMock()

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=mock_budcluster_client,
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            service = DeploymentOrchestrationService(session=mock_session)
            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.sync_deployment_status(mock_deployment.id)

            # BudCluster get_job should NOT be called on the pipeline path
            mock_budcluster_client.get_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_updates_component_from_step_status(
        self,
        mock_session: MagicMock,
        mock_pipeline_client: AsyncMock,
    ) -> None:
        """Running step status in pipeline progress updates the component to DEPLOYING."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        mock_component = _make_mock_component(
            status=ComponentDeploymentStatus.DEPLOYING,
        )
        mock_deployment = _make_mock_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-123",
            components=[mock_component],
        )

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            service = DeploymentOrchestrationService(session=mock_session)
            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.sync_deployment_status(mock_deployment.id)

            # deploy_llm step is "running", which maps to DEPLOYING
            service.deployment_manager.update_component_deployment_status.assert_called_with(
                component_id=mock_component.id,
                status=ComponentDeploymentStatus.DEPLOYING,
                error_message=None,
            )

    @pytest.mark.asyncio
    async def test_sync_completed_execution_sets_running(
        self,
        mock_session: MagicMock,
    ) -> None:
        """A completed pipeline execution sets deployment and components to RUNNING."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        mock_component = _make_mock_component(
            status=ComponentDeploymentStatus.DEPLOYING,
        )
        mock_deployment = _make_mock_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-123",
            components=[mock_component],
        )

        completed_client = AsyncMock()
        completed_client.get_execution_progress.return_value = {
            "execution": {
                "id": "exec-123",
                "status": "completed",
            },
            "steps": [
                {"name": "deploy_llm", "status": "completed"},
            ],
        }

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=completed_client,
            ),
        ):
            service = DeploymentOrchestrationService(session=mock_session)
            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.deployment_manager.update_deployment_status = MagicMock()
            service.deployment_manager.update_component_deployment_status = MagicMock()

            await service.sync_deployment_status(mock_deployment.id)

            # Deployment set to RUNNING
            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.RUNNING,
            )

            # Component set to RUNNING
            service.deployment_manager.update_component_deployment_status.assert_called_with(
                component_id=mock_component.id,
                status=ComponentDeploymentStatus.RUNNING,
            )

    @pytest.mark.asyncio
    async def test_sync_failed_execution_sets_failed(
        self,
        mock_session: MagicMock,
    ) -> None:
        """A failed pipeline execution sets deployment to FAILED with error message."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        mock_component = _make_mock_component(
            status=ComponentDeploymentStatus.DEPLOYING,
        )
        mock_deployment = _make_mock_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-123",
            components=[mock_component],
        )

        failed_client = AsyncMock()
        failed_client.get_execution_progress.return_value = {
            "execution": {
                "id": "exec-123",
                "status": "failed",
                "error": "Model deployment timed out",
            },
            "steps": [],
        }

        with (
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=AsyncMock(),
            ),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=failed_client,
            ),
        ):
            service = DeploymentOrchestrationService(session=mock_session)
            service.deployment_manager.get_deployment = MagicMock(return_value=mock_deployment)
            service.deployment_manager.update_deployment_status = MagicMock()

            await service.sync_deployment_status(mock_deployment.id)

            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.FAILED,
                error_message="Model deployment timed out",
            )
