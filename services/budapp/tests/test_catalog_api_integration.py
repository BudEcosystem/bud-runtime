"""Integration tests for model catalog API endpoints."""

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from budapp.commons.constants import ModalityEnum, PermissionEnum
from budapp.endpoint_ops.models import DeploymentPricing
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.model_ops.models import Model as ModelModel
from budapp.model_ops.schemas import ModelCatalogFilter, ModelCatalogItem, ModelCatalogResponse
from budapp.model_ops.services import ModelCatalogService
from budapp.user_ops.models import User as UserModel


@pytest.fixture
def mock_user_with_client_access():
    """Create a mock user with CLIENT_ACCESS permission."""
    user = Mock(spec=UserModel)
    user.id = uuid4()
    user.email = "client@example.com"
    user.name = "Client User"
    user.is_superuser = False
    user.permissions = [PermissionEnum.CLIENT_ACCESS]
    return user


@pytest.fixture
def mock_catalog_items():
    """Create mock catalog items."""
    return [
        {
            "id": str(uuid4()),
            "name": "GPT-4",
            "modality": ["text"],
            "status": "active",
            "description": "Advanced language model",
            "capabilities": ["reasoning", "coding", "nlp"],
            "token_limit": 8192,
            "max_input_tokens": 4096,
            "use_cases": ["chatbot", "code generation"],
            "author": "OpenAI",
            "model_size": 1760,
            "provider_type": "CLOUD",
            "uri": "openai/gpt-4",
            "source": "openai",
            "provider_icon": "openai_icon.png",
            "published_date": datetime.utcnow().isoformat(),
            "endpoint_id": str(uuid4()),
            "supported_endpoints": ["text-generation", "chat-completion"],
            "pricing": {
                "input_cost": 0.03,
                "output_cost": 0.06,
                "currency": "USD",
                "per_tokens": 1000
            }
        },
        {
            "id": str(uuid4()),
            "name": "Claude-3",
            "modality": ["text"],
            "status": "active",
            "description": "Anthropic's language model",
            "capabilities": ["analysis", "writing", "coding"],
            "token_limit": 100000,
            "max_input_tokens": 100000,
            "use_cases": ["research", "analysis", "writing"],
            "author": "Anthropic",
            "model_size": 2000,
            "provider_type": "CLOUD",
            "uri": "anthropic/claude-3",
            "source": "anthropic",
            "provider_icon": "anthropic_icon.png",
            "published_date": datetime.utcnow().isoformat(),
            "endpoint_id": str(uuid4()),
            "supported_endpoints": ["text-generation", "chat-completion"],
            "pricing": {
                "input_cost": 0.015,
                "output_cost": 0.075,
                "currency": "USD",
                "per_tokens": 1000
            }
        }
    ]


