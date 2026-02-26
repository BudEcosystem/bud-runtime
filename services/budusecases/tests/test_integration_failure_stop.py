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

"""Integration tests for deployment failure and stop scenarios.

Verifies:
- Component failure propagation via pipeline step events.
- Stopping pipeline-orchestrated deployments (cancel_execution path).
- Graceful handling when pipeline cancel fails (already completed).
- Stopping legacy deployments (per-job cancellation path).
- Execution cancelled event handling.
- Sync status routing to pipeline vs. legacy paths.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budusecases.clients.budcluster.schemas import JobResponse, JobStatus
from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus
from budusecases.deployments.services import DeploymentOrchestrationService
from budusecases.events.pipeline_listener import handle_pipeline_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_component(
    name: str,
    component_type: str = "model",
    status: ComponentDeploymentStatus = ComponentDeploymentStatus.DEPLOYING,
    job_id=None,
) -> MagicMock:
    """Create a mock ComponentDeployment with the given attributes."""
    comp = MagicMock()
    comp.id = uuid4()
    comp.component_name = name
    comp.component_type = component_type
    comp.selected_component = f"{name}-default"
    comp.status = status
    comp.error_message = None
    comp.endpoint_url = None
    comp.job_id = job_id
    comp.config = {}
    return comp


def _make_deployment(
    status: DeploymentStatus = DeploymentStatus.DEPLOYING,
    pipeline_execution_id: str | None = None,
    components: list[MagicMock] | None = None,
) -> MagicMock:
    """Create a mock UseCaseDeployment with the given attributes."""
    dep = MagicMock()
    dep.id = uuid4()
    dep.name = "test-deployment"
    dep.cluster_id = uuid4()
    dep.user_id = uuid4()
    dep.template_id = uuid4()
    dep.status = status
    dep.pipeline_execution_id = pipeline_execution_id
    dep.error_message = None
    dep.parameters = {}
    dep.metadata_ = {}
    dep.component_deployments = components or []
    return dep


def _make_service(mock_session, mock_budcluster_client=None):
    """Instantiate DeploymentOrchestrationService with mocked BudClusterClient and DeploymentDataManager."""
    if mock_budcluster_client is None:
        mock_budcluster_client = AsyncMock()
    with patch(
        "budusecases.deployments.services.BudClusterClient",
        return_value=mock_budcluster_client,
    ):
        svc = DeploymentOrchestrationService(session=mock_session)

    # Replace the real DeploymentDataManager with a MagicMock so we can assert
    # on method calls (update_deployment_status, update_component_deployment_status, etc.)
    mock_dm = MagicMock()
    svc.deployment_manager = mock_dm

    return svc, mock_budcluster_client


# ===========================================================================
# Test 1: Component failure via step event
# ===========================================================================


class TestComponentFailureViaStepEvent:
    """Verify that step_failed events correctly mark individual components."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.fixture
    def deployment(self) -> MagicMock:
        llm = _make_component("llm", "model", ComponentDeploymentStatus.DEPLOYING)
        vector_db = _make_component("vector_db", "vector_db", ComponentDeploymentStatus.DEPLOYING)
        return _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-001",
            components=[llm, vector_db],
        )

    @pytest.mark.asyncio
    async def test_step_failed_marks_component_failed(self, session, deployment):
        """step_failed event should mark only the targeted component as FAILED."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_component_deployment_status = MagicMock()
            mock_manager.update_component_deployment_job = MagicMock()

            event = {
                "type": "step_failed",
                "execution_id": "exec-001",
                "data": {
                    "step_name": "deploy_llm",
                    "error_message": "OOM: insufficient GPU memory",
                },
            }

            await handle_pipeline_event(event, session)

            # The LLM component should be updated to FAILED with error message
            mock_manager.update_component_deployment_status.assert_called_once_with(
                component_id=deployment.component_deployments[0].id,
                status=ComponentDeploymentStatus.FAILED,
                endpoint_url=None,
                error_message="OOM: insufficient GPU memory",
            )
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_db_unchanged_after_llm_failure(self, session, deployment):
        """vector_db component should remain untouched when llm fails."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_component_deployment_status = MagicMock()
            mock_manager.update_component_deployment_job = MagicMock()

            event = {
                "type": "step_failed",
                "execution_id": "exec-001",
                "data": {
                    "step_name": "deploy_llm",
                    "error_message": "OOM: insufficient GPU memory",
                },
            }

            await handle_pipeline_event(event, session)

            # Only one call -- for the llm component, not vector_db
            assert mock_manager.update_component_deployment_status.call_count == 1
            called_component_id = mock_manager.update_component_deployment_status.call_args[1]["component_id"]
            assert called_component_id == deployment.component_deployments[0].id

    @pytest.mark.asyncio
    async def test_execution_completed_failed_sets_deployment_failed(self, session, deployment):
        """workflow_failed event sets the overall deployment to FAILED."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_deployment_status = MagicMock()

            event = {
                "type": "workflow_failed",
                "execution_id": "exec-001",
                "data": {
                    "success": False,
                    "message": "Pipeline execution failed",
                },
            }

            await handle_pipeline_event(event, session)

            mock_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.FAILED,
                error_message="Pipeline execution failed",
            )
            session.commit.assert_called_once()


# ===========================================================================
# Test 2: Stop pipeline deployment
# ===========================================================================


class TestStopPipelineDeployment:
    """Verify that stop_deployment cancels pipeline execution and updates statuses."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_cancel_execution_called(self, session):
        """cancel_execution must be called with the pipeline_execution_id."""
        comp_deploying = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING)
        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-abc",
            components=[comp_deploying],
        )

        service, _ = _make_service(session)

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.cancel_execution = AsyncMock(return_value={})

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            await service.stop_deployment(deployment.id)

            mock_pipeline_client.cancel_execution.assert_called_once_with("exec-abc")

    @pytest.mark.asyncio
    async def test_deployment_status_set_to_stopped(self, session):
        """Deployment status should become STOPPED after stop_deployment."""
        comp_deploying = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING)
        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-abc",
            components=[comp_deploying],
        )

        service, _ = _make_service(session)

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.cancel_execution = AsyncMock(return_value={})

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            await service.stop_deployment(deployment.id)

            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.STOPPED,
            )

    @pytest.mark.asyncio
    async def test_non_terminal_components_stopped(self, session):
        """DEPLOYING and RUNNING components should become STOPPED; FAILED/STOPPED should not change."""
        comp_deploying = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING)
        comp_running = _make_component("embedder", status=ComponentDeploymentStatus.RUNNING)
        comp_failed = _make_component("vector_db", status=ComponentDeploymentStatus.FAILED)
        comp_stopped = _make_component("reranker", status=ComponentDeploymentStatus.STOPPED)

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-abc",
            components=[comp_deploying, comp_running, comp_failed, comp_stopped],
        )

        service, _ = _make_service(session)

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.cancel_execution = AsyncMock(return_value={})

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            await service.stop_deployment(deployment.id)

            # DEPLOYING and RUNNING components should be set to STOPPED
            update_calls = service.deployment_manager.update_component_deployment_status.call_args_list
            updated_ids = [c[1]["component_id"] for c in update_calls]

            assert comp_deploying.id in updated_ids
            assert comp_running.id in updated_ids
            assert comp_failed.id not in updated_ids
            assert comp_stopped.id not in updated_ids

            for call in update_calls:
                assert call[1]["status"] == ComponentDeploymentStatus.STOPPED


