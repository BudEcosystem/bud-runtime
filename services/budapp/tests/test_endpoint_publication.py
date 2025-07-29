"""Tests for endpoint publication functionality."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from budapp.commons.constants import EndpointStatusEnum
from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.crud import EndpointDataManager, PublicationHistoryDataManager
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.endpoint_ops.models import PublicationHistory as PublicationHistoryModel
from budapp.endpoint_ops.schemas import (
    EndpointFilter,
    EndpointListResponse,
    PublicationHistoryEntry,
    PublishEndpointResponse,
    UpdatePublicationStatusRequest,
)
from budapp.endpoint_ops.services import EndpointService
from budapp.user_ops.models import User as UserModel


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    session.execute = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    return session


@pytest.fixture
def mock_endpoint():
    """Create a mock endpoint."""
    endpoint = Mock()
    endpoint.id = uuid4()
    endpoint.name = "Test Endpoint"
    endpoint.status = EndpointStatusEnum.RUNNING
    endpoint.is_published = False
    endpoint.published_date = None
    endpoint.published_by = None
    endpoint.project_id = uuid4()
    endpoint.model_id = uuid4()
    endpoint.cache_config = "{}"  # Add default cache_config
    return endpoint


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=UserModel)
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_superuser = True
    return user


class TestEndpointPublicationService:
    """Test cases for EndpointService publication methods."""

    @pytest.mark.asyncio
    async def test_update_publication_status_publish_success(self, mock_session, mock_endpoint, mock_user):
        """Test successful publication of an endpoint."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_publication_status', new_callable=AsyncMock) as mock_update:
                with patch.object(PublicationHistoryDataManager, 'create_publication_history', new_callable=AsyncMock) as mock_history:
                    mock_retrieve.return_value = mock_endpoint

                    # Configure the updated endpoint
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
                        action_metadata={"reason": "Ready for production"}
                    )

                    # Assert
                    assert result.is_published is True
                    assert result.published_by == mock_user.id
                    assert result.published_date is not None

                    # Verify history was created
                    mock_history.assert_called_once()
                    history_call_args = mock_history.call_args[1]
                    assert history_call_args['action'] == 'publish'
                    assert history_call_args['performed_by'] == mock_user.id
                    assert history_call_args['action_metadata'] == {"reason": "Ready for production"}

    @pytest.mark.asyncio
    async def test_update_publication_status_unpublish_success(self, mock_session, mock_endpoint, mock_user):
        """Test successful unpublishing of an endpoint."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id
        mock_endpoint.is_published = True
        mock_endpoint.published_date = datetime.now(timezone.utc)
        mock_endpoint.published_by = uuid4()

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_publication_status', new_callable=AsyncMock) as mock_update:
                with patch.object(PublicationHistoryDataManager, 'create_publication_history', new_callable=AsyncMock) as mock_history:
                    mock_retrieve.return_value = mock_endpoint

                    # Configure the updated endpoint
                    updated_endpoint = Mock()
                    updated_endpoint.id = endpoint_id
                    updated_endpoint.is_published = False
                    updated_endpoint.published_date = None
                    updated_endpoint.published_by = mock_user.id
                    mock_update.return_value = updated_endpoint

                    # Act
                    result = await service.update_publication_status(
                        endpoint_id=endpoint_id,
                        action="unpublish",
                        current_user_id=mock_user.id,
                        action_metadata={"reason": "Security issue found"}
                    )

                    # Assert
                    assert result.is_published is False
                    assert result.published_date is None

                    # Verify history was created
                    mock_history.assert_called_once()
                    history_call_args = mock_history.call_args[1]
                    assert history_call_args['action'] == 'unpublish'
                    assert history_call_args['action_metadata'] == {"reason": "Security issue found"}

    @pytest.mark.asyncio
    async def test_update_publication_status_endpoint_not_found(self, mock_session, mock_user):
        """Test publication when endpoint not found."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = None

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=endpoint_id,
                    action="publish",
                    current_user_id=mock_user.id
                )

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_update_publication_status_invalid_action(self, mock_session, mock_endpoint, mock_user):
        """Test publication with invalid action."""
        # Arrange
        service = EndpointService(mock_session)

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = mock_endpoint

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=mock_endpoint.id,
                    action="invalid_action",
                    current_user_id=mock_user.id
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid action" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_update_publication_status_invalid_endpoint_state(self, mock_session, mock_endpoint, mock_user):
        """Test publishing endpoint in invalid state."""
        # Arrange
        service = EndpointService(mock_session)
        mock_endpoint.status = EndpointStatusEnum.DELETED

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = mock_endpoint

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=mock_endpoint.id,
                    action="publish",
                    current_user_id=mock_user.id
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot publish endpoint" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_update_publication_status_idempotent_publish(self, mock_session, mock_endpoint, mock_user):
        """Test idempotent publish operation."""
        # Arrange
        service = EndpointService(mock_session)
        mock_endpoint.is_published = True
        mock_endpoint.published_date = datetime.now(timezone.utc)

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = mock_endpoint

            # Act
            result = await service.update_publication_status(
                endpoint_id=mock_endpoint.id,
                action="publish",
                current_user_id=mock_user.id
            )

            # Assert - should return the endpoint without error
            assert result == mock_endpoint

    @pytest.mark.asyncio
    async def test_get_publication_history_success(self, mock_session, mock_endpoint, mock_user):
        """Test getting publication history."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = mock_endpoint.id

        # Create mock history entries
        history_entries = []
        for i in range(3):
            entry = Mock()
            entry.id = uuid4()
            entry.deployment_id = endpoint_id
            entry.action = "publish" if i % 2 == 0 else "unpublish"
            entry.performed_by = mock_user.id
            entry.performed_at = datetime.now(timezone.utc)
            entry.action_metadata = {"iteration": i}
            history_entries.append(entry)

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(PublicationHistoryDataManager, 'get_publication_history', new_callable=AsyncMock) as mock_get_history:
                with patch('budapp.user_ops.crud.UserDataManager.retrieve_by_fields', new_callable=AsyncMock) as mock_get_user:
                    mock_retrieve.return_value = mock_endpoint
                    mock_get_history.return_value = (history_entries, 3)
                    mock_get_user.return_value = mock_user

                    # Act
                    result = await service.get_publication_history(
                        endpoint_id=endpoint_id,
                        page=1,
                        limit=20
                    )

                    # Assert
                    assert result['total_record'] == 3
                    assert len(result['history']) == 3
                    assert result['page'] == 1
                    assert result['limit'] == 20

    @pytest.mark.asyncio
    async def test_get_publication_history_endpoint_not_found(self, mock_session):
        """Test getting publication history for non-existent endpoint."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = None

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.get_publication_history(endpoint_id=endpoint_id)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestEndpointPublicationCRUD:
    """Test cases for CRUD operations related to publication."""

    @pytest.mark.asyncio
    async def test_update_publication_status_crud(self, mock_session):
        """Test CRUD update_publication_status method."""
        # Arrange
        crud = EndpointDataManager(mock_session)
        endpoint_id = uuid4()
        user_id = uuid4()
        published_date = datetime.now(timezone.utc)

        # Mock the database execute and result
        mock_result = Mock()
        mock_result.scalar_one.return_value = Mock(
            id=endpoint_id,
            is_published=True,
            published_by=user_id,
            published_date=published_date
        )
        mock_session.execute.return_value = mock_result

        # Act
        result = await crud.update_publication_status(
            endpoint_id=endpoint_id,
            is_published=True,
            published_by=user_id,
            published_date=published_date
        )

        # Assert
        assert result.is_published is True
        assert result.published_by == user_id
        assert result.published_date == published_date
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_published_endpoints_count(self, mock_session):
        """Test counting published endpoints."""
        # Arrange
        crud = EndpointDataManager(mock_session)
        project_id = uuid4()

        # Mock the count result
        mock_session.execute.return_value.scalar.return_value = 5
        crud.execute_scalar = Mock(return_value=5)

        # Act
        result = await crud.get_published_endpoints_count(project_id=project_id)

        # Assert
        assert result == 5

    @pytest.mark.asyncio
    async def test_create_publication_history(self, mock_session):
        """Test creating publication history entry."""
        # Arrange
        crud = PublicationHistoryDataManager(mock_session)
        deployment_id = uuid4()
        user_id = uuid4()
        action_time = datetime.now(timezone.utc)

        # Act
        await crud.create_publication_history(
            deployment_id=deployment_id,
            action="publish",
            performed_by=user_id,
            performed_at=action_time,
            action_metadata={"reason": "Initial publication"},
            previous_state={"is_published": False},
            new_state={"is_published": True}
        )

        # Assert
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Check the created object
        created_obj = mock_session.add.call_args[0][0]
        assert created_obj.deployment_id == deployment_id
        assert created_obj.action == "publish"
        assert created_obj.performed_by == user_id
        assert created_obj.action_metadata == {"reason": "Initial publication"}