class TestCatalogAPIEndpoints:
    """Test cases for catalog API endpoints."""

    # @pytest.mark.asyncio
    # async def test_list_catalog_models_success(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test successful listing of catalog models."""
    #     # Arrange
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_published_models', new_callable=AsyncMock) as mock_get_models:
    #             mock_get_models.return_value = (mock_catalog_items, len(mock_catalog_items))
    #
    #             # Act
    #             response = client.get(
    #                 "/api/v1/models/catalog",
    #                 params={"page": 1, "limit": 10}
    #             )
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["object"] == "catalog.models.list"
    #             assert data["total_record"] == 2
    #             assert len(data["models"]) == 2
    #             assert data["models"][0]["name"] == "GPT-4"
    #             assert data["models"][0]["pricing"]["input_cost"] == 0.03
    #
    # @pytest.mark.asyncio
    # async def test_list_catalog_models_with_filters(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test listing catalog models with filters."""
    #     # Arrange
    #     filtered_items = [item for item in mock_catalog_items if item["modality"] == ["text"]]
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_published_models', new_callable=AsyncMock) as mock_get_models:
    #             mock_get_models.return_value = (filtered_items, len(filtered_items))
    #
    #             # Act
    #             response = client.get(
    #                 "/api/v1/models/catalog",
    #                 params={
    #                     "page": 1,
    #                     "limit": 10,
    #                     "modality": "text"
    #                 }
    #             )
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #
    #             # Verify filter was passed to service
    #             mock_get_models.assert_called_once()
    #             call_args = mock_get_models.call_args
    #             assert "modality" in call_args.kwargs["filters"]
    #
    # @pytest.mark.asyncio
    # async def test_get_catalog_model_details_success(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test getting model details by endpoint ID."""
    #     # Arrange
    #     endpoint_id = uuid4()
    #     model_detail = mock_catalog_items[0].copy()
    #     model_detail["endpoint_id"] = str(endpoint_id)
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_model_details', new_callable=AsyncMock) as mock_get_details:
    #             mock_get_details.return_value = model_detail
    #
    #             # Act
    #             response = client.get(f"/api/v1/models/catalog/{endpoint_id}")
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["name"] == "GPT-4"
    #             assert data["endpoint_id"] == str(endpoint_id)
    #             assert data["pricing"]["input_cost"] == 0.03
    #
    # @pytest.mark.asyncio
    # async def test_get_catalog_model_details_not_found(self, client: TestClient, mock_user_with_client_access):
    #     """Test getting model details when model not found."""
    #     # Arrange
    #     endpoint_id = uuid4()
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_model_details', new_callable=AsyncMock) as mock_get_details:
    #             mock_get_details.return_value = None
    #
    #             # Act
    #             response = client.get(f"/api/v1/models/catalog/{endpoint_id}")
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_404_NOT_FOUND
    #             data = response.json()
    #             assert "Published model not found" in data["message"]
    #
    # @pytest.mark.asyncio
    # async def test_catalog_models_with_search(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test searching catalog models using the search parameter."""
    #     # Arrange
    #     search_results = [item for item in mock_catalog_items if "GPT" in item["name"]]
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_published_models', new_callable=AsyncMock) as mock_get_models:
    #             mock_get_models.return_value = (search_results, len(search_results))
    #
    #             # Act
    #             response = client.get(
    #                 "/api/v1/models/catalog",
    #                 params={
    #                     "search": "GPT",
    #                     "page": 1,
    #                     "limit": 10
    #                 }
    #             )
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["object"] == "catalog.models.list"
    #             assert len(data["models"]) == 1
    #             assert "GPT" in data["models"][0]["name"]
    #
    #             # Verify search term was passed
    #             mock_get_models.assert_called_once()
    #             call_args = mock_get_models.call_args
    #             assert call_args.kwargs["search_term"] == "GPT"
    #
    # @pytest.mark.asyncio
    # async def test_catalog_access_denied_without_permission(self, client: TestClient):
    #     """Test that catalog endpoints require CLIENT_ACCESS permission."""
    #     # Arrange
    #     user_without_permission = Mock(spec=UserModel)
    #     user_without_permission.id = uuid4()
    #     user_without_permission.permissions = []  # No CLIENT_ACCESS
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=user_without_permission):
    #         # Act
    #         response = client.get("/api/v1/models/catalog")
    #
    #         # Assert
    #         assert response.status_code == status.HTTP_403_FORBIDDEN
    #
    # @pytest.mark.asyncio
    # async def test_catalog_pagination(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test catalog pagination."""
    #     # Arrange
    #     page = 2
    #     limit = 1
    #     offset = (page - 1) * limit
    #     paginated_items = mock_catalog_items[offset:offset + limit]
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_published_models', new_callable=AsyncMock) as mock_get_models:
    #             mock_get_models.return_value = (paginated_items, len(mock_catalog_items))
    #
    #             # Act
    #             response = client.get(
    #                 "/api/v1/models/catalog",
    #                 params={
    #                     "page": page,
    #                     "limit": limit
    #                 }
    #             )
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["page"] == page
    #             assert data["limit"] == limit
    #             assert len(data["models"]) == 1
    #             assert data["total_record"] == 2
    #
    # @pytest.mark.asyncio
    # async def test_catalog_ordering(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test catalog ordering by different fields."""
    #     # Arrange
    #     sorted_items = sorted(mock_catalog_items, key=lambda x: x["name"])
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_published_models', new_callable=AsyncMock) as mock_get_models:
    #             mock_get_models.return_value = (sorted_items, len(sorted_items))
    #
    #             # Act
    #             response = client.get(
    #                 "/api/v1/models/catalog",
    #                 params={
    #                     "page": 1,
    #                     "limit": 10,
    #                     "order_by": "name:asc"
    #                 }
    #             )
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #
    #             # Verify ordering was passed to service
    #             mock_get_models.assert_called_once()
    #             call_args = mock_get_models.call_args
    #             assert call_args.kwargs["order_by"] is not None
    #
    # @pytest.mark.asyncio
    # async def test_catalog_search_minimum_length(self, client: TestClient, mock_user_with_client_access):
    #     """Test that search requires minimum query length."""
    #     # Arrange
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         # Act
    #         response = client.get(
    #             "/api/v1/models/catalog",
    #             params={
    #                 "search": "a",  # Too short
    #                 "page": 1,
    #                 "limit": 10
    #             }
    #         )
    #
    #         # Assert
    #         assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    #
    # @pytest.mark.asyncio
    # async def test_catalog_combined_search_and_filter(self, client: TestClient, mock_user_with_client_access, mock_catalog_items):
    #     """Test combining search with filters."""
    #     # Arrange
    #     filtered_search_results = [
    #         item for item in mock_catalog_items
    #         if "GPT" in item["name"] and "text" in item["modality"]
    #     ]
    #
    #     with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_user_with_client_access):
    #         with patch.object(ModelCatalogService, 'get_published_models', new_callable=AsyncMock) as mock_get_models:
    #             mock_get_models.return_value = (filtered_search_results, len(filtered_search_results))
    #
    #             # Act
    #             response = client.get(
    #                 "/api/v1/models/catalog",
    #                 params={
    #                     "search": "GPT",
    #                     "modality": "text",
    #                     "page": 1,
    #                     "limit": 10,
    #                     "order_by": "name:asc"
    #                 }
    #             )
    #
    #             # Assert
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert len(data["models"]) == 1
    #
    #             # Verify both search and filters were passed
    #             mock_get_models.assert_called_once()
    #             call_args = mock_get_models.call_args
    #             assert call_args.kwargs["search_term"] == "GPT"
    #             assert "modality" in call_args.kwargs["filters"]
