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

"""Integration tests for mixed model + helm deployment via pipeline.

These tests verify the full flow when a BudUseCases template contains both
model-type components (vector_db, llm) and helm-type components
(agent_runtime).  The test suite exercises:

1. DAG structure with correct action types per component type
2. Helm chart configuration propagation (chart_ref, chart_version, values)
3. Sequential step completion processing with mixed component types
4. Helm component failure propagation
5. Component selections reflected in DAG step params
"""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from budusecases.deployments.dag_builder import build_deployment_dag
from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus
from budusecases.events.pipeline_listener import handle_pipeline_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ids() -> tuple[str, str, str, str]:
    """Return (deployment_id, deployment_name, cluster_id, user_id)."""
    return str(uuid4()), "mixed-deployment", str(uuid4()), str(uuid4())


def _step_names(dag: dict[str, Any]) -> list[str]:
    """Extract ordered step names from a DAG dict."""
    return [s["name"] for s in dag["steps"]]


def _step_by_name(dag: dict[str, Any], name: str) -> dict[str, Any]:
    """Find a step dict by name.  Raises ValueError if not found."""
    for step in dag["steps"]:
        if step["name"] == name:
            return step
    raise ValueError(f"Step {name!r} not found in DAG")


def _make_mixed_template() -> dict[str, Any]:
    """Build a template with vector_db (vector_db), llm (model), and
    agent_runtime (helm) components.
    """
    return {
        "components": [
            {
                "name": "vector_db",
                "type": "vector_db",
                "required": True,
                "default_component": "qdrant",
            },
            {
                "name": "llm",
                "type": "model",
                "required": True,
                "default_component": "llama-3-8b",
            },
            {
                "name": "agent_runtime",
                "type": "helm",
                "required": True,
                "chart": {
                    "ref": "oci://registry.example.com/agent-chart",
                    "version": "1.0.0",
                    "values": {
                        "llm_endpoint": "{{ steps.deploy_llm.outputs.endpoint_url }}",
                    },
                },
            },
        ],
        "deployment_order": ["vector_db", "llm", "agent_runtime"],
    }


def _make_mock_deployment(
    deployment_id: str,
    execution_id: str,
    component_specs: list[tuple[str, str]],
    deployment_status: DeploymentStatus = DeploymentStatus.DEPLOYING,
    component_status: ComponentDeploymentStatus = ComponentDeploymentStatus.DEPLOYING,
) -> MagicMock:
    """Build a mock UseCaseDeployment with ComponentDeployment children.

    Args:
        deployment_id: UUID string for the deployment.
        execution_id: Pipeline execution ID.
        component_specs: List of (component_name, component_type) tuples.
        deployment_status: Initial deployment status.
        component_status: Initial status for all component deployments.

    Returns:
        A MagicMock resembling a UseCaseDeployment with component_deployments.
    """
    components = []
    for comp_name, comp_type in component_specs:
        comp = MagicMock()
        comp.id = uuid4()
        comp.component_name = comp_name
        comp.component_type = comp_type
        comp.status = component_status
        comp.selected_component = f"selected-{comp_name}"
        comp.endpoint_url = None
        comp.error_message = None
        comp.job_id = None
        components.append(comp)

    deployment = MagicMock()
    deployment.id = deployment_id
    deployment.status = deployment_status
    deployment.pipeline_execution_id = execution_id
    deployment.component_deployments = components
    return deployment


def _make_mock_manager(deployment: MagicMock) -> MagicMock:
    """Build a mock DeploymentDataManager that returns the given deployment."""
    manager = MagicMock()
    manager.get_deployment_by_pipeline_execution.return_value = deployment
    manager.update_component_deployment_status.return_value = None
    manager.update_component_deployment_job.return_value = None
    manager.update_deployment_status.return_value = None
    return manager


# ============================================================================
# Test 1: Mixed DAG structure with correct action types
# ============================================================================


