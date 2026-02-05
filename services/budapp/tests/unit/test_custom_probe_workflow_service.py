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

"""Unit tests for custom probe workflow service methods.

Tests the multi-step workflow for creating custom probes:
- Step 1: Probe type selection (derives model_uri, scanner_type, handler)
- Step 2: Policy configuration
- Step 3: Probe metadata + trigger workflow
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from budapp.commons.constants import (
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from budapp.guardrails.schemas import (
    ContentItem,
    CustomProbeTypeEnum,
    CustomProbeWorkflowRequest,
    DefinitionItem,
    PolicyConfig,
    PolicyExample,
    SafeContentConfig,
    ViolationCategory,
)


class TestProbeTypeConfig:
    """Tests for ProbeTypeConfig and PROBE_TYPE_CONFIGS."""

    def test_probe_type_configs_contains_llm_policy(self):
        """Test that PROBE_TYPE_CONFIGS contains llm_policy configuration."""
        from budapp.guardrails.services import PROBE_TYPE_CONFIGS, ProbeTypeConfig

        assert "llm_policy" in PROBE_TYPE_CONFIGS
        config = PROBE_TYPE_CONFIGS["llm_policy"]

        assert isinstance(config, ProbeTypeConfig)
        assert config.model_uri == "openai/gpt-oss-safeguard-20b"
        assert config.scanner_type == "llm"
        assert config.handler == "gpt_safeguard"
        assert config.model_provider_type == "openai"

    def test_probe_type_config_dataclass_fields(self):
        """Test that ProbeTypeConfig has correct fields."""
        from budapp.guardrails.services import ProbeTypeConfig

        config = ProbeTypeConfig(
            model_uri="test/model",
            scanner_type="classifier",
            handler="test_handler",
            model_provider_type="custom",
        )

        assert config.model_uri == "test/model"
        assert config.scanner_type == "classifier"
        assert config.handler == "test_handler"
        assert config.model_provider_type == "custom"


class TestCustomProbeWorkflowServiceStep1:
    """Tests for Step 1: Probe type selection."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = MagicMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailCustomProbeService instance."""
        from budapp.guardrails.services import GuardrailCustomProbeService

        return GuardrailCustomProbeService(mock_session)

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = Mock()
        workflow.id = uuid4()
        workflow.status = WorkflowStatusEnum.IN_PROGRESS
        workflow.workflow_type = WorkflowTypeEnum.CLOUD_MODEL_ONBOARDING
        return workflow

    @pytest.fixture
    def mock_workflow_step(self):
        """Create a mock workflow step."""
        step = Mock()
        step.id = uuid4()
        step.step_number = 1
        step.data = {}
        return step

    @pytest.mark.asyncio
    async def test_step1_derives_config_from_probe_type(self, service, mock_workflow, mock_workflow_step):
        """Test Step 1 derives model_uri, scanner_type, handler from probe_type_option."""
        user_id = uuid4()
        project_id = uuid4()

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    result = await service.add_custom_probe_workflow(
                        current_user_id=user_id,
                        request=request,
                    )

                    # Verify workflow was created
                    assert result == mock_workflow

                    # Verify step data was updated with derived config
                    update_call = mock_step_dm.update_by_fields.call_args
                    if update_call:
                        step_data = update_call[0][1].get("data", {})
                        assert step_data.get("probe_type_option") == "llm_policy"
                        assert step_data.get("model_uri") == "openai/gpt-oss-safeguard-20b"
                        assert step_data.get("scanner_type") == "llm"
                        assert step_data.get("handler") == "gpt_safeguard"
                        assert step_data.get("model_provider_type") == "openai"
                        assert step_data.get("project_id") == str(project_id)

    @pytest.mark.asyncio
    async def test_step1_with_existing_workflow(self, service, mock_workflow, mock_workflow_step):
        """Test Step 1 with existing workflow_id."""
        user_id = uuid4()

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    result = await service.add_custom_probe_workflow(
                        current_user_id=user_id,
                        request=request,
                    )

                    assert result == mock_workflow