# ===========================================================================
# Test 3: Stop when pipeline already completed
# ===========================================================================


class TestStopPipelineAlreadyCompleted:
    """Verify graceful handling when cancel_execution raises an exception."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_stop_still_updates_status_on_cancel_error(self, session):
        """Deployment should still be STOPPED even if cancel_execution fails."""
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING)
        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-done",
            components=[comp],
        )

        service, _ = _make_service(session)

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.cancel_execution = AsyncMock(side_effect=Exception("Pipeline already completed"))

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            # Should NOT raise
            await service.stop_deployment(deployment.id)

            # Deployment status must still be updated to STOPPED
            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.STOPPED,
            )

    @pytest.mark.asyncio
    async def test_session_commit_called_after_cancel_error(self, session):
        """session.commit() must still be called even when cancel fails."""
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING)
        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-done",
            components=[comp],
        )

        service, _ = _make_service(session)

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.cancel_execution = AsyncMock(side_effect=RuntimeError("Execution not found"))

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            await service.stop_deployment(deployment.id)

            session.commit.assert_called_once()


# ===========================================================================
# Test 4: Stop legacy deployment (no pipeline)
# ===========================================================================


class TestStopLegacyDeployment:
    """Verify the legacy per-job cancellation path when no pipeline_execution_id exists."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_cancel_job_called_for_each_component(self, session):
        """cancel_job should be called for each component with a job_id."""
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        comp1 = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id_1)
        comp2 = _make_component(
            "vector_db",
            component_type="vector_db",
            status=ComponentDeploymentStatus.DEPLOYING,
            job_id=job_id_2,
        )

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp1, comp2],
        )

        mock_budcluster = AsyncMock()
        service, _ = _make_service(session, mock_budcluster)

        with patch.object(service, "_get_deployment", return_value=deployment):
            await service.stop_deployment(deployment.id)

            # Both jobs should have been cancelled
            cancel_calls = mock_budcluster.cancel_job.call_args_list
            cancelled_job_ids = [c[0][0] for c in cancel_calls]
            assert job_id_1 in cancelled_job_ids
            assert job_id_2 in cancelled_job_ids

    @pytest.mark.asyncio
    async def test_cancel_execution_not_called_for_legacy(self, session):
        """cancel_execution must NOT be called when there is no pipeline."""
        job_id = uuid4()
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id)

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp],
        )

        mock_budcluster = AsyncMock()
        service, _ = _make_service(session, mock_budcluster)

        mock_pipeline_client = AsyncMock()

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            await service.stop_deployment(deployment.id)

            mock_pipeline_client.cancel_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_deployment_set_to_stopped(self, session):
        """Legacy deployment status should become STOPPED."""
        job_id = uuid4()
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id)

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp],
        )

        mock_budcluster = AsyncMock()
        service, _ = _make_service(session, mock_budcluster)

        with patch.object(service, "_get_deployment", return_value=deployment):
            await service.stop_deployment(deployment.id)

            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.STOPPED,
            )


