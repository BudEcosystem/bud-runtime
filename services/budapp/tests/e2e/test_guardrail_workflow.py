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

"""End-to-end tests for guardrail deployment workflow.

Tests complete workflow scenarios including provider selection,
probe selection, model status derivation, skip logic, and rollback.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from budapp.commons.constants import (
    EndpointStatusEnum,
    GuardrailDeploymentStatusEnum,
    GuardrailStatusEnum,
    WorkflowStatusEnum,
)
from budapp.guardrails.schemas import (
    GuardrailProfileProbeSelection,
    GuardrailProfileRuleSelection,
    ModelDeploymentStatus,
)


class TestWorkflowModelStatusDerivation:
    """Tests for model status derivation in the workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.fixture
    def mock_probe_with_rules(self):
        """Create mock probe with rules."""
        rule1 = Mock()
        rule1.id = uuid4()
        rule1.name = "Rule 1"
        rule1.model_uri = "org/model-1"
        rule1.model_id = None  # Not onboarded

        rule2 = Mock()
        rule2.id = uuid4()
        rule2.name = "Rule 2"
        rule2.model_uri = "org/model-2"
        rule2.model_id = uuid4()  # Onboarded

        probe = Mock()
        probe.id = uuid4()
        probe.name = "Test Probe"
        probe.rules = [rule1, rule2]

        return probe

    @pytest.mark.asyncio
    async def test_derive_model_statuses_mixed_states(self, service, mock_probe_with_rules):
        """Test deriving model statuses with mixed onboarding states."""
        probe_selections = [GuardrailProfileProbeSelection(id=mock_probe_with_rules.id, rules=None)]

        with patch("budapp.guardrails.services.GuardrailsProbeRulesDataManager") as MockDataManager:
            mock_dm = AsyncMock()
            mock_dm.get_probes_with_rules = AsyncMock(return_value=[mock_probe_with_rules])
            MockDataManager.return_value = mock_dm

            # Mock endpoint query for onboarded model (model 2)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []  # No endpoints
            service.session.execute = AsyncMock(return_value=mock_result)

            result = await service.derive_model_statuses(probe_selections, project_id=None)

            assert result.total_models == 2
            assert result.models_requiring_onboarding == 1  # model-1
            assert result.models_reusable == 0
            # Skip to step should be None since models need onboarding
            assert result.skip_to_step is None
            assert result.credential_required is True

    @pytest.mark.asyncio
    async def test_derive_model_statuses_all_deployed(self, service):
        """Test skip logic when all models are already deployed."""
        probe_id = uuid4()
        rule_id = uuid4()
        model_id = uuid4()
        endpoint_id = uuid4()

        # Mock rule with onboarded and deployed model
        rule = Mock()
        rule.id = rule_id
        rule.name = "Deployed Rule"
        rule.model_uri = "org/deployed-model"
        rule.model_id = model_id

        probe = Mock()
        probe.id = probe_id
        probe.name = "Test Probe"
        probe.rules = [rule]

        probe_selections = [GuardrailProfileProbeSelection(id=probe_id, rules=None)]

        with patch("budapp.guardrails.services.GuardrailsProbeRulesDataManager") as MockDataManager:
            mock_dm = AsyncMock()
            mock_dm.get_probes_with_rules = AsyncMock(return_value=[probe])
            MockDataManager.return_value = mock_dm

            # Mock running endpoint
            mock_endpoint = Mock()
            mock_endpoint.id = endpoint_id
            mock_endpoint.name = "running-endpoint"
            mock_endpoint.endpoint = "http://localhost:8000"
            mock_endpoint.status = EndpointStatusEnum.RUNNING
            mock_endpoint.cluster_id = uuid4()
            mock_endpoint.cluster = Mock(name="test-cluster")

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_endpoint]
            service.session.execute = AsyncMock(return_value=mock_result)

            result = await service.derive_model_statuses(probe_selections, project_id=None)

            assert result.total_models == 1
            assert result.models_requiring_onboarding == 0
            assert result.models_requiring_deployment == 0
            assert result.models_reusable == 1
            # Should skip to step 12 (profile configuration)
            assert result.skip_to_step == 12
            assert result.credential_required is False

    @pytest.mark.asyncio
    async def test_derive_model_statuses_all_onboarded(self, service):
        """Test skip logic when all models are onboarded but not deployed."""
        probe_id = uuid4()
        rule_id = uuid4()
        model_id = uuid4()

        # Mock rule with onboarded but not deployed model
        rule = Mock()
        rule.id = rule_id
        rule.name = "Onboarded Rule"
        rule.model_uri = "org/onboarded-model"
        rule.model_id = model_id

        probe = Mock()
        probe.id = probe_id
        probe.name = "Test Probe"
        probe.rules = [rule]

        probe_selections = [GuardrailProfileProbeSelection(id=probe_id, rules=None)]

        with patch("budapp.guardrails.services.GuardrailsProbeRulesDataManager") as MockDataManager:
            mock_dm = AsyncMock()
            mock_dm.get_probes_with_rules = AsyncMock(return_value=[probe])
            MockDataManager.return_value = mock_dm

            # No endpoints (model not deployed)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            service.session.execute = AsyncMock(return_value=mock_result)

            result = await service.derive_model_statuses(probe_selections, project_id=None)

            assert result.total_models == 1
            assert result.models_requiring_onboarding == 0
            assert result.models_requiring_deployment == 1
            # Should skip to step 8 (cluster recommendation)
            assert result.skip_to_step == 8
            assert result.credential_required is False


