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

"""Tests for guardrail custom probe service, CRUD, and pipeline actions."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from budapp.commons.constants import (
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    ProbeTypeEnum,
    ScannerTypeEnum,
)
from budapp.guardrails.schemas import (
    ClassifierConfig,
    CategoryDef,
    GuardrailCustomProbeCreate,
    GuardrailCustomProbeUpdate,
    HeadMapping,
    LLMConfig,
    PolicyConfig,
)


class TestGuardrailCustomProbeService:
    """Tests for GuardrailCustomProbeService."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailCustomProbeService instance with mock session."""
        from budapp.guardrails.services import GuardrailCustomProbeService

        return GuardrailCustomProbeService(mock_session)

    @pytest.mark.asyncio
    async def test_create_custom_probe_success(self, service, mock_session):
        """Test successful creation of a custom classifier probe."""
        user_id = uuid4()
        project_id = uuid4()
        model_id = uuid4()
        provider_id = uuid4()
        probe_id = uuid4()

        request = GuardrailCustomProbeCreate(
            name="Test Classifier Probe",
            description="A test classifier probe",
            scanner_type=ScannerTypeEnum.CLASSIFIER,
            model_id=model_id,
            model_config_data=ClassifierConfig(
                head_mappings=[HeadMapping(head_name="default", target_labels=["SAFE", "UNSAFE"])]
            ),
        )

        # Mock model lookup
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.uri = "test-model-uri"
        mock_model.provider_type = "custom"
        mock_model.is_gated = False

        # Mock provider lookup
        mock_provider = Mock()
        mock_provider.id = provider_id

        # Mock created probe
        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = request.name
        mock_probe.description = request.description
        mock_probe.probe_type = ProbeTypeEnum.CUSTOM
        mock_probe.created_by = user_id
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        with patch("budapp.guardrails.services.ModelDataManager") as MockModelDM, patch(
            "budapp.guardrails.services.ProviderDataManager"
        ) as MockProviderDM, patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardrailDM:
            # Configure model data manager
            mock_model_dm = MockModelDM.return_value
            mock_model_dm.retrieve_by_fields = AsyncMock(return_value=mock_model)

            # Configure provider data manager
            mock_provider_dm = MockProviderDM.return_value
            mock_provider_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)

            # Configure guardrail data manager
            mock_guardrail_dm = MockGuardrailDM.return_value
            mock_guardrail_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)

            result = await service.create_custom_probe(
                request=request,
                project_id=project_id,
                user_id=user_id,
            )

            assert result.id == probe_id
            assert result.name == request.name
            mock_guardrail_dm.create_custom_probe_with_rule.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_custom_probe_model_not_found(self, service, mock_session):
        """Test error when model is not found."""
        from budapp.commons.exceptions import ClientException

        user_id = uuid4()
        project_id = uuid4()
        model_id = uuid4()

        request = GuardrailCustomProbeCreate(
            name="Test Probe",
            scanner_type=ScannerTypeEnum.CLASSIFIER,
            model_id=model_id,
            model_config_data=ClassifierConfig(head_mappings=[HeadMapping(target_labels=["TEST"])]),
        )

        with patch("budapp.guardrails.services.ModelDataManager") as MockModelDM:
            mock_model_dm = MockModelDM.return_value
            mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)

            with pytest.raises(ClientException) as exc_info:
                await service.create_custom_probe(
                    request=request,
                    project_id=project_id,
                    user_id=user_id,
                )

            assert "not found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_create_custom_probe_provider_not_found(self, service, mock_session):
        """Test error when BudSentinel provider is not found."""
        from budapp.commons.exceptions import ClientException

        user_id = uuid4()
        project_id = uuid4()
        model_id = uuid4()

        request = GuardrailCustomProbeCreate(
            name="Test Probe",
            scanner_type=ScannerTypeEnum.CLASSIFIER,
            model_id=model_id,
            model_config_data=ClassifierConfig(head_mappings=[HeadMapping(target_labels=["TEST"])]),
        )

        mock_model = Mock()
        mock_model.id = model_id
        mock_model.uri = "test-uri"
        mock_model.provider_type = "custom"
        mock_model.is_gated = False

        with patch("budapp.guardrails.services.ModelDataManager") as MockModelDM, patch(
            "budapp.guardrails.services.ProviderDataManager"
        ) as MockProviderDM:
            mock_model_dm = MockModelDM.return_value
            mock_model_dm.retrieve_by_fields = AsyncMock(return_value=mock_model)

            mock_provider_dm = MockProviderDM.return_value
            mock_provider_dm.retrieve_by_fields = AsyncMock(return_value=None)

            with pytest.raises(ClientException) as exc_info:
                await service.create_custom_probe(
                    request=request,
                    project_id=project_id,
                    user_id=user_id,
                )

            assert "BudSentinel provider not found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_update_custom_probe_success(self, service, mock_session):
        """Test successful update of a custom probe."""
        user_id = uuid4()
        probe_id = uuid4()

        request = GuardrailCustomProbeUpdate(
            name="Updated Probe Name",
            description="Updated description",
        )

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Original Name"
        mock_probe.description = "Original description"
        mock_probe.created_by = user_id
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardrailDM:
            mock_guardrail_dm = MockGuardrailDM.return_value
            mock_guardrail_dm.retrieve_by_fields = AsyncMock(return_value=mock_probe)

            # Mock update_by_fields to return updated probe
            updated_probe = Mock()
            updated_probe.id = probe_id
            updated_probe.name = request.name
            updated_probe.description = request.description
            updated_probe.created_by = user_id
            mock_guardrail_dm.update_by_fields = AsyncMock(return_value=updated_probe)

            result = await service.update_custom_probe(
                probe_id=probe_id,
                request=request,
                user_id=user_id,
            )

            assert result.name == request.name

    @pytest.mark.asyncio
    async def test_update_custom_probe_not_found(self, service, mock_session):
        """Test error when probe to update is not found."""
        from budapp.commons.exceptions import ClientException

        user_id = uuid4()
        probe_id = uuid4()

        request = GuardrailCustomProbeUpdate(name="Updated Name")

        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardrailDM:
            mock_guardrail_dm = MockGuardrailDM.return_value
            mock_guardrail_dm.retrieve_by_fields = AsyncMock(return_value=None)

            with pytest.raises(ClientException) as exc_info:
                await service.update_custom_probe(
                    probe_id=probe_id,
                    request=request,
                    user_id=user_id,
                )

            assert "not found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_update_custom_probe_not_owner(self, service, mock_session):
        """Test error when user is not the owner of the probe."""
        from budapp.commons.exceptions import ClientException

        user_id = uuid4()
        other_user_id = uuid4()
        probe_id = uuid4()

        request = GuardrailCustomProbeUpdate(name="Updated Name")

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.created_by = other_user_id  # Different user
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardrailDM:
            mock_guardrail_dm = MockGuardrailDM.return_value
            mock_guardrail_dm.retrieve_by_fields = AsyncMock(return_value=mock_probe)

            with pytest.raises(ClientException) as exc_info:
                await service.update_custom_probe(
                    probe_id=probe_id,
                    request=request,
                    user_id=user_id,
                )

            assert "permission" in str(exc_info.value.message).lower()

    @pytest.mark.asyncio
    async def test_delete_custom_probe_success(self, service, mock_session):
        """Test successful deletion of a custom probe."""
        user_id = uuid4()
        probe_id = uuid4()

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.created_by = user_id
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardrailDM, patch(
            "budapp.guardrails.services.GuardrailsProbeRulesDataManager"
        ) as MockProbeRulesDM:
            mock_guardrail_dm = MockGuardrailDM.return_value
            mock_guardrail_dm.retrieve_by_fields = AsyncMock(return_value=mock_probe)

            mock_probe_rules_dm = MockProbeRulesDM.return_value
            mock_probe_rules_dm.soft_delete_deprecated_probes = AsyncMock()

            await service.delete_custom_probe(
                probe_id=probe_id,
                user_id=user_id,
            )

            mock_probe_rules_dm.soft_delete_deprecated_probes.assert_called_once_with([str(probe_id)])

    @pytest.mark.asyncio
    async def test_delete_custom_probe_not_owner(self, service, mock_session):
        """Test error when user tries to delete a probe they don't own."""
        from budapp.commons.exceptions import ClientException

        user_id = uuid4()
        other_user_id = uuid4()
        probe_id = uuid4()

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.created_by = other_user_id
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardrailDM:
            mock_guardrail_dm = MockGuardrailDM.return_value
            mock_guardrail_dm.retrieve_by_fields = AsyncMock(return_value=mock_probe)

            with pytest.raises(ClientException) as exc_info:
                await service.delete_custom_probe(
                    probe_id=probe_id,
                    user_id=user_id,
                )

            assert "permission" in str(exc_info.value.message).lower()