# ===========================================================================
# Test 5: Execution cancelled event
# ===========================================================================


class TestExecutionCancelledEvent:
    """Verify execution_cancelled event marks deployment and non-terminal components as STOPPED."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.fixture
    def deployment(self) -> MagicMock:
        comp_running = _make_component("llm", status=ComponentDeploymentStatus.RUNNING)
        comp_deploying = _make_component("embedder", status=ComponentDeploymentStatus.DEPLOYING)
        comp_pending = _make_component("vector_db", status=ComponentDeploymentStatus.PENDING)
        return _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-cancel",
            components=[comp_running, comp_deploying, comp_pending],
        )

    @pytest.mark.asyncio
    async def test_deployment_set_to_stopped(self, session, deployment):
        """Deployment status should become STOPPED on execution_cancelled."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_deployment_status = MagicMock()
            mock_manager.update_component_deployment_status = MagicMock()

            event = {
                "type": "execution_cancelled",
                "execution_id": "exec-cancel",
            }

            await handle_pipeline_event(event, session)

            mock_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.STOPPED,
            )

    @pytest.mark.asyncio
    async def test_deploying_component_stopped(self, session, deployment):
        """DEPLOYING component should transition to STOPPED."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_deployment_status = MagicMock()
            mock_manager.update_component_deployment_status = MagicMock()

            event = {
                "type": "execution_cancelled",
                "execution_id": "exec-cancel",
            }

            await handle_pipeline_event(event, session)

            # The DEPLOYING and PENDING components should be updated to STOPPED
            update_calls = mock_manager.update_component_deployment_status.call_args_list
            updated_ids = [c[1]["component_id"] for c in update_calls]

            # embedder (DEPLOYING) should be stopped
            deploying_comp = deployment.component_deployments[1]
            assert deploying_comp.id in updated_ids

    @pytest.mark.asyncio
    async def test_pending_component_stopped(self, session, deployment):
        """PENDING component should transition to STOPPED."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_deployment_status = MagicMock()
            mock_manager.update_component_deployment_status = MagicMock()

            event = {
                "type": "execution_cancelled",
                "execution_id": "exec-cancel",
            }

            await handle_pipeline_event(event, session)

            update_calls = mock_manager.update_component_deployment_status.call_args_list
            updated_ids = [c[1]["component_id"] for c in update_calls]

            # vector_db (PENDING) should be stopped
            pending_comp = deployment.component_deployments[2]
            assert pending_comp.id in updated_ids

    @pytest.mark.asyncio
    async def test_running_component_preserved(self, session, deployment):
        """RUNNING component should NOT be changed (terminal state preserved)."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_deployment_status = MagicMock()
            mock_manager.update_component_deployment_status = MagicMock()

            event = {
                "type": "execution_cancelled",
                "execution_id": "exec-cancel",
            }

            await handle_pipeline_event(event, session)

            update_calls = mock_manager.update_component_deployment_status.call_args_list
            updated_ids = [c[1]["component_id"] for c in update_calls]

            # llm (RUNNING) should NOT be in the updated list
            running_comp = deployment.component_deployments[0]
            assert running_comp.id not in updated_ids

    @pytest.mark.asyncio
    async def test_only_two_components_updated(self, session, deployment):
        """Exactly two components (DEPLOYING + PENDING) should be updated, not three."""
        manager_cls_path = "budusecases.events.pipeline_listener.DeploymentDataManager"
        with patch(manager_cls_path) as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_deployment_by_pipeline_execution.return_value = deployment
            mock_manager.update_deployment_status = MagicMock()
            mock_manager.update_component_deployment_status = MagicMock()

            event = {
                "type": "execution_cancelled",
                "execution_id": "exec-cancel",
            }

            await handle_pipeline_event(event, session)

            assert mock_manager.update_component_deployment_status.call_count == 2


# ===========================================================================
# Test 6: Sync status uses pipeline path
# ===========================================================================


class TestSyncStatusPipelinePath:
    """Verify sync_deployment_status routes through BudPipelineClient when pipeline_execution_id exists."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_pipeline_client_used_for_sync(self, session):
        """get_execution_progress should be called when pipeline_execution_id is set."""
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING)
        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id="exec-sync-001",
            components=[comp],
        )

        service, mock_budcluster = _make_service(session)

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.get_execution_progress = AsyncMock(
            return_value={
                "execution": {"status": "running"},
                "steps": [],
            }
        )

        with (
            patch.object(service, "_get_deployment", return_value=deployment),
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
        ):
            await service.sync_deployment_status(deployment.id)

            mock_pipeline_client.get_execution_progress.assert_called_once_with("exec-sync-001")
            # Legacy budcluster client should NOT be used
            mock_budcluster.get_job.assert_not_called()


