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

"""Tests for the pipeline event listener.

Covers all event types handled by ``handle_pipeline_event``:
  - step_completed / step_failed  (component status updates)
  - workflow_completed / workflow_failed  (deployment status updates)
  - execution_cancelled  (deployment + component cancellation)
  - Edge cases: unknown execution_id, missing execution_id, non-deploy steps

Events use the NotificationPayload format produced by budpipeline's
EventPublisher, with ``execution_id`` inside the ``payload`` dict.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus
from budusecases.events.pipeline_listener import handle_pipeline_event

# ============================================================================
# Helpers
# ============================================================================


def _make_step_event(
    execution_id: str,
    step_name: str,
    status: str = "COMPLETED",
    result: dict | None = None,
    error_message: str | None = None,
) -> dict:
    """Build a NotificationPayload-format step event."""
    message = f"Step '{step_name}' completed" if status == "COMPLETED" else f"Step '{step_name}' failed"
    if error_message:
        message = error_message
    content: dict = {
        "title": step_name,
        "message": message,
        "status": status,
    }
    if result is not None:
        content["result"] = result
    return {
        "notification_type": "event",
        "name": "bud-notification",
        "payload": {
            "category": "internal",
            "type": "usecase_deployment",
            "event": step_name,
            "workflow_id": str(uuid4()),
            "execution_id": execution_id,
            "source": "budpipeline",
            "content": content,
        },
    }


def _make_workflow_event(
    execution_id: str,
    status: str = "COMPLETED",
    success: bool | None = None,
    error_message: str | None = None,
) -> dict:
    """Build a NotificationPayload-format workflow completion event."""
    message = (
        "Pipeline execution completed" if status == "COMPLETED" else (error_message or "Pipeline execution failed")
    )
    content: dict = {
        "title": "Pipeline Execution",
        "message": message,
        "status": status,
    }
    result_data: dict = {}
    if success is not None:
        result_data["success"] = success
    if result_data:
        content["result"] = result_data
    return {
        "notification_type": "event",
        "name": "bud-notification",
        "payload": {
            "category": "internal",
            "type": "usecase_deployment",
            "event": "results",
            "workflow_id": str(uuid4()),
            "execution_id": execution_id,
            "source": "budpipeline",
            "content": content,
        },
    }


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock database session with commit support."""
    session = MagicMock()
    session.commit = MagicMock()
    return session


@pytest.fixture
def comp_llm() -> MagicMock:
    """Create a mock LLM component deployment."""
    comp = MagicMock()
    comp.id = uuid4()
    comp.component_name = "llm"
    comp.status = ComponentDeploymentStatus.DEPLOYING
    return comp


@pytest.fixture
def comp_vector_db() -> MagicMock:
    """Create a mock vector_db component deployment."""
    comp = MagicMock()
    comp.id = uuid4()
    comp.component_name = "vector_db"
    comp.status = ComponentDeploymentStatus.DEPLOYING
    return comp


@pytest.fixture
def mock_deployment(comp_llm: MagicMock, comp_vector_db: MagicMock) -> MagicMock:
    """Create a mock deployment with two component_deployments (llm, vector_db)."""
    deployment = MagicMock()
    deployment.id = uuid4()
    deployment.status = DeploymentStatus.DEPLOYING
    deployment.component_deployments = [comp_llm, comp_vector_db]
    return deployment


# ============================================================================
# Step completed -> component RUNNING
# ============================================================================