class TestMixedDagStructure:
    """Verify that a template with vector_db, model, and helm components
    produces a DAG with the correct action types and dependency chain.
    """

    def test_dag_step_order_and_actions(self) -> None:
        """Steps are ordered: cluster_health -> deploy_vector_db ->
        deploy_llm -> deploy_agent_runtime -> notify_complete,
        with correct actions for each.
        """
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        expected_order = [
            "cluster_health",
            "deploy_vector_db",
            "deploy_llm",
            "deploy_agent_runtime",
            "notify_complete",
        ]
        assert _step_names(dag) == expected_order

    def test_deploy_vector_db_action_and_dependency(self) -> None:
        """deploy_vector_db uses deployment_create and depends on cluster_health."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        step = _step_by_name(dag, "deploy_vector_db")
        assert step["action"] == "deployment_create"
        assert step["depends_on"] == ["cluster_health"]

    def test_deploy_llm_action_and_dependency(self) -> None:
        """deploy_llm uses deployment_create and depends on deploy_vector_db."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        step = _step_by_name(dag, "deploy_llm")
        assert step["action"] == "deployment_create"
        assert step["depends_on"] == ["deploy_vector_db"]

    def test_deploy_agent_runtime_action_and_dependency(self) -> None:
        """deploy_agent_runtime uses helm_deploy and depends on deploy_llm."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        step = _step_by_name(dag, "deploy_agent_runtime")
        assert step["action"] == "helm_deploy"
        assert step["depends_on"] == ["deploy_llm"]

    def test_helm_step_chart_params(self) -> None:
        """deploy_agent_runtime params include chart_ref and chart_version
        from the template.
        """
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        step = _step_by_name(dag, "deploy_agent_runtime")
        assert step["params"]["chart_ref"] == "oci://registry.example.com/agent-chart"
        assert step["params"]["chart_version"] == "1.0.0"

    def test_jinja2_references_preserved_in_mixed_dag(self) -> None:
        """Jinja2 step-reference expressions in helm values are preserved
        (not resolved at DAG build time).
        """
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        step = _step_by_name(dag, "deploy_agent_runtime")
        assert step["params"]["values"]["llm_endpoint"] == "{{ steps.deploy_llm.outputs.endpoint_url }}"

    def test_notify_complete_depends_on_last_deploy(self) -> None:
        """notify_complete depends on the last deploy step (deploy_agent_runtime)."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        notify_step = _step_by_name(dag, "notify_complete")
        assert notify_step["depends_on"] == ["deploy_agent_runtime"]


# ============================================================================
# Test 2: Mixed deployment with helm chart config
# ============================================================================