class TestCustomProbeWorkflowServiceStep2:
    """Tests for Step 2: Policy configuration."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = MagicMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailCustomProbeService instance."""
        from budapp.guardrails.services import GuardrailCustomProbeService

        return GuardrailCustomProbeService(mock_session)

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = Mock()
        workflow.id = uuid4()
        workflow.status = WorkflowStatusEnum.IN_PROGRESS
        return workflow

    @pytest.fixture
    def sample_policy(self):
        """Create a sample PolicyConfig."""
        return PolicyConfig(
            task="Evaluate content for harmful material",
            definitions=[DefinitionItem(term="harmful", definition="Content that causes harm")],
            safe_content=SafeContentConfig(
                description="Safe content",
                items=[ContentItem(name="safe", description="Safe content", example="Hello world")],
                examples=[PolicyExample(input="Hello", rationale="Greeting is safe")],
            ),
            violations=[
                ViolationCategory(
                    category="harmful_content",
                    severity="High",
                    description="Harmful content",
                    items=[ContentItem(name="harm", description="Harmful", example="Bad content")],
                    examples=[PolicyExample(input="Bad", rationale="This is harmful")],
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_step2_stores_policy(self, service, mock_workflow, sample_policy):
        """Test Step 2 stores policy configuration."""
        user_id = uuid4()

        # Step 1 data already stored
        step1_data = {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(uuid4()),
        }

        mock_step = Mock()
        mock_step.id = uuid4()
        mock_step.step_number = 1
        mock_step.data = step1_data

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=2,
            policy=sample_policy,
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    result = await service.add_custom_probe_workflow(
                        current_user_id=user_id,
                        request=request,
                    )

                    assert result == mock_workflow

                    # Verify policy was stored
                    update_call = mock_step_dm.update_by_fields.call_args
                    if update_call:
                        step_data = update_call[0][1].get("data", {})
                        assert "policy" in step_data
                        assert step_data["policy"]["task"] == "Evaluate content for harmful material"


class TestCustomProbeWorkflowServiceStep3:
    """Tests for Step 3: Probe metadata and trigger."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = MagicMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailCustomProbeService instance."""
        from budapp.guardrails.services import GuardrailCustomProbeService

        return GuardrailCustomProbeService(mock_session)

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = Mock()
        workflow.id = uuid4()
        workflow.status = WorkflowStatusEnum.IN_PROGRESS
        return workflow

    @pytest.fixture
    def accumulated_step_data(self):
        """Create accumulated step data from steps 1 and 2."""
        return {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(uuid4()),
            "policy": {
                "task": "Evaluate content",
                "definitions": [{"term": "harmful", "definition": "Content that causes harm"}],
                "safe_content": {
                    "description": "Safe content",
                    "items": [{"name": "safe", "description": "Safe content", "example": "Hello"}],
                    "examples": [{"input": "Hello", "rationale": "Greeting is safe"}],
                },
                "violations": [
                    {
                        "category": "harmful_content",
                        "severity": "High",
                        "description": "Harmful content",
                        "items": [{"name": "harm", "description": "Harmful", "example": "Bad"}],
                        "examples": [{"input": "Bad", "rationale": "Harmful"}],
                    }
                ],
            },
        }

    @pytest.mark.asyncio
    async def test_step3_stores_metadata(self, service, mock_workflow, accumulated_step_data):
        """Test Step 3 stores name, description, guard_types, modality_types."""
        user_id = uuid4()

        mock_step = Mock()
        mock_step.id = uuid4()
        mock_step.step_number = 2
        mock_step.data = accumulated_step_data

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            name="My Custom Probe",
            description="Detects harmful content",
            guard_types=["input", "output"],
            modality_types=["text"],
            trigger_workflow=False,  # Don't trigger yet
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    result = await service.add_custom_probe_workflow(
                        current_user_id=user_id,
                        request=request,
                    )

                    assert result == mock_workflow

                    # Verify metadata was stored
                    update_call = mock_step_dm.update_by_fields.call_args
                    if update_call:
                        step_data = update_call[0][1].get("data", {})
                        assert step_data.get("name") == "My Custom Probe"
                        assert step_data.get("description") == "Detects harmful content"
                        assert step_data.get("guard_types") == ["input", "output"]
                        assert step_data.get("modality_types") == ["text"]

    @pytest.mark.asyncio
    async def test_step3_trigger_workflow_creates_probe(self, service, mock_workflow, accumulated_step_data):
        """Test Step 3 with trigger_workflow=True creates the probe."""
        user_id = uuid4()
        probe_id = uuid4()
        provider_id = uuid4()

        accumulated_step_data["name"] = "My Custom Probe"
        accumulated_step_data["description"] = "Test description"
        accumulated_step_data["guard_types"] = ["input"]
        accumulated_step_data["modality_types"] = ["text"]

        mock_step = Mock()
        mock_step.id = uuid4()
        mock_step.step_number = 3
        mock_step.data = accumulated_step_data

        # Mock probe result
        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "My Custom Probe"

        # Mock provider
        mock_provider = Mock()
        mock_provider.id = provider_id
        mock_provider.type = "bud_sentinel"

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            name="My Custom Probe",
            trigger_workflow=True,
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                            mock_deploy_dm = AsyncMock()
                            mock_deploy_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockDeployDM.return_value = mock_deploy_dm

                            with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                                mock_model_dm = AsyncMock()
                                mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)
                                MockModelDM.return_value = mock_model_dm

                                result = await service.add_custom_probe_workflow(
                                    current_user_id=user_id,
                                    request=request,
                                )

                                assert result == mock_workflow

                                # Verify probe was created
                                mock_deploy_dm.create_custom_probe_with_rule.assert_called_once()

                                # Verify workflow was marked complete
                                mock_wf_dm.update_by_fields.assert_called()


class TestExecuteCustomProbeWorkflow:
    """Tests for _execute_custom_probe_workflow private method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = MagicMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a GuardrailCustomProbeService instance."""
        from budapp.guardrails.services import GuardrailCustomProbeService

        return GuardrailCustomProbeService(mock_session)

    @pytest.fixture
    def workflow_data(self):
        """Create complete workflow data for execution."""
        return {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(uuid4()),
            "policy": {
                "task": "Evaluate content",
                "definitions": [{"term": "harmful", "definition": "Content that causes harm"}],
                "safe_content": {
                    "description": "Safe content",
                    "items": [{"name": "safe", "description": "Safe", "example": "Hello"}],
                    "examples": [{"input": "Hello", "rationale": "Safe"}],
                },
                "violations": [
                    {
                        "category": "harmful",
                        "severity": "High",
                        "description": "Harmful",
                        "items": [{"name": "harm", "description": "Harmful", "example": "Bad"}],
                        "examples": [{"input": "Bad", "rationale": "Harmful"}],
                    }
                ],
            },
            "name": "Test Probe",
            "description": "Test Description",
            "guard_types": ["input", "output"],
            "modality_types": ["text"],
        }

    @pytest.mark.asyncio
    async def test_execute_assigns_model_id_when_model_exists(self, service, workflow_data):
        """Test that model_id is assigned when model exists by URI."""
        user_id = uuid4()
        workflow_id = uuid4()
        model_id = uuid4()
        probe_id = uuid4()
        provider_id = uuid4()

        # Mock existing model
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.uri = "openai/gpt-oss-safeguard-20b"

        mock_workflow = Mock()
        mock_workflow.id = workflow_id

        mock_step = Mock()
        mock_step.data = workflow_data

        mock_probe = Mock()
        mock_probe.id = probe_id

        mock_provider = Mock()
        mock_provider.id = provider_id

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                    mock_model_dm = AsyncMock()
                    mock_model_dm.retrieve_by_fields = AsyncMock(return_value=mock_model)
                    MockModelDM.return_value = mock_model_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                            mock_deploy_dm = AsyncMock()
                            mock_deploy_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockDeployDM.return_value = mock_deploy_dm

                            await service._execute_custom_probe_workflow(
                                data=workflow_data,
                                workflow_id=workflow_id,
                                current_user_id=user_id,
                            )

                            # Verify model_id was passed to create_custom_probe_with_rule
                            create_call = mock_deploy_dm.create_custom_probe_with_rule.call_args
                            assert create_call.kwargs.get("model_id") == model_id

    @pytest.mark.asyncio
    async def test_execute_model_id_none_when_model_not_found(self, service, workflow_data):
        """Test that model_id is None when model doesn't exist."""
        user_id = uuid4()
        workflow_id = uuid4()
        probe_id = uuid4()
        provider_id = uuid4()

        mock_workflow = Mock()
        mock_workflow.id = workflow_id

        mock_step = Mock()
        mock_step.data = workflow_data

        mock_probe = Mock()
        mock_probe.id = probe_id

        mock_provider = Mock()
        mock_provider.id = provider_id

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                    mock_model_dm = AsyncMock()
                    mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)
                    MockModelDM.return_value = mock_model_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                            mock_deploy_dm = AsyncMock()
                            mock_deploy_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockDeployDM.return_value = mock_deploy_dm

                            await service._execute_custom_probe_workflow(
                                data=workflow_data,
                                workflow_id=workflow_id,
                                current_user_id=user_id,
                            )

                            # Verify model_id was None
                            create_call = mock_deploy_dm.create_custom_probe_with_rule.call_args
                            assert create_call.kwargs.get("model_id") is None

    @pytest.mark.asyncio
    async def test_execute_marks_workflow_completed_on_success(self, service, workflow_data):
        """Test that workflow is marked COMPLETED on success."""
        user_id = uuid4()
        workflow_id = uuid4()
        probe_id = uuid4()
        provider_id = uuid4()

        mock_workflow = Mock()
        mock_workflow.id = workflow_id

        mock_step = Mock()
        mock_step.data = workflow_data

        mock_probe = Mock()
        mock_probe.id = probe_id

        mock_provider = Mock()
        mock_provider.id = provider_id

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                    mock_model_dm = AsyncMock()
                    mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)
                    MockModelDM.return_value = mock_model_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                            mock_deploy_dm = AsyncMock()
                            mock_deploy_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockDeployDM.return_value = mock_deploy_dm

                            await service._execute_custom_probe_workflow(
                                data=workflow_data,
                                workflow_id=workflow_id,
                                current_user_id=user_id,
                            )

                            # Verify workflow was marked completed
                            update_calls = mock_wf_dm.update_by_fields.call_args_list
                            status_update = [
                                call
                                for call in update_calls
                                if "status" in call[0][1] and call[0][1]["status"] == WorkflowStatusEnum.COMPLETED
                            ]
                            assert len(status_update) == 1

    @pytest.mark.asyncio
    async def test_execute_marks_workflow_failed_on_error(self, service, workflow_data):
        """Test that workflow is marked FAILED on error."""
        user_id = uuid4()
        workflow_id = uuid4()
        provider_id = uuid4()

        mock_workflow = Mock()
        mock_workflow.id = workflow_id

        mock_step = Mock()
        mock_step.data = workflow_data

        mock_provider = Mock()
        mock_provider.id = provider_id

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                    mock_model_dm = AsyncMock()
                    mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)
                    MockModelDM.return_value = mock_model_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                            mock_deploy_dm = AsyncMock()
                            mock_deploy_dm.create_custom_probe_with_rule = AsyncMock(
                                side_effect=Exception("Database error")
                            )
                            MockDeployDM.return_value = mock_deploy_dm

                            await service._execute_custom_probe_workflow(
                                data=workflow_data,
                                workflow_id=workflow_id,
                                current_user_id=user_id,
                            )

                            # Verify workflow was marked failed
                            update_calls = mock_wf_dm.update_by_fields.call_args_list
                            status_update = [
                                call
                                for call in update_calls
                                if "status" in call[0][1] and call[0][1]["status"] == WorkflowStatusEnum.FAILED
                            ]
                            assert len(status_update) == 1

    @pytest.mark.asyncio
    async def test_execute_builds_llm_config_correctly(self, service, workflow_data):
        """Test that LLMConfig is built correctly with handler and policy."""
        user_id = uuid4()
        workflow_id = uuid4()
        probe_id = uuid4()
        provider_id = uuid4()

        mock_workflow = Mock()
        mock_workflow.id = workflow_id

        mock_step = Mock()
        mock_step.data = workflow_data

        mock_probe = Mock()
        mock_probe.id = probe_id

        mock_provider = Mock()
        mock_provider.id = provider_id

        with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
            mock_wf_dm = AsyncMock()
            mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
            mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
            MockWorkflowDM.return_value = mock_wf_dm

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step])
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                    mock_model_dm = AsyncMock()
                    mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)
                    MockModelDM.return_value = mock_model_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockDeployDM:
                            mock_deploy_dm = AsyncMock()
                            mock_deploy_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockDeployDM.return_value = mock_deploy_dm

                            await service._execute_custom_probe_workflow(
                                data=workflow_data,
                                workflow_id=workflow_id,
                                current_user_id=user_id,
                            )

                            # Verify model_config structure
                            create_call = mock_deploy_dm.create_custom_probe_with_rule.call_args
                            model_config = create_call.kwargs.get("model_config")

                            assert model_config is not None
                            assert model_config.get("handler") == "gpt_safeguard"
                            assert "policy" in model_config
                            assert model_config["policy"]["task"] == "Evaluate content"
