"""Unit tests for JWT-based playground authentication."""

import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status

from budapp.commons.constants import EndpointStatusEnum, ProjectStatusEnum, UserTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.commons.security import hash_token
from budapp.playground_ops.schemas import (
    EndpointInfo,
    PlaygroundInitializeRequest,
    PlaygroundInitializeResponse,
)
from budapp.playground_ops.services import PlaygroundService


class TestJWTHashing:
    """Test JWT hashing functionality."""

    @pytest.mark.asyncio
    async def test_jwt_hashing_consistency(self):
        """Test that JWT hashing produces consistent results."""
        # Arrange
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        session = Mock()
        service = PlaygroundService(session)

        # Act
        hash1 = await service.hash_jwt_token(jwt_token)
        hash2 = await service.hash_jwt_token(jwt_token)

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 character hex string

    @pytest.mark.asyncio
    async def test_jwt_hashing_uses_same_pattern_as_api_keys(self):
        """Test that JWT hashing uses the same pattern as API keys."""
        # Arrange
        token = "test-token"
        session = Mock()
        service = PlaygroundService(session)

        # Act
        jwt_hash = await service.hash_jwt_token(token)
        expected_hash = hash_token(f"bud-{token}")

        # Assert
        assert jwt_hash == expected_hash

    @pytest.mark.asyncio
    async def test_different_jwts_produce_different_hashes(self):
        """Test that different JWT tokens produce different hashes."""
        # Arrange
        jwt1 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.rTCH8cLoGxAm_xw68z-zXVKi9ie6xJn9tnVWjd_9ftE"
        jwt2 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIn0.LwimMJA5puF0KHNbYFqEU0oXhHCLmtRqW3hRjAuCCGo"
        session = Mock()
        service = PlaygroundService(session)

        # Act
        hash1 = await service.hash_jwt_token(jwt1)
        hash2 = await service.hash_jwt_token(jwt2)

        # Assert
        assert hash1 != hash2


