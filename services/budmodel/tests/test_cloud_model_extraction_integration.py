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

"""Integration tests for cloud model extraction with real budconnect response structure."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from budmodel.model_info.cloud_service import CloudModelExtractionService
from budmodel.model_info.schemas import CloudModelExtractionRequest, ModelInfo


class TestCloudModelExtractionIntegration:
    """Integration tests for cloud model extraction."""

    @pytest.mark.asyncio
    async def test_extract_anthropic_claude_sonnet_4_5_with_null_fields(self):
        """Test extraction with actual budconnect response structure for anthropic/claude-sonnet-4-5."""
        # This is the actual response structure from budconnect
        budconnect_response = {
            "id": "588b7b6a-4375-4f1f-8e3c-e52b15202e30",
            "model_info_id": "0225da88-8f78-4959-969c-3439a55568fb",
            "description": "Claude Sonnet 4.5 is a state-of-the-art coding and agent-building model",
            "advantages": [
                "Achieves state-of-the-art performance on SWE-bench Verified",
                "Leads OSWorld benchmark with 61.4% accuracy",
            ],
            "disadvantages": [
                "CBRN classifiers may inadvertently flag normal content",
                "Research preview features are temporary",
            ],
            "use_cases": [
                "Building complex AI agents for extended tasks.",
                "Real-world software development and debugging.",
            ],
            "evaluations": None,  # NULL in response
            "languages": None,  # NULL in response
            "tags": [],  # Empty array
            "tasks": None,  # NULL in response - this was causing the error
            "papers": None,  # NULL in response
            "github_url": None,
            "website_url": None,
            "logo_url": None,
            "architecture": None,
            "model_tree": None,
            "uri": "anthropic/claude-sonnet-4-5",
            "modality": ["text_input", "text_output", "image_input"],
            "provider_name": "Anthropic",
            "provider_type": "anthropic",
        }

        # Mock the BudConnect client
        with patch("budmodel.model_info.cloud_service.BudConnectClient") as mock_client_class:
            mock_client = Mock()
            mock_client.fetch_model_details = AsyncMock(return_value=budconnect_response)
            mock_client_class.return_value = mock_client

            # Create request and service
            request = CloudModelExtractionRequest(model_uri="anthropic/claude-sonnet-4-5")
            service = CloudModelExtractionService()

            # Execute extraction
            result = await service(request)

            # Verify the result
            assert isinstance(result.model_info, ModelInfo)
            assert result.model_info.uri == "anthropic/claude-sonnet-4-5"
            assert result.model_info.author == "Anthropic"
            assert "Claude Sonnet 4.5" in result.model_info.description

            # Verify NULL fields are handled correctly (converted to empty lists)
            assert result.model_info.tasks == []  # Was None, should be []
            assert result.model_info.languages == []  # Was None, should be []
            assert result.model_info.tags == []  # Was empty array, should remain []

            # Verify populated fields
            assert len(result.model_info.use_cases) == 2
            assert len(result.model_info.strengths) == 2
            assert len(result.model_info.limitations) == 2

            # Verify modality conversion
            assert result.model_info.modality == "text_input, text_output, image_input"

    @pytest.mark.asyncio
    async def test_extract_with_all_null_optional_fields(self):
        """Test extraction when all optional fields are null."""
        budconnect_response = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test model description",
            "modality": ["text_input"],
            "tags": None,
            "tasks": None,
            "use_cases": None,
            "advantages": None,
            "disadvantages": None,
            "languages": None,
            "papers": None,
            "github_url": None,
            "website_url": None,
            "logo_url": None,
            "architecture": None,
            "model_tree": None,
            "evaluations": None,
        }

        with patch("budmodel.model_info.cloud_service.BudConnectClient") as mock_client_class:
            mock_client = Mock()
            mock_client.fetch_model_details = AsyncMock(return_value=budconnect_response)
            mock_client_class.return_value = mock_client

            request = CloudModelExtractionRequest(model_uri="test/model")
            service = CloudModelExtractionService()
            result = await service(request)

            # All null list fields should be empty lists
            assert result.model_info.tasks == []
            assert result.model_info.tags == []
            assert result.model_info.use_cases == []
            assert result.model_info.strengths == []
            assert result.model_info.limitations == []
            assert result.model_info.languages == []

    @pytest.mark.asyncio
    async def test_extract_with_empty_string_provider_name(self):
        """Test extraction with empty string provider name defaults to 'Unknown'."""
        budconnect_response = {
            "uri": "test/model",
            "provider_name": "",  # Empty string
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        with patch("budmodel.model_info.cloud_service.BudConnectClient") as mock_client_class:
            mock_client = Mock()
            mock_client.fetch_model_details = AsyncMock(return_value=budconnect_response)
            mock_client_class.return_value = mock_client

            request = CloudModelExtractionRequest(model_uri="test/model")
            service = CloudModelExtractionService()
            result = await service(request)

            assert result.model_info.author == "Unknown"

    @pytest.mark.asyncio
    async def test_extract_with_null_description(self):
        """Test extraction with null description defaults to empty string."""
        budconnect_response = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": None,  # NULL
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        with patch("budmodel.model_info.cloud_service.BudConnectClient") as mock_client_class:
            mock_client = Mock()
            mock_client.fetch_model_details = AsyncMock(return_value=budconnect_response)
            mock_client_class.return_value = mock_client

            request = CloudModelExtractionRequest(model_uri="test/model")
            service = CloudModelExtractionService()
            result = await service(request)

            assert result.model_info.description == ""
