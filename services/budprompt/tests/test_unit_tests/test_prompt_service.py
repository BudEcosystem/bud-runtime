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

"""Unit tests for PromptService class."""

import json
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest

from budprompt.commons.exceptions import ClientException
from budprompt.prompt.schemas import (
    Message,
    ModelSettings,
    PromptConfigRequest,
    PromptConfigurationData,
)
from budprompt.prompt.services import PromptService


class TestPromptService:
    """Test cases for PromptService class."""

    @pytest.fixture
    def mock_redis_service(self):
        """Create a mock Redis service."""
        mock_redis = AsyncMock()
        return mock_redis

    @pytest.fixture
    def prompt_service(self, mock_redis_service):
        """Create PromptService instance with mocked Redis."""
        service = PromptService()
        service.redis_service = mock_redis_service
        return service

    @pytest.fixture
    def sample_config_data(self):
        """Create sample configuration data."""
        return PromptConfigurationData(
            deployment_name="gpt-4",
            model_settings=ModelSettings(
                temperature=0.7,
                max_tokens=1000,
            ),
            stream=True,
            messages=[
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content="Hello!"),
            ],
            llm_retry_limit=3,
            enable_tools=True,
            allow_multiple_calls=True,
            system_prompt_role="system",
        )

    @pytest.fixture
    def sample_request(self):
        """Create sample prompt config request."""
        return PromptConfigRequest(
            prompt_id="test-prompt-123",
            deployment_name="gpt-4",
            model_settings=ModelSettings(temperature=0.7),
            stream=True,
        )


class TestSavePromptConfig(TestPromptService):
    """Test cases for save_prompt_config method."""

    @pytest.mark.asyncio
    async def test_save_new_config_success(self, prompt_service, mock_redis_service, sample_request):
        """Test successful saving of new configuration."""
        # Arrange
        mock_redis_service.get.return_value = None  # No existing config
        mock_redis_service.set.return_value = True

        # Act
        with patch('budprompt.prompt.services.app_settings') as mock_settings:
            mock_settings.prompt_config_redis_ttl = 86400
            result = await prompt_service.save_prompt_config(sample_request)

        # Assert
        assert result.code == 200
        assert result.message == "Prompt configuration saved successfully"
        assert result.prompt_id == "test-prompt-123"

        # Verify Redis interactions
        mock_redis_service.get.assert_called_once_with("prompt:test-prompt-123")
        mock_redis_service.set.assert_called_once()

        # Verify the stored data
        call_args = mock_redis_service.set.call_args
        assert call_args[0][0] == "prompt:test-prompt-123"
        assert call_args[1]["ex"] == 86400

    @pytest.mark.asyncio
    async def test_update_existing_config_success(self, prompt_service, mock_redis_service, sample_config_data):
        """Test successful update of existing configuration."""
        # Arrange
        existing_data = sample_config_data.model_dump_json(exclude_none=True)
        mock_redis_service.get.return_value = existing_data
        mock_redis_service.set.return_value = True

        # Create update request with partial fields
        update_request = PromptConfigRequest(
            prompt_id="test-prompt-123",
            deployment_name="gpt-3.5-turbo",
            llm_retry_limit=5,
        )

        # Act
        with patch('budprompt.prompt.services.app_settings') as mock_settings:
            mock_settings.prompt_config_redis_ttl = 86400
            result = await prompt_service.save_prompt_config(update_request)

        # Assert
        assert result.code == 200
        assert result.prompt_id == "test-prompt-123"

        # Verify Redis was called correctly
        mock_redis_service.get.assert_called_once_with("prompt:test-prompt-123")
        mock_redis_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_config_redis_error(self, prompt_service, mock_redis_service, sample_request):
        """Test handling of Redis errors during save."""
        # Arrange
        mock_redis_service.get.side_effect = Exception("Redis connection failed")

        # Act & Assert
        with pytest.raises(ClientException) as exc_info:
            await prompt_service.save_prompt_config(sample_request)

        assert exc_info.value.status_code == 500
        assert "Failed to store prompt configuration" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_save_config_invalid_json(self, prompt_service, mock_redis_service, sample_request):
        """Test handling of invalid JSON from Redis."""
        # Arrange
        mock_redis_service.get.return_value = "invalid json {{"

        # Act & Assert
        with pytest.raises(ClientException) as exc_info:
            await prompt_service.save_prompt_config(sample_request)

        assert exc_info.value.status_code == 500
        assert "Invalid data format" in exc_info.value.message