class TestHelmChartConfigInMixedDag:
    """Verify that helm chart configuration (ref, version, values with Jinja2
    references) is correctly propagated into the DAG step params.
    """

    def test_chart_ref_in_params(self) -> None:
        """Helm step params include chart_ref matching the template chart ref."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-chart",
                        "version": "1.0.0",
                        "values": {
                            "llm_endpoint": "{{ steps.deploy_llm.outputs.endpoint_url }}",
                        },
                    },
                },
            ],
            "deployment_order": ["llm", "agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        helm_step = _step_by_name(dag, "deploy_agent_runtime")
        assert helm_step["params"]["chart_ref"] == "oci://registry.example.com/agent-chart"

    def test_chart_version_in_params(self) -> None:
        """Helm step params include chart_version from the template."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-chart",
                        "version": "1.0.0",
                        "values": {
                            "llm_endpoint": "{{ steps.deploy_llm.outputs.endpoint_url }}",
                        },
                    },
                },
            ],
            "deployment_order": ["llm", "agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        helm_step = _step_by_name(dag, "deploy_agent_runtime")
        assert helm_step["params"]["chart_version"] == "1.0.0"

    def test_jinja2_values_unchanged(self) -> None:
        """Jinja2 step-reference values in helm chart are kept verbatim."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        jinja_ref = "{{ steps.deploy_llm.outputs.endpoint_url }}"

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-chart",
                        "version": "1.0.0",
                        "values": {
                            "llm_endpoint": jinja_ref,
                        },
                    },
                },
            ],
            "deployment_order": ["llm", "agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
            parameters={},
        )

        helm_step = _step_by_name(dag, "deploy_agent_runtime")
        assert helm_step["params"]["values"]["llm_endpoint"] == jinja_ref


# ============================================================================
# Test 3: Sequential step completion with mixed types
# ============================================================================


class TestSequentialStepCompletion:
    """Process step_completed events in order for each deploy step and
    verify that each component transitions to RUNNING, then
    execution_completed sets the deployment to RUNNING.
    """

    @pytest.mark.asyncio
    async def test_step_completed_transitions_components_to_running(self) -> None:
        """Process step_completed for each deploy step in order.  After all
        three, process workflow_completed and verify deployment is RUNNING.
        """
        deployment_id = str(uuid4())
        execution_id = str(uuid4())

        deployment = _make_mock_deployment(
            deployment_id=deployment_id,
            execution_id=execution_id,
            component_specs=[
                ("vector_db", "vector_db"),
                ("llm", "model"),
                ("agent_runtime", "helm"),
            ],
        )

        mock_manager = _make_mock_manager(deployment)
        mock_session = MagicMock()

        with patch(
            "budusecases.events.pipeline_listener.DeploymentDataManager",
            return_value=mock_manager,
        ):
            # Step 1: deploy_vector_db completed
            await handle_pipeline_event(
                {
                    "type": "step_completed",
                    "execution_id": execution_id,
                    "data": {"step_name": "deploy_vector_db"},
                },
                session=mock_session,
            )

            # The handler should update vector_db component to RUNNING
            mock_manager.update_component_deployment_status.assert_called_with(
                component_id=deployment.component_deployments[0].id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=None,
                error_message=None,
            )
            mock_manager.update_component_deployment_status.reset_mock()

            # Step 2: deploy_llm completed
            await handle_pipeline_event(
                {
                    "type": "step_completed",
                    "execution_id": execution_id,
                    "data": {"step_name": "deploy_llm"},
                },
                session=mock_session,
            )

            mock_manager.update_component_deployment_status.assert_called_with(
                component_id=deployment.component_deployments[1].id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=None,
                error_message=None,
            )
            mock_manager.update_component_deployment_status.reset_mock()

            # Step 3: deploy_agent_runtime completed (helm type)
            await handle_pipeline_event(
                {
                    "type": "step_completed",
                    "execution_id": execution_id,
                    "data": {"step_name": "deploy_agent_runtime"},
                },
                session=mock_session,
            )

            mock_manager.update_component_deployment_status.assert_called_with(
                component_id=deployment.component_deployments[2].id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url=None,
                error_message=None,
            )
            mock_manager.update_component_deployment_status.reset_mock()

            # Step 4: workflow_completed
            await handle_pipeline_event(
                {
                    "type": "workflow_completed",
                    "execution_id": execution_id,
                    "data": {"success": True},
                },
                session=mock_session,
            )

            mock_manager.update_deployment_status.assert_called_with(
                deployment_id=deployment_id,
                status=DeploymentStatus.RUNNING,
                error_message=None,
            )

    @pytest.mark.asyncio
    async def test_step_completed_with_endpoint_url(self) -> None:
        """step_completed event with endpoint_url in outputs propagates to
        the component deployment.
        """
        deployment_id = str(uuid4())
        execution_id = str(uuid4())

        deployment = _make_mock_deployment(
            deployment_id=deployment_id,
            execution_id=execution_id,
            component_specs=[
                ("vector_db", "vector_db"),
                ("llm", "model"),
                ("agent_runtime", "helm"),
            ],
        )

        mock_manager = _make_mock_manager(deployment)
        mock_session = MagicMock()

        with patch(
            "budusecases.events.pipeline_listener.DeploymentDataManager",
            return_value=mock_manager,
        ):
            await handle_pipeline_event(
                {
                    "type": "step_completed",
                    "execution_id": execution_id,
                    "data": {
                        "step_name": "deploy_llm",
                        "outputs": {
                            "endpoint_url": "https://cluster.example.com/llm",
                        },
                    },
                },
                session=mock_session,
            )

            mock_manager.update_component_deployment_status.assert_called_with(
                component_id=deployment.component_deployments[1].id,
                status=ComponentDeploymentStatus.RUNNING,
                endpoint_url="https://cluster.example.com/llm",
                error_message=None,
            )


# ============================================================================
# Test 4: Helm component failure stops pipeline
# ============================================================================


class TestHelmComponentFailure:
    """Verify that a step_failed event for the helm component correctly
    marks the component as FAILED, and a subsequent workflow_failed marks
    the overall deployment as FAILED.
    """

    @pytest.mark.asyncio
    async def test_helm_step_failed_marks_component_failed(self) -> None:
        """step_failed for deploy_agent_runtime sets agent_runtime to FAILED."""
        deployment_id = str(uuid4())
        execution_id = str(uuid4())

        deployment = _make_mock_deployment(
            deployment_id=deployment_id,
            execution_id=execution_id,
            component_specs=[
                ("vector_db", "vector_db"),
                ("llm", "model"),
                ("agent_runtime", "helm"),
            ],
        )

        mock_manager = _make_mock_manager(deployment)
        mock_session = MagicMock()

        with patch(
            "budusecases.events.pipeline_listener.DeploymentDataManager",
            return_value=mock_manager,
        ):
            await handle_pipeline_event(
                {
                    "type": "step_failed",
                    "execution_id": execution_id,
                    "data": {
                        "step_name": "deploy_agent_runtime",
                        "error_message": "Helm chart install timed out",
                    },
                },
                session=mock_session,
            )

            mock_manager.update_component_deployment_status.assert_called_with(
                component_id=deployment.component_deployments[2].id,
                status=ComponentDeploymentStatus.FAILED,
                endpoint_url=None,
                error_message="Helm chart install timed out",
            )

    @pytest.mark.asyncio
    async def test_workflow_failed_marks_deployment_failed(self) -> None:
        """workflow_failed after helm step failure sets deployment to FAILED."""
        deployment_id = str(uuid4())
        execution_id = str(uuid4())

        deployment = _make_mock_deployment(
            deployment_id=deployment_id,
            execution_id=execution_id,
            component_specs=[
                ("vector_db", "vector_db"),
                ("llm", "model"),
                ("agent_runtime", "helm"),
            ],
        )

        mock_manager = _make_mock_manager(deployment)
        mock_session = MagicMock()

        with patch(
            "budusecases.events.pipeline_listener.DeploymentDataManager",
            return_value=mock_manager,
        ):
            await handle_pipeline_event(
                {
                    "type": "workflow_failed",
                    "execution_id": execution_id,
                    "data": {
                        "success": False,
                        "message": "Step deploy_agent_runtime failed",
                    },
                },
                session=mock_session,
            )

            mock_manager.update_deployment_status.assert_called_with(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                error_message="Step deploy_agent_runtime failed",
            )

    @pytest.mark.asyncio
    async def test_model_step_failure_also_handled(self) -> None:
        """step_failed for a model step (deploy_llm) sets llm to FAILED."""
        deployment_id = str(uuid4())
        execution_id = str(uuid4())

        deployment = _make_mock_deployment(
            deployment_id=deployment_id,
            execution_id=execution_id,
            component_specs=[
                ("vector_db", "vector_db"),
                ("llm", "model"),
                ("agent_runtime", "helm"),
            ],
        )

        mock_manager = _make_mock_manager(deployment)
        mock_session = MagicMock()

        with patch(
            "budusecases.events.pipeline_listener.DeploymentDataManager",
            return_value=mock_manager,
        ):
            await handle_pipeline_event(
                {
                    "type": "step_failed",
                    "execution_id": execution_id,
                    "data": {
                        "step_name": "deploy_llm",
                        "error": "Model download failed",
                    },
                },
                session=mock_session,
            )

            mock_manager.update_component_deployment_status.assert_called_with(
                component_id=deployment.component_deployments[1].id,
                status=ComponentDeploymentStatus.FAILED,
                endpoint_url=None,
                error_message="Model download failed",
            )


# ============================================================================
# Test 5: Component selections in DAG
# ============================================================================


class TestComponentSelectionsInDag:
    """Verify that user-provided component selections are reflected in the
    DAG step params (model_id for model/vector_db steps).
    """

    def test_selected_components_in_model_step_params(self) -> None:
        """DAG step params include the selected component names as model_id."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        vector_db_step = _step_by_name(dag, "deploy_vector_db")
        assert vector_db_step["params"]["model_id"] == "qdrant"

        llm_step = _step_by_name(dag, "deploy_llm")
        assert llm_step["params"]["model_id"] == "llama-3-8b"

    def test_different_selections_reflected(self) -> None:
        """Changing component selections changes the corresponding model_id."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "milvus",
                "llm": "mistral-7b",
                "agent_runtime": "agent-runtime-v2",
            },
        )

        vector_db_step = _step_by_name(dag, "deploy_vector_db")
        assert vector_db_step["params"]["model_id"] == "milvus"

        llm_step = _step_by_name(dag, "deploy_llm")
        assert llm_step["params"]["model_id"] == "mistral-7b"

    def test_default_component_used_when_not_selected(self) -> None:
        """When a component is not in selections, the default_component
        from the template is used.
        """
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        # Only select llm, not vector_db -- vector_db should use "qdrant" default
        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        vector_db_step = _step_by_name(dag, "deploy_vector_db")
        assert vector_db_step["params"]["model_id"] == "qdrant"

    def test_helm_step_not_affected_by_selection(self) -> None:
        """Helm steps use chart_ref from the template config, not model_id.
        The component selection is not placed in model_id for helm steps.
        """
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()
        template = _make_mixed_template()

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        helm_step = _step_by_name(dag, "deploy_agent_runtime")
        # Helm steps should NOT have model_id; they have chart_ref instead
        assert "model_id" not in helm_step["params"]
        assert "chart_ref" in helm_step["params"]