# ===========================================================================
# Test 7: Sync status uses legacy path
# ===========================================================================


class TestSyncStatusLegacyPath:
    """Verify sync_deployment_status uses budcluster_client.get_job when no pipeline_execution_id."""

    @pytest.fixture
    def session(self) -> MagicMock:
        session = MagicMock()
        session.commit = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_budcluster_get_job_called(self, session):
        """get_job should be called for each component with a job_id."""
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        comp1 = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id_1)
        comp2 = _make_component(
            "vector_db",
            component_type="vector_db",
            status=ComponentDeploymentStatus.DEPLOYING,
            job_id=job_id_2,
        )

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp1, comp2],
        )

        mock_budcluster = AsyncMock()
        mock_budcluster.get_job = AsyncMock(
            return_value=JobResponse(
                id=uuid4(),
                name="deploy-component",
                job_type="model_deployment",
                status=JobStatus.COMPLETED,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
        )

        service, _ = _make_service(session, mock_budcluster)

        with patch.object(service, "_get_deployment", return_value=deployment):
            await service.sync_deployment_status(deployment.id)

            # get_job called once per component with a job_id
            assert mock_budcluster.get_job.call_count == 2
            called_job_ids = [c[0][0] for c in mock_budcluster.get_job.call_args_list]
            assert job_id_1 in called_job_ids
            assert job_id_2 in called_job_ids

    @pytest.mark.asyncio
    async def test_component_statuses_updated_from_jobs(self, session):
        """Component statuses should be updated based on job statuses."""
        job_id = uuid4()
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id)

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp],
        )

        mock_budcluster = AsyncMock()
        mock_budcluster.get_job = AsyncMock(
            return_value=JobResponse(
                id=job_id,
                name="deploy-llm",
                job_type="model_deployment",
                status=JobStatus.COMPLETED,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
        )

        service, _ = _make_service(session, mock_budcluster)

        with patch.object(service, "_get_deployment", return_value=deployment):
            await service.sync_deployment_status(deployment.id)

            service.deployment_manager.update_component_deployment_status.assert_called_once_with(
                component_id=comp.id,
                status=ComponentDeploymentStatus.RUNNING,  # COMPLETED job -> RUNNING component
            )

    @pytest.mark.asyncio
    async def test_deployment_marked_running_when_all_complete(self, session):
        """Deployment should be set to RUNNING when all jobs complete."""
        job_id = uuid4()
        comp = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id)

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp],
        )

        mock_budcluster = AsyncMock()
        mock_budcluster.get_job = AsyncMock(
            return_value=JobResponse(
                id=job_id,
                name="deploy-llm",
                job_type="model_deployment",
                status=JobStatus.COMPLETED,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
        )

        service, _ = _make_service(session, mock_budcluster)

        with patch.object(service, "_get_deployment", return_value=deployment):
            await service.sync_deployment_status(deployment.id)

            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.RUNNING,
            )

    @pytest.mark.asyncio
    async def test_deployment_marked_failed_when_any_job_fails(self, session):
        """Deployment should be set to FAILED when any job fails."""
        job_id_ok = uuid4()
        job_id_fail = uuid4()

        comp_ok = _make_component("llm", status=ComponentDeploymentStatus.DEPLOYING, job_id=job_id_ok)
        comp_fail = _make_component(
            "vector_db",
            component_type="vector_db",
            status=ComponentDeploymentStatus.DEPLOYING,
            job_id=job_id_fail,
        )

        deployment = _make_deployment(
            status=DeploymentStatus.DEPLOYING,
            pipeline_execution_id=None,
            components=[comp_ok, comp_fail],
        )

        mock_budcluster = AsyncMock()

        async def _get_job(jid):
            if jid == job_id_ok:
                return JobResponse(
                    id=jid,
                    name="deploy-llm",
                    job_type="model_deployment",
                    status=JobStatus.COMPLETED,
                    cluster_id=uuid4(),
                    config={},
                    created_at="2024-01-01T00:00:00Z",
                    updated_at="2024-01-01T00:00:00Z",
                )
            return JobResponse(
                id=jid,
                name="deploy-vector-db",
                job_type="vector_db_deployment",
                status=JobStatus.FAILED,
                cluster_id=uuid4(),
                config={},
                error_message="Helm install failed",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )

        mock_budcluster.get_job = AsyncMock(side_effect=_get_job)

        service, _ = _make_service(session, mock_budcluster)

        with patch.object(service, "_get_deployment", return_value=deployment):
            await service.sync_deployment_status(deployment.id)

            service.deployment_manager.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.FAILED,
            )