class TestWorkflowCancellationRollback:
    """Tests for workflow cancellation and rollback functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = Mock()
        workflow.id = uuid4()
        workflow.status = WorkflowStatusEnum.IN_PROGRESS
        return workflow

    @pytest.fixture
    def mock_workflow_steps(self):
        """Create mock workflow steps with deployment data."""
        profile_id = str(uuid4())
        endpoint_id = str(uuid4())

        step1 = Mock()
        step1.data = {
            "provider_id": str(uuid4()),
            "probe_selections": [{"id": str(uuid4())}],
        }

        step2 = Mock()
        step2.data = {
            "profile_id": profile_id,
            "endpoint_ids": [endpoint_id],
            "deployment": [{"id": str(uuid4())}],
            "model_statuses": [
                {"model_id": str(uuid4()), "status": "running"},
            ],
        }

        return [step1, step2]

    @pytest.mark.asyncio
    async def test_cancel_workflow_marks_cancelled(self, service, mock_workflow, mock_workflow_steps):
        """Test that cancellation marks workflow as CANCELLED."""
        workflow_id = mock_workflow.id

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=mock_workflow_steps)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                    mock_deploy_dm = AsyncMock()
                    mock_deploy_dm.get_all_by_fields = AsyncMock(return_value=[])
                    MockDeployDM.return_value = mock_deploy_dm

                    with patch("budapp.guardrails.services.RedisService") as MockRedis:
                        mock_redis = AsyncMock()
                        mock_redis.delete = AsyncMock()
                        mock_redis.get = AsyncMock(return_value=None)
                        MockRedis.return_value = mock_redis

                        with patch("budapp.guardrails.services.EndpointDataManager") as MockEndpointDM:
                            mock_ep_dm = AsyncMock()
                            mock_ep_dm.retrieve_by_fields = AsyncMock(return_value=None)
                            MockEndpointDM.return_value = mock_ep_dm

                            result = await service.cancel_workflow_with_rollback(
                                workflow_id=workflow_id,
                                reason="Test cancellation",
                            )

                            # Verify workflow was marked as cancelled
                            update_call = mock_wf_dm.update_by_fields.call_args
                            assert WorkflowStatusEnum.CANCELLED in str(update_call) or "CANCELLED" in str(update_call)

                            assert result["status"] in ("success", "partial")
                            assert result["reason"] == "Test cancellation"

    @pytest.mark.asyncio
    async def test_cancel_workflow_preserves_onboarded_models(self, service, mock_workflow, mock_workflow_steps):
        """Test that rollback preserves onboarded models (J2 design decision)."""
        workflow_id = mock_workflow.id

        # Add model status to step data showing onboarded model
        mock_workflow_steps[1].data["model_statuses"] = [
            {"model_id": str(uuid4()), "status": "running"},
            {"model_id": str(uuid4()), "status": "onboarded"},
        ]

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=mock_workflow_steps)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                    mock_deploy_dm = AsyncMock()
                    mock_deploy_dm.get_all_by_fields = AsyncMock(return_value=[])
                    MockDeployDM.return_value = mock_deploy_dm

                    with patch("budapp.guardrails.services.RedisService") as MockRedis:
                        mock_redis = AsyncMock()
                        mock_redis.delete = AsyncMock()
                        mock_redis.get = AsyncMock(return_value=None)
                        MockRedis.return_value = mock_redis

                        with patch("budapp.guardrails.services.EndpointDataManager"):
                            result = await service.cancel_workflow_with_rollback(
                                workflow_id=workflow_id,
                                reason="Test cancellation",
                            )

                            # Should report preserved models
                            assert result["preserved"]["onboarded_models"] == 2

    @pytest.mark.asyncio
    async def test_cancel_workflow_not_found(self, service):
        """Test cancellation when workflow doesn't exist."""
        workflow_id = uuid4()

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=None)
            MockWorkflowDM.return_value = mock_wf_dm

            result = await service.cancel_workflow_with_rollback(workflow_id=workflow_id)

            assert result["status"] == "error"
            assert result["message"] == "Workflow not found"