class TestGetPromptConfig(TestPromptService):
    """Test cases for get_prompt_config method."""

    @pytest.mark.asyncio
    async def test_get_config_success(self, prompt_service, mock_redis_service, sample_config_data):
        """Test successful retrieval of configuration."""
        # Arrange
        prompt_id = "test-prompt-123"
        config_json = sample_config_data.model_dump_json(exclude_none=True)
        mock_redis_service.get.return_value = config_json

        # Act
        result = await prompt_service.get_prompt_config(prompt_id)

        # Assert
        assert result.code == 200
        assert result.message == "Prompt configuration retrieved successfully"
        assert result.prompt_id == prompt_id
        assert result.data.deployment_name == "gpt-4"
        assert result.data.model_settings.temperature == 0.7
        assert len(result.data.messages) == 2

        # Verify Redis was called correctly
        mock_redis_service.get.assert_called_once_with("prompt:test-prompt-123")

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, prompt_service, mock_redis_service):
        """Test retrieval when configuration doesn't exist."""
        # Arrange
        prompt_id = "non-existent-id"
        mock_redis_service.get.return_value = None

        # Act & Assert
        with pytest.raises(ClientException) as exc_info:
            await prompt_service.get_prompt_config(prompt_id)

        assert exc_info.value.status_code == 404
        assert f"Prompt configuration not found for prompt_id: {prompt_id}" in exc_info.value.message

        # Verify Redis was called
        mock_redis_service.get.assert_called_once_with("prompt:non-existent-id")

    @pytest.mark.asyncio
    async def test_get_config_invalid_json(self, prompt_service, mock_redis_service):
        """Test handling of invalid JSON data from Redis."""
        # Arrange
        prompt_id = "test-prompt-123"
        mock_redis_service.get.return_value = "invalid json {{"

        # Act & Assert
        with pytest.raises(ClientException) as exc_info:
            await prompt_service.get_prompt_config(prompt_id)

        assert exc_info.value.status_code == 500
        # The error message could be either from JSON parsing or general exception
        assert "Failed to retrieve prompt configuration" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_config_redis_error(self, prompt_service, mock_redis_service):
        """Test handling of Redis connection errors."""
        # Arrange
        prompt_id = "test-prompt-123"
        mock_redis_service.get.side_effect = Exception("Redis connection failed")

        # Act & Assert
        with pytest.raises(ClientException) as exc_info:
            await prompt_service.get_prompt_config(prompt_id)

        assert exc_info.value.status_code == 500
        assert "Failed to retrieve prompt configuration" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_config_with_partial_data(self, prompt_service, mock_redis_service):
        """Test retrieval of configuration with partial fields."""
        # Arrange
        prompt_id = "test-prompt-123"
        partial_config = PromptConfigurationData(
            deployment_name="gpt-4",
            stream=False,
        )
        config_json = partial_config.model_dump_json(exclude_none=True)
        mock_redis_service.get.return_value = config_json

        # Act
        result = await prompt_service.get_prompt_config(prompt_id)

        # Assert
        assert result.code == 200
        assert result.prompt_id == prompt_id
        assert result.data.deployment_name == "gpt-4"
        assert result.data.stream == False
        assert result.data.model_settings is None
        assert result.data.messages is None


class TestPromptServiceIntegration(TestPromptService):
    """Integration tests for save and get operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_config_flow(self, prompt_service, mock_redis_service):
        """Test complete flow of saving and retrieving configuration."""
        # Arrange
        prompt_id = str(uuid.uuid4())
        request = PromptConfigRequest(
            prompt_id=prompt_id,
            deployment_name="gpt-4",
            model_settings=ModelSettings(
                temperature=0.8,
                max_tokens=1500,
            ),
            stream=True,
            messages=[
                Message(role="system", content="Test system message"),
            ],
            enable_tools=True,
        )

        # Mock Redis for save operation
        mock_redis_service.get.return_value = None  # No existing config
        mock_redis_service.set.return_value = True

        # Act - Save configuration
        with patch('budprompt.prompt.services.app_settings') as mock_settings:
            mock_settings.prompt_config_redis_ttl = 86400
            save_result = await prompt_service.save_prompt_config(request)

        # Assert save operation
        assert save_result.code == 200
        assert save_result.prompt_id == prompt_id

        # Get the saved data from the set call
        saved_json = mock_redis_service.set.call_args[0][1]

        # Mock Redis for get operation
        mock_redis_service.get.return_value = saved_json

        # Act - Get configuration
        get_result = await prompt_service.get_prompt_config(prompt_id)

        # Assert get operation
        assert get_result.code == 200
        assert get_result.prompt_id == prompt_id
        assert get_result.data.deployment_name == "gpt-4"
        assert get_result.data.model_settings.temperature == 0.8
        assert get_result.data.stream == True
        assert len(get_result.data.messages) == 1
        assert get_result.data.enable_tools == True

    @pytest.mark.asyncio
    async def test_update_and_get_config_flow(self, prompt_service, mock_redis_service):
        """Test updating existing configuration and retrieving it."""
        # Arrange
        prompt_id = "update-test-123"

        # Initial configuration
        initial_config = PromptConfigurationData(
            deployment_name="gpt-4",
            model_settings=ModelSettings(temperature=0.7),
            stream=True,
        )
        initial_json = initial_config.model_dump_json(exclude_none=True)

        # Update request with partial fields
        update_request = PromptConfigRequest(
            prompt_id=prompt_id,
            deployment_name="gpt-3.5-turbo",
            llm_retry_limit=10,
        )

        # Mock Redis for update operation
        mock_redis_service.get.return_value = initial_json
        mock_redis_service.set.return_value = True

        # Act - Update configuration
        with patch('budprompt.prompt.services.app_settings') as mock_settings:
            mock_settings.prompt_config_redis_ttl = 86400
            update_result = await prompt_service.save_prompt_config(update_request)

        # Get the updated data from the set call
        updated_json = mock_redis_service.set.call_args[0][1]

        # Mock Redis for get operation
        mock_redis_service.get.return_value = updated_json

        # Act - Get updated configuration
        get_result = await prompt_service.get_prompt_config(prompt_id)

        # Assert
        assert get_result.code == 200
        assert get_result.data.deployment_name == "gpt-3.5-turbo"  # Updated
        assert get_result.data.model_settings.temperature == 0.7  # Preserved
        assert get_result.data.stream == True  # Preserved
        assert get_result.data.llm_retry_limit == 10  # Updated


# docker exec -it budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/test_unit_tests/test_prompt_service.py -v"
