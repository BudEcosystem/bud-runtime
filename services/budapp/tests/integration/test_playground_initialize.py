"""Integration tests for playground JWT initialization flow."""

import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budapp.commons.constants import EndpointStatusEnum, UserTypeEnum
from budapp.commons.dependencies import get_current_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.main import app
from budapp.playground_ops.schemas import PlaygroundInitializeRequest, PlaygroundInitializeResponse


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_superuser = False
    user.status = "active"
    return user


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return Mock()


class TestPlaygroundInitializeEndpoint:
    """Integration tests for /playground/initialize endpoint."""

    def test_initialize_endpoint_success(self, client, mock_current_user, mock_session):
        """Test successful initialization through the endpoint."""
        # Arrange
        user_id = mock_current_user.id
        project_id = uuid4()
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE5MTYyMzkwMjJ9.4Adcj3UFYzPUVaVF43FmMab6RlaQD8A9V8wFzzht-KQ"

        # Override FastAPI dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_session] = lambda: mock_session

        try:
            # Mock service dependencies
            with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
                 patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
                 patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
                 patch('budapp.playground_ops.services.RedisService') as mock_redis:

                # Setup database mocks
                mock_db_user = Mock(id=user_id, user_type=UserTypeEnum.CLIENT)
                mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_db_user)

                mock_project = Mock(id=project_id, name="Test Project")
                # Mock project service with proper structure
                mock_project_wrapper = Mock()
                mock_project_wrapper.project = mock_project
                mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_wrapper], 1))

                mock_endpoint = Mock()
                mock_endpoint.id = uuid4()
                mock_endpoint.name = "test-endpoint"
                mock_endpoint.status = EndpointStatusEnum.RUNNING
                mock_endpoint.project_id = project_id
                mock_endpoint.model = Mock(id=uuid4(), name="test-model")

                mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                    return_value=([(mock_endpoint, None, None, None)], 1)
                )

                mock_redis_instance = Mock()
                mock_redis_instance.set = AsyncMock()
                mock_redis.return_value = mock_redis_instance

                # Act
                response = client.post(
                    "/playground/initialize",
                    json={"jwt_token": jwt_token},
                    headers={"Authorization": f"Bearer {jwt_token}"}
                )

                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["initialization_status"] == "success"
                assert data["user_id"] == str(user_id)

                # Verify Redis was called
                mock_redis_instance.set.assert_called_once()
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()

    def test_initialize_endpoint_invalid_jwt_format(self, client):
        """Test initialization with invalid JWT format."""
        # Arrange
        invalid_jwt = "not.a.jwt"  # Invalid format
        mock_user = Mock(id=uuid4())

        # Override dependencies to avoid Dapr issues
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_session] = lambda: Mock()

        try:
            # Act
            response = client.post(
                "/playground/initialize",
                json={"jwt_token": invalid_jwt},
                headers={"Authorization": f"Bearer {invalid_jwt}"}
            )

            # Assert
            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "Invalid JWT token format" in str(data)
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()

    def test_initialize_endpoint_unauthorized(self, client):
        """Test initialization without proper authorization."""
        # Arrange
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        # Override dependency to raise an exception
        def raise_unauthorized():
            raise Exception("Unauthorized")

        app.dependency_overrides[get_current_user] = raise_unauthorized
        app.dependency_overrides[get_session] = lambda: Mock()

        try:
            # Act
            response = client.post(
                "/playground/initialize",
                json={"jwt_token": jwt_token},
                headers={"Authorization": f"Bearer {jwt_token}"}
            )

            # Assert - should get 500 error when dependency raises exception
            assert response.status_code == 500
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()


