"""Integration tests for endpoint publication API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from budapp.commons.constants import EndpointStatusEnum, PermissionEnum
from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.endpoint_ops.schemas import (
    PublicationHistoryEntry,
    PublicationHistoryResponse,
    PublishEndpointResponse,
    UpdatePublicationStatusRequest,
)
from budapp.main import app
from budapp.user_ops.schemas import User


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "admin@example.com"
    user.name = "Admin User"
    user.is_superuser = True
    user.status = "active"
    return user


@pytest.fixture
def mock_endpoint():
    """Create a mock endpoint for testing."""
    endpoint = Mock()
    endpoint.id = uuid4()
    endpoint.name = "Test Endpoint"
    endpoint.status = EndpointStatusEnum.RUNNING
    endpoint.is_published = False
    endpoint.published_date = None
    endpoint.published_by = None
    endpoint.project_id = uuid4()
    endpoint.model_id = uuid4()
    endpoint.model = Mock(name="Test Model", id=uuid4())
    endpoint.project = Mock(name="Test Project", id=uuid4())
    endpoint.cluster = None
    endpoint.created_at = datetime.now(timezone.utc)
    endpoint.modified_at = datetime.now(timezone.utc)
    endpoint.is_deprecated = False
    endpoint.supported_endpoints = []
    return endpoint


@pytest.fixture
def auth_headers(mock_current_user):
    """Create authorization headers."""
    return {
        "Authorization": "Bearer test-token",
        "X-Resource-Type": "project",
        "X-Entity-Id": str(uuid4())
    }


class TestPublicationAPIEndpoints:
    """Integration tests for publication API endpoints."""

    @pytest.mark.asyncio
    async def test_update_publication_status_publish(self, client, mock_current_user, mock_endpoint, auth_headers):
        """Test PUT /endpoints/{endpoint_id}/publish endpoint for publishing."""
        endpoint_id = mock_endpoint.id

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.update_publication_status', new_callable=AsyncMock) as mock_update:
                    # Configure the updated endpoint
                    mock_endpoint.is_published = True
                    mock_endpoint.published_date = datetime.now(timezone.utc)
                    mock_endpoint.published_by = mock_current_user.id
                    mock_update.return_value = mock_endpoint

                    # Make request
                    response = client.put(
                        f"/endpoints/{endpoint_id}/publish",
                        json={"action": "publish", "metadata": {"reason": "Ready for production"}},
                        headers=auth_headers
                    )

                    # Assert
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["data"]["is_published"] is True
                    assert data["data"]["endpoint_id"] == str(endpoint_id)
                    assert "published successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_update_publication_status_unpublish(self, client, mock_current_user, mock_endpoint, auth_headers):
        """Test PUT /endpoints/{endpoint_id}/publish endpoint for unpublishing."""
        endpoint_id = mock_endpoint.id
        mock_endpoint.is_published = True
        mock_endpoint.published_date = datetime.now(timezone.utc)

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.update_publication_status', new_callable=AsyncMock) as mock_update:
                    # Configure the updated endpoint
                    mock_endpoint.is_published = False
                    mock_endpoint.published_date = None
                    mock_update.return_value = mock_endpoint

                    # Make request
                    response = client.put(
                        f"/endpoints/{endpoint_id}/publish",
                        json={"action": "unpublish", "metadata": {"reason": "Security issue"}},
                        headers=auth_headers
                    )

                    # Assert
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["data"]["is_published"] is False
                    assert "unpublished successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_update_publication_status_not_found(self, client, mock_current_user, auth_headers):
        """Test PUT /endpoints/{endpoint_id}/publish with non-existent endpoint."""
        endpoint_id = uuid4()

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.update_publication_status', new_callable=AsyncMock) as mock_update:
                    mock_update.side_effect = ClientException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        message=f"Endpoint with ID {endpoint_id} not found"
                    )

                    # Make request
                    response = client.put(
                        f"/endpoints/{endpoint_id}/publish",
                        json={"action": "publish"},
                        headers=auth_headers
                    )

                    # Assert
                    assert response.status_code == status.HTTP_404_NOT_FOUND
                    data = response.json()
                    assert "not found" in data["message"]

    @pytest.mark.asyncio
    async def test_update_publication_status_invalid_action(self, client, mock_current_user, auth_headers):
        """Test PUT /endpoints/{endpoint_id}/publish with invalid action."""
        endpoint_id = uuid4()

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                # Make request with invalid action
                response = client.put(
                    f"/endpoints/{endpoint_id}/publish",
                    json={"action": "invalid_action"},
                    headers=auth_headers
                )

                # Assert - should fail at schema validation
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_publication_history(self, client, mock_current_user, mock_endpoint, auth_headers):
        """Test GET /endpoints/{endpoint_id}/publication-history endpoint."""
        endpoint_id = mock_endpoint.id

        # Create mock history entries
        history_entries = []
        for i in range(3):
            entry = PublicationHistoryEntry(
                id=uuid4(),
                deployment_id=endpoint_id,
                action="publish" if i % 2 == 0 else "unpublish",
                performed_by=uuid4(),
                performed_at=datetime.now(timezone.utc),
                metadata={"iteration": i},
                previous_state={"is_published": i % 2 != 0},
                new_state={"is_published": i % 2 == 0},
                created_at=datetime.now(timezone.utc),
                modified_at=datetime.now(timezone.utc),
                performed_by_user={
                    "id": str(uuid4()),
                    "email": f"user{i}@example.com",
                    "name": f"User {i}"
                }
            )
            history_entries.append(entry)

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.get_publication_history', new_callable=AsyncMock) as mock_get_history:
                    mock_get_history.return_value = {
                        "history": history_entries,
                        "total_record": 3,
                        "page": 1,
                        "limit": 20,
                        "code": status.HTTP_200_OK,
                        "message": "Successfully retrieved publication history"
                    }

                    # Make request
                    response = client.get(
                        f"/endpoints/{endpoint_id}/publication-history",
                        headers=auth_headers,
                        params={"page": 1, "limit": 20}
                    )

                    # Assert
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["total_record"] == 3
                    assert len(data["data"]["history"]) == 3
                    assert data["data"]["history"][0]["action"] in ["publish", "unpublish"]

    @pytest.mark.asyncio
    async def test_get_publication_history_pagination(self, client, mock_current_user, auth_headers):
        """Test publication history pagination."""
        endpoint_id = uuid4()

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.get_publication_history', new_callable=AsyncMock) as mock_get_history:
                    mock_get_history.return_value = {
                        "history": [],
                        "total_record": 100,
                        "page": 2,
                        "limit": 10,
                        "code": status.HTTP_200_OK,
                        "message": "Successfully retrieved publication history"
                    }

                    # Make request
                    response = client.get(
                        f"/endpoints/{endpoint_id}/publication-history",
                        headers=auth_headers,
                        params={"page": 2, "limit": 10}
                    )

                    # Assert
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["page"] == 2
                    assert data["limit"] == 10
                    assert data["total_record"] == 100

    @pytest.mark.asyncio
    async def test_list_endpoints_with_publication_filter(self, client, mock_current_user, auth_headers):
        """Test GET /endpoints/ with is_published filter."""
        project_id = uuid4()

        # Create mock published endpoints
        published_endpoints = []
        for i in range(2):
            endpoint = Mock()
            endpoint.id = uuid4()
            endpoint.name = f"Published Endpoint {i}"
            endpoint.status = EndpointStatusEnum.RUNNING
            endpoint.is_published = True
            endpoint.published_date = datetime.now(timezone.utc)
            endpoint.published_by = uuid4()
            endpoint.model = Mock(id=uuid4(), name=f"Model {i}")
            endpoint.cluster = None
            endpoint.created_at = datetime.now(timezone.utc)
            endpoint.modified_at = datetime.now(timezone.utc)
            endpoint.is_deprecated = False
            endpoint.supported_endpoints = []
            published_endpoints.append(endpoint)

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.get_all_endpoints', new_callable=AsyncMock) as mock_get_all:
                    mock_get_all.return_value = (published_endpoints, 2)

                    # Make request with is_published filter
                    response = client.get(
                        "/endpoints/",
                        headers=auth_headers,
                        params={
                            "project_id": str(project_id),
                            "is_published": True,
                            "page": 1,
                            "limit": 10
                        }
                    )

                    # Assert
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["total_record"] == 2
                    assert len(data["data"]["endpoints"]) == 2
                    assert all(ep["is_published"] for ep in data["data"]["endpoints"])

    @pytest.mark.asyncio
    async def test_permission_denied_for_non_admin(self, client, auth_headers):
        """Test that non-admin users cannot publish/unpublish endpoints."""
        endpoint_id = uuid4()

        # Create non-admin user
        non_admin_user = Mock(spec=User)
        non_admin_user.id = uuid4()
        non_admin_user.email = "user@example.com"
        non_admin_user.is_superuser = False
        non_admin_user.status = "active"

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=non_admin_user):
            with patch('budapp.commons.permission_handler.check_resource_based_permissions', return_value=False):
                # Make request
                response = client.put(
                    f"/endpoints/{endpoint_id}/publish",
                    json={"action": "publish"},
                    headers=auth_headers
                )

                # Assert - should get permission denied
                assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_publish_already_published_endpoint_integration(self, client, mock_current_user, auth_headers):
        """Integration test for publishing an already published endpoint."""
        endpoint_id = uuid4()

        # Create already published endpoint
        published_endpoint = Mock()
        published_endpoint.id = endpoint_id
        published_endpoint.name = "Already Published Endpoint"
        published_endpoint.status = EndpointStatusEnum.RUNNING
        published_endpoint.is_published = True
        published_endpoint.published_date = datetime.now(timezone.utc)
        published_endpoint.published_by = uuid4()

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.update_publication_status', new_callable=AsyncMock) as mock_update:
                    mock_update.return_value = published_endpoint

                    # Make request
                    response = client.put(
                        f"/endpoints/{endpoint_id}/publish",
                        json={"action": "publish", "metadata": {"reason": "Re-publishing"}},
                        headers=auth_headers
                    )

                    # Assert - should succeed (idempotent)
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["data"]["is_published"] is True
                    assert data["message"] == "Endpoint published successfully"

    @pytest.mark.asyncio
    async def test_publish_endpoint_invalid_state_integration(self, client, mock_current_user, auth_headers):
        """Integration test for publishing an endpoint in invalid state."""
        endpoint_id = uuid4()

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.update_publication_status', new_callable=AsyncMock) as mock_update:
                    # Mock service to raise exception for invalid state
                    mock_update.side_effect = ClientException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        message="Cannot publish endpoint in PENDING state. Endpoint must be in RUNNING state to be published."
                    )

                    # Make request
                    response = client.put(
                        f"/endpoints/{endpoint_id}/publish",
                        json={"action": "publish", "metadata": {"reason": "Testing"}},
                        headers=auth_headers
                    )

                    # Assert
                    assert response.status_code == status.HTTP_400_BAD_REQUEST
                    data = response.json()
                    assert "Cannot publish endpoint in PENDING state" in data["message"]
                    assert "must be in RUNNING state" in data["message"]

    @pytest.mark.asyncio
    async def test_unpublish_already_unpublished_endpoint_integration(self, client, mock_current_user, auth_headers):
        """Integration test for unpublishing an already unpublished endpoint."""
        endpoint_id = uuid4()

        # Create unpublished endpoint
        unpublished_endpoint = Mock()
        unpublished_endpoint.id = endpoint_id
        unpublished_endpoint.name = "Unpublished Endpoint"
        unpublished_endpoint.status = EndpointStatusEnum.RUNNING
        unpublished_endpoint.is_published = False
        unpublished_endpoint.published_date = None
        unpublished_endpoint.published_by = None

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                with patch('budapp.endpoint_ops.services.EndpointService.update_publication_status', new_callable=AsyncMock) as mock_update:
                    mock_update.return_value = unpublished_endpoint

                    # Make request
                    response = client.put(
                        f"/endpoints/{endpoint_id}/publish",
                        json={"action": "unpublish", "metadata": {"reason": "Re-unpublishing"}},
                        headers=auth_headers
                    )

                    # Assert - should succeed (idempotent)
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["data"]["is_published"] is False
                    assert data["message"] == "Endpoint unpublished successfully"

    @pytest.mark.asyncio
    async def test_invalid_publication_action_integration(self, client, mock_current_user, auth_headers):
        """Integration test for invalid publication action."""
        endpoint_id = uuid4()

        with patch('budapp.commons.dependencies.get_current_active_user', return_value=mock_current_user):
            with patch('budapp.commons.permission_handler.require_permissions', return_value=lambda x: x):
                # Make request with invalid action
                response = client.put(
                    f"/endpoints/{endpoint_id}/publish",
                    json={"action": "invalid_action"},
                    headers=auth_headers
                )

                # Assert - should fail validation
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