class TestPlaygroundInitialization:
    """Test playground session initialization."""

    @pytest.mark.asyncio
    async def test_initialize_session_success(self):
        """Test successful playground session initialization."""
        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        project_id = uuid4()
        endpoint_id = uuid4()
        model_id = uuid4()
        jwt_token = "test-jwt-token"
        jwt_expiry = int(time.time()) + 3600  # 1 hour from now

        # Mock user data
        mock_user = Mock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Mock project data
        mock_project = Mock()
        mock_project.id = project_id
        mock_project.name = "Test Project"

        # Mock endpoint data
        mock_endpoint = Mock()
        mock_endpoint.id = endpoint_id
        mock_endpoint.name = "test-endpoint"
        mock_endpoint.status = EndpointStatusEnum.RUNNING
        mock_endpoint.project_id = project_id
        mock_endpoint.model = Mock()
        mock_endpoint.model.id = model_id
        mock_endpoint.model.name = "test-model"

        # Setup mocks
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis:

            # Configure mocks
            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service response with proper structure
            mock_project_response = Mock()
            mock_project_response.project = mock_project
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_response], 1))

            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=([(mock_endpoint, None, None, None)], 1)
            )
            mock_redis_instance = Mock()
            mock_redis_instance.set = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Act
            response = await service.initialize_session(jwt_token, user_id, jwt_expiry)

            # Assert
            assert isinstance(response, PlaygroundInitializeResponse)
            assert response.user_id == user_id
            assert response.initialization_status == "success"
            assert response.ttl == 3600
            assert response.message == "JWT session initialized successfully"

            # Verify Redis was called with correct data
            mock_redis_instance.set.assert_called_once()
            call_args = mock_redis_instance.set.call_args
            redis_key = call_args[0][0]
            redis_data = json.loads(call_args[0][1])

            # Check Redis key format
            expected_hash = await service.hash_jwt_token(jwt_token)
            assert redis_key == f"api_key:{expected_hash}"

            # Check Redis data structure
            assert "test-endpoint" in redis_data
            assert redis_data["test-endpoint"]["endpoint_id"] == str(endpoint_id)
            assert redis_data["test-endpoint"]["model_id"] == str(model_id)
            assert redis_data["__metadata__"]["user_id"] == str(user_id)
            assert redis_data["__metadata__"]["api_key_id"] is None

    @pytest.mark.asyncio
    async def test_initialize_session_expired_jwt(self):
        """Test initialization with expired JWT token."""
        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        jwt_token = "expired-jwt-token"
        jwt_expiry = int(time.time()) - 3600  # 1 hour ago (expired)

        # Mock user data
        mock_user = Mock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Mock project data
        mock_project = Mock()
        mock_project.id = uuid4()

        # Setup mocks
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service:

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service response with proper structure
            mock_project_response = Mock()
            mock_project_response.project = mock_project
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_response], 1))

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.initialize_session(jwt_token, user_id, jwt_expiry)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "expired" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_initialize_session_no_projects(self):
        """Test initialization when user has no active projects."""
        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        jwt_token = "test-jwt-token"

        # Mock user data
        mock_user = Mock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mocks
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service:

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([], 0))

            # Act & Assert
            with pytest.raises(ClientException) as exc_info:
                await service.initialize_session(jwt_token, user_id)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "No active projects" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_initialize_session_admin_user(self):
        """Test initialization for admin user shows all endpoints."""
        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        project_id = uuid4()
        jwt_token = "admin-jwt-token"

        # Mock user data (ADMIN type)
        mock_user = Mock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.ADMIN

        # Mock project data
        mock_project = Mock()
        mock_project.id = project_id

        # Mock endpoints (both published and unpublished)
        endpoint1 = Mock()
        endpoint1.id = uuid4()
        endpoint1.name = "published-endpoint"
        endpoint1.status = EndpointStatusEnum.RUNNING
        endpoint1.project_id = project_id
        endpoint1.model = Mock(id=uuid4(), name="model1")

        endpoint2 = Mock()
        endpoint2.id = uuid4()
        endpoint2.name = "unpublished-endpoint"
        endpoint2.status = EndpointStatusEnum.RUNNING
        endpoint2.project_id = project_id
        endpoint2.model = Mock(id=uuid4(), name="model2")

        # Setup mocks
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis:

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service response with proper structure
            mock_project_response = Mock()
            mock_project_response.project = mock_project
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_response], 1))

            # Admin users should get all endpoints (not filtered by is_published)
            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=(
                    [(endpoint1, None, None, None), (endpoint2, None, None, None)],
                    2
                )
            )

            mock_redis_instance = Mock()
            mock_redis_instance.set = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Act
            response = await service.initialize_session(jwt_token, user_id)

            # Assert
            assert response.initialization_status == "success"
            assert response.user_id == user_id

            # Verify endpoint manager was called without is_published filter
            call_args = mock_endpoint_manager.return_value.get_all_playground_deployments.call_args
            filters = call_args[1]['filters']
            assert 'is_published' not in filters
            assert filters['status'] == EndpointStatusEnum.RUNNING