class TestJWTToRedisFlow:
    """Test the complete JWT to Redis storage flow."""

    @pytest.mark.asyncio
    async def test_jwt_stored_with_correct_hash(self):
        """Test that JWT is stored in Redis with correct hash as key."""
        from budapp.commons.security import hash_token
        from budapp.playground_ops.services import PlaygroundService

        # Arrange
        jwt_token = "test-jwt-token"
        user_id = uuid4()
        project_id = uuid4()
        session = Mock()
        service = PlaygroundService(session)

        # Calculate expected hash
        expected_hash = hash_token(f"bud-{jwt_token}")
        expected_redis_key = f"api_key:{expected_hash}"

        # Mock dependencies
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis:

            mock_user = Mock(id=user_id, user_type=UserTypeEnum.CLIENT)
            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service with proper structure
            mock_project_wrapper = Mock()
            mock_project_wrapper.project = Mock(id=project_id)
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_wrapper], 1))

            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=([], 0)
            )

            mock_redis_instance = Mock()
            mock_redis_instance.set = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Act
            await service.initialize_session(jwt_token, user_id)

            # Assert
            mock_redis_instance.set.assert_called_once()
            actual_redis_key = mock_redis_instance.set.call_args[0][0]
            assert actual_redis_key == expected_redis_key

    @pytest.mark.asyncio
    async def test_gateway_compatible_redis_structure(self):
        """Test that Redis structure is compatible with gateway expectations."""
        from budapp.playground_ops.services import PlaygroundService

        # Arrange
        jwt_token = "gateway-test-jwt"
        user_id = uuid4()
        project_id = uuid4()
        endpoint_id = uuid4()
        model_id = uuid4()
        session = Mock()
        service = PlaygroundService(session)

        # Create mock endpoint
        mock_endpoint = Mock()
        mock_endpoint.id = endpoint_id
        mock_endpoint.name = "gateway-endpoint"
        mock_endpoint.status = EndpointStatusEnum.RUNNING
        mock_endpoint.project_id = project_id
        mock_endpoint.model = Mock(id=model_id, name="gateway-model")

        # Mock dependencies
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis:

            mock_user = Mock(id=user_id, user_type=UserTypeEnum.ADMIN)
            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service with proper structure for ADMIN user
            mock_project_wrapper = Mock()
            mock_project_wrapper.project = Mock(id=project_id)
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_wrapper], 1))

            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=([(mock_endpoint, None, None, None)], 1)
            )

            mock_redis_instance = Mock()
            captured_data = {}

            async def capture_redis_data(key, data, **kwargs):
                captured_data['key'] = key
                captured_data['data'] = json.loads(data)

            mock_redis_instance.set = AsyncMock(side_effect=capture_redis_data)
            mock_redis.return_value = mock_redis_instance

            # Act
            await service.initialize_session(jwt_token, user_id)

            # Assert - Verify structure matches gateway expectations
            stored_data = captured_data['data']

            # Check endpoint mapping structure
            assert "gateway-endpoint" in stored_data
            endpoint_data = stored_data["gateway-endpoint"]
            assert endpoint_data["endpoint_id"] == str(endpoint_id)
            assert endpoint_data["model_id"] == str(model_id)
            assert endpoint_data["project_id"] == str(project_id)

            # Check metadata structure
            assert "__metadata__" in stored_data
            metadata = stored_data["__metadata__"]
            assert metadata["user_id"] == str(user_id)
            assert metadata["api_key_project_id"] == str(project_id)
            assert metadata["api_key_id"] is None  # JWT doesn't have api_key_id

    @pytest.mark.asyncio
    async def test_ttl_propagation_to_redis(self):
        """Test that JWT expiry is correctly propagated as Redis TTL."""
        from budapp.playground_ops.services import PlaygroundService

        # Arrange
        jwt_token = "ttl-test-jwt"
        user_id = uuid4()
        project_id = uuid4()
        session = Mock()
        service = PlaygroundService(session)

        # Set JWT expiry to 1 hour from now
        current_time = int(time.time())
        jwt_expiry = current_time + 3600

        # Mock dependencies
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService') as mock_redis, \
             patch('budapp.playground_ops.services.time.time', return_value=current_time):

            mock_user = Mock(id=user_id, user_type=UserTypeEnum.CLIENT)
            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service with proper structure
            mock_project_wrapper = Mock()
            mock_project_wrapper.project = Mock(id=project_id)
            mock_project_service.return_value.get_all_active_projects = AsyncMock(return_value=([mock_project_wrapper], 1))

            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                return_value=([], 0)
            )

            mock_redis_instance = Mock()
            captured_ttl = None

            async def capture_ttl(key, data, ex=None, **kwargs):
                nonlocal captured_ttl
                captured_ttl = ex

            mock_redis_instance.set = AsyncMock(side_effect=capture_ttl)
            mock_redis.return_value = mock_redis_instance

            # Act
            response = await service.initialize_session(jwt_token, user_id, jwt_expiry)

            # Assert
            assert captured_ttl == 3600  # TTL should be 1 hour
            assert response.ttl == 3600


