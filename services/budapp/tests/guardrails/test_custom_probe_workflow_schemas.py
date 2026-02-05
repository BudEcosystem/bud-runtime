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

"""Unit tests for custom probe workflow schemas."""

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from budapp.commons.constants import ProbeTypeEnum, ScannerTypeEnum
from budapp.guardrails.schemas import (
    ContentItem,
    CustomProbeTypeEnum,
    CustomProbeWorkflowRequest,
    CustomProbeWorkflowSteps,
    DefinitionItem,
    GuardrailCustomProbeResponse,
    PolicyConfig,
    PolicyExample,
    SafeContentConfig,
    ViolationCategory,
)


class TestCustomProbeTypeEnum:
    """Tests for CustomProbeTypeEnum enum."""

    def test_enum_has_llm_policy_value(self):
        """Test that LLM_POLICY enum value exists."""
        assert CustomProbeTypeEnum.LLM_POLICY.value == "llm_policy"

    def test_enum_is_string_enum(self):
        """Test that enum values are strings."""
        for probe_type in CustomProbeTypeEnum:
            assert isinstance(probe_type.value, str)

    def test_enum_comparison(self):
        """Test enum comparison works correctly."""
        assert CustomProbeTypeEnum.LLM_POLICY == "llm_policy"

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        probe_type = CustomProbeTypeEnum("llm_policy")
        assert probe_type == CustomProbeTypeEnum.LLM_POLICY

    def test_enum_invalid_value(self):
        """Test that invalid values raise error."""
        with pytest.raises(ValueError):
            CustomProbeTypeEnum("invalid_type")


class TestCustomProbeWorkflowRequest:
    """Tests for CustomProbeWorkflowRequest schema."""

    def test_create_new_workflow_step1(self):
        """Test creating a new workflow at step 1."""
        project_id = uuid4()
        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
        )

        assert request.workflow_id is None
        assert request.workflow_total_steps == 3
        assert request.step_number == 1
        assert request.probe_type_option == CustomProbeTypeEnum.LLM_POLICY
        assert request.project_id == project_id
        assert request.trigger_workflow is False

    def test_continue_workflow_step2(self):
        """Test continuing an existing workflow at step 2."""
        workflow_id = uuid4()
        policy = PolicyConfig(
            task="Test task",
            definitions=[DefinitionItem(term="test", definition="A test definition")],
            safe_content=SafeContentConfig(
                description="Safe content",
                items=[ContentItem(name="safe", description="Safe item", example="Hello")],
                examples=[PolicyExample(input="Hello", rationale="Normal greeting")],
            ),
            violations=[
                ViolationCategory(
                    category="harmful",
                    severity="High",
                    description="Harmful content",
                    items=[ContentItem(name="harm", description="Harmful item", example="Bad")],
                    examples=[PolicyExample(input="Bad", rationale="Harmful")],
                )
            ],
        )

        request = CustomProbeWorkflowRequest(
            workflow_id=workflow_id,
            step_number=2,
            policy=policy,
        )

        assert request.workflow_id == workflow_id
        assert request.workflow_total_steps is None
        assert request.step_number == 2
        assert request.policy == policy

    def test_final_step_with_trigger(self):
        """Test step 3 with trigger_workflow=True."""
        workflow_id = uuid4()

        request = CustomProbeWorkflowRequest(
            workflow_id=workflow_id,
            step_number=3,
            trigger_workflow=True,
            name="My Custom Probe",
            description="Detects harmful content",
            guard_types=["input", "output"],
            modality_types=["text"],
        )

        assert request.workflow_id == workflow_id
        assert request.step_number == 3
        assert request.trigger_workflow is True
        assert request.name == "My Custom Probe"
        assert request.description == "Detects harmful content"
        assert request.guard_types == ["input", "output"]
        assert request.modality_types == ["text"]

    def test_validation_error_missing_workflow_id_and_total_steps(self):
        """Test that missing both workflow_id and workflow_total_steps raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CustomProbeWorkflowRequest(
                step_number=1,
                probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            )

        errors = exc_info.value.errors()
        assert any("workflow_total_steps" in str(e) for e in errors)

    def test_validation_error_both_workflow_id_and_total_steps(self):
        """Test that providing both workflow_id and workflow_total_steps raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CustomProbeWorkflowRequest(
                workflow_id=uuid4(),
                workflow_total_steps=3,
                step_number=1,
            )

        errors = exc_info.value.errors()
        assert any("cannot be provided together" in str(e) for e in errors)

    def test_step_number_must_be_positive(self):
        """Test that step_number must be greater than 0."""
        with pytest.raises(ValidationError) as exc_info:
            CustomProbeWorkflowRequest(
                workflow_total_steps=3,
                step_number=0,
            )

        errors = exc_info.value.errors()
        assert any("step_number" in str(e["loc"]) for e in errors)

    def test_step_number_required(self):
        """Test that step_number is required."""
        with pytest.raises(ValidationError) as exc_info:
            CustomProbeWorkflowRequest(
                workflow_total_steps=3,
            )

        errors = exc_info.value.errors()
        assert any("step_number" in str(e["loc"]) for e in errors)

    def test_all_fields_optional_except_workflow_management(self):
        """Test that step-specific fields are optional."""
        # New workflow with only required fields
        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
        )

        assert request.probe_type_option is None
        assert request.project_id is None
        assert request.policy is None
        assert request.name is None
        assert request.description is None
        assert request.guard_types is None
        assert request.modality_types is None

    def test_serialization(self):
        """Test request serializes correctly."""
        project_id = uuid4()
        request = CustomProbeWorkflowRequest(
            workflow_total_steps=3,
            step_number=1,
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
        )

        data = request.model_dump(mode="json")

        assert data["workflow_total_steps"] == 3
        assert data["step_number"] == 1
        assert data["probe_type_option"] == "llm_policy"
        assert data["project_id"] == str(project_id)
        assert data["trigger_workflow"] is False