class TestWorkflowWithSkipLogic:
    """Tests for workflow execution with skip logic."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.mark.asyncio
    async def test_get_workflow_model_statuses_returns_cached(self, service):
        """Test that cached model statuses are returned without re-derivation."""
        workflow_id = uuid4()
        cached_statuses = {
            "model_statuses": [
                {
                    "rule_id": str(uuid4()),
                    "rule_name": "Test Rule",
                    "probe_id": str(uuid4()),
                    "probe_name": "Test Probe",
                    "model_uri": "org/model",
                    "status": "running",
                    "requires_onboarding": False,
                    "requires_deployment": False,
                    "can_reuse": True,
                }
            ],
            "total_models": 1,
            "models_requiring_onboarding": 0,
            "models_requiring_deployment": 0,
            "models_reusable": 1,
            "skip_to_step": 12,
            "credential_required": False,
        }

        mock_step = Mock()
        mock_step.data = cached_statuses

        with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
            mock_step_dm = AsyncMock()
            mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
            MockStepDM.return_value = mock_step_dm

            result = await service.get_workflow_model_statuses(
                workflow_id=workflow_id,
                refresh=False,  # Don't refresh, use cached
            )

            # Should return cached values without calling derive_model_statuses
            assert result.total_models == 1
            assert result.skip_to_step == 12
            assert result.models_reusable == 1

    @pytest.mark.asyncio
    async def test_get_workflow_model_statuses_empty_workflow(self, service):
        """Test handling of workflow with no steps."""
        workflow_id = uuid4()

        with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
            mock_step_dm = AsyncMock()
            mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[])
            MockStepDM.return_value = mock_step_dm

            result = await service.get_workflow_model_statuses(workflow_id=workflow_id)

            assert result.total_models == 0
            assert len(result.models) == 0


class TestEndToEndWorkflowScenarios:
    """End-to-end workflow scenario tests."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailDeploymentWorkflowService instance."""
        from budapp.guardrails.services import GuardrailDeploymentWorkflowService

        return GuardrailDeploymentWorkflowService(mock_session)

    @pytest.mark.asyncio
    async def test_scenario_all_models_need_onboarding(self, service):
        """Scenario: All models need onboarding - no skip enabled."""
        probe_id = uuid4()
        rule_id = uuid4()

        # Rule with model that needs onboarding
        rule = Mock()
        rule.id = rule_id
        rule.name = "Not Onboarded Rule"
        rule.model_uri = "org/new-model"
        rule.model_id = None  # Not onboarded

        probe = Mock()
        probe.id = probe_id
        probe.name = "Test Probe"
        probe.rules = [rule]

        probe_selections = [GuardrailProfileProbeSelection(id=probe_id, rules=None)]

        with patch("budapp.guardrails.services.GuardrailsProbeRulesDataManager") as MockDataManager:
            mock_dm = AsyncMock()
            mock_dm.get_probes_with_rules = AsyncMock(return_value=[probe])
            MockDataManager.return_value = mock_dm

            result = await service.derive_model_statuses(probe_selections, project_id=None)

            # No skip - must go through full workflow
            assert result.skip_to_step is None
            assert result.credential_required is True
            assert result.models_requiring_onboarding == 1

    @pytest.mark.asyncio
    async def test_scenario_reuse_existing_endpoints(self, service):
        """Scenario: Reuse existing running endpoints - skip to profile config."""
        probe_id = uuid4()
        rule_id = uuid4()
        model_id = uuid4()
        endpoint_id = uuid4()

        # Rule with deployed model
        rule = Mock()
        rule.id = rule_id
        rule.name = "Deployed Rule"
        rule.model_uri = "org/deployed-model"
        rule.model_id = model_id

        probe = Mock()
        probe.id = probe_id
        probe.name = "Test Probe"
        probe.rules = [rule]

        # Mock running endpoint
        mock_endpoint = Mock()
        mock_endpoint.id = endpoint_id
        mock_endpoint.name = "running-endpoint"
        mock_endpoint.endpoint = "http://localhost:8000"
        mock_endpoint.status = EndpointStatusEnum.RUNNING
        mock_endpoint.cluster_id = uuid4()
        mock_endpoint.cluster = Mock(name="test-cluster")

        probe_selections = [GuardrailProfileProbeSelection(id=probe_id, rules=None)]

        with patch("budapp.guardrails.services.GuardrailsProbeRulesDataManager") as MockDataManager:
            mock_dm = AsyncMock()
            mock_dm.get_probes_with_rules = AsyncMock(return_value=[probe])
            MockDataManager.return_value = mock_dm

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_endpoint]
            service.session.execute = AsyncMock(return_value=mock_result)

            result = await service.derive_model_statuses(probe_selections, project_id=None)

            # Skip to step 12 - profile configuration
            assert result.skip_to_step == 12
            assert result.can_reuse is True if hasattr(result, "can_reuse") else True
            assert result.models_reusable == 1
            assert result.credential_required is False

    @pytest.mark.asyncio
    async def test_scenario_partial_deployment(self, service):
        """Scenario: Some models deployed, some need deployment - skip to cluster."""
        probe_id = uuid4()

        # Rule 1: Onboarded but not deployed
        rule1 = Mock()
        rule1.id = uuid4()
        rule1.name = "Onboarded Rule"
        rule1.model_uri = "org/onboarded-model"
        rule1.model_id = uuid4()

        # Rule 2: Already deployed
        rule2 = Mock()
        rule2.id = uuid4()
        rule2.name = "Deployed Rule"
        rule2.model_uri = "org/deployed-model"
        rule2.model_id = uuid4()

        probe = Mock()
        probe.id = probe_id
        probe.name = "Test Probe"
        probe.rules = [rule1, rule2]

        # Mock endpoint only for rule2's model
        mock_endpoint = Mock()
        mock_endpoint.id = uuid4()
        mock_endpoint.name = "running-endpoint"
        mock_endpoint.endpoint = "http://localhost:8000"
        mock_endpoint.status = EndpointStatusEnum.RUNNING
        mock_endpoint.cluster_id = uuid4()
        mock_endpoint.cluster = Mock(name="test-cluster")

        probe_selections = [GuardrailProfileProbeSelection(id=probe_id, rules=None)]

        with patch("budapp.guardrails.services.GuardrailsProbeRulesDataManager") as MockDataManager:
            mock_dm = AsyncMock()
            mock_dm.get_probes_with_rules = AsyncMock(return_value=[probe])
            MockDataManager.return_value = mock_dm

            # First call for rule1 - no endpoints, second for rule2 - has endpoint
            mock_result_empty = MagicMock()
            mock_result_empty.scalars.return_value.all.return_value = []

            mock_result_with_ep = MagicMock()
            mock_result_with_ep.scalars.return_value.all.return_value = [mock_endpoint]

            service.session.execute = AsyncMock(side_effect=[mock_result_empty, mock_result_with_ep])

            result = await service.derive_model_statuses(probe_selections, project_id=None)

            # Should skip to step 8 (cluster recommendation) since all onboarded
            assert result.skip_to_step == 8
            assert result.models_requiring_onboarding == 0
            assert result.models_requiring_deployment == 1  # rule1 needs deployment
