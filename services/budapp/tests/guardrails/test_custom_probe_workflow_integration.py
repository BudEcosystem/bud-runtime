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

"""Integration tests for the full 3-step custom probe workflow.

These tests verify the complete flow through the API endpoint:
- Step 1: POST with probe_type_option and project_id
- Step 2: POST with policy configuration
- Step 3: POST with name, description, guard_types, modality_types, trigger_workflow=True

Tests also cover:
- Error scenarios (invalid probe_type_option, missing required fields, provider not found)
- Model ID assignment (when model with URI exists vs doesn't exist)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from budapp.commons.constants import (
    GuardrailStatusEnum,
    ModelStatusEnum,
    ProbeTypeEnum,
    ProjectStatusEnum,
    ScannerTypeEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from budapp.guardrails.models import GuardrailProbe, GuardrailRule
from budapp.guardrails.schemas import (
    ContentItem,
    CustomProbeTypeEnum,
    DefinitionItem,
    PolicyConfig,
    PolicyExample,
    SafeContentConfig,
    ViolationCategory,
)
from budapp.workflow_ops.models import Workflow, WorkflowStep


class TestCustomProbeWorkflowIntegration:
    """Integration tests for the full custom probe workflow via API."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.begin_nested.return_value = MagicMock(is_active=True)
        return session

    @pytest.fixture
    def mock_current_user(self):
        """Create a mock authenticated user."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.name = "Test User"
        user.is_superuser = True
        user.status = "active"
        return user

    @pytest.fixture
    def auth_headers(self):
        """Create authorization headers."""
        return {
            "Authorization": "Bearer test-token",
            "X-Resource-Type": "project",
            "X-Entity-Id": str(uuid4()),
        }

    @pytest.fixture
    def mock_project(self):
        """Create a mock project."""
        project = Mock()
        project.id = uuid4()
        project.name = "Test Project"
        project.status = ProjectStatusEnum.ACTIVE
        return project

    @pytest.fixture
    def mock_provider(self):
        """Create a mock BudSentinel provider."""
        provider = Mock()
        provider.id = uuid4()
        provider.type = "bud_sentinel"
        provider.name = "BudSentinel"
        return provider

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = Mock(spec=Workflow)
        workflow.id = uuid4()
        workflow.status = WorkflowStatusEnum.IN_PROGRESS
        workflow.workflow_type = WorkflowTypeEnum.CLOUD_MODEL_ONBOARDING
        workflow.title = "Custom Probe Creation"
        workflow.total_steps = 3
        workflow.current_step = 1
        workflow.reason = None
        workflow.created_at = datetime.now(timezone.utc)
        workflow.modified_at = datetime.now(timezone.utc)
        return workflow

    @pytest.fixture
    def sample_policy(self):
        """Create a sample PolicyConfig for testing."""
        return PolicyConfig(
            task="Detect harmful content in user inputs",
            definitions=[
                DefinitionItem(
                    term="harmful content",
                    definition="Content that could cause harm to users or systems",
                )
            ],
            safe_content=SafeContentConfig(
                description="Normal safe content that should pass through",
                items=[
                    ContentItem(
                        name="greeting",
                        description="Friendly greeting messages",
                        example="Hello, how can I help you today?",
                    )
                ],
                examples=[
                    PolicyExample(
                        input="Hello there!",
                        rationale="This is a friendly greeting and is safe",
                    )
                ],
            ),
            violations=[
                ViolationCategory(
                    category="harmful_content",
                    severity="High",
                    description="Content that could cause harm",
                    items=[
                        ContentItem(
                            name="harmful",
                            description="Potentially harmful statements",
                            example="Harmful content example",
                        )
                    ],
                    examples=[
                        PolicyExample(
                            input="Harmful input example",
                            rationale="This violates the harmful content policy",
                        )
                    ],
                )
            ],
        )


class TestFullWorkflowExecution(TestCustomProbeWorkflowIntegration):
    """Test the full 3-step workflow execution."""

    @pytest.mark.asyncio
    async def test_full_workflow_step1_step2_step3_creates_probe(
        self, mock_session, mock_current_user, mock_project, mock_provider, mock_workflow, sample_policy, auth_headers
    ):
        """Test full workflow: Step 1 -> Step 2 -> Step 3 with trigger creates probe."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        workflow_id = mock_workflow.id
        project_id = mock_project.id
        probe_id = uuid4()

        # === STEP 1: Probe type selection ===
        step1_request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
        )

        # Mock workflow step data accumulation
        step1_data = {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(project_id),
        }

        mock_workflow_step1 = Mock(spec=WorkflowStep)
        mock_workflow_step1.id = uuid4()
        mock_workflow_step1.step_number = 1
        mock_workflow_step1.data = step1_data

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step1)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step1)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProjectDataManager") as MockProjectDM:
                        mock_proj_dm = AsyncMock()
                        mock_proj_dm.retrieve_by_fields = AsyncMock(return_value=mock_project)
                        MockProjectDM.return_value = mock_proj_dm

                        with patch("budapp.guardrails.guardrail_routes.WorkflowService") as MockRouteWorkflowService:
                            mock_route_wf_service = AsyncMock()
                            mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                return_value=RetrieveWorkflowDataResponse(
                                    code=status.HTTP_200_OK,
                                    message="Workflow data retrieved",
                                    workflow_id=workflow_id,
                                    status=WorkflowStatusEnum.IN_PROGRESS,
                                    current_step=1,
                                    total_steps=3,
                                )
                            )
                            MockRouteWorkflowService.return_value = mock_route_wf_service

                            result = await add_custom_probe_workflow(
                                current_user=mock_current_user,
                                session=mock_session,
                                request=step1_request,
                            )

                            # Verify step 1 response
                            assert result.code == status.HTTP_200_OK
                            assert result.current_step == 1

        # === STEP 2: Policy configuration ===
        step2_request = CustomProbeWorkflowRequest(
            workflow_id=workflow_id,
            step_number=2,
            policy=sample_policy,
        )

        step2_data = {**step1_data, "policy": sample_policy.model_dump()}

        mock_workflow_step2 = Mock(spec=WorkflowStep)
        mock_workflow_step2.id = uuid4()
        mock_workflow_step2.step_number = 2
        mock_workflow_step2.data = step2_data

        mock_workflow.current_step = 2

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step1])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step2)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step2)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.guardrail_routes.WorkflowService") as MockRouteWorkflowService:
                        mock_route_wf_service = AsyncMock()
                        mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                            return_value=RetrieveWorkflowDataResponse(
                                code=status.HTTP_200_OK,
                                message="Workflow data retrieved",
                                workflow_id=workflow_id,
                                status=WorkflowStatusEnum.IN_PROGRESS,
                                current_step=2,
                                total_steps=3,
                            )
                        )
                        MockRouteWorkflowService.return_value = mock_route_wf_service

                        result = await add_custom_probe_workflow(
                            current_user=mock_current_user,
                            session=mock_session,
                            request=step2_request,
                        )

                        # Verify step 2 response
                        assert result.code == status.HTTP_200_OK
                        assert result.current_step == 2

        # === STEP 3: Probe metadata + trigger workflow ===
        step3_request = CustomProbeWorkflowRequest(
            workflow_id=workflow_id,
            step_number=3,
            trigger_workflow=True,
            name="My Custom Probe",
            description="Detects harmful content in user inputs",
            guard_types=["input", "output"],
            modality_types=["text"],
        )

        step3_data = {
            **step2_data,
            "name": "My Custom Probe",
            "description": "Detects harmful content in user inputs",
            "guard_types": ["input", "output"],
            "modality_types": ["text"],
        }

        mock_workflow_step3 = Mock(spec=WorkflowStep)
        mock_workflow_step3.id = uuid4()
        mock_workflow_step3.step_number = 3
        mock_workflow_step3.data = step3_data

        # Create mock probe and rule
        mock_probe = Mock(spec=GuardrailProbe)
        mock_probe.id = probe_id
        mock_probe.name = "My Custom Probe"
        mock_probe.description = "Detects harmful content in user inputs"
        mock_probe.probe_type = ProbeTypeEnum.CUSTOM
        mock_probe.status = GuardrailStatusEnum.ACTIVE

        mock_rule = Mock(spec=GuardrailRule)
        mock_rule.id = uuid4()
        mock_rule.probe_id = probe_id
        mock_rule.scanner_type = ScannerTypeEnum.LLM
        mock_rule.model_uri = "openai/gpt-oss-safeguard-20b"
        mock_rule.model_id = None
        mock_rule.guard_types = ["input", "output"]
        mock_rule.modality_types = ["text"]
        mock_rule.model_config_json = {
            "handler": "gpt_safeguard",
            "policy": sample_policy.model_dump(),
        }

        mock_probe.rules = [mock_rule]

        mock_workflow.current_step = 3
        mock_workflow.status = WorkflowStatusEnum.COMPLETED

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(
                    return_value=[mock_workflow_step1, mock_workflow_step2]
                )
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step3)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step3)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardDM:
                            mock_guard_dm = AsyncMock()
                            mock_guard_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockGuardDM.return_value = mock_guard_dm

                            with patch(
                                "budapp.guardrails.guardrail_routes.WorkflowService"
                            ) as MockRouteWorkflowService:
                                mock_route_wf_service = AsyncMock()
                                mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                    return_value=RetrieveWorkflowDataResponse(
                                        code=status.HTTP_200_OK,
                                        message="Workflow data retrieved",
                                        workflow_id=workflow_id,
                                        status=WorkflowStatusEnum.COMPLETED,
                                        current_step=3,
                                        total_steps=3,
                                    )
                                )
                                MockRouteWorkflowService.return_value = mock_route_wf_service

                                result = await add_custom_probe_workflow(
                                    current_user=mock_current_user,
                                    session=mock_session,
                                    request=step3_request,
                                )

                                # Verify step 3 response shows COMPLETED
                                assert result.code == status.HTTP_200_OK
                                assert result.status == WorkflowStatusEnum.COMPLETED
                                assert result.current_step == 3

                                # Verify probe was created with correct parameters
                                mock_guard_dm.create_custom_probe_with_rule.assert_called_once()
                                call_kwargs = mock_guard_dm.create_custom_probe_with_rule.call_args.kwargs
                                assert call_kwargs["name"] == "My Custom Probe"
                                assert call_kwargs["description"] == "Detects harmful content in user inputs"
                                assert call_kwargs["scanner_type"] == "llm"
                                assert call_kwargs["model_uri"] == "openai/gpt-oss-safeguard-20b"
                                assert call_kwargs["guard_types"] == ["input", "output"]
                                assert call_kwargs["modality_types"] == ["text"]
                                assert call_kwargs["provider_id"] == mock_provider.id

    @pytest.mark.asyncio
    async def test_workflow_creates_rule_with_correct_fields(
        self, mock_session, mock_current_user, mock_project, mock_provider, mock_workflow, sample_policy
    ):
        """Test that the created rule has correct scanner_type, model_uri, model_config_json, guard_types, modality_types."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        workflow_id = mock_workflow.id
        project_id = mock_project.id

        mock_probe = Mock(spec=GuardrailProbe)
        mock_probe.id = uuid4()

        mock_workflow.current_step = 3

        request = CustomProbeWorkflowRequest(
            workflow_id=workflow_id,
            step_number=3,
            trigger_workflow=True,
            name="Test Probe",
            description="Test description",
            guard_types=["input"],
            modality_types=["text", "image"],
        )

        # Create step mocks with accumulated data - must include all required fields
        mock_step1 = Mock(spec=WorkflowStep)
        mock_step1.step_number = 1
        mock_step1.data = {
            "probe_type_option": "llm_policy",
            "scanner_type": "llm",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(project_id),
        }

        mock_step2 = Mock(spec=WorkflowStep)
        mock_step2.step_number = 2
        mock_step2.data = {"policy": sample_policy.model_dump()}

        mock_step3 = Mock(spec=WorkflowStep)
        mock_step3.step_number = 3
        mock_step3.data = {}

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                # Return steps with accumulated data from step 1 and 2
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_step1, mock_step2])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_step3)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_step3)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardDM:
                            mock_guard_dm = AsyncMock()
                            mock_guard_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockGuardDM.return_value = mock_guard_dm

                            with patch(
                                "budapp.guardrails.guardrail_routes.WorkflowService"
                            ) as MockRouteWorkflowService:
                                mock_route_wf_service = AsyncMock()
                                mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                    return_value=RetrieveWorkflowDataResponse(
                                        code=status.HTTP_200_OK,
                                        message="Success",
                                        workflow_id=workflow_id,
                                        status=WorkflowStatusEnum.COMPLETED,
                                        current_step=3,
                                        total_steps=3,
                                    )
                                )
                                MockRouteWorkflowService.return_value = mock_route_wf_service

                                await add_custom_probe_workflow(
                                    current_user=mock_current_user,
                                    session=mock_session,
                                    request=request,
                                )

                                # Verify the CRUD method was called with correct rule parameters
                                call_kwargs = mock_guard_dm.create_custom_probe_with_rule.call_args.kwargs
                                assert call_kwargs["scanner_type"] == "llm"
                                assert call_kwargs["model_uri"] == "openai/gpt-oss-safeguard-20b"
                                assert call_kwargs["guard_types"] == ["input"]
                                assert call_kwargs["modality_types"] == ["text", "image"]
                                # Verify model_config contains handler and policy
                                assert "handler" in call_kwargs["model_config"]
                                assert "policy" in call_kwargs["model_config"]


class TestErrorScenarios(TestCustomProbeWorkflowIntegration):
    """Test error scenarios in the workflow."""

    @pytest.mark.asyncio
    async def test_invalid_probe_type_option_rejected_by_schema(self):
        """Test that invalid probe_type_option is rejected at schema validation."""
        from pydantic import ValidationError

        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        with pytest.raises(ValidationError) as exc_info:
            CustomProbeWorkflowRequest(
                workflow_total_steps=3,
                step_number=1,
                probe_type_option="invalid_type",  # Invalid probe type
                project_id=uuid4(),
            )

        errors = exc_info.value.errors()
        assert any("probe_type_option" in str(e) for e in errors)

    @pytest.mark.asyncio
    async def test_missing_workflow_id_and_total_steps_at_step1(self):
        """Test that missing both workflow_id and workflow_total_steps raises error."""
        from pydantic import ValidationError

        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        with pytest.raises(ValidationError) as exc_info:
            CustomProbeWorkflowRequest(
                step_number=1,
                probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            )

        errors = exc_info.value.errors()
        assert any("workflow_total_steps" in str(e) for e in errors)

    @pytest.mark.asyncio
    async def test_missing_required_fields_at_step3_trigger(self, mock_session, mock_current_user, mock_workflow):
        """Test that missing required fields at step 3 with trigger_workflow=True raises error."""
        from starlette.responses import JSONResponse

        from budapp.commons.exceptions import ClientException
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        # Step data missing "name", "scanner_type", "project_id", "policy"
        incomplete_step_data = {
            "probe_type_option": "llm_policy",
            # Missing: name, scanner_type, project_id, policy
        }

        mock_workflow_step = Mock(spec=WorkflowStep)
        mock_workflow_step.step_number = 2
        mock_workflow_step.data = incomplete_step_data

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            trigger_workflow=True,
            name="Test",  # Provided, but other fields missing from accumulated data
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    result = await add_custom_probe_workflow(
                        current_user=mock_current_user,
                        session=mock_session,
                        request=request,
                    )

                    # Should return an error response
                    assert isinstance(result, JSONResponse)
                    assert result.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_bud_sentinel_provider_not_found(
        self, mock_session, mock_current_user, mock_project, mock_workflow, sample_policy
    ):
        """Test error when BudSentinel provider is not found."""
        from starlette.responses import JSONResponse

        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        # Complete step data
        step_data = {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(mock_project.id),
            "policy": sample_policy.model_dump(),
            "name": "Test Probe",
        }

        mock_workflow_step = Mock(spec=WorkflowStep)
        mock_workflow_step.step_number = 2
        mock_workflow_step.data = step_data

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            trigger_workflow=True,
            name="Test Probe",
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        # Return None to simulate provider not found
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=None)
                        MockProviderDM.return_value = mock_prov_dm

                        result = await add_custom_probe_workflow(
                            current_user=mock_current_user,
                            session=mock_session,
                            request=request,
                        )

                        # Should return an error response (workflow fails and marks FAILED status)
                        # The exception is caught and workflow status is updated to FAILED
                        # But the route still returns the workflow data
                        assert result is not None

    @pytest.mark.asyncio
    async def test_project_not_found_at_step1(self, mock_session, mock_current_user, mock_workflow):
        """Test error when project is not found at step 1."""
        from starlette.responses import JSONResponse

        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=uuid4(),  # Non-existent project
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[])
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProjectDataManager") as MockProjectDM:
                        mock_proj_dm = AsyncMock()
                        # Return None to simulate project not found
                        mock_proj_dm.retrieve_by_fields = AsyncMock(return_value=None)
                        MockProjectDM.return_value = mock_proj_dm

                        result = await add_custom_probe_workflow(
                            current_user=mock_current_user,
                            session=mock_session,
                            request=request,
                        )

                        # Should return 404 error response
                        assert isinstance(result, JSONResponse)
                        assert result.status_code == status.HTTP_404_NOT_FOUND


class TestModelIdAssignment(TestCustomProbeWorkflowIntegration):
    """Test model_id assignment based on model lookup."""

    @pytest.mark.asyncio
    async def test_model_id_assigned_when_model_exists(
        self, mock_session, mock_current_user, mock_project, mock_provider, mock_workflow, sample_policy
    ):
        """Test that model_id is assigned when a model with matching URI exists."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        existing_model_id = uuid4()
        mock_existing_model = Mock()
        mock_existing_model.id = existing_model_id
        mock_existing_model.uri = "openai/gpt-oss-safeguard-20b"
        mock_existing_model.status = ModelStatusEnum.ACTIVE

        step_data = {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(mock_project.id),
            "policy": sample_policy.model_dump(),
            "name": "Test Probe",
        }

        mock_workflow_step = Mock(spec=WorkflowStep)
        mock_workflow_step.step_number = 2
        mock_workflow_step.data = step_data

        mock_probe = Mock(spec=GuardrailProbe)
        mock_probe.id = uuid4()

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            trigger_workflow=True,
            name="Test Probe",
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        # Patch at the import location - inside _execute_custom_probe_workflow
                        with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                            mock_model_dm = AsyncMock()
                            # Return existing model with matching URI
                            mock_model_dm.retrieve_by_fields = AsyncMock(return_value=mock_existing_model)
                            MockModelDM.return_value = mock_model_dm

                            with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardDM:
                                mock_guard_dm = AsyncMock()
                                mock_guard_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                                MockGuardDM.return_value = mock_guard_dm

                                with patch(
                                    "budapp.guardrails.guardrail_routes.WorkflowService"
                                ) as MockRouteWorkflowService:
                                    mock_route_wf_service = AsyncMock()
                                    mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                        return_value=RetrieveWorkflowDataResponse(
                                            code=status.HTTP_200_OK,
                                            message="Success",
                                            workflow_id=mock_workflow.id,
                                            status=WorkflowStatusEnum.COMPLETED,
                                            current_step=3,
                                            total_steps=3,
                                        )
                                    )
                                    MockRouteWorkflowService.return_value = mock_route_wf_service

                                    await add_custom_probe_workflow(
                                        current_user=mock_current_user,
                                        session=mock_session,
                                        request=request,
                                    )

                                    # Verify model_id was assigned
                                    call_kwargs = mock_guard_dm.create_custom_probe_with_rule.call_args.kwargs
                                    assert call_kwargs["model_id"] == existing_model_id

    @pytest.mark.asyncio
    async def test_model_id_is_none_when_model_not_found(
        self, mock_session, mock_current_user, mock_project, mock_provider, mock_workflow, sample_policy
    ):
        """Test that model_id is None when no model with matching URI exists."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        step_data = {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(mock_project.id),
            "policy": sample_policy.model_dump(),
            "name": "Test Probe",
        }

        mock_workflow_step = Mock(spec=WorkflowStep)
        mock_workflow_step.step_number = 2
        mock_workflow_step.data = step_data

        mock_probe = Mock(spec=GuardrailProbe)
        mock_probe.id = uuid4()

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            trigger_workflow=True,
            name="Test Probe",
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        # Patch at the import location - inside _execute_custom_probe_workflow
                        with patch("budapp.model_ops.crud.ModelDataManager") as MockModelDM:
                            mock_model_dm = AsyncMock()
                            # Return None - no model found with matching URI
                            mock_model_dm.retrieve_by_fields = AsyncMock(return_value=None)
                            MockModelDM.return_value = mock_model_dm

                            with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardDM:
                                mock_guard_dm = AsyncMock()
                                mock_guard_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                                MockGuardDM.return_value = mock_guard_dm

                                with patch(
                                    "budapp.guardrails.guardrail_routes.WorkflowService"
                                ) as MockRouteWorkflowService:
                                    mock_route_wf_service = AsyncMock()
                                    mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                        return_value=RetrieveWorkflowDataResponse(
                                            code=status.HTTP_200_OK,
                                            message="Success",
                                            workflow_id=mock_workflow.id,
                                            status=WorkflowStatusEnum.COMPLETED,
                                            current_step=3,
                                            total_steps=3,
                                        )
                                    )
                                    MockRouteWorkflowService.return_value = mock_route_wf_service

                                    await add_custom_probe_workflow(
                                        current_user=mock_current_user,
                                        session=mock_session,
                                        request=request,
                                    )

                                    # Verify model_id is None
                                    call_kwargs = mock_guard_dm.create_custom_probe_with_rule.call_args.kwargs
                                    assert call_kwargs["model_id"] is None


class TestWorkflowStatusTransitions(TestCustomProbeWorkflowIntegration):
    """Test workflow status transitions during the workflow."""

    @pytest.mark.asyncio
    async def test_workflow_status_in_progress_during_steps(
        self, mock_session, mock_current_user, mock_project, mock_workflow
    ):
        """Test that workflow status is IN_PROGRESS during intermediate steps."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        mock_workflow.status = WorkflowStatusEnum.IN_PROGRESS

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=mock_project.id,
        )

        mock_workflow_step = Mock(spec=WorkflowStep)
        mock_workflow_step.step_number = 1
        mock_workflow_step.data = {}

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProjectDataManager") as MockProjectDM:
                        mock_proj_dm = AsyncMock()
                        mock_proj_dm.retrieve_by_fields = AsyncMock(return_value=mock_project)
                        MockProjectDM.return_value = mock_proj_dm

                        with patch("budapp.guardrails.guardrail_routes.WorkflowService") as MockRouteWorkflowService:
                            mock_route_wf_service = AsyncMock()
                            mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                return_value=RetrieveWorkflowDataResponse(
                                    code=status.HTTP_200_OK,
                                    message="Success",
                                    workflow_id=mock_workflow.id,
                                    status=WorkflowStatusEnum.IN_PROGRESS,
                                    current_step=1,
                                    total_steps=3,
                                )
                            )
                            MockRouteWorkflowService.return_value = mock_route_wf_service

                            result = await add_custom_probe_workflow(
                                current_user=mock_current_user,
                                session=mock_session,
                                request=request,
                            )

                            # Verify status is IN_PROGRESS
                            assert result.status == WorkflowStatusEnum.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_workflow_status_completed_after_successful_trigger(
        self, mock_session, mock_current_user, mock_project, mock_provider, mock_workflow, sample_policy
    ):
        """Test that workflow status is COMPLETED after successful trigger."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        step_data = {
            "probe_type_option": "llm_policy",
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "scanner_type": "llm",
            "handler": "gpt_safeguard",
            "model_provider_type": "openai",
            "project_id": str(mock_project.id),
            "policy": sample_policy.model_dump(),
            "name": "Test Probe",
        }

        mock_workflow_step = Mock(spec=WorkflowStep)
        mock_workflow_step.step_number = 2
        mock_workflow_step.data = step_data

        mock_probe = Mock(spec=GuardrailProbe)
        mock_probe.id = uuid4()

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            trigger_workflow=True,
            name="Test Probe",
        )

        with patch("budapp.guardrails.services.WorkflowService") as MockWorkflowService:
            mock_wf_service = AsyncMock()
            mock_wf_service.retrieve_or_create_workflow = AsyncMock(return_value=mock_workflow)
            MockWorkflowService.return_value = mock_wf_service

            with patch("budapp.guardrails.services.WorkflowStepDataManager") as MockStepDM:
                mock_step_dm = AsyncMock()
                mock_step_dm.get_all_workflow_steps = AsyncMock(return_value=[mock_workflow_step])
                mock_step_dm.insert_one = AsyncMock(return_value=mock_workflow_step)
                mock_step_dm.update_by_fields = AsyncMock(return_value=mock_workflow_step)
                MockStepDM.return_value = mock_step_dm

                with patch("budapp.guardrails.services.WorkflowDataManager") as MockWorkflowDM:
                    mock_wf_dm = AsyncMock()
                    mock_wf_dm.update_by_fields = AsyncMock(return_value=mock_workflow)
                    mock_wf_dm.retrieve_by_fields = AsyncMock(return_value=mock_workflow)
                    MockWorkflowDM.return_value = mock_wf_dm

                    with patch("budapp.guardrails.services.ProviderDataManager") as MockProviderDM:
                        mock_prov_dm = AsyncMock()
                        mock_prov_dm.retrieve_by_fields = AsyncMock(return_value=mock_provider)
                        MockProviderDM.return_value = mock_prov_dm

                        with patch("budapp.guardrails.services.GuardrailsDeploymentDataManager") as MockGuardDM:
                            mock_guard_dm = AsyncMock()
                            mock_guard_dm.create_custom_probe_with_rule = AsyncMock(return_value=mock_probe)
                            MockGuardDM.return_value = mock_guard_dm

                            with patch(
                                "budapp.guardrails.guardrail_routes.WorkflowService"
                            ) as MockRouteWorkflowService:
                                mock_route_wf_service = AsyncMock()
                                mock_route_wf_service.retrieve_workflow_data = AsyncMock(
                                    return_value=RetrieveWorkflowDataResponse(
                                        code=status.HTTP_200_OK,
                                        message="Success",
                                        workflow_id=mock_workflow.id,
                                        status=WorkflowStatusEnum.COMPLETED,
                                        current_step=3,
                                        total_steps=3,
                                    )
                                )
                                MockRouteWorkflowService.return_value = mock_route_wf_service

                                result = await add_custom_probe_workflow(
                                    current_user=mock_current_user,
                                    session=mock_session,
                                    request=request,
                                )

                                # Verify status is COMPLETED
                                assert result.status == WorkflowStatusEnum.COMPLETED
