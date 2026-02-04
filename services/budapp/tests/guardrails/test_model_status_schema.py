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

"""Unit tests for guardrail model status schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from budapp.guardrails.schemas import (
    GuardrailModelStatus,
    GuardrailModelStatusResponse,
    ModelDeploymentStatus,
)


class TestModelDeploymentStatus:
    """Tests for ModelDeploymentStatus enum."""

    def test_enum_values_exist(self):
        """Test that all expected enum values exist."""
        expected_values = [
            "not_onboarded",
            "onboarded",
            "running",
            "unhealthy",
            "deploying",
            "pending",
            "failure",
            "deleting",
        ]
        actual_values = [status.value for status in ModelDeploymentStatus]
        assert sorted(actual_values) == sorted(expected_values)

    def test_enum_is_string_enum(self):
        """Test that enum values are strings."""
        for status in ModelDeploymentStatus:
            assert isinstance(status.value, str)
            assert status.value == status.name.lower()

    def test_enum_comparison(self):
        """Test enum comparison works correctly."""
        assert ModelDeploymentStatus.NOT_ONBOARDED == "not_onboarded"
        assert ModelDeploymentStatus.RUNNING == "running"
        assert ModelDeploymentStatus.FAILURE != ModelDeploymentStatus.RUNNING

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        status = ModelDeploymentStatus("running")
        assert status == ModelDeploymentStatus.RUNNING

    def test_enum_invalid_value(self):
        """Test that invalid values raise error."""
        with pytest.raises(ValueError):
            ModelDeploymentStatus("invalid_status")


class TestGuardrailModelStatus:
    """Tests for GuardrailModelStatus schema."""

    @pytest.fixture
    def valid_model_status_data(self):
        """Provide valid model status data."""
        return {
            "rule_id": uuid4(),
            "rule_name": "Test Rule",
            "probe_id": uuid4(),
            "probe_name": "Test Probe",
            "model_uri": "org/model-name",
            "status": ModelDeploymentStatus.NOT_ONBOARDED,
            "requires_onboarding": True,
            "requires_deployment": True,
            "can_reuse": False,
        }

    def test_create_minimal_model_status(self, valid_model_status_data):
        """Test creating model status with minimal required fields."""
        status = GuardrailModelStatus(**valid_model_status_data)

        assert status.rule_name == "Test Rule"
        assert status.probe_name == "Test Probe"
        assert status.model_uri == "org/model-name"
        assert status.status == ModelDeploymentStatus.NOT_ONBOARDED
        assert status.requires_onboarding is True
        assert status.requires_deployment is True
        assert status.can_reuse is False
        assert status.model_id is None
        assert status.endpoint_id is None

    def test_create_model_status_with_endpoint_info(self, valid_model_status_data):
        """Test creating model status with endpoint details."""
        endpoint_id = uuid4()
        cluster_id = uuid4()

        status = GuardrailModelStatus(
            **valid_model_status_data,
            model_id=uuid4(),
            endpoint_id=endpoint_id,
            endpoint_name="test-endpoint",
            endpoint_url="http://localhost:8000",
            cluster_id=cluster_id,
            cluster_name="test-cluster",
        )

        assert status.endpoint_id == endpoint_id
        assert status.endpoint_name == "test-endpoint"
        assert status.endpoint_url == "http://localhost:8000"
        assert status.cluster_id == cluster_id
        assert status.cluster_name == "test-cluster"

    def test_model_status_with_running_status(self):
        """Test model status for a running deployment."""
        status = GuardrailModelStatus(
            rule_id=uuid4(),
            rule_name="Running Rule",
            probe_id=uuid4(),
            probe_name="Running Probe",
            model_uri="org/running-model",
            model_id=uuid4(),
            status=ModelDeploymentStatus.RUNNING,
            endpoint_id=uuid4(),
            endpoint_name="running-endpoint",
            requires_onboarding=False,
            requires_deployment=False,
            can_reuse=True,
        )

        assert status.status == ModelDeploymentStatus.RUNNING
        assert status.requires_onboarding is False
        assert status.requires_deployment is False
        assert status.can_reuse is True

    def test_model_status_with_unhealthy_shows_warning(self):
        """Test that unhealthy status can set show_warning flag."""
        status = GuardrailModelStatus(
            rule_id=uuid4(),
            rule_name="Unhealthy Rule",
            probe_id=uuid4(),
            probe_name="Unhealthy Probe",
            model_uri="org/unhealthy-model",
            model_id=uuid4(),
            status=ModelDeploymentStatus.UNHEALTHY,
            requires_onboarding=False,
            requires_deployment=False,
            can_reuse=False,
            show_warning=True,
        )

        assert status.status == ModelDeploymentStatus.UNHEALTHY
        assert status.show_warning is True

    def test_model_status_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            GuardrailModelStatus(
                rule_id=uuid4(),
                # Missing rule_name, probe_id, probe_name, model_uri, status, etc.
            )

        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors}
        assert "rule_name" in missing_fields
        assert "probe_id" in missing_fields
        assert "status" in missing_fields

    def test_model_status_from_attributes(self, valid_model_status_data):
        """Test model_config allows from_attributes."""
        # The model_config should have from_attributes=True
        assert GuardrailModelStatus.model_config.get("from_attributes") is True
        # Verify we can create an instance with the data
        _ = GuardrailModelStatus(**valid_model_status_data)

    def test_model_status_serialization(self, valid_model_status_data):
        """Test model status serializes to dict correctly."""
        status = GuardrailModelStatus(**valid_model_status_data)
        data = status.model_dump(mode="json")

        assert "rule_id" in data
        assert "rule_name" in data
        assert "model_uri" in data
        assert "status" in data
        assert data["status"] == "not_onboarded"
        assert "requires_onboarding" in data


class TestGuardrailModelStatusResponse:
    """Tests for GuardrailModelStatusResponse schema."""

    @pytest.fixture
    def sample_model_statuses(self):
        """Provide sample model status objects."""
        return [
            GuardrailModelStatus(
                rule_id=uuid4(),
                rule_name="Rule 1",
                probe_id=uuid4(),
                probe_name="Probe 1",
                model_uri="org/model-1",
                status=ModelDeploymentStatus.NOT_ONBOARDED,
                requires_onboarding=True,
                requires_deployment=True,
                can_reuse=False,
            ),
            GuardrailModelStatus(
                rule_id=uuid4(),
                rule_name="Rule 2",
                probe_id=uuid4(),
                probe_name="Probe 2",
                model_uri="org/model-2",
                model_id=uuid4(),
                status=ModelDeploymentStatus.RUNNING,
                endpoint_id=uuid4(),
                requires_onboarding=False,
                requires_deployment=False,
                can_reuse=True,
            ),
        ]

    def test_create_response_with_models(self, sample_model_statuses):
        """Test creating response with model statuses."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=sample_model_statuses,
            total_models=2,
            models_requiring_onboarding=1,
            models_requiring_deployment=1,
            models_reusable=1,
        )

        assert len(response.models) == 2
        assert response.total_models == 2
        assert response.models_requiring_onboarding == 1
        assert response.models_requiring_deployment == 1
        assert response.models_reusable == 1
        assert response.skip_to_step is None
        assert response.credential_required is False

    def test_create_response_with_skip_logic(self, sample_model_statuses):
        """Test response with skip_to_step set."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=sample_model_statuses,
            total_models=2,
            models_requiring_onboarding=0,
            models_requiring_deployment=0,
            models_reusable=2,
            skip_to_step=12,  # Skip to profile configuration
        )

        assert response.skip_to_step == 12
        assert response.models_requiring_onboarding == 0

    def test_create_response_with_credential_required(self, sample_model_statuses):
        """Test response with credential_required flag."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=sample_model_statuses,
            total_models=2,
            models_requiring_onboarding=1,
            models_requiring_deployment=1,
            models_reusable=1,
            credential_required=True,
        )

        assert response.credential_required is True

    def test_create_empty_response(self):
        """Test creating response with no models."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=[],
            total_models=0,
            models_requiring_onboarding=0,
            models_requiring_deployment=0,
            models_reusable=0,
        )

        assert len(response.models) == 0
        assert response.total_models == 0
        assert response.skip_to_step is None

    def test_response_object_field(self, sample_model_statuses):
        """Test that object field has correct default value."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=sample_model_statuses,
            total_models=2,
            models_requiring_onboarding=1,
            models_requiring_deployment=1,
            models_reusable=1,
        )

        assert response.object == "guardrail.model_status"

    def test_response_serialization(self, sample_model_statuses):
        """Test response serializes correctly."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=sample_model_statuses,
            total_models=2,
            models_requiring_onboarding=1,
            models_requiring_deployment=1,
            models_reusable=1,
            skip_to_step=8,
            credential_required=True,
        )

        data = response.model_dump(mode="json")

        assert "models" in data
        assert len(data["models"]) == 2
        assert data["total_models"] == 2
        assert data["skip_to_step"] == 8
        assert data["credential_required"] is True
        assert data["object"] == "guardrail.model_status"

    def test_response_inherits_success_response(self, sample_model_statuses):
        """Test that response inherits from SuccessResponse."""
        response = GuardrailModelStatusResponse(
            message="OK",
            models=sample_model_statuses,
            total_models=2,
            models_requiring_onboarding=1,
            models_requiring_deployment=1,
            models_reusable=1,
        )

        # SuccessResponse provides message and code fields
        assert hasattr(response, "message")
        assert hasattr(response, "code")
        assert response.message == "OK"
        assert response.code == 200


class TestModelStatusSkipLogic:
    """Tests for skip logic based on model deployment status."""

    def test_all_models_deployed_skip_to_profile(self):
        """Test that all deployed models enable skip to step 12."""
        models = [
            GuardrailModelStatus(
                rule_id=uuid4(),
                rule_name="Rule 1",
                probe_id=uuid4(),
                probe_name="Probe 1",
                model_uri="org/model-1",
                model_id=uuid4(),
                status=ModelDeploymentStatus.RUNNING,
                endpoint_id=uuid4(),
                requires_onboarding=False,
                requires_deployment=False,
                can_reuse=True,
            ),
        ]

        # Simulate the skip logic from derive_model_statuses
        models_requiring_onboarding = sum(1 for m in models if m.requires_onboarding)
        models_requiring_deployment = sum(1 for m in models if m.requires_deployment)

        skip_to_step = None
        if models_requiring_onboarding == 0 and models_requiring_deployment == 0:
            skip_to_step = 12

        assert skip_to_step == 12

    def test_models_onboarded_skip_to_cluster(self):
        """Test that onboarded but not deployed models enable skip to step 8."""
        models = [
            GuardrailModelStatus(
                rule_id=uuid4(),
                rule_name="Rule 1",
                probe_id=uuid4(),
                probe_name="Probe 1",
                model_uri="org/model-1",
                model_id=uuid4(),
                status=ModelDeploymentStatus.ONBOARDED,
                requires_onboarding=False,
                requires_deployment=True,
                can_reuse=False,
            ),
        ]

        # Simulate the skip logic from derive_model_statuses
        models_requiring_onboarding = sum(1 for m in models if m.requires_onboarding)
        models_requiring_deployment = sum(1 for m in models if m.requires_deployment)

        skip_to_step = None
        if models_requiring_onboarding == 0 and models_requiring_deployment == 0:
            skip_to_step = 12
        elif models_requiring_onboarding == 0:
            skip_to_step = 8

        assert skip_to_step == 8

    def test_models_need_onboarding_no_skip(self):
        """Test that models needing onboarding don't enable skip."""
        models = [
            GuardrailModelStatus(
                rule_id=uuid4(),
                rule_name="Rule 1",
                probe_id=uuid4(),
                probe_name="Probe 1",
                model_uri="org/model-1",
                status=ModelDeploymentStatus.NOT_ONBOARDED,
                requires_onboarding=True,
                requires_deployment=True,
                can_reuse=False,
            ),
        ]

        # Simulate the skip logic from derive_model_statuses
        models_requiring_onboarding = sum(1 for m in models if m.requires_onboarding)
        models_requiring_deployment = sum(1 for m in models if m.requires_deployment)

        skip_to_step = None
        if models_requiring_onboarding == 0 and models_requiring_deployment == 0:
            skip_to_step = 12
        elif models_requiring_onboarding == 0:
            skip_to_step = 8

        assert skip_to_step is None