class TestUserTypeFiltering:
    """Test that different user types get appropriate endpoint filtering."""

    @pytest.mark.asyncio
    async def test_client_user_sees_only_published_models(self):
        """Test that CLIENT users only see published models."""
        from budapp.playground_ops.services import PlaygroundService

        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        project_id = uuid4()
        jwt_token = "client-jwt"

        # Mock CLIENT user
        mock_user = Mock(id=user_id, user_type=UserTypeEnum.CLIENT)

        # Mock dependencies
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService'):

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service with proper structure
            mock_project_wrapper = Mock()
            mock_project_wrapper.project = Mock(id=project_id)
            mock_project_service.return_value.get_all_active_projects = AsyncMock(
                return_value=([mock_project_wrapper], 1)
            )

            # Capture the filters passed to endpoint manager
            captured_filters = {}

            async def capture_filters(project_ids, offset, limit, filters, **kwargs):
                captured_filters.update(filters)
                return ([], 0)

            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                side_effect=capture_filters
            )

            # Act
            await service.initialize_session(jwt_token, user_id)

            # Assert
            assert captured_filters.get("is_published") is True
            assert captured_filters.get("status") == EndpointStatusEnum.RUNNING

    @pytest.mark.asyncio
    async def test_admin_user_sees_all_models(self):
        """Test that ADMIN users see all models (published and unpublished)."""
        from budapp.playground_ops.services import PlaygroundService

        # Arrange
        session = Mock()
        service = PlaygroundService(session)
        user_id = uuid4()
        project_id = uuid4()
        jwt_token = "admin-jwt"

        # Mock ADMIN user
        mock_user = Mock(id=user_id, user_type=UserTypeEnum.ADMIN)

        # Mock dependencies
        with patch('budapp.playground_ops.services.UserDataManager') as mock_user_manager, \
             patch('budapp.playground_ops.services.ProjectService') as mock_project_service, \
             patch('budapp.playground_ops.services.EndpointDataManager') as mock_endpoint_manager, \
             patch('budapp.playground_ops.services.RedisService'):

            mock_user_manager.return_value.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock project service with proper structure for ADMIN user - gets multiple projects
            mock_project_wrapper = Mock()
            mock_project_wrapper.project = Mock(id=project_id)
            mock_project_service.return_value.get_all_active_projects = AsyncMock(
                return_value=([mock_project_wrapper], 1)
            )

            # Capture the filters passed to endpoint manager
            captured_filters = {}
            captured_project_ids = None

            async def capture_filters(project_ids, offset, limit, filters, **kwargs):
                nonlocal captured_project_ids
                captured_filters.update(filters)
                captured_project_ids = project_ids
                return ([], 0)

            mock_endpoint_manager.return_value.get_all_playground_deployments = AsyncMock(
                side_effect=capture_filters
            )

            # Act
            await service.initialize_session(jwt_token, user_id)

            # Assert
            assert "is_published" not in captured_filters  # No filtering by published status
            assert captured_filters.get("status") == EndpointStatusEnum.RUNNING
            assert captured_project_ids == [project_id]  # ADMIN users get project-filtered endpoints


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
