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

"""Unit tests for PromptConfigurationService validate_schema method."""

import uuid
from unittest.mock import Mock, patch

import pytest
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import NotificationContent, NotificationRequest

from budprompt.prompt.schemas import (
    PromptSchemaRequest,
    SchemaBase,
)
from budprompt.prompt.services import PromptConfigurationService


class TestValidateSchema:
    """Test cases for the validate_schema method of PromptConfigurationService."""

    @pytest.fixture
    def mock_notification_request(self):
        """Create a mock notification request."""
        notification_req = Mock(spec=NotificationRequest)
        notification_req.model_copy = Mock(return_value=notification_req)
        notification_req.payload = Mock()
        notification_req.payload.event = None
        notification_req.payload.content = None
        return notification_req

    @pytest.fixture
    def valid_simple_schema(self):
        """Create a valid simple JSON schema."""
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["name", "age"],
        }

    @pytest.fixture
    def valid_nested_schema(self):
        """Create a valid nested JSON schema."""
        return {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                    "required": ["name"],
                },
                "settings": {
                    "type": "object",
                    "properties": {
                        "theme": {"type": "string"},
                        "notifications": {"type": "boolean"},
                    },
                },
            },
            "required": ["user"],
        }

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_both_schemas_success(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request, valid_simple_schema
    ):
        """Test successful validation with input schema."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        # Create request for input schema
        request = PromptSchemaRequest(
            prompt_id="test_prompt_1",
            schema=SchemaBase(
                schema=valid_simple_schema,
                validations={
                    "InputSchema": {
                        "name": "Name must be at least 3 characters",
                        "age": "Age must be between 18 and 100",
                    }
                }
            ),
            type="input",
        )

        # Act
        result = PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert
        # Should publish start notification
        assert mock_dapr_workflow.publish_notification.call_count == 2

        # Check first call (start notification)
        first_call = mock_dapr_workflow.publish_notification.call_args_list[0]
        assert first_call[1]["workflow_id"] == workflow_id

        # Check second call (success notification)
        second_call = mock_dapr_workflow.publish_notification.call_args_list[1]
        assert second_call[1]["workflow_id"] == workflow_id

        # Verify sleep was called
        mock_sleep.assert_called_once_with(3)

        # validate_schema now returns None as codes are generated separately
        assert result is None

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_only_input_schema(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request, valid_simple_schema
    ):
        """Test validation with input schema."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_2",
            schema=SchemaBase(
                schema=valid_simple_schema,
                validations={}
            ),
            type="input",
        )

        # Act
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert
        assert mock_dapr_workflow.publish_notification.call_count == 2
        mock_sleep.assert_called_once_with(3)

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_only_output_schema(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request, valid_simple_schema
    ):
        """Test validation with output schema."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_3",
            schema=SchemaBase(
                schema=valid_simple_schema,
                validations={}
            ),
            type="output",
        )

        # Act
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert
        assert mock_dapr_workflow.publish_notification.call_count == 2
        mock_sleep.assert_called_once_with(3)

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_invalid_field_references(
        self, mock_dapr_workflow, _mock_sleep, mock_notification_request, valid_simple_schema
    ):
        """Test validation fails when field references don't exist in schema."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_4",
            schema=SchemaBase(
                schema=valid_simple_schema,
                validations={
                    "InputSchema": {
                        "non_existent_field": "This field doesn't exist",  # Invalid field
                    }
                }
            ),
            type="input",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PromptConfigurationService.validate_schema(
                workflow_id=workflow_id,
                notification_request=mock_notification_request,
                schema=request.schema.schema,
                validations=request.schema.validations,
                schema_type=request.type,
            )

        assert "Field 'non_existent_field' not found" in str(exc_info.value)

        # Should publish start and failure notifications
        assert mock_dapr_workflow.publish_notification.call_count == 2

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_handles_flexible_schemas(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request
    ):
        """Test validation handles flexible schema structures gracefully."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        # Schema without explicit type field - should still be handled
        flexible_schema = {
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "integer"}
            }
        }

        request = PromptSchemaRequest(
            prompt_id="test_prompt_5",
            schema=SchemaBase(
                schema=flexible_schema,
                validations={}
            ),
            type="input",
        )

        # Act - Should not raise an exception, the function is robust
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert - Should complete successfully
        assert mock_dapr_workflow.publish_notification.call_count == 2
        mock_sleep.assert_called_once_with(3)

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_nested_schema_and_validations(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request, valid_nested_schema
    ):
        """Test validation with nested schema structure."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_6",
            schema=SchemaBase(
                schema=valid_nested_schema,
                validations={
                    "InputSchema": {
                        "user": "User object must be valid",
                        "settings": "Settings must be properly configured",
                    }
                }
            ),
            type="input",
        )

        # Act
        result = PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert
        assert mock_dapr_workflow.publish_notification.call_count == 2
        mock_sleep.assert_called_once_with(3)
        # validate_schema now returns None as codes are generated separately
        assert result is None

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_empty_validations(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request, valid_simple_schema
    ):
        """Test validation succeeds with empty validations dictionary."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_7",
            schema=SchemaBase(
                schema=valid_simple_schema,
                validations={}  # Empty validations
            ),
            type="input",
        )

        # Act
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert
        assert mock_dapr_workflow.publish_notification.call_count == 2
        mock_sleep.assert_called_once_with(3)

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_both_schemas_none(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request
    ):
        """Test validation when both schemas are None."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_8",
            schema=None,
            type="input",
        )

        # Act
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=None,
            validations=None,
            schema_type=request.type,
        )

        # Assert
        # Should still publish notifications even with no schemas
        assert mock_dapr_workflow.publish_notification.call_count == 2
        mock_sleep.assert_called_once_with(3)

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_notification_content(
        self, _mock_dapr_workflow, _mock_sleep, mock_notification_request, valid_simple_schema
    ):
        """Test that correct notification content is published."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_9",
            schema=SchemaBase(
                schema=valid_simple_schema,
                validations={}
            ),
            type="input",
        )

        # Act
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=request.schema.schema,
            validations=request.schema.validations,
            schema_type=request.type,
        )

        # Assert
        # Check notification content
        assert mock_notification_request.payload.event == "validation"

        # Verify the notification content was set correctly
        # Last content should be success
        last_content = mock_notification_request.payload.content
        assert isinstance(last_content, NotificationContent)
        assert last_content.title == "Successfully validated schemas"
        assert last_content.status == WorkflowStatus.COMPLETED

class TestGenerateValidationCodes:
    """Test cases for the generate_validation_codes method."""

    @pytest.fixture
    def mock_notification_request(self):
        """Create a mock notification request."""
        notification_req = Mock(spec=NotificationRequest)
        notification_req.model_copy = Mock(return_value=notification_req)
        notification_req.payload = Mock()
        notification_req.payload.event = None
        notification_req.payload.content = None
        return notification_req

    @patch('budprompt.prompt.services.dapr_workflow')
    def test_generate_validation_codes_success(
        self, mock_dapr_workflow, mock_notification_request
    ):
        """Test successful validation code generation with actual LLM calls."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_gen_1",
            schema=SchemaBase(
                schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
                validations={
                    "InputSchema": {
                        "name": "Name must be at least 3 characters",
                        "age": "Age must be between 18 and 100",
                    }
                }
            ),
            type="input",
        )

        # Act - This will make actual LLM calls
        result = PromptConfigurationService.generate_validation_codes(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            validations=request.schema.validations,
        )

        # Assert
        # Should publish start and completion notifications
        assert mock_dapr_workflow.publish_notification.call_count == 2

        # Verify result structure
        assert result is not None
        assert "InputSchema" in result
        assert "name" in result["InputSchema"]
        assert "age" in result["InputSchema"]
        assert "prompt" in result["InputSchema"]["name"]
        assert "code" in result["InputSchema"]["name"]

        # Verify the actual LLM generated code contains meaningful validation logic
        name_code = result["InputSchema"]["name"]["code"]
        age_code = result["InputSchema"]["age"]["code"]

        # The LLM should generate actual validation functions, not just return True
        assert "def validate_name" in name_code
        assert "def validate_age" in age_code

    @patch('budprompt.prompt.services.dapr_workflow')
    def test_generate_validation_codes_with_output_schema(
        self, mock_dapr_workflow, mock_notification_request
    ):
        """Test validation code generation with output schema using actual LLM."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_gen_2",
            schema=SchemaBase(
                schema={
                    "type": "object",
                    "properties": {
                        "token": {"type": "string"},
                        "expires_in": {"type": "integer"},
                    },
                },
                validations={
                    "OutputSchema": {
                        "token": "Token must be a non-empty string with at least 20 characters",
                        "expires_in": "Expires_in must be a positive integer between 60 and 86400 (1 minute to 24 hours)",
                    }
                }
            ),
            type="output",
        )

        # Act - This will make actual LLM calls
        result = PromptConfigurationService.generate_validation_codes(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            validations=request.schema.validations,
        )

        print(result, "===============")

        # Assert
        # Should publish start and completion notifications
        assert mock_dapr_workflow.publish_notification.call_count == 2

        # Verify result structure for output
        assert result is not None
        assert "OutputSchema" in result
        assert "token" in result["OutputSchema"]
        assert "expires_in" in result["OutputSchema"]

        # Get the generated code
        token_code = result["OutputSchema"]["token"]["code"]
        expires_code = result["OutputSchema"]["expires_in"]["code"]

        # Verify functions are properly named
        assert "def validate_token" in token_code
        assert "def validate_expires_in" in expires_code

    @patch('budprompt.prompt.services.dapr_workflow')
    def test_generate_validation_codes_no_validations(
        self, mock_dapr_workflow, mock_notification_request
    ):
        """Test when there are no validations to generate."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        request = PromptSchemaRequest(
            prompt_id="test_prompt_gen_3",
            schema=SchemaBase(
                schema={"type": "object", "properties": {}},
                validations={}
            ),
            type="input",
        )

        # Act
        result = PromptConfigurationService.generate_validation_codes(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            validations=request.schema.validations,
        )

        # Assert
        # Should still publish notifications even when no validations
        assert mock_dapr_workflow.publish_notification.call_count == 2  # Start and completion
        assert result is None  # No validation codes generated

class TestPromptIdGeneration:
    """Test cases for prompt_id auto-generation."""

    def test_prompt_id_is_none_when_not_provided(self):
        """Test that prompt_id defaults to None when not provided in the schema."""
        # Create request without prompt_id
        request_data = {
            "schema": {
                "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                "validations": {}
            },
            "type": "input"
        }

        # Create the request - prompt_id should be None (UUID generation happens in router)
        request = PromptSchemaRequest(**request_data)

        # Assert prompt_id is None when not provided
        assert request.prompt_id is None

    def test_prompt_id_preserved_when_provided(self):
        """Test that provided prompt_id is preserved."""
        # Create request with explicit prompt_id
        provided_prompt_id = "custom-prompt-id-123"
        request_data = {
            "prompt_id": provided_prompt_id,
            "schema": {
                "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                "validations": {}
            },
            "type": "input"
        }

        # Create the request
        request = PromptSchemaRequest(**request_data)

        # Assert the provided prompt_id is preserved
        assert request.prompt_id == provided_prompt_id

# docker exec -it budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/test_unit_tests/test_prompt_configuration_service.py -v"
