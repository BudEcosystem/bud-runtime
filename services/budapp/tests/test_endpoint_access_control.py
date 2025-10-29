"""Tests for endpoint access control functionality."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.crud import EndpointDataManager
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.endpoint_ops.services import EndpointService
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project as ProjectModel
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
def mock_user():
    """Create a mock user."""
    user = Mock(spec=UserModel)
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    return user


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = Mock(spec=ProjectModel)
    project.id = uuid4()
    project.name = "Test Project"
    return project


@pytest.fixture
def mock_endpoint():
    """Create a mock endpoint."""
    endpoint = Mock(spec=EndpointModel)
    endpoint.id = uuid4()
    endpoint.name = "Test Endpoint"
    endpoint.project_id = uuid4()
    return endpoint


class TestEndpointAccessControl:
    """Test cases for endpoint access control."""

    @pytest.mark.asyncio
    async def test_get_all_endpoints_with_project_id_user_has_access(
        self, mock_session, mock_user, mock_project
    ):
        """Test getting endpoints with project_id when user has access."""
        # Arrange
        service = EndpointService(mock_session)
        project_id = mock_project.id
        user_id = mock_user.id

        with patch.object(
            ProjectDataManager, "retrieve_by_fields", new_callable=AsyncMock
        ) as mock_retrieve_project:
            with patch.object(
                ProjectDataManager, "is_user_in_project", new_callable=AsyncMock
            ) as mock_is_user_in_project:
                with patch.object(
                    EndpointDataManager, "get_all_active_endpoints", new_callable=AsyncMock
                ) as mock_get_endpoints:
                    mock_retrieve_project.return_value = mock_project
                    mock_is_user_in_project.return_value = True
                    mock_get_endpoints.return_value = ([], 0)

                    # Act
                    result, count = await service.get_all_endpoints(
                        current_user_id=user_id,
                        is_superuser=False,
                        project_id=project_id,
                        offset=0,
                        limit=10,
                        filters={},
                        order_by=[],
                        search=False,
                    )

                    # Assert
                    assert result == []
                    assert count == 0
                    mock_retrieve_project.assert_called_once()
                    mock_is_user_in_project.assert_called_once_with(user_id, project_id)
                    mock_get_endpoints.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_endpoints_with_project_id_user_no_access(
        self, mock_session, mock_user, mock_project
    ):
        """Test getting endpoints with project_id when user has no access."""
        # Arrange
        service = EndpointService(mock_session)
        project_id = mock_project.id
        user_id = mock_user.id

        with patch.object(
            ProjectDataManager, "retrieve_by_fields", new_callable=AsyncMock
        ) as mock_retrieve_project:
            with patch.object(
                ProjectDataManager, "is_user_in_project", new_callable=AsyncMock
            ) as mock_is_user_in_project:
                mock_retrieve_project.return_value = mock_project
                mock_is_user_in_project.return_value = False

                # Act & Assert
                with pytest.raises(ClientException) as exc_info:
                    await service.get_all_endpoints(
                        current_user_id=user_id,
                        is_superuser=False,
                        project_id=project_id,
                        offset=0,
                        limit=10,
                        filters={},
                        order_by=[],
                        search=False,
                    )

                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "Access denied" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_all_endpoints_without_project_id(self, mock_session, mock_user):
        """Test getting endpoints without project_id filters by user's projects."""
        # Arrange
        service = EndpointService(mock_session)
        user_id = mock_user.id
        user_project_ids = [uuid4(), uuid4(), uuid4()]

        # Create mock instances
        mock_project_manager = Mock(spec=ProjectDataManager)
        mock_project_manager.get_user_project_ids = AsyncMock(return_value=user_project_ids)

        mock_endpoint_manager = Mock(spec=EndpointDataManager)
        mock_endpoint_manager.get_all_active_endpoints = AsyncMock(return_value=([], 0))

        # Patch the manager constructors to return our mocks
        with patch('budapp.endpoint_ops.services.ProjectDataManager', return_value=mock_project_manager):
            with patch('budapp.endpoint_ops.services.EndpointDataManager', return_value=mock_endpoint_manager):
                # Act
                result, count = await service.get_all_endpoints(
                    current_user_id=user_id,
                    is_superuser=False,
                    project_id=None,
                    offset=0,
                    limit=10,
                    filters={},
                    order_by=[],
                    search=False,
                )

                # Assert
                assert result == []
                assert count == 0
                mock_project_manager.get_user_project_ids.assert_called_once_with(user_id)
                # Verify that get_all_active_endpoints was called with the list of project IDs
                call_args = mock_endpoint_manager.get_all_active_endpoints.call_args
                assert call_args[0][0] == user_project_ids  # First positional argument

    @pytest.mark.asyncio
    async def test_get_all_endpoints_without_project_id_no_projects(
        self, mock_session, mock_user
    ):
        """Test getting endpoints when user has no associated projects."""
        # Arrange
        service = EndpointService(mock_session)
        user_id = mock_user.id

        # Create mock instances
        mock_project_manager = Mock(spec=ProjectDataManager)
        mock_project_manager.get_user_project_ids = AsyncMock(return_value=[])

        mock_endpoint_manager = Mock(spec=EndpointDataManager)
        mock_endpoint_manager.get_all_active_endpoints = AsyncMock(return_value=([], 0))

        # Patch the manager constructors to return our mocks
        with patch('budapp.endpoint_ops.services.ProjectDataManager', return_value=mock_project_manager):
            with patch('budapp.endpoint_ops.services.EndpointDataManager', return_value=mock_endpoint_manager):
                # Act
                result, count = await service.get_all_endpoints(
                    current_user_id=user_id,
                    is_superuser=False,
                    project_id=None,
                    offset=0,
                    limit=10,
                    filters={},
                    order_by=[],
                    search=False,
                )

                # Assert
                assert result == []
                assert count == 0
                mock_project_manager.get_user_project_ids.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_all_endpoints_superuser_with_project_id(
        self, mock_session, mock_user, mock_project
    ):
        """Test superuser can access any project without permission check."""
        # Arrange
        service = EndpointService(mock_session)
        project_id = mock_project.id
        user_id = mock_user.id

        with patch.object(
            ProjectDataManager, "retrieve_by_fields", new_callable=AsyncMock
        ) as mock_retrieve_project:
            with patch.object(
                ProjectDataManager, "is_user_in_project", new_callable=AsyncMock
            ) as mock_is_user_in_project:
                with patch.object(
                    EndpointDataManager, "get_all_active_endpoints", new_callable=AsyncMock
                ) as mock_get_endpoints:
                    mock_retrieve_project.return_value = mock_project
                    mock_get_endpoints.return_value = ([], 0)

                    # Act
                    result, count = await service.get_all_endpoints(
                        current_user_id=user_id,
                        is_superuser=True,
                        project_id=project_id,
                        offset=0,
                        limit=10,
                        filters={},
                        order_by=[],
                        search=False,
                    )

                    # Assert
                    assert result == []
                    assert count == 0
                    mock_retrieve_project.assert_called_once()
                    # Superuser should not check project association
                    mock_is_user_in_project.assert_not_called()
                    mock_get_endpoints.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_endpoints_superuser_without_project_id(
        self, mock_session, mock_user
    ):
        """Test superuser can access all endpoints without project filtering."""
        # Arrange
        service = EndpointService(mock_session)
        user_id = mock_user.id

        # Create mock instances
        mock_project_manager = Mock(spec=ProjectDataManager)
        mock_project_manager.get_user_project_ids = AsyncMock()

        mock_endpoint_manager = Mock(spec=EndpointDataManager)
        mock_endpoint_manager.get_all_active_endpoints = AsyncMock(return_value=([], 0))

        # Patch the manager constructors to return our mocks
        with patch('budapp.endpoint_ops.services.ProjectDataManager', return_value=mock_project_manager):
            with patch('budapp.endpoint_ops.services.EndpointDataManager', return_value=mock_endpoint_manager):
                # Act
                result, count = await service.get_all_endpoints(
                    current_user_id=user_id,
                    is_superuser=True,
                    project_id=None,
                    offset=0,
                    limit=10,
                    filters={},
                    order_by=[],
                    search=False,
                )

                # Assert
                assert result == []
                assert count == 0
                # Superuser should not query user's project IDs
                mock_project_manager.get_user_project_ids.assert_not_called()
                # Should call get_all_active_endpoints with None (all projects)
                call_args = mock_endpoint_manager.get_all_active_endpoints.call_args
                assert call_args[0][0] is None  # First positional argument should be None