class TestRedisCache:
    """Test Redis cache population for JWT tokens."""

    @pytest.mark.asyncio
    async def test_redis_cache_structure(self):
        """Test that Redis cache uses correct structure for JWT tokens."""
        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        project_id = uuid4()
        jwt_token = "test-jwt-token"

        # Create test endpoints
        endpoints_data = [
            {
                "id": uuid4(),
                "name": "endpoint-1",
                "model_id": uuid4(),
                "project_id": project_id,
            },
            {
                "id": uuid4(),
                "name": "endpoint-2",
                "model_id": uuid4(),
                "project_id": project_id,
            },
        ]

        # Mock data
        mock_user = Mock(id=user_id, user_type=UserTypeEnum.CLIENT)
        mock_project = Mock(id=project_id)

        mock_endpoints = []
        for ep_data in endpoints_data:
            mock_ep = Mock()
            mock_ep.id = ep_data["id"]
            mock_ep.name = ep_data["name"]
            mock_ep.status = EndpointStatusEnum.ACTIVE
            mock_ep.project_id = ep_data["project_id"]
            mock_ep.model = Mock(id=ep_data["model_id"], name=f"model-{ep_data['name']}")
            mock_endpoints.append((mock_ep, None, None, None))

        # Setup mocks
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis:

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)
            mock_project_service.return_value.list_projects = AsyncMock(return_value=([mock_project], 1))
            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=(mock_endpoints, len(mock_endpoints))
            )

            mock_redis_instance = Mock()
            mock_redis_instance.set = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Act
            await service.initialize_session(jwt_token, user_id)

            # Assert
            mock_redis_instance.set.assert_called_once()
            call_args = mock_redis_instance.set.call_args
            redis_data = json.loads(call_args[0][1])

            # Verify structure matches API key pattern
            assert "__metadata__" in redis_data
            assert redis_data["__metadata__"]["api_key_id"] is None  # JWT doesn't have api_key_id
            assert redis_data["__metadata__"]["user_id"] == str(user_id)
            assert redis_data["__metadata__"]["api_key_project_id"] == str(project_id)

            # Verify endpoints are stored correctly
            for ep_data in endpoints_data:
                assert ep_data["name"] in redis_data
                assert redis_data[ep_data["name"]]["endpoint_id"] == str(ep_data["id"])
                assert redis_data[ep_data["name"]]["model_id"] == str(ep_data["model_id"])
                assert redis_data[ep_data["name"]]["project_id"] == str(ep_data["project_id"])

    @pytest.mark.asyncio
    async def test_redis_ttl_set_correctly(self):
        """Test that Redis TTL is set based on JWT expiry."""
        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        project_id = uuid4()
        jwt_token = "test-jwt-token"
        current_time = int(time.time())
        jwt_expiry = current_time + 7200  # 2 hours from now

        # Mock data
        mock_user = Mock(id=user_id, user_type=UserTypeEnum.CLIENT)
        mock_project = Mock(id=project_id)

        # Setup mocks
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis, \
             patch('budapp.playground_ops.services.time.time', return_value=current_time):

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)
            mock_project_service.return_value.list_projects = AsyncMock(return_value=([mock_project], 1))
            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=([], 0)
            )

            mock_redis_instance = Mock()
            mock_redis_instance.set = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Act
            response = await service.initialize_session(jwt_token, user_id, jwt_expiry)

            # Assert
            assert response.ttl == 7200  # Should match the calculated TTL

            # Verify Redis was called with correct TTL
            mock_redis_instance.set.assert_called_once()
            call_kwargs = mock_redis_instance.set.call_args[1]
            assert call_kwargs.get('ex') == 7200


class TestPlaygroundInitializeRequest:
    """Test request validation for playground initialization."""

    def test_valid_jwt_format(self):
        """Test that valid JWT format passes validation."""
        # Arrange
        valid_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        # Act
        request = PlaygroundInitializeRequest(jwt_token=valid_jwt)

        # Assert
        assert request.jwt_token == valid_jwt

    def test_invalid_jwt_format_missing_parts(self):
        """Test that JWT with missing parts fails validation."""
        # Arrange
        invalid_jwt = "not.a.jwt"  # Only 2 parts instead of 3

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PlaygroundInitializeRequest(jwt_token="not.jwt")

        assert "Invalid JWT token format" in str(exc_info.value)

    def test_empty_jwt_token(self):
        """Test that empty JWT token fails validation."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PlaygroundInitializeRequest(jwt_token="")

        assert "JWT token cannot be empty" in str(exc_info.value)

    def test_jwt_token_whitespace_trimmed(self):
        """Test that JWT token whitespace is trimmed."""
        # Arrange
        jwt_with_spaces = "  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c  "
        expected_jwt = jwt_with_spaces.strip()

        # Act
        request = PlaygroundInitializeRequest(jwt_token=jwt_with_spaces)

        # Assert
        assert request.jwt_token == expected_jwt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