class TestCustomProbeWorkflowSteps:
    """Tests for CustomProbeWorkflowSteps schema."""

    def test_create_empty_steps(self):
        """Test creating workflow steps with no data."""
        steps = CustomProbeWorkflowSteps()

        assert steps.probe_type_option is None
        assert steps.project_id is None
        assert steps.model_uri is None
        assert steps.scanner_type is None
        assert steps.handler is None
        assert steps.model_provider_type is None
        assert steps.policy is None
        assert steps.name is None
        assert steps.description is None
        assert steps.guard_types is None
        assert steps.modality_types is None
        assert steps.probe_id is None
        assert steps.model_id is None
        assert steps.workflow_execution_status is None

    def test_create_steps_with_step1_data(self):
        """Test creating workflow steps with step 1 data."""
        project_id = uuid4()
        steps = CustomProbeWorkflowSteps(
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
            model_uri="openai/gpt-oss-safeguard-20b",
            scanner_type="llm",
            handler="gpt_safeguard",
            model_provider_type="openai",
        )

        assert steps.probe_type_option == CustomProbeTypeEnum.LLM_POLICY
        assert steps.project_id == project_id
        assert steps.model_uri == "openai/gpt-oss-safeguard-20b"
        assert steps.scanner_type == "llm"
        assert steps.handler == "gpt_safeguard"
        assert steps.model_provider_type == "openai"

    def test_create_steps_with_all_data(self):
        """Test creating workflow steps with all data accumulated."""
        project_id = uuid4()
        probe_id = uuid4()
        model_id = uuid4()
        policy_dict = {"task": "Test task", "definitions": []}

        steps = CustomProbeWorkflowSteps(
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
            model_uri="openai/gpt-oss-safeguard-20b",
            scanner_type="llm",
            handler="gpt_safeguard",
            model_provider_type="openai",
            policy=policy_dict,
            name="My Probe",
            description="Test description",
            guard_types=["input", "output"],
            modality_types=["text"],
            probe_id=probe_id,
            model_id=model_id,
            workflow_execution_status={"status": "success", "message": "Created"},
        )

        assert steps.name == "My Probe"
        assert steps.description == "Test description"
        assert steps.guard_types == ["input", "output"]
        assert steps.modality_types == ["text"]
        assert steps.probe_id == probe_id
        assert steps.model_id == model_id
        assert steps.workflow_execution_status == {"status": "success", "message": "Created"}

    def test_serialization(self):
        """Test workflow steps serializes correctly."""
        project_id = uuid4()
        steps = CustomProbeWorkflowSteps(
            probe_type_option=CustomProbeTypeEnum.LLM_POLICY,
            project_id=project_id,
            model_uri="openai/gpt-oss-safeguard-20b",
        )

        data = steps.model_dump(mode="json")

        assert data["probe_type_option"] == "llm_policy"
        assert data["project_id"] == str(project_id)
        assert data["model_uri"] == "openai/gpt-oss-safeguard-20b"


