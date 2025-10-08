"""Tests for cluster settings API endpoints."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budapp.cluster_ops.models import ClusterSettings
from budapp.cluster_ops.schemas import ClusterSettingsResponse
from budapp.user_ops.models import User

# Import test helpers after the models to avoid circular imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'test_helpers'))
from cluster_settings_helpers import MockFactory, TestDataBuilder, AssertionHelpers


@pytest.fixture
def mock_user():
    """Create a mock user."""
    return MockFactory.create_mock_user()


@pytest.fixture
def test_client():
    """Create a test client."""
    from budapp.main import app
    return TestClient(app)


class TestClusterSettingsAPI:
    """Test cluster settings API endpoints."""

    def test_get_cluster_settings_success(self, test_client, mock_user):
        """Test GET /clusters/{cluster_id}/settings success."""
        cluster_id = uuid4()

        # Create mock response directly since we can't import ClusterSettingsResponse
        from budapp.cluster_ops.schemas import ClusterSettingsResponse
        now = datetime.now(timezone.utc)
        mock_response = ClusterSettingsResponse(
            id=uuid4(),
            cluster_id=cluster_id,
            default_storage_class="gp2",
            created_by=mock_user.id,
            created_at=now,
            modified_at=now
        )

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.get_cluster_settings',
                      return_value=mock_response) as mock_get:
                response = test_client.get(f"/clusters/{cluster_id}/settings")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                AssertionHelpers.assert_api_response_success(data, status.HTTP_200_OK)
                assert data["data"]["settings"]["id"] == str(mock_response.id)
                assert data["data"]["settings"]["cluster_id"] == str(cluster_id)
                assert data["data"]["settings"]["default_storage_class"] == "gp2"

                mock_get.assert_called_once_with(cluster_id)

    def test_get_cluster_settings_not_found(self, test_client, mock_user):
        """Test GET /clusters/{cluster_id}/settings when not found."""
        cluster_id = uuid4()

        from fastapi import HTTPException

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.get_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Cluster settings not found")):
                response = test_client.get(f"/clusters/{cluster_id}/settings")

                assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_cluster_settings_success(self, test_client, mock_user):
        """Test POST /clusters/{cluster_id}/settings success."""
        cluster_id = uuid4()

        request_data = {
            "default_storage_class": "premium-ssd"
        }

        # Create mock response directly since we can't import ClusterSettingsResponse
        from budapp.cluster_ops.schemas import ClusterSettingsResponse
        now = datetime.now(timezone.utc)
        mock_response = ClusterSettingsResponse(
            id=uuid4(),
            cluster_id=cluster_id,
            default_storage_class="premium-ssd",
            created_by=mock_user.id,
            created_at=now,
            modified_at=now
        )

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.create_cluster_settings',
                      return_value=mock_response) as mock_create:
                response = test_client.post(
                    f"/clusters/{cluster_id}/settings",
                    json=request_data
                )

                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                assert data["success"] is True
                assert data["data"]["settings"]["id"] == str(mock_response.id)
                assert data["data"]["settings"]["default_storage_class"] == "premium-ssd"

                mock_create.assert_called_once()

    def test_create_cluster_settings_invalid_storage_class(self, test_client, mock_user):
        """Test POST /clusters/{cluster_id}/settings with invalid storage class."""
        cluster_id = uuid4()

        request_data = {
            "default_storage_class": "invalid@storage"
        }

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            response = test_client.post(
                f"/clusters/{cluster_id}/settings",
                json=request_data
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_cluster_settings_already_exists(self, test_client, mock_user):
        """Test POST /clusters/{cluster_id}/settings when settings already exist."""
        cluster_id = uuid4()

        request_data = {
            "default_storage_class": "gp2"
        }

        from fastapi import HTTPException

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.create_cluster_settings',
                      side_effect=HTTPException(status_code=409, detail="Settings already exist")):
                response = test_client.post(
                    f"/clusters/{cluster_id}/settings",
                    json=request_data
                )

                assert response.status_code == status.HTTP_409_CONFLICT

    def test_update_cluster_settings_success(self, test_client, mock_user):
        """Test PUT /clusters/{cluster_id}/settings success."""
        cluster_id = uuid4()
        settings_id = uuid4()
        now = datetime.now(timezone.utc)

        request_data = {
            "default_storage_class": "updated-storage"
        }

        mock_response = ClusterSettingsResponse(
            id=settings_id,
            cluster_id=cluster_id,
            default_storage_class="updated-storage",
            created_by=mock_user.id,
            created_at=now,
            modified_at=now
        )

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.update_cluster_settings',
                      return_value=mock_response) as mock_update:
                response = test_client.put(
                    f"/clusters/{cluster_id}/settings",
                    json=request_data
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["success"] is True
                assert data["data"]["settings"]["default_storage_class"] == "updated-storage"

                mock_update.assert_called_once()

    def test_update_cluster_settings_not_found(self, test_client, mock_user):
        """Test PUT /clusters/{cluster_id}/settings when settings not found."""
        cluster_id = uuid4()

        request_data = {
            "default_storage_class": "updated-storage"
        }

        from fastapi import HTTPException

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.update_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Settings not found")):
                response = test_client.put(
                    f"/clusters/{cluster_id}/settings",
                    json=request_data
                )

                assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_cluster_settings_success(self, test_client, mock_user):
        """Test DELETE /clusters/{cluster_id}/settings success."""
        cluster_id = uuid4()

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.delete_cluster_settings',
                      return_value=True) as mock_delete:
                response = test_client.delete(f"/clusters/{cluster_id}/settings")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["success"] is True
                assert data["message"] == "Cluster settings deleted successfully"

                mock_delete.assert_called_once_with(cluster_id)

    def test_delete_cluster_settings_not_found(self, test_client, mock_user):
        """Test DELETE /clusters/{cluster_id}/settings when settings not found."""
        cluster_id = uuid4()

        from fastapi import HTTPException

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.delete_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Settings not found")):
                response = test_client.delete(f"/clusters/{cluster_id}/settings")

                assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthorized_access(self, test_client):
        """Test all endpoints without authentication."""
        cluster_id = uuid4()

        # Test GET without auth
        response = test_client.get(f"/clusters/{cluster_id}/settings")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Test POST without auth
        response = test_client.post(
            f"/clusters/{cluster_id}/settings",
            json={"default_storage_class": "test"}
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Test PUT without auth
        response = test_client.put(
            f"/clusters/{cluster_id}/settings",
            json={"default_storage_class": "test"}
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Test DELETE without auth
        response = test_client.delete(f"/clusters/{cluster_id}/settings")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_invalid_uuid_format(self, test_client, mock_user):
        """Test endpoints with invalid UUID format."""
        invalid_cluster_id = "not-a-valid-uuid"

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            # Test GET with invalid UUID
            response = test_client.get(f"/clusters/{invalid_cluster_id}/settings")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # Test POST with invalid UUID
            response = test_client.post(
                f"/clusters/{invalid_cluster_id}/settings",
                json={"default_storage_class": "test"}
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # Test PUT with invalid UUID
            response = test_client.put(
                f"/clusters/{invalid_cluster_id}/settings",
                json={"default_storage_class": "test"}
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # Test DELETE with invalid UUID
            response = test_client.delete(f"/clusters/{invalid_cluster_id}/settings")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_cluster_not_found(self, test_client, mock_user):
        """Test endpoints when cluster doesn't exist."""
        cluster_id = uuid4()

        from fastapi import HTTPException

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            # Test GET when cluster not found
            with patch('budapp.cluster_ops.services.ClusterService.get_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Cluster not found")):
                response = test_client.get(f"/clusters/{cluster_id}/settings")
                assert response.status_code == status.HTTP_404_NOT_FOUND

            # Test POST when cluster not found
            with patch('budapp.cluster_ops.services.ClusterService.create_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Cluster not found")):
                response = test_client.post(
                    f"/clusters/{cluster_id}/settings",
                    json={"default_storage_class": "test"}
                )
                assert response.status_code == status.HTTP_404_NOT_FOUND

            # Test PUT when cluster not found
            with patch('budapp.cluster_ops.services.ClusterService.update_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Cluster not found")):
                response = test_client.put(
                    f"/clusters/{cluster_id}/settings",
                    json={"default_storage_class": "test"}
                )
                assert response.status_code == status.HTTP_404_NOT_FOUND

            # Test DELETE when cluster not found
            with patch('budapp.cluster_ops.services.ClusterService.delete_cluster_settings',
                      side_effect=HTTPException(status_code=404, detail="Cluster not found")):
                response = test_client.delete(f"/clusters/{cluster_id}/settings")
                assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_request_body_validation(self, test_client, mock_user):
        """Test POST and PUT with empty or missing request body."""
        cluster_id = uuid4()

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            # Test POST with empty body
            response = test_client.post(f"/clusters/{cluster_id}/settings", json={})
            # Should be valid since default_storage_class is optional
            assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY or response.status_code == status.HTTP_404_NOT_FOUND

            # Test PUT with empty body
            response = test_client.put(f"/clusters/{cluster_id}/settings", json={})
            # Should be valid since default_storage_class is optional
            assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY or response.status_code == status.HTTP_404_NOT_FOUND

    def test_none_storage_class_handling(self, test_client, mock_user):
        """Test handling of null/None storage class values."""
        cluster_id = uuid4()
        settings_id = uuid4()
        now = datetime.now(timezone.utc)

        request_data = {
            "default_storage_class": None
        }

        mock_response = ClusterSettingsResponse(
            id=settings_id,
            cluster_id=cluster_id,
            default_storage_class=None,
            created_by=mock_user.id,
            created_at=now,
            modified_at=now
        )

        with patch('budapp.cluster_ops.cluster_settings_routes.get_current_user', return_value=mock_user):
            with patch('budapp.cluster_ops.services.ClusterService.create_cluster_settings',
                      return_value=mock_response) as mock_create:
                response = test_client.post(
                    f"/clusters/{cluster_id}/settings",
                    json=request_data
                )

                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                assert data["data"]["settings"]["default_storage_class"] is None