class TestEndpointPublicationSchemas:
    """Test cases for publication-related schemas."""

    def test_endpoint_filter_with_publication(self):
        """Test EndpointFilter schema with is_published field."""
        # Test with is_published=True
        filter_data = {"name": "test", "is_published": True}
        filter_obj = EndpointFilter(**filter_data)
        assert filter_obj.is_published is True

        # Test with is_published=False
        filter_data = {"is_published": False}
        filter_obj = EndpointFilter(**filter_data)
        assert filter_obj.is_published is False

        # Test without is_published
        filter_data = {"name": "test"}
        filter_obj = EndpointFilter(**filter_data)
        assert filter_obj.is_published is None

    def test_endpoint_list_response_with_publication(self):
        """Test EndpointListResponse schema with publication fields."""
        response_data = {
            "id": uuid4(),
            "name": "Test Endpoint",
            "status": EndpointStatusEnum.RUNNING,
            "model": {
                "id": uuid4(),
                "name": "Test Model",
                "author": "Test Author",
                "modality": ["text_input", "text_output"],
                "source": "test_source",
                "uri": "test://model/uri",
                "provider_type": "cloud_model",
                "created_at": datetime.now(timezone.utc),
                "modified_at": datetime.now(timezone.utc),
                "supported_endpoints": []
            },
            "created_at": datetime.now(timezone.utc),
            "modified_at": datetime.now(timezone.utc),
            "is_deprecated": False,
            "supported_endpoints": [],
            "is_published": True,
            "published_date": datetime.now(timezone.utc),
            "published_by": uuid4()
        }

        response = EndpointListResponse(**response_data)
        assert response.is_published is True
        assert response.published_date is not None
        assert response.published_by is not None

    def test_update_publication_status_request(self):
        """Test UpdatePublicationStatusRequest schema."""
        # Valid publish action
        request = UpdatePublicationStatusRequest(
            action="publish",
            action_metadata={"reason": "Ready for production"}
        )
        assert request.action == "publish"
        assert request.action_metadata["reason"] == "Ready for production"

        # Valid unpublish action
        request = UpdatePublicationStatusRequest(
            action="unpublish",
            action_metadata=None
        )
        assert request.action == "unpublish"
        assert request.action_metadata is None

        # Invalid action should raise validation error
        with pytest.raises(ValueError):
            UpdatePublicationStatusRequest(action="invalid")

    def test_publication_history_entry(self):
        """Test PublicationHistoryEntry schema."""
        entry_data = {
            "id": uuid4(),
            "deployment_id": uuid4(),
            "action": "publish",
            "performed_by": uuid4(),
            "performed_at": datetime.now(timezone.utc),
            "action_metadata": {"reason": "Test"},
            "previous_state": {"is_published": False},
            "new_state": {"is_published": True},
            "created_at": datetime.now(timezone.utc),
            "modified_at": datetime.now(timezone.utc),
            "performed_by_user": {
                "id": uuid4(),
                "email": "test@example.com",
                "name": "Test User"
            }
        }

        entry = PublicationHistoryEntry(**entry_data)
        assert entry.action == "publish"
        assert entry.action_metadata["reason"] == "Test"
        assert entry.performed_by_user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_publish_already_published_endpoint(self, mock_session, mock_user):
        """Test publishing an already published endpoint (idempotent operation)."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        # Create already published endpoint
        published_endpoint = Mock()
        published_endpoint.id = endpoint_id
        published_endpoint.name = "Already Published Endpoint"
        published_endpoint.status = EndpointStatusEnum.RUNNING
        published_endpoint.is_published = True
        published_endpoint.published_date = datetime.now(timezone.utc)
        published_endpoint.published_by = uuid4()

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = published_endpoint

            # Act
            result = await service.update_publication_status(
                endpoint_id=endpoint_id,
                action="publish",
                current_user_id=mock_user.id,
                action_metadata={"reason": "Attempting to republish"}
            )

            # Assert - should return without error (idempotent)
            assert result.is_published is True
            assert result == published_endpoint

    @pytest.mark.asyncio
    async def test_unpublish_already_unpublished_endpoint(self, mock_session, mock_user):
        """Test unpublishing an already unpublished endpoint (idempotent operation)."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        # Create unpublished endpoint
        unpublished_endpoint = Mock()
        unpublished_endpoint.id = endpoint_id
        unpublished_endpoint.name = "Unpublished Endpoint"
        unpublished_endpoint.status = EndpointStatusEnum.RUNNING
        unpublished_endpoint.is_published = False
        unpublished_endpoint.published_date = None
        unpublished_endpoint.published_by = None

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = unpublished_endpoint

            # Act
            result = await service.update_publication_status(
                endpoint_id=endpoint_id,
                action="unpublish",
                current_user_id=mock_user.id,
                action_metadata={"reason": "Attempting to unpublish again"}
            )

            # Assert - should return without error (idempotent)
            assert result.is_published is False
            assert result == unpublished_endpoint

    @pytest.mark.asyncio
    async def test_publish_endpoint_invalid_state_pending(self, mock_session, mock_user):
        """Test publishing an endpoint in PENDING state should fail."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        # Create endpoint in PENDING state
        pending_endpoint = Mock()
        pending_endpoint.id = endpoint_id
        pending_endpoint.name = "Pending Endpoint"
        pending_endpoint.status = EndpointStatusEnum.PENDING
        pending_endpoint.is_published = False
        pending_endpoint.published_date = None
        pending_endpoint.published_by = None

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = pending_endpoint

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=endpoint_id,
                    action="publish",
                    current_user_id=mock_user.id,
                    action_metadata={"reason": "Trying to publish pending endpoint"}
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot publish endpoint in pending state" in exc_info.value.message
            assert "must be in RUNNING state" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_publish_endpoint_invalid_state_failed(self, mock_session, mock_user):
        """Test publishing an endpoint in FAILED state should fail."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        # Create endpoint in FAILED state
        failed_endpoint = Mock()
        failed_endpoint.id = endpoint_id
        failed_endpoint.name = "Failed Endpoint"
        failed_endpoint.status = EndpointStatusEnum.FAILURE
        failed_endpoint.is_published = False
        failed_endpoint.published_date = None
        failed_endpoint.published_by = None

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = failed_endpoint

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=endpoint_id,
                    action="publish",
                    current_user_id=mock_user.id,
                    action_metadata={"reason": "Trying to publish failed endpoint"}
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot publish endpoint in failure state" in exc_info.value.message
            assert "must be in RUNNING state" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_publish_endpoint_invalid_state_unhealthy(self, mock_session, mock_user):
        """Test publishing an endpoint in UNHEALTHY state should fail."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        # Create endpoint in UNHEALTHY state
        unhealthy_endpoint = Mock()
        unhealthy_endpoint.id = endpoint_id
        unhealthy_endpoint.name = "Unhealthy Endpoint"
        unhealthy_endpoint.status = EndpointStatusEnum.UNHEALTHY
        unhealthy_endpoint.is_published = False
        unhealthy_endpoint.published_date = None
        unhealthy_endpoint.published_by = None

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = unhealthy_endpoint

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.update_publication_status(
                    endpoint_id=endpoint_id,
                    action="publish",
                    current_user_id=mock_user.id,
                    action_metadata={"reason": "Trying to publish unhealthy endpoint"}
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot publish endpoint in unhealthy state" in exc_info.value.message
            assert "must be in RUNNING state" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_unpublish_endpoint_any_state(self, mock_session, mock_user):
        """Test unpublishing an endpoint in any state should succeed."""
        # Test various states for unpublish operation
        states_to_test = [
            EndpointStatusEnum.RUNNING,
            EndpointStatusEnum.PENDING,
            EndpointStatusEnum.FAILURE,
            EndpointStatusEnum.UNHEALTHY,
            EndpointStatusEnum.DELETING
        ]

        for state in states_to_test:
            # Arrange
            service = EndpointService(mock_session)
            endpoint_id = uuid4()

            # Create published endpoint in various states
            endpoint = Mock()
            endpoint.id = endpoint_id
            endpoint.name = f"Endpoint in {state} state"
            endpoint.status = state
            endpoint.is_published = True
            endpoint.published_date = datetime.now(timezone.utc)
            endpoint.published_by = uuid4()

            with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
                with patch.object(EndpointDataManager, 'update_publication_status', new_callable=AsyncMock) as mock_update:
                    with patch.object(PublicationHistoryDataManager, 'create_publication_history', new_callable=AsyncMock):
                        mock_retrieve.return_value = endpoint

                        # Configure the updated endpoint
                        updated_endpoint = Mock()
                        updated_endpoint.id = endpoint_id
                        updated_endpoint.is_published = False
                        updated_endpoint.published_date = None
                        updated_endpoint.published_by = None
                        updated_endpoint.status = state
                        mock_update.return_value = updated_endpoint

                        # Act - should succeed regardless of state
                        result = await service.update_publication_status(
                            endpoint_id=endpoint_id,
                            action="unpublish",
                            current_user_id=mock_user.id,
                            action_metadata={"reason": f"Unpublishing {state} endpoint"}
                        )

                        # Assert
                        assert result.is_published is False
                        assert result.published_date is None

    @pytest.mark.asyncio
    async def test_publish_endpoint_state_transition(self, mock_session, mock_user):
        """Test publishing an endpoint tracks proper state transitions in history."""
        # Arrange
        service = EndpointService(mock_session)
        endpoint_id = uuid4()

        # Create endpoint ready to be published
        endpoint = Mock()
        endpoint.id = endpoint_id
        endpoint.name = "Test Endpoint"
        endpoint.status = EndpointStatusEnum.RUNNING
        endpoint.is_published = False
        endpoint.published_date = None
        endpoint.published_by = None

        with patch.object(EndpointDataManager, 'retrieve_by_fields', new_callable=AsyncMock) as mock_retrieve:
            with patch.object(EndpointDataManager, 'update_publication_status', new_callable=AsyncMock) as mock_update:
                with patch.object(PublicationHistoryDataManager, 'create_publication_history', new_callable=AsyncMock) as mock_history:
                    mock_retrieve.return_value = endpoint

                    # Configure the updated endpoint
                    action_time = datetime.now(timezone.utc)
                    updated_endpoint = Mock()
                    updated_endpoint.id = endpoint_id
                    updated_endpoint.is_published = True
                    updated_endpoint.published_date = action_time
                    updated_endpoint.published_by = mock_user.id
                    mock_update.return_value = updated_endpoint

                    # Act
                    await service.update_publication_status(
                        endpoint_id=endpoint_id,
                        action="publish",
                        current_user_id=mock_user.id,
                        action_metadata={"reason": "Testing state transition", "version": "1.0"}
                    )

                    # Assert - verify state transition tracking
                    mock_history.assert_called_once()
                    call_args = mock_history.call_args[1]

                    assert call_args['deployment_id'] == endpoint_id
                    assert call_args['action'] == "publish"
                    assert call_args['performed_by'] == mock_user.id
                    assert call_args['action_metadata'] == {"reason": "Testing state transition", "version": "1.0"}

                    # Verify state transition
                    assert call_args['previous_state']['is_published'] is False
                    assert call_args['previous_state']['published_date'] is None
                    assert call_args['previous_state']['published_by'] is None

                    assert call_args['new_state']['is_published'] is True
                    assert call_args['new_state']['published_date'] is not None
                    assert call_args['new_state']['published_by'] == str(mock_user.id)