class TestStepCompleted:
    """Tests for step_completed events."""

    async def test_step_completed_sets_component_running(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        comp_llm: MagicMock,
    ) -> None:
        """step_completed for 'deploy_llm' should update LLM component to RUNNING."""
        execution_id = str(uuid4())
        event_data = _make_step_event(execution_id, "deploy_llm", status="COMPLETED")

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_called_once_with(
                component_id=comp_llm.id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=None,
                error_message=None,
            )
            mock_session.commit.assert_called_once()

    async def test_step_completed_stores_job_id(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        comp_llm: MagicMock,
    ) -> None:
        """step_completed with job_id in outputs should call update_component_deployment_job."""
        execution_id = str(uuid4())
        job_id = uuid4()
        event_data = _make_step_event(
            execution_id,
            "deploy_llm",
            status="COMPLETED",
            result={"job_id": str(job_id)},
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_job.assert_called_once_with(
                component_id=comp_llm.id,
                job_id=job_id,
            )

    async def test_step_completed_stores_endpoint_url(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        comp_llm: MagicMock,
    ) -> None:
        """step_completed with endpoint_url in outputs should pass it to status update."""
        execution_id = str(uuid4())
        endpoint_url = "https://llm.example.com/v1"
        event_data = _make_step_event(
            execution_id,
            "deploy_llm",
            status="COMPLETED",
            result={"endpoint_url": endpoint_url},
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_called_once_with(
                component_id=comp_llm.id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=endpoint_url,
                error_message=None,
            )

    async def test_step_completed_stores_both_job_id_and_endpoint_url(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        comp_llm: MagicMock,
    ) -> None:
        """step_completed with both job_id and endpoint_url should update both."""
        execution_id = str(uuid4())
        job_id = uuid4()
        endpoint_url = "https://llm.example.com/v1"
        event_data = _make_step_event(
            execution_id,
            "deploy_llm",
            status="COMPLETED",
            result={"job_id": str(job_id), "endpoint_url": endpoint_url},
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_called_once_with(
                component_id=comp_llm.id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=endpoint_url,
                error_message=None,
            )
            manager_instance.update_component_deployment_job.assert_called_once_with(
                component_id=comp_llm.id,
                job_id=job_id,
            )

    async def test_step_completed_invalid_job_id_does_not_crash(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """step_completed with an invalid (non-UUID) job_id should log warning, not crash."""
        execution_id = str(uuid4())
        event_data = _make_step_event(
            execution_id,
            "deploy_llm",
            status="COMPLETED",
            result={"job_id": "not-a-valid-uuid"},
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            # Should not raise
            await handle_pipeline_event(event_data, mock_session)

            # update_component_deployment_job should NOT have been called
            manager_instance.update_component_deployment_job.assert_not_called()
            # But status update should still have been called
            manager_instance.update_component_deployment_status.assert_called_once()


# ============================================================================
# Step failed -> component FAILED
# ============================================================================


class TestStepFailed:
    """Tests for step_failed events."""

    async def test_step_failed_sets_component_failed(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
        comp_vector_db: MagicMock,
    ) -> None:
        """step_failed for 'deploy_vector_db' should set vector_db component to FAILED."""
        execution_id = str(uuid4())
        error_msg = "Qdrant pod crashed: OOMKilled"
        event_data = _make_step_event(
            execution_id,
            "deploy_vector_db",
            status="FAILED",
            error_message=error_msg,
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_called_once_with(
                component_id=comp_vector_db.id,
                status=ComponentDeploymentStatus.FAILED,
                endpoint_url=None,
                error_message=error_msg,
            )
            mock_session.commit.assert_called_once()


# ============================================================================
# Execution completed (workflow_completed / workflow_failed)
# ============================================================================


class TestExecutionCompleted:
    """Tests for workflow_completed and workflow_failed events."""

    async def test_workflow_completed_sets_deployment_running(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """workflow_completed should set the deployment status to RUNNING."""
        execution_id = str(uuid4())
        event_data = _make_workflow_event(execution_id, status="COMPLETED", success=True)

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.RUNNING,
                error_message=None,
            )
            mock_session.commit.assert_called_once()

    async def test_workflow_completed_implicit_success(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """workflow_completed without explicit 'success' field defaults to True."""
        execution_id = str(uuid4())
        event_data = _make_workflow_event(execution_id, status="COMPLETED")

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.RUNNING,
                error_message=None,
            )

    async def test_workflow_failed_sets_deployment_failed(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """workflow_failed should set the deployment status to FAILED with an error message."""
        execution_id = str(uuid4())
        error_msg = "Pipeline execution timed out"
        event_data = _make_workflow_event(
            execution_id,
            status="FAILED",
            success=False,
            error_message=error_msg,
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.FAILED,
                error_message=error_msg,
            )
            mock_session.commit.assert_called_once()

    async def test_workflow_failed_implicit_failure(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """workflow_failed without explicit 'success' field defaults to False."""
        execution_id = str(uuid4())
        error_msg = "Some failure"
        event_data = _make_workflow_event(
            execution_id,
            status="FAILED",
            error_message=error_msg,
        )

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.FAILED,
                error_message=error_msg,
            )


# ============================================================================
# Execution cancelled
# ============================================================================


class TestExecutionCancelled:
    """Tests for execution_cancelled events."""

    async def test_execution_cancelled_sets_deployment_stopped(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """execution_cancelled should set the deployment to STOPPED."""
        execution_id = str(uuid4())
        # execution_cancelled uses the old flat format (from Dapr workflow engine, not EventPublisher)
        event_data = {
            "type": "execution_cancelled",
            "payload": {
                "execution_id": execution_id,
            },
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.STOPPED,
            )
            mock_session.commit.assert_called_once()

    async def test_execution_cancelled_stops_non_terminal_components(
        self,
        mock_session: MagicMock,
    ) -> None:
        """execution_cancelled should set DEPLOYING components to STOPPED, skip terminal ones."""
        deploying_comp = MagicMock()
        deploying_comp.id = uuid4()
        deploying_comp.component_name = "llm"
        deploying_comp.status = ComponentDeploymentStatus.DEPLOYING

        pending_comp = MagicMock()
        pending_comp.id = uuid4()
        pending_comp.component_name = "embedder"
        pending_comp.status = ComponentDeploymentStatus.PENDING

        running_comp = MagicMock()
        running_comp.id = uuid4()
        running_comp.component_name = "vector_db"
        running_comp.status = ComponentDeploymentStatus.RUNNING

        failed_comp = MagicMock()
        failed_comp.id = uuid4()
        failed_comp.component_name = "reranker"
        failed_comp.status = ComponentDeploymentStatus.FAILED

        deployment = MagicMock()
        deployment.id = uuid4()
        deployment.status = DeploymentStatus.DEPLOYING
        deployment.component_deployments = [deploying_comp, pending_comp, running_comp, failed_comp]

        execution_id = str(uuid4())
        event_data = {
            "type": "execution_cancelled",
            "payload": {
                "execution_id": execution_id,
            },
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = deployment

            await handle_pipeline_event(event_data, mock_session)

            # Deployment itself should be STOPPED
            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=deployment.id,
                status=DeploymentStatus.STOPPED,
            )

            # Non-terminal components (DEPLOYING, PENDING) should be set to STOPPED
            # Terminal components (RUNNING, FAILED, STOPPED) should NOT be updated
            component_status_calls = manager_instance.update_component_deployment_status.call_args_list
            updated_component_ids = {call.kwargs["component_id"] for call in component_status_calls}

            assert deploying_comp.id in updated_component_ids
            assert pending_comp.id in updated_component_ids
            assert running_comp.id not in updated_component_ids
            assert failed_comp.id not in updated_component_ids

            # All updated components should have been set to STOPPED
            for call in component_status_calls:
                assert call.kwargs["status"] == ComponentDeploymentStatus.STOPPED

    async def test_execution_cancelled_already_stopped_component_not_updated(
        self,
        mock_session: MagicMock,
    ) -> None:
        """execution_cancelled should skip components already in STOPPED status."""
        stopped_comp = MagicMock()
        stopped_comp.id = uuid4()
        stopped_comp.component_name = "llm"
        stopped_comp.status = ComponentDeploymentStatus.STOPPED

        deployment = MagicMock()
        deployment.id = uuid4()
        deployment.status = DeploymentStatus.DEPLOYING
        deployment.component_deployments = [stopped_comp]

        execution_id = str(uuid4())
        event_data = {
            "type": "execution_cancelled",
            "payload": {
                "execution_id": execution_id,
            },
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_not_called()


# ============================================================================
# Edge cases: unknown execution_id, missing execution_id, non-deploy steps
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and graceful error handling."""

    async def test_unknown_execution_id_no_error(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Event with unknown execution_id should be handled gracefully (no crash)."""
        event_data = _make_step_event(str(uuid4()), "deploy_llm", status="COMPLETED")

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = None

            # Should not raise
            await handle_pipeline_event(event_data, mock_session)

            # No status updates should have been made
            manager_instance.update_component_deployment_status.assert_not_called()
            manager_instance.update_deployment_status.assert_not_called()
            # Commit should NOT be called when deployment is not found
            mock_session.commit.assert_not_called()

    async def test_missing_execution_id_no_error(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Event without execution_id field should be handled gracefully."""
        event_data = {
            "notification_type": "event",
            "payload": {
                "event": "deploy_llm",
                "content": {"status": "COMPLETED"},
            },
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            # Should not raise
            await handle_pipeline_event(event_data, mock_session)

            # DeploymentDataManager should not even be queried
            MockManager.return_value.get_deployment_by_pipeline_execution.assert_not_called()
            mock_session.commit.assert_not_called()

    async def test_non_deploy_step_skipped(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """step_completed for 'cluster_health' (non-deploy step) should not update any component."""
        execution_id = str(uuid4())
        event_data = _make_step_event(execution_id, "cluster_health", status="COMPLETED")

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_not_called()
            manager_instance.update_component_deployment_job.assert_not_called()
            # Commit is still called (at the end of handle_pipeline_event)
            mock_session.commit.assert_called_once()

    async def test_notify_complete_step_skipped(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """step_completed for 'notify_complete' should not update any component."""
        execution_id = str(uuid4())
        event_data = _make_step_event(execution_id, "notify_complete", status="COMPLETED")

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_not_called()

    async def test_deploy_step_unknown_component_no_crash(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """step_completed for 'deploy_reranker' with no matching component should not crash."""
        execution_id = str(uuid4())
        event_data = _make_step_event(execution_id, "deploy_reranker", status="COMPLETED")

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            # Should not raise
            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_not_called()
            # Commit still called at end of handle_pipeline_event
            mock_session.commit.assert_called_once()

    async def test_unhandled_event_type_ignored(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """An event with unrecognized status/event combo should be silently ignored."""
        execution_id = str(uuid4())
        event_data = {
            "notification_type": "event",
            "payload": {
                "event": "progress",
                "execution_id": execution_id,
                "content": {"status": "RUNNING", "message": "Progress: 50%"},
            },
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.update_component_deployment_status.assert_not_called()
            manager_instance.update_deployment_status.assert_not_called()
            # Commit still called
            mock_session.commit.assert_called_once()

    async def test_empty_event_data_no_crash(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Completely empty event_data should not crash."""
        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            await handle_pipeline_event({}, mock_session)

            MockManager.return_value.get_deployment_by_pipeline_execution.assert_not_called()
            mock_session.commit.assert_not_called()


# ============================================================================
# Event layout variations (nested vs flat)
# ============================================================================


class TestEventLayoutVariations:
    """Tests for different event payload layouts."""

    async def test_execution_id_in_payload(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """execution_id nested inside 'payload' should be found (primary path)."""
        execution_id = str(uuid4())
        event_data = _make_workflow_event(execution_id, status="COMPLETED", success=True)

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.get_deployment_by_pipeline_execution.assert_called_once_with(execution_id)
            manager_instance.update_deployment_status.assert_called_once_with(
                deployment_id=mock_deployment.id,
                status=DeploymentStatus.RUNNING,
                error_message=None,
            )

    async def test_execution_id_at_top_level_fallback(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """execution_id at top level should still be found (fallback path)."""
        execution_id = str(uuid4())
        event_data = {
            "type": "execution_cancelled",
            "execution_id": execution_id,
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            manager_instance.get_deployment_by_pipeline_execution.assert_called_once_with(execution_id)

    async def test_missing_type_field_still_commits(
        self,
        mock_session: MagicMock,
        mock_deployment: MagicMock,
    ) -> None:
        """Event with execution_id but no recognizable event type should still commit."""
        execution_id = str(uuid4())
        event_data = {
            "payload": {
                "execution_id": execution_id,
            },
        }

        with patch("budusecases.events.pipeline_listener.DeploymentDataManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.get_deployment_by_pipeline_execution.return_value = mock_deployment

            await handle_pipeline_event(event_data, mock_session)

            # No handler matched, but commit should still be called
            manager_instance.update_deployment_status.assert_not_called()
            manager_instance.update_component_deployment_status.assert_not_called()
            mock_session.commit.assert_called_once()
