"""Tests for model catalog and pricing functionality."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from budapp.commons.constants import EndpointStatusEnum
from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.crud import EndpointDataManager, PublicationHistoryDataManager
from budapp.endpoint_ops.models import DeploymentPricing
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.endpoint_ops.schemas import (
    DeploymentPricingInput,
    DeploymentPricingResponse,
    UpdatePricingRequest,
    UpdatePublicationStatusRequest,
)
from budapp.endpoint_ops.services import EndpointService
from budapp.model_ops.crud import ModelDataManager
from budapp.model_ops.models import Model as ModelModel
from budapp.model_ops.schemas import (
    ModelCatalogFilter,
    ModelCatalogItem,
    ModelCatalogResponse,
)
from budapp.model_ops.services import ModelCatalogService
from budapp.shared.redis_service import RedisService
from budapp.user_ops.models import User as UserModel


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    session.execute = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def mock_model():
    """Create a mock model."""
    model = Mock(spec=ModelModel)
    model.id = uuid4()
    model.name = "GPT-4"
    model.description = "Advanced language model"
    model.modality = ["text_input"]  # Use string value instead of enum
    model.status = "active"  # Use string value instead of enum
    model.author = "OpenAI"
    model.model_size = 1760
    model.provider_type = "CLOUD"
    model.strengths = ["reasoning", "coding"]
    model.tags = [{"name": "nlp", "color": "#3B82F6"}, {"name": "generation", "color": "#10B981"}]
    model.token_limit = 8192
    model.max_input_tokens = 4096
    model.use_cases = ["chatbot", "code generation", "content creation"]
    model.supported_endpoints = ["text-generation", "chat-completion"]
    return model


@pytest.fixture
def mock_endpoint():
    """Create a mock endpoint."""
    endpoint = Mock()
    endpoint.id = uuid4()
    endpoint.name = "gpt-4-endpoint"
    endpoint.status = EndpointStatusEnum.RUNNING
    endpoint.is_published = True
    endpoint.published_date = datetime.now(timezone.utc)
    endpoint.published_by = uuid4()
    endpoint.model_id = uuid4()
    return endpoint


@pytest.fixture
def mock_pricing():
    """Create a mock pricing object."""
    pricing = Mock(spec=DeploymentPricing)
    pricing.id = uuid4()
    pricing.endpoint_id = uuid4()
    pricing.input_cost = Decimal("0.03")
    pricing.output_cost = Decimal("0.06")
    pricing.currency = "USD"
    pricing.per_tokens = 1000
    pricing.is_current = True
    pricing.created_by = uuid4()  # Add created_by as UUID
    pricing.created_at = datetime.now(timezone.utc)
    pricing.modified_at = datetime.now(timezone.utc)  # Add modified_at as datetime
    return pricing


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=UserModel)
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_superuser = True
    return user


class TestPricingIntegration:
    """Test cases for pricing integration with publish API."""

    @pytest.mark.asyncio
    async def test_publish_endpoint_with_pricing_success(self, mock_session, mock_endpoint, mock_user):
        """Test successful publication of an endpoint with pricing."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()
        mock_endpoint.is_published = False
        mock_endpoint.id = endpoint_id

        pricing_data = DeploymentPricingInput(
            input_cost=0.03,
            output_cost=0.06,
            currency="USD",
            per_tokens=1000
        )

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_publication_status', new_callable=AsyncMock) as mock_update:
                with patch.object(EndpointDataManager, 'update_previous_pricing', new_callable=AsyncMock) as mock_update_pricing:
                    with patch.object(EndpointDataManager, 'create_deployment_pricing', new_callable=AsyncMock) as mock_create_pricing:
                        with patch.object(PublicationHistoryDataManager, 'create_publication_history', new_callable=AsyncMock):
                            with patch.object(RedisService, 'invalidate_catalog_cache', new_callable=AsyncMock):
                                    mock_retrieve.return_value = mock_endpoint

                                    # Configure the updated endpoint to be returned by update_publication_status
                                    updated_endpoint = Mock()
                                    updated_endpoint.id = endpoint_id
                                    updated_endpoint.is_published = True
                                    updated_endpoint.published_date = datetime.now(timezone.utc)
                                    updated_endpoint.published_by = mock_user.id
                                    mock_update.return_value = updated_endpoint

                                    # Act
                                    result = await service.update_publication_status(
                                        endpoint_id=endpoint_id,
                                        action="publish",
                                        current_user_id=mock_user.id,
                                        pricing=pricing_data.model_dump()
                                    )

                                    # Assert
                                    assert result.is_published is True
                                    mock_update_pricing.assert_called_once_with(endpoint_id)
                                    mock_create_pricing.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_endpoint_without_pricing_fails(self, mock_session, mock_endpoint, mock_user):
        """Test that publishing without pricing fails."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()
        mock_endpoint.is_published = False
        mock_endpoint.id = endpoint_id

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = mock_endpoint

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=endpoint_id,
                    action="publish",
                    current_user_id=mock_user.id,
                    pricing=None
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Pricing information is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_update_pricing_success(self, mock_session, mock_endpoint, mock_user, mock_pricing):
        """Test successful pricing update."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id
        mock_endpoint.is_published = True

        new_pricing_data = {
            "input_cost": 0.05,
            "output_cost": 0.10,
            "currency": "USD",
            "per_tokens": 1000
        }

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_previous_pricing', new_callable=AsyncMock) as mock_update_pricing:
                with patch.object(EndpointDataManager, 'create_deployment_pricing', new_callable=AsyncMock) as mock_create_pricing:
                    with patch.object(RedisService, 'invalidate_catalog_cache', new_callable=AsyncMock):
                            mock_retrieve.return_value = mock_endpoint
                            mock_create_pricing.return_value = mock_pricing

                            # Act
                            result = await service.update_pricing(
                                endpoint_id=endpoint_id,
                                pricing_data=new_pricing_data,
                                current_user_id=mock_user.id
                            )

                            # Assert
                            assert result is not None
                            mock_update_pricing.assert_called_once_with(endpoint_id)
                            mock_create_pricing.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pricing_history(self, mock_session, mock_endpoint, mock_pricing):
        """Test retrieving pricing history."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id

        # Create multiple pricing records
        pricing_history = [mock_pricing, mock_pricing, mock_pricing]

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'get_pricing_history', new_callable=AsyncMock) as mock_history:
                mock_retrieve.return_value = mock_endpoint
                mock_history.return_value = (pricing_history, 3)  # Return tuple with (history, total_count)

                # Act
                result = await service.get_pricing_history(
                    endpoint_id=endpoint_id,
                    page=1,
                    limit=10
                )

                # Assert
                assert result['total_record'] == 3
                assert len(result['pricing_history']) == 3
                assert result['page'] == 1
                assert result['limit'] == 10
                assert result['code'] == status.HTTP_200_OK

                # Verify DataManager was called with correct parameters
                mock_history.assert_called_once_with(
                    endpoint_id=endpoint_id,
                    offset=0,  # (page-1) * limit = (1-1) * 10 = 0
                    limit=10
                )


class TestModelCatalog:
    """Test cases for model catalog functionality."""

    @pytest.mark.asyncio
    async def test_get_published_models_with_cache_hit(self, mock_session):
        """Test getting published models when cache is available."""
        # Arrange
        service = ModelCatalogService(mock_session)
        filters = {"modality": ["text"]}

        cached_data = {
            "items": [
                {
                    "id": str(uuid4()),
                    "name": "GPT-4",
                    "modality": ["text"],
                    "pricing": {
                        "input_cost": 0.03,
                        "output_cost": 0.06,
                        "currency": "USD",
                        "per_tokens": 1000
                    }
                }
            ],
            "count": 1
        }

        with patch.object(RedisService, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = json.dumps(cached_data)

            # Act
            items, count = await service.get_published_models(
                filters=filters,
                offset=0,
                limit=10
            )

            # Assert
            assert len(items) == 1
            assert count == 1
            assert items[0]["name"] == "GPT-4"
            assert items[0]["pricing"]["input_cost"] == 0.03

    @pytest.mark.asyncio
    async def test_get_published_models_with_cache_miss(self, mock_session, mock_model, mock_endpoint):
        """Test getting published models when cache is not available."""
        # Arrange
        service = ModelCatalogService(mock_session)
        filters = {}

        # Mock database results
        db_results = [(
            mock_model,
            mock_endpoint,
            Decimal("0.03"),  # input_cost
            Decimal("0.06"),  # output_cost
            "USD",            # currency
            1000             # per_tokens
        )]

        with patch.object(RedisService, 'get', new_callable=AsyncMock) as mock_get:
            with patch.object(RedisService, 'set', new_callable=AsyncMock) as mock_set:
                with patch.object(ModelDataManager, 'get_published_models_catalog', new_callable=AsyncMock) as mock_catalog:
                    mock_get.return_value = None  # Cache miss
                    mock_catalog.return_value = (db_results, 1)

                    # Act
                    items, count = await service.get_published_models(
                        filters=filters,
                        offset=0,
                        limit=10
                    )

                    # Assert
                    assert len(items) == 1
                    assert count == 1
                    assert items[0]["name"] == mock_model.name
                    assert items[0]["pricing"]["input_cost"] == 0.03
                    assert items[0]["pricing"]["output_cost"] == 0.06

                    # Verify cache was set
                    mock_set.assert_called_once()
                    args, kwargs = mock_set.call_args
                    assert kwargs.get('ex') == 300  # 5-minute TTL

    @pytest.mark.asyncio
    async def test_get_model_details_success(self, mock_session, mock_model, mock_endpoint):
        """Test getting model details by endpoint ID."""
        # Arrange
        service = ModelCatalogService(mock_session)
        endpoint_id = mock_endpoint.id

        db_result = (
            mock_model,
            mock_endpoint,
            Decimal("0.03"),
            Decimal("0.06"),
            "USD",
            1000
        )

        with patch.object(RedisService, 'get', new_callable=AsyncMock) as mock_get:
            with patch.object(RedisService, 'set', new_callable=AsyncMock):
                with patch.object(ModelDataManager, 'get_published_model_detail', new_callable=AsyncMock) as mock_detail:
                    mock_get.return_value = None  # Cache miss
                    mock_detail.return_value = db_result

                    # Act
                    result = await service.get_model_details(endpoint_id)

                    # Assert
                    assert result["name"] == mock_model.name
                    assert result["endpoint_id"] == str(mock_endpoint.id)
                    assert result["pricing"]["input_cost"] == 0.03
                    assert "capabilities" in result
                    assert len(result["capabilities"]) > 0

    @pytest.mark.asyncio
    async def test_get_model_details_not_found(self, mock_session):
        """Test getting model details when model is not found."""
        # Arrange
        service = ModelCatalogService(mock_session)
        endpoint_id = uuid4()

        with patch.object(RedisService, 'get', new_callable=AsyncMock) as mock_get:
            with patch.object(ModelDataManager, 'get_published_model_detail', new_callable=AsyncMock) as mock_detail:
                mock_get.return_value = None
                mock_detail.return_value = None

                # Act & Assert
                with pytest.raises(ClientException) as exc_info:
                    await service.get_model_details(endpoint_id)

                assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
                assert "Published model not found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_catalog_search_functionality(self, mock_session, mock_model, mock_endpoint):
        """Test catalog search with search term."""
        # Arrange
        service = ModelCatalogService(mock_session)
        search_term = "GPT"

        db_results = [(
            mock_model,
            mock_endpoint,
            Decimal("0.03"),
            Decimal("0.06"),
            "USD",
            1000
        )]

        with patch.object(RedisService, 'get', new_callable=AsyncMock) as mock_get:
            with patch.object(RedisService, 'set', new_callable=AsyncMock):
                with patch.object(ModelDataManager, 'get_published_models_catalog', new_callable=AsyncMock) as mock_catalog:
                    mock_get.return_value = None
                    mock_catalog.return_value = (db_results, 1)

                    # Act
                    items, count = await service.get_published_models(
                        filters={},
                        offset=0,
                        limit=10,
                        search_term=search_term
                    )

                    # Assert
                    assert len(items) == 1
                    assert count == 1
                    # Verify search term was passed to CRUD
                    mock_catalog.assert_called_once()
                    call_args = mock_catalog.call_args
                    assert call_args.kwargs['search_term'] == search_term


class TestCacheInvalidation:
    """Test cases for cache invalidation."""

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_publish(self, mock_session, mock_endpoint, mock_user):
        """Test that cache is invalidated when endpoint is published."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id
        mock_endpoint.is_published = False

        pricing_data = {
            "input_cost": 0.03,
            "output_cost": 0.06,
            "currency": "USD",
            "per_tokens": 1000
        }

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_publication_status', new_callable=AsyncMock) as mock_update:
                with patch.object(EndpointDataManager, 'update_previous_pricing', new_callable=AsyncMock):
                    with patch.object(EndpointDataManager, 'create_deployment_pricing', new_callable=AsyncMock):
                        with patch.object(PublicationHistoryDataManager, 'create_publication_history', new_callable=AsyncMock):
                            with patch('budapp.endpoint_ops.services.RedisService') as mock_redis_class:
                                mock_redis_instance = AsyncMock()
                                mock_redis_class.return_value = mock_redis_instance
                                mock_retrieve.return_value = mock_endpoint

                                # Configure the updated endpoint
                                updated_endpoint = Mock()
                                updated_endpoint.id = endpoint_id
                                updated_endpoint.is_published = True
                                updated_endpoint.published_date = datetime.now(timezone.utc)
                                updated_endpoint.published_by = mock_user.id
                                mock_update.return_value = updated_endpoint

                                # Act
                                await service.update_publication_status(
                                    endpoint_id=endpoint_id,
                                    action="publish",
                                    current_user_id=mock_user.id,
                                    pricing=pricing_data
                                )

                                # Assert cache invalidation
                                mock_redis_instance.invalidate_catalog_cache.assert_called_once_with(endpoint_id=str(endpoint_id))

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_pricing_update(self, mock_session, mock_endpoint, mock_user, mock_pricing):
        """Test that cache is invalidated when pricing is updated."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id
        mock_endpoint.is_published = True

        new_pricing_data = {
            "input_cost": 0.05,
            "output_cost": 0.10,
            "currency": "USD",
            "per_tokens": 1000
        }

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_previous_pricing', new_callable=AsyncMock):
                with patch.object(EndpointDataManager, 'create_deployment_pricing', new_callable=AsyncMock) as mock_create:
                    with patch('budapp.endpoint_ops.services.RedisService') as mock_redis_class:
                            mock_redis_instance = AsyncMock()
                            mock_redis_class.return_value = mock_redis_instance
                            mock_retrieve.return_value = mock_endpoint
                            mock_create.return_value = mock_pricing

                            # Act
                            await service.update_pricing(
                                endpoint_id=endpoint_id,
                                pricing_data=new_pricing_data,
                                current_user_id=mock_user.id
                            )

                            # Assert cache invalidation
                            mock_redis_instance.invalidate_catalog_cache.assert_called_once_with(endpoint_id=str(endpoint_id))