class TestGuardrailPipelineActions:
    """Tests for GuardrailPipelineActions."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def pipeline_actions(self, mock_session):
        """Create a GuardrailPipelineActions instance with mock session."""
        from budapp.guardrails.pipeline_actions import GuardrailPipelineActions

        return GuardrailPipelineActions(mock_session)

    @pytest.mark.asyncio
    async def test_validate_deployment_model_probes_require_cluster(self, pipeline_actions, mock_session):
        """Test that model probes require cluster_id."""
        probe_id = uuid4()
        probe_selections = [{"probe_id": str(probe_id)}]

        # Mock model probe (has model_scanner or custom type)
        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Test Model Probe"
        mock_probe.probe_type = ProbeTypeEnum.MODEL_SCANNER

        with patch.object(pipeline_actions, "session") as session_mock:
            # Mock the data manager
            with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
                mock_dm = MockDM.return_value
                mock_dm.get_model_probes_from_selections = AsyncMock(return_value=[mock_probe])

                # Mock the selectinload query for checking gated status
                mock_execute = MagicMock()
                mock_probe_with_rules = Mock()
                mock_probe_with_rules.rules = []
                mock_execute.scalar_one_or_none.return_value = mock_probe_with_rules
                session_mock.execute.return_value = mock_execute

                result = await pipeline_actions.validate_deployment(
                    profile_id=uuid4(),
                    probe_selections=probe_selections,
                    cluster_id=None,  # No cluster provided
                    credential_id=None,
                )

                assert result["success"] is False
                assert any("cluster_id required" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_deployment_gated_models_require_credentials(self, pipeline_actions, mock_session):
        """Test that gated model probes require credential_id."""
        probe_id = uuid4()
        cluster_id = uuid4()
        probe_selections = [{"probe_id": str(probe_id)}]

        # Mock gated model probe
        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Gated Model Probe"
        mock_probe.probe_type = ProbeTypeEnum.MODEL_SCANNER

        mock_rule = Mock()
        mock_rule.is_gated = True

        mock_probe_with_rules = Mock()
        mock_probe_with_rules.rules = [mock_rule]

        with patch.object(pipeline_actions, "session") as session_mock:
            with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
                mock_dm = MockDM.return_value
                mock_dm.get_model_probes_from_selections = AsyncMock(return_value=[mock_probe])

                mock_execute = MagicMock()
                mock_execute.scalar_one_or_none.return_value = mock_probe_with_rules
                session_mock.execute.return_value = mock_execute

                result = await pipeline_actions.validate_deployment(
                    profile_id=uuid4(),
                    probe_selections=probe_selections,
                    cluster_id=cluster_id,
                    credential_id=None,  # No credentials provided
                )

                assert result["success"] is False
                assert any("credential_id required" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_deployment_success_with_model_probes(self, pipeline_actions, mock_session):
        """Test successful validation with model probes when cluster_id is provided."""
        probe_id = uuid4()
        cluster_id = uuid4()
        probe_selections = [{"probe_id": str(probe_id)}]

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Test Model Probe"
        mock_probe.probe_type = ProbeTypeEnum.MODEL_SCANNER

        mock_probe_with_rules = Mock()
        mock_probe_with_rules.rules = []  # No rules with gated models

        with patch.object(pipeline_actions, "session") as session_mock:
            with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
                mock_dm = MockDM.return_value
                mock_dm.get_model_probes_from_selections = AsyncMock(return_value=[mock_probe])

                mock_execute = MagicMock()
                mock_execute.scalar_one_or_none.return_value = mock_probe_with_rules
                session_mock.execute.return_value = mock_execute

                result = await pipeline_actions.validate_deployment(
                    profile_id=uuid4(),
                    probe_selections=probe_selections,
                    cluster_id=cluster_id,
                    credential_id=None,
                )

                assert result["success"] is True
                assert "model_probes" in result
                assert result["has_model_probes"] is True

    @pytest.mark.asyncio
    async def test_validate_deployment_no_model_probes(self, pipeline_actions, mock_session):
        """Test validation passes without cluster_id when no model probes."""
        probe_id = uuid4()
        probe_selections = [{"probe_id": str(probe_id)}]

        with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
            mock_dm = MockDM.return_value
            mock_dm.get_model_probes_from_selections = AsyncMock(return_value=[])  # No model probes

            result = await pipeline_actions.validate_deployment(
                profile_id=uuid4(),
                probe_selections=probe_selections,
                cluster_id=None,
                credential_id=None,
            )

            assert result["success"] is True
            assert result["has_model_probes"] is False

    @pytest.mark.asyncio
    async def test_identify_model_requirements_models_to_onboard(self, pipeline_actions, mock_session):
        """Test identifying models that need onboarding (model_id is None)."""
        probe_id = uuid4()
        cluster_id = uuid4()
        probe_selections = [{"probe_id": str(probe_id)}]

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Test Probe"

        # Rule without model_id means it needs onboarding
        mock_rule = Mock()
        mock_rule.id = uuid4()
        mock_rule.model_id = None  # Not yet onboarded
        mock_rule.model_uri = "hf://test-model"
        mock_rule.model_provider_type = "huggingface"
        mock_rule.is_gated = False

        mock_probe_with_rules = Mock()
        mock_probe_with_rules.rules = [mock_rule]

        with patch.object(pipeline_actions, "session") as session_mock:
            with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
                mock_dm = MockDM.return_value
                mock_dm.get_model_probes_from_selections = AsyncMock(return_value=[mock_probe])

                mock_execute = MagicMock()
                mock_execute.scalar_one_or_none.return_value = mock_probe_with_rules
                session_mock.execute.return_value = mock_execute

                result = await pipeline_actions.identify_model_requirements(
                    probe_selections=probe_selections,
                    cluster_id=cluster_id,
                )

                assert len(result["models_to_onboard"]) == 1
                assert len(result["models_to_deploy"]) == 0
                assert result["models_to_onboard"][0]["model_uri"] == "hf://test-model"

    @pytest.mark.asyncio
    async def test_identify_model_requirements_models_to_deploy(self, pipeline_actions, mock_session):
        """Test identifying models that need deployment (model_id exists)."""
        probe_id = uuid4()
        cluster_id = uuid4()
        model_id = uuid4()
        probe_selections = [{"probe_id": str(probe_id)}]

        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Test Probe"

        # Rule with model_id means it just needs deployment
        mock_rule = Mock()
        mock_rule.id = uuid4()
        mock_rule.model_id = model_id  # Already onboarded
        mock_rule.model_uri = "hf://test-model"
        mock_rule.model_provider_type = "huggingface"

        mock_probe_with_rules = Mock()
        mock_probe_with_rules.rules = [mock_rule]

        with patch.object(pipeline_actions, "session") as session_mock:
            with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
                mock_dm = MockDM.return_value
                mock_dm.get_model_probes_from_selections = AsyncMock(return_value=[mock_probe])

                mock_execute = MagicMock()
                mock_execute.scalar_one_or_none.return_value = mock_probe_with_rules
                session_mock.execute.return_value = mock_execute

                result = await pipeline_actions.identify_model_requirements(
                    probe_selections=probe_selections,
                    cluster_id=cluster_id,
                )

                assert len(result["models_to_onboard"]) == 0
                assert len(result["models_to_deploy"]) == 1
                assert result["models_to_deploy"][0]["model_id"] == str(model_id)

    @pytest.mark.asyncio
    async def test_build_guardrail_config_classifier(self, pipeline_actions, mock_session):
        """Test building guardrail config for classifier scanner."""
        profile_id = uuid4()
        rule_id = uuid4()

        mock_rule = Mock()
        mock_rule.id = rule_id
        mock_rule.uri = "custom.user.test.rule"
        mock_rule.scanner_type = "classifier"
        mock_rule.model_uri = "test-classifier-model"
        mock_rule.model_config_json = {"head_mappings": [{"head_name": "default", "target_labels": ["SAFE", "UNSAFE"]}]}

        with patch.object(pipeline_actions, "session") as session_mock:
            session_mock.get.return_value = mock_rule

            rule_deployments = [
                {
                    "rule_id": str(rule_id),
                    "endpoint_url": "http://localhost:8000",
                    "endpoint_id": str(uuid4()),
                }
            ]

            result = await pipeline_actions.build_guardrail_config(
                profile_id=profile_id,
                rule_deployments=rule_deployments,
            )

            assert "custom_rules" in result
            assert "metadata_json" in result
            assert "latentbud" in result["metadata_json"]
            assert len(result["custom_rules"]) == 1
            assert result["custom_rules"][0]["scanner"] == "latentbud"

    @pytest.mark.asyncio
    async def test_build_guardrail_config_llm(self, pipeline_actions, mock_session):
        """Test building guardrail config for LLM scanner."""
        profile_id = uuid4()
        rule_id = uuid4()

        mock_rule = Mock()
        mock_rule.id = rule_id
        mock_rule.uri = "custom.user.test.rule"
        mock_rule.scanner_type = "llm"
        mock_rule.model_uri = "gpt-4"
        mock_rule.model_config_json = {"handler": "gpt_safeguard", "policy": {"task": "safety"}}

        with patch.object(pipeline_actions, "session") as session_mock:
            session_mock.get.return_value = mock_rule

            rule_deployments = [
                {
                    "rule_id": str(rule_id),
                    "endpoint_url": "http://localhost:8000",
                    "endpoint_id": str(uuid4()),
                }
            ]

            result = await pipeline_actions.build_guardrail_config(
                profile_id=profile_id,
                rule_deployments=rule_deployments,
            )

            assert "custom_rules" in result
            assert "metadata_json" in result
            assert "llm" in result["metadata_json"]
            assert result["metadata_json"]["llm"]["url"] == "http://localhost:8000/v1"
            assert len(result["custom_rules"]) == 1
            assert result["custom_rules"][0]["scanner"] == "llm"

    @pytest.mark.asyncio
    async def test_get_deployment_progress_all_running(self, pipeline_actions, mock_session):
        """Test deployment progress when all endpoints are running."""
        guardrail_deployment_id = uuid4()
        endpoint_id_1 = uuid4()
        endpoint_id_2 = uuid4()
        rule_id_1 = uuid4()
        rule_id_2 = uuid4()

        mock_deployment_1 = Mock()
        mock_deployment_1.endpoint_id = endpoint_id_1
        mock_deployment_1.rule_id = rule_id_1

        mock_deployment_2 = Mock()
        mock_deployment_2.endpoint_id = endpoint_id_2
        mock_deployment_2.rule_id = rule_id_2

        mock_endpoint_1 = Mock()
        mock_endpoint_1.id = endpoint_id_1
        mock_endpoint_1.name = "endpoint-1"
        mock_endpoint_1.status = Mock(value="running")

        mock_endpoint_2 = Mock()
        mock_endpoint_2.id = endpoint_id_2
        mock_endpoint_2.name = "endpoint-2"
        mock_endpoint_2.status = Mock(value="running")

        with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
            mock_dm = MockDM.return_value
            mock_dm.get_rule_deployments_for_guardrail = AsyncMock(return_value=[mock_deployment_1, mock_deployment_2])
            mock_session.get = Mock(side_effect=[mock_endpoint_1, mock_endpoint_2])

            result = await pipeline_actions.get_deployment_progress(guardrail_deployment_id)

            assert result["status"] == "running"
            assert result["progress_percentage"] == 100.0
            assert result["status_breakdown"]["running"] == 2

    @pytest.mark.asyncio
    async def test_get_deployment_progress_partial_failure(self, pipeline_actions, mock_session):
        """Test deployment progress with some endpoint failures."""
        guardrail_deployment_id = uuid4()
        endpoint_id_1 = uuid4()
        endpoint_id_2 = uuid4()
        rule_id_1 = uuid4()
        rule_id_2 = uuid4()

        mock_deployment_1 = Mock()
        mock_deployment_1.endpoint_id = endpoint_id_1
        mock_deployment_1.rule_id = rule_id_1

        mock_deployment_2 = Mock()
        mock_deployment_2.endpoint_id = endpoint_id_2
        mock_deployment_2.rule_id = rule_id_2

        mock_endpoint_1 = Mock()
        mock_endpoint_1.id = endpoint_id_1
        mock_endpoint_1.name = "endpoint-1"
        mock_endpoint_1.status = Mock(value="running")

        mock_endpoint_2 = Mock()
        mock_endpoint_2.id = endpoint_id_2
        mock_endpoint_2.name = "endpoint-2"
        mock_endpoint_2.status = Mock(value="failure")

        with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
            mock_dm = MockDM.return_value
            mock_dm.get_rule_deployments_for_guardrail = AsyncMock(return_value=[mock_deployment_1, mock_deployment_2])
            mock_session.get = Mock(side_effect=[mock_endpoint_1, mock_endpoint_2])

            result = await pipeline_actions.get_deployment_progress(guardrail_deployment_id)

            assert result["status"] == "partial_failure"
            assert result["status_breakdown"]["running"] == 1
            assert result["status_breakdown"]["failure"] == 1

    @pytest.mark.asyncio
    async def test_get_deployment_progress_no_models(self, pipeline_actions, mock_session):
        """Test deployment progress when no model deployments exist."""
        guardrail_deployment_id = uuid4()

        with patch("budapp.guardrails.pipeline_actions.GuardrailsDeploymentDataManager") as MockDM:
            mock_dm = MockDM.return_value
            mock_dm.get_rule_deployments_for_guardrail = AsyncMock(return_value=[])

            result = await pipeline_actions.get_deployment_progress(guardrail_deployment_id)

            assert result["status"] == "no_models"
            assert result["progress_percentage"] == 100.0


class TestGuardrailsDeploymentDataManagerCustomProbes:
    """Tests for custom probe CRUD methods in GuardrailsDeploymentDataManager."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = MagicMock()
        session.begin_nested = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.scalar = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def data_manager(self, mock_session):
        """Create a GuardrailsDeploymentDataManager instance."""
        from budapp.guardrails.crud import GuardrailsDeploymentDataManager

        return GuardrailsDeploymentDataManager(mock_session)

    @pytest.mark.asyncio
    async def test_get_custom_probes_filters_by_user(self, data_manager, mock_session):
        """Test that get_custom_probes filters by user_id and probe_type."""
        user_id = uuid4()

        # Create mock probes
        mock_probe = Mock()
        mock_probe.id = uuid4()
        mock_probe.name = "User Custom Probe"
        mock_probe.probe_type = ProbeTypeEnum.CUSTOM
        mock_probe.created_by = user_id
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        # Mock session scalar for count
        mock_session.scalar = AsyncMock(return_value=1)

        # Mock session execute for list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_probe]
        mock_session.execute = AsyncMock(return_value=mock_result)

        probes, total = await data_manager.get_custom_probes(user_id=user_id)

        assert total == 1
        assert len(probes) == 1
        assert probes[0].created_by == user_id

    @pytest.mark.asyncio
    async def test_get_model_probes_from_selections(self, data_manager, mock_session):
        """Test get_model_probes_from_selections returns only model-based probes."""
        probe_id_1 = uuid4()
        probe_id_2 = uuid4()

        mock_probe_1 = Mock()
        mock_probe_1.id = probe_id_1
        mock_probe_1.probe_type = ProbeTypeEnum.MODEL_SCANNER

        mock_probe_2 = Mock()
        mock_probe_2.id = probe_id_2
        mock_probe_2.probe_type = ProbeTypeEnum.CUSTOM

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_probe_1, mock_probe_2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        probes = await data_manager.get_model_probes_from_selections([probe_id_1, probe_id_2])

        # Should return both MODEL_SCANNER and CUSTOM probes
        assert len(probes) == 2