class TestGuardrailCustomProbeResponseUpdated:
    """Tests for updated GuardrailCustomProbeResponse with guard_types and modality_types."""

    @pytest.fixture
    def mock_probe_with_rule(self):
        """Create a mock probe object with a rule containing guard_types and modality_types."""
        probe_id = uuid4()
        model_id = uuid4()
        now = datetime.now(timezone.utc)

        # Create mock rule with guard_types and modality_types
        mock_rule = Mock()
        mock_rule.scanner_type = ScannerTypeEnum.LLM
        mock_rule.model_id = model_id
        mock_rule.model_uri = "openai/gpt-oss-safeguard-20b"
        mock_rule.model_config_json = {"handler": "gpt_safeguard", "policy": {"task": "test"}}
        mock_rule.guard_types = ["input", "output"]
        mock_rule.modality_types = ["text"]

        # Create mock probe
        mock_probe = Mock()
        mock_probe.id = probe_id
        mock_probe.name = "Test Probe"
        mock_probe.description = "Test description"
        mock_probe.probe_type = ProbeTypeEnum.CUSTOM
        mock_probe.status = "active"
        mock_probe.created_at = now
        mock_probe.modified_at = now
        mock_probe.rules = [mock_rule]

        return mock_probe

    def test_response_extracts_guard_types_from_rule(self, mock_probe_with_rule):
        """Test that guard_types is extracted from the rule."""
        response = GuardrailCustomProbeResponse.model_validate(mock_probe_with_rule)

        assert response.guard_types == ["input", "output"]

    def test_response_extracts_modality_types_from_rule(self, mock_probe_with_rule):
        """Test that modality_types is extracted from the rule."""
        response = GuardrailCustomProbeResponse.model_validate(mock_probe_with_rule)

        assert response.modality_types == ["text"]

    def test_response_from_dict_with_guard_types(self):
        """Test creating response from dict with guard_types."""
        data = {
            "id": uuid4(),
            "name": "Test Probe",
            "description": "Test description",
            "probe_type": ProbeTypeEnum.CUSTOM,
            "scanner_type": ScannerTypeEnum.LLM,
            "model_id": uuid4(),
            "model_uri": "openai/gpt-oss-safeguard-20b",
            "model_config_json": {"handler": "gpt_safeguard"},
            "guard_types": ["input"],
            "modality_types": ["text", "image"],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "modified_at": datetime.now(timezone.utc),
        }

        response = GuardrailCustomProbeResponse.model_validate(data)

        assert response.guard_types == ["input"]
        assert response.modality_types == ["text", "image"]

    def test_response_handles_none_guard_types(self):
        """Test response handles None guard_types gracefully."""
        mock_rule = Mock()
        mock_rule.scanner_type = ScannerTypeEnum.LLM
        mock_rule.model_id = uuid4()
        mock_rule.model_uri = "openai/gpt-oss-safeguard-20b"
        mock_rule.model_config_json = None
        mock_rule.guard_types = None
        mock_rule.modality_types = None

        mock_probe = Mock()
        mock_probe.id = uuid4()
        mock_probe.name = "Test"
        mock_probe.description = None
        mock_probe.probe_type = ProbeTypeEnum.CUSTOM
        mock_probe.status = "active"
        mock_probe.created_at = datetime.now(timezone.utc)
        mock_probe.modified_at = datetime.now(timezone.utc)
        mock_probe.rules = [mock_rule]

        response = GuardrailCustomProbeResponse.model_validate(mock_probe)

        assert response.guard_types is None
        assert response.modality_types is None

    def test_response_serialization_includes_new_fields(self, mock_probe_with_rule):
        """Test that serialization includes guard_types and modality_types."""
        response = GuardrailCustomProbeResponse.model_validate(mock_probe_with_rule)
        data = response.model_dump(mode="json")

        assert "guard_types" in data
        assert "modality_types" in data
        assert data["guard_types"] == ["input", "output"]
        assert data["modality_types"] == ["text"]

    def test_response_probe_without_rules_returns_data_as_is(self):
        """Test that probe without rules returns data unchanged."""
        mock_probe = Mock()
        mock_probe.id = uuid4()
        mock_probe.name = "Test"
        mock_probe.description = None
        mock_probe.probe_type = ProbeTypeEnum.CUSTOM
        mock_probe.status = "active"
        mock_probe.created_at = datetime.now(timezone.utc)
        mock_probe.modified_at = datetime.now(timezone.utc)
        mock_probe.rules = []  # Empty rules
        mock_probe.scanner_type = None
        mock_probe.model_id = None
        mock_probe.model_uri = None
        mock_probe.model_config_json = None
        mock_probe.guard_types = None
        mock_probe.modality_types = None

        response = GuardrailCustomProbeResponse.model_validate(mock_probe)

        # When rules are empty, the object is returned as-is
        # so it uses the probe's own attributes
        assert response.name == "Test"
