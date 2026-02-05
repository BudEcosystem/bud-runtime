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

"""Unit tests for custom probe workflow route endpoint."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from budapp.commons.constants import WorkflowStatusEnum
from budapp.commons.exceptions import ClientException
from budapp.guardrails.schemas import CustomProbeTypeEnum


class TestCustomProbeWorkflowRoute:
    """Tests for POST /guardrails/custom-probe-workflow endpoint."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.name = "Test User"
        return user

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow model."""
        workflow = Mock()
        workflow.id = uuid4()
        workflow.status = WorkflowStatusEnum.IN_PROGRESS
        workflow.title = "Custom Probe Creation"
        workflow.total_steps = 3
        workflow.current_step_number = 1
        workflow.workflow_type = "cloud_model_onboarding"
        workflow.tag = "Custom Probe"
        workflow.created_at = datetime.now(timezone.utc)
        workflow.modified_at = datetime.now(timezone.utc)
        return workflow

    @pytest.fixture
    def mock_workflow_data_response(self, mock_workflow):
        """Create a mock RetrieveWorkflowDataResponse."""
        from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse

        return RetrieveWorkflowDataResponse(
            code=status.HTTP_200_OK,
            message="Workflow data retrieved successfully",
            workflow_id=mock_workflow.id,
            status=mock_workflow.status,
            current_step=mock_workflow.current_step_number,
            total_steps=mock_workflow.total_steps,
        )

    @pytest.mark.asyncio
    async def test_add_custom_probe_workflow_success_step1(
        self,
        mock_session,
        mock_user,
        mock_workflow,
        mock_workflow_data_response,
    ):
        """Test successful custom probe workflow creation - Step 1."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=uuid4(),
        )

        with patch("budapp.guardrails.guardrail_routes.GuardrailCustomProbeService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.add_custom_probe_workflow.return_value = mock_workflow

            with patch("budapp.guardrails.guardrail_routes.WorkflowService") as MockWorkflowService:
                mock_wf_service = AsyncMock()
                MockWorkflowService.return_value = mock_wf_service
                mock_wf_service.retrieve_workflow_data.return_value = mock_workflow_data_response

                result = await add_custom_probe_workflow(
                    current_user=mock_user,
                    session=mock_session,
                    request=request,
                )

        # Verify service was called correctly
        MockService.assert_called_once_with(mock_session)
        mock_service.add_custom_probe_workflow.assert_called_once_with(
            current_user_id=mock_user.id,
            request=request,
        )
        MockWorkflowService.assert_called_once_with(mock_session)
        mock_wf_service.retrieve_workflow_data.assert_called_once_with(mock_workflow.id)

        # Verify response is the expected schema object
        assert result == mock_workflow_data_response

    @pytest.mark.asyncio
    async def test_add_custom_probe_workflow_client_exception(
        self,
        mock_session,
        mock_user,
    ):
        """Test custom probe workflow returns error response on ClientException."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
        )

        with patch("budapp.guardrails.guardrail_routes.GuardrailCustomProbeService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.add_custom_probe_workflow.side_effect = ClientException(
                message="Project not found or is not active",
                status_code=status.HTTP_404_NOT_FOUND,
            )

            result = await add_custom_probe_workflow(
                current_user=mock_user,
                session=mock_session,
                request=request,
            )

        # Result is a JSONResponse from ErrorResponse.to_http_response()
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_add_custom_probe_workflow_generic_exception(
        self,
        mock_session,
        mock_user,
    ):
        """Test custom probe workflow returns 500 on generic exception."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
        )

        with patch("budapp.guardrails.guardrail_routes.GuardrailCustomProbeService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.add_custom_probe_workflow.side_effect = Exception("Unexpected database error")

            result = await add_custom_probe_workflow(
                current_user=mock_user,
                session=mock_session,
                request=request,
            )

        # Result is a JSONResponse from ErrorResponse.to_http_response()
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_add_custom_probe_workflow_success_step2(
        self,
        mock_session,
        mock_user,
        mock_workflow,
        mock_workflow_data_response,
    ):
        """Test successful custom probe workflow - Step 2 (policy configuration)."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import (
            ContentItem,
            CustomProbeWorkflowRequest,
            DefinitionItem,
            PolicyConfig,
            PolicyExample,
            SafeContentConfig,
        )

        policy = PolicyConfig(
            task="Detect harmful content",
            definitions=[DefinitionItem(term="harmful", definition="Content that is dangerous")],
            safe_content=SafeContentConfig(
                description="Normal safe content",
                items=[ContentItem(name="greeting", description="Hello messages", example="Hello!")],
                examples=[PolicyExample(input="Hello there", rationale="This is a greeting")],
            ),
            violations=[],
        )

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=2,
            policy=policy,
        )

        with patch("budapp.guardrails.guardrail_routes.GuardrailCustomProbeService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.add_custom_probe_workflow.return_value = mock_workflow

            with patch("budapp.guardrails.guardrail_routes.WorkflowService") as MockWorkflowService:
                mock_wf_service = AsyncMock()
                MockWorkflowService.return_value = mock_wf_service
                mock_wf_service.retrieve_workflow_data.return_value = mock_workflow_data_response

                result = await add_custom_probe_workflow(
                    current_user=mock_user,
                    session=mock_session,
                    request=request,
                )

        # Verify the service was called
        mock_service.add_custom_probe_workflow.assert_called_once()
        assert result == mock_workflow_data_response

    @pytest.mark.asyncio
    async def test_add_custom_probe_workflow_success_step3_trigger(
        self,
        mock_session,
        mock_user,
        mock_workflow,
        mock_workflow_data_response,
    ):
        """Test successful custom probe workflow - Step 3 with trigger_workflow=True."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        request = CustomProbeWorkflowRequest(
            workflow_id=mock_workflow.id,
            step_number=3,
            trigger_workflow=True,
            name="My Custom Probe",
            description="A custom probe for policy enforcement",
            guard_types=["input", "output"],
            modality_types=["text"],
        )

        with patch("budapp.guardrails.guardrail_routes.GuardrailCustomProbeService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.add_custom_probe_workflow.return_value = mock_workflow

            with patch("budapp.guardrails.guardrail_routes.WorkflowService") as MockWorkflowService:
                mock_wf_service = AsyncMock()
                MockWorkflowService.return_value = mock_wf_service
                mock_wf_service.retrieve_workflow_data.return_value = mock_workflow_data_response

                result = await add_custom_probe_workflow(
                    current_user=mock_user,
                    session=mock_session,
                    request=request,
                )

        # Verify trigger_workflow was included in request
        call_args = mock_service.add_custom_probe_workflow.call_args
        assert call_args.kwargs["request"].trigger_workflow is True
        assert call_args.kwargs["request"].name == "My Custom Probe"
        assert result == mock_workflow_data_response

    @pytest.mark.asyncio
    async def test_add_custom_probe_workflow_client_exception_preserves_status_code(
        self,
        mock_session,
        mock_user,
    ):
        """Test that ClientException status code is preserved in the error response."""
        from budapp.guardrails.guardrail_routes import add_custom_probe_workflow
        from budapp.guardrails.schemas import CustomProbeWorkflowRequest

        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
        )

        # Test with a different status code (400)
        with patch("budapp.guardrails.guardrail_routes.GuardrailCustomProbeService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.add_custom_probe_workflow.side_effect = ClientException(
                message="Invalid probe type",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

            result = await add_custom_probe_workflow(
                current_user=mock_user,
                session=mock_session,
                request=request,
            )

        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