class TestProjectDataManagerAccessControl:
    """Test cases for ProjectDataManager access control methods."""

    @pytest.mark.asyncio
    async def test_get_user_project_ids_with_active_projects(self, mock_session):
        """Test getting user project IDs with active projects."""
        # Arrange
        data_manager = ProjectDataManager(mock_session)
        user_id = uuid4()
        project_ids = [uuid4(), uuid4(), uuid4()]

        # Mock scalars_all to return project IDs
        data_manager.scalars_all = Mock(return_value=project_ids)

        # Act
        result = await data_manager.get_user_project_ids(user_id)

        # Assert
        assert result == project_ids
        data_manager.scalars_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_project_ids_no_projects(self, mock_session):
        """Test getting user project IDs when user has no projects."""
        # Arrange
        data_manager = ProjectDataManager(mock_session)
        user_id = uuid4()

        # Mock scalars_all to return empty list
        data_manager.scalars_all = Mock(return_value=[])

        # Act
        result = await data_manager.get_user_project_ids(user_id)

        # Assert
        assert result == []
        data_manager.scalars_all.assert_called_once()


class TestEndpointDataManagerProjectFiltering:
    """Test cases for EndpointDataManager project filtering."""

    @pytest.mark.asyncio
    async def test_get_all_active_endpoints_with_single_project_id(self, mock_session):
        """Test getting endpoints with a single project ID."""
        # Arrange
        data_manager = EndpointDataManager(mock_session)
        project_id = uuid4()

        # Mock the necessary methods
        data_manager.validate_fields = AsyncMock()
        data_manager.execute_scalar = Mock(return_value=0)
        data_manager.scalars_all = Mock(return_value=[])

        # Act
        result, count = await data_manager.get_all_active_endpoints(
            project_id=project_id, offset=0, limit=10, filters={}, order_by=[], search=False
        )

        # Assert
        assert result == []
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_all_active_endpoints_with_multiple_project_ids(self, mock_session):
        """Test getting endpoints with multiple project IDs."""
        # Arrange
        data_manager = EndpointDataManager(mock_session)
        project_ids = [uuid4(), uuid4(), uuid4()]

        # Mock the necessary methods
        data_manager.validate_fields = AsyncMock()
        data_manager.execute_scalar = Mock(return_value=0)
        data_manager.scalars_all = Mock(return_value=[])

        # Act
        result, count = await data_manager.get_all_active_endpoints(
            project_id=project_ids, offset=0, limit=10, filters={}, order_by=[], search=False
        )

        # Assert
        assert result == []
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_all_active_endpoints_with_empty_project_ids_list(self, mock_session):
        """Test getting endpoints with empty project IDs list."""
        # Arrange
        data_manager = EndpointDataManager(mock_session)
        project_ids = []

        # Mock the necessary methods
        data_manager.validate_fields = AsyncMock()
        data_manager.execute_scalar = Mock(return_value=0)
        data_manager.scalars_all = Mock(return_value=[])

        # Act
        result, count = await data_manager.get_all_active_endpoints(
            project_id=project_ids, offset=0, limit=10, filters={}, order_by=[], search=False
        )

        # Assert
        assert result == []
        assert count == 0
