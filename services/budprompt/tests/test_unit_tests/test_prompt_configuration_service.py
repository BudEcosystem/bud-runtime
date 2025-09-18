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

import json
import uuid
from unittest.mock import AsyncMock, Mock, patch

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
                "content": {"type": "string"},
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["content", "name", "age"],
        }

    @pytest.fixture
    def valid_nested_schema(self):
        """Create a valid nested JSON schema."""
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
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
            "required": ["content", "user"],
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
                "content": {"type": "string"},
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

        # Create SchemaBase with None values
        schema_base = SchemaBase(
            schema=None,
            validations=None
        )

        request = PromptSchemaRequest(
            prompt_id="test_prompt_8",
            schema=schema_base,  # Now using SchemaBase object
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

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_missing_content_field(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request
    ):
        """Test validation fails when schema has properties but missing content field."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        # Schema with properties but no 'content' field
        schema_without_content = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }

        request = PromptSchemaRequest(
            prompt_id="test_prompt_missing_content",
            schema=SchemaBase(
                schema=schema_without_content,
                validations={}
            ),
            type="input",
        )

        # Act & Assert - Should raise SchemaGenerationException
        with pytest.raises(Exception) as exc_info:
            PromptConfigurationService.validate_schema(
                workflow_id=workflow_id,
                notification_request=mock_notification_request,
                schema=request.schema.schema,
                validations=request.schema.validations,
                schema_type=request.type,
            )

        # Verify the correct exception and message
        assert "Schema must contain a 'content' field" in str(exc_info.value)

        # Should publish start and failure notifications
        assert mock_dapr_workflow.publish_notification.call_count == 2

    @patch('budprompt.prompt.services.time.sleep')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_missing_content_field_output_schema(
        self, mock_dapr_workflow, mock_sleep, mock_notification_request
    ):
        """Test validation fails for output schema missing content field."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        # Schema with properties but no 'content' field
        schema_without_content = {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "status": {"type": "string"}
            }
        }

        request = PromptSchemaRequest(
            prompt_id="test_output_missing_content",
            schema=SchemaBase(
                schema=schema_without_content,
                validations={}
            ),
            type="output",
        )

        # Act & Assert - Should raise SchemaGenerationException
        with pytest.raises(Exception) as exc_info:
            PromptConfigurationService.validate_schema(
                workflow_id=workflow_id,
                notification_request=mock_notification_request,
                schema=request.schema.schema,
                validations=request.schema.validations,
                schema_type=request.type,
            )

        # Verify the correct exception and message
        assert "Schema must contain a 'content' field" in str(exc_info.value)

        # Should publish start and failure notifications
        assert mock_dapr_workflow.publish_notification.call_count == 2

    @patch('budprompt.prompt.services.ModelGeneratorFactory')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_refs_and_defs(
        self, mock_dapr_workflow, mock_factory, mock_notification_request
    ):
        """Test schema validation with $defs and $ref works correctly."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        schema_with_refs = {
            "$defs": {
                "Person": {
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "email": {"format": "email", "type": "string"}
                    },
                    "required": ["name", "age", "email"],
                    "title": "Person",
                    "type": "object"
                }
            },
            "properties": {
                "content": {"$ref": "#/$defs/Person"}
            },
            "required": ["content"],
            "title": "Schema",
            "type": "object"
        }

        validations = {
            "Person": {
                "name": "Name must be at least 3 characters",
                "age": "Age must be between 18 and 100"
            }
        }

        # Create a mock model that simulates the structure created by CustomModelGenerator
        mock_person_model = Mock()
        mock_person_model.__name__ = "Person"
        mock_person_model.model_fields = {
            "name": Mock(annotation=str),
            "age": Mock(annotation=int),
            "email": Mock(annotation=str)
        }

        mock_main_model = Mock()
        mock_main_model.__name__ = "DynamicInputschema"
        mock_main_model.model_fields = {
            "content": Mock(annotation=mock_person_model)
        }

        mock_factory.create_model = AsyncMock(return_value=mock_main_model)

        # Act & Assert - should not raise any exception
        PromptConfigurationService.validate_schema(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            schema=schema_with_refs,
            validations=validations,
            schema_type="input"
        )

        # Should publish start and success notifications
        assert mock_dapr_workflow.publish_notification.call_count == 2

    @patch('budprompt.prompt.services.ModelGeneratorFactory')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_invalid_ref_field(
        self, mock_dapr_workflow, mock_factory, mock_notification_request
    ):
        """Test schema validation fails when validation references non-existent field in $ref model."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        schema_with_refs = {
            "$defs": {
                "Person": {
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"}
                    },
                    "required": ["name", "age"],
                    "title": "Person",
                    "type": "object"
                }
            },
            "properties": {
                "content": {"$ref": "#/$defs/Person"}
            },
            "required": ["content"],
            "title": "Schema",
            "type": "object"
        }

        # Validation references a field that doesn't exist in Person
        validations = {
            "Person": {
                "name": "Name must be at least 3 characters",
                "email": "Must be a valid email"  # This field doesn't exist in Person
            }
        }

        # Create a mock model
        mock_person_model = Mock()
        mock_person_model.__name__ = "Person"
        mock_person_model.model_fields = {
            "name": Mock(annotation=str),
            "age": Mock(annotation=int)
            # Note: no email field
        }

        mock_main_model = Mock()
        mock_main_model.__name__ = "DynamicInputschema"
        mock_main_model.model_fields = {
            "content": Mock(annotation=mock_person_model)
        }

        mock_factory.create_model = AsyncMock(return_value=mock_main_model)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PromptConfigurationService.validate_schema(
                workflow_id=workflow_id,
                notification_request=mock_notification_request,
                schema=schema_with_refs,
                validations=validations,
                schema_type="input"
            )

        # Verify the error message
        assert "Field 'email' not found in model 'Person'" in str(exc_info.value)

    @patch('budprompt.prompt.services.ModelGeneratorFactory')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_validate_schema_with_invalid_model_name_in_validations(
        self, mock_dapr_workflow, mock_factory, mock_notification_request
    ):
        """Test schema validation fails when validation references non-existent model (typo in model name)."""
        # Arrange
        workflow_id = str(uuid.uuid4())

        schema_with_refs = {
            "$defs": {
                "Person": {  # Model is named "Person"
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "email": {"format": "email", "type": "string"}
                    },
                    "required": ["name", "age", "email"],
                    "title": "Person",
                    "type": "object"
                }
            },
            "properties": {
                "content": {"$ref": "#/$defs/Person"}
            },
            "required": ["content"],
            "title": "Schema",
            "type": "object"
        }

        # Validation uses wrong model name "Persons" instead of "Person"
        validations = {
            "Persons": {  # This is a typo - should be "Person"
                "name": "Name must be at least 3 characters",
                "age": "Age must be between 18 and 100"
            }
        }

        # Create a mock model
        mock_person_model = Mock()
        mock_person_model.__name__ = "Person"
        mock_person_model.model_fields = {
            "name": Mock(annotation=str),
            "age": Mock(annotation=int),
            "email": Mock(annotation=str)
        }

        mock_main_model = Mock()
        mock_main_model.__name__ = "DynamicInputschema"
        mock_main_model.model_fields = {
            "content": Mock(annotation=mock_person_model)
        }

        mock_factory.create_model = AsyncMock(return_value=mock_main_model)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PromptConfigurationService.validate_schema(
                workflow_id=workflow_id,
                notification_request=mock_notification_request,
                schema=schema_with_refs,
                validations=validations,
                schema_type="input"
            )

        # Verify the error message
        assert "Model 'Persons' not found in schema structure" in str(exc_info.value)

    @patch('budprompt.prompt.services.run_async')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_store_prompt_configuration_with_null_schema(
        self, mock_dapr_workflow, mock_run_async, mock_notification_request
    ):
        """Test that null schema can be stored to clear existing schema."""
        # Arrange
        workflow_id = str(uuid.uuid4())
        prompt_id = "test-null-schema"

        # Create request with null schema
        request = PromptSchemaRequest(
            prompt_id=prompt_id,
            schema=SchemaBase(schema=None, validations=None),
            type="input"
        )
        request_json = request.model_dump_json(exclude_unset=True)

        # Mock Redis operations
        mock_run_async.side_effect = [
            None,  # get returns None (no existing data)
            None,  # set returns None
            None,  # set default version returns None
        ]

        # Act
        result = PromptConfigurationService.store_prompt_configuration(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            prompt_id=prompt_id,
            request_json=request_json,  # Pass request_json instead of schema
            validation_codes=None,  # Clear validation codes
        )

        # Assert
        assert result == prompt_id
        assert mock_dapr_workflow.publish_notification.call_count == 2  # Start and complete

    @patch('budprompt.prompt.services.run_async')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_store_prompt_configuration_update_with_null_values(
        self, mock_dapr_workflow, mock_run_async, mock_notification_request
    ):
        """Test updating existing configuration with null values to clear fields."""
        # Arrange
        workflow_id = str(uuid.uuid4())
        prompt_id = "test-update-null"

        # Create request to clear input schema
        request = PromptSchemaRequest(
            prompt_id=prompt_id,
            schema=SchemaBase(schema=None, validations=None),
            type="input"
        )
        request_json = request.model_dump_json(exclude_unset=True)

        # Existing configuration with input schema and validation
        existing_config = {
            "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "input_validation": {"InputSchema": {"name": {"prompt": "Name validation", "code": "def validate_name()"}}},
            "output_schema": {"type": "object", "properties": {"result": {"type": "string"}}},
        }

        # Mock Redis operations
        mock_run_async.side_effect = [
            json.dumps(existing_config),  # get returns existing data
            None,  # set returns None
            None,  # set default version returns None
        ]

        # Act - Update input schema to null (should clear it)
        result = PromptConfigurationService.store_prompt_configuration(
            workflow_id=workflow_id,
            notification_request=mock_notification_request,
            prompt_id=prompt_id,
            request_json=request_json,  # Pass request_json instead of schema
            validation_codes=None,  # Clear input validation codes
        )

        # Assert
        assert result == prompt_id
        # Since we're mocking run_async, we can't easily verify the exact stored data
        # But we can verify that the function completed successfully
        assert mock_dapr_workflow.publish_notification.call_count == 2  # Start and complete

    @patch('budprompt.prompt.services.run_async')
    @patch('budprompt.prompt.services.dapr_workflow')
    def test_prompt_schema_request_with_null_schema(
        self, mock_dapr_workflow, mock_run_async
    ):
        """Test PromptConfigurationService.__call__ with schema containing null values."""
        # Arrange
        service = PromptConfigurationService()
        workflow_id = str(uuid.uuid4())

        # Create request with SchemaBase having null schema and validations
        # This tests clearing existing schema/validations
        request = PromptSchemaRequest(
            prompt_id="test-null-prompt",
            schema=SchemaBase(
                schema=None,  # Clear schema
                validations=None  # Clear validations
            ),
            type="input",
        )

        # Mock Redis operations
        mock_run_async.side_effect = [
            None,  # get returns None (no existing data)
            None,  # set returns None
            None,  # set default version returns None
        ]

        # Act
        result = service(request, workflow_id)

        # Assert
        assert result.prompt_id == "test-null-prompt"
        assert result.workflow_id == uuid.UUID(workflow_id)
        # Verify notifications were published
        assert mock_dapr_workflow.publish_notification.call_count >= 2

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
