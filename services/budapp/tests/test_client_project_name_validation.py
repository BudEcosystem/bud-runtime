"""Test project name validation for CLIENT_APP projects."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from budapp.commons.constants import ProjectTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.project_ops.models import Project as ProjectModel
from budapp.project_ops.services import ProjectService


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock()
    return session


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def project_service(mock_session):
    """Create a project service instance."""
    return ProjectService(mock_session)


class TestClientProjectNameValidation:
    """Test suite for CLIENT_APP project name validation."""

    @pytest.mark.asyncio
    async def test_client_project_duplicate_name_within_user_projects(self, project_service, mock_user):
        """Test that CLIENT_APP projects check name uniqueness only within user's projects."""
        project_data = {
            "name": "My Project",
            "description": "Test project",
            "project_type": ProjectTypeEnum.CLIENT_APP.value,
        }

        # Mock the data manager methods
        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value
            # User already has a project with the same name
            mock_dm_instance.check_duplicate_name_for_user_projects = AsyncMock(return_value=True)

            # This should raise an exception since the user already has a project with this name
            with pytest.raises(ClientException) as exc_info:
                await project_service.create_project(project_data, mock_user.id)

            assert "Project already exist with same name" in str(exc_info.value)
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_called_once_with(
                "My Project", mock_user.id, ProjectTypeEnum.CLIENT_APP.value
            )

    @pytest.mark.asyncio
    async def test_client_project_allows_same_name_for_different_users(self, project_service, mock_user):
        """Test that CLIENT_APP projects allow the same name for different users."""
        project_data = {
            "name": "My Project",
            "description": "Test project",
            "project_type": ProjectTypeEnum.CLIENT_APP.value,
        }

        # Mock the data manager methods
        with (
            patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager,
            patch("budapp.project_ops.services.UserDataManager") as MockUserDataManager,
            patch("budapp.project_ops.services.PermissionService") as MockPermissionService,
        ):
            mock_dm_instance = MockDataManager.return_value
            mock_user_dm_instance = MockUserDataManager.return_value
            mock_permission_service = MockPermissionService.return_value

            # User doesn't have a project with this name
            mock_dm_instance.check_duplicate_name_for_user_projects = AsyncMock(return_value=False)

            # Mock the insert operation
            mock_project = Mock(spec=ProjectModel)
            mock_project.id = uuid4()
            mock_project.name = "My Project"
            mock_dm_instance.insert_one = AsyncMock(return_value=mock_project)

            # Mock user retrieval
            mock_user_dm_instance.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock permission creation
            mock_permission_service.create_resource_permission_by_user = AsyncMock()

            # Mock add_users_to_project
            project_service.add_users_to_project = AsyncMock(return_value=mock_project)

            # This should succeed since the user doesn't have a project with this name
            result = await project_service.create_project(project_data, mock_user.id)

            assert result is not None
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_called_once_with(
                "My Project", mock_user.id, ProjectTypeEnum.CLIENT_APP.value
            )
            # Should not check globally for CLIENT_APP projects
            mock_dm_instance.retrieve_by_fields.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_project_checks_name_globally(self, project_service, mock_user):
        """Test that ADMIN_APP projects check name uniqueness globally."""
        project_data = {
            "name": "Admin Project",
            "description": "Admin test project",
            "project_type": ProjectTypeEnum.ADMIN_APP.value,
        }

        # Mock the data manager methods
        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value

            # Global check finds a duplicate
            mock_dm_instance.retrieve_by_fields = AsyncMock(return_value=Mock())

            # This should raise an exception since a project with this name exists globally
            with pytest.raises(ClientException) as exc_info:
                await project_service.create_project(project_data, mock_user.id)

            assert "Project already exist with same name" in str(exc_info.value)
            # Should not check user-specific for ADMIN_APP projects
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_not_called()
            # Should check globally
            mock_dm_instance.retrieve_by_fields.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_project_type_is_client_app(self, project_service, mock_user):
        """Test that projects default to CLIENT_APP type when not specified."""
        project_data = {
            "name": "Default Type Project",
            "description": "Test project without explicit type",
            # No project_type specified
        }

        # Mock the data manager methods
        with (
            patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager,
            patch("budapp.project_ops.services.UserDataManager") as MockUserDataManager,
            patch("budapp.project_ops.services.PermissionService") as MockPermissionService,
        ):
            mock_dm_instance = MockDataManager.return_value
            mock_user_dm_instance = MockUserDataManager.return_value
            mock_permission_service = MockPermissionService.return_value

            # User doesn't have a project with this name
            mock_dm_instance.check_duplicate_name_for_user_projects = AsyncMock(return_value=False)

            # Mock the insert operation
            mock_project = Mock(spec=ProjectModel)
            mock_project.id = uuid4()
            mock_dm_instance.insert_one = AsyncMock(return_value=mock_project)

            # Mock user retrieval
            mock_user_dm_instance.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock permission creation
            mock_permission_service.create_resource_permission_by_user = AsyncMock()

            # Mock add_users_to_project
            project_service.add_users_to_project = AsyncMock(return_value=mock_project)

            # Create project without specifying type
            await project_service.create_project(project_data, mock_user.id)

            # Should use user-specific check (default is CLIENT_APP)
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_called_once()
            # Should not check globally
            mock_dm_instance.retrieve_by_fields.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_name_different_project_types_allowed(self, project_service, mock_user):
        """Test that the same user can have projects with the same name but different types."""
        # First, create a CLIENT_APP project
        client_project_data = {
            "name": "My Project",
            "project_type": ProjectTypeEnum.CLIENT_APP.value,
        }

        with (
            patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager,
            patch("budapp.project_ops.services.UserDataManager") as MockUserDataManager,
            patch("budapp.project_ops.services.PermissionService") as MockPermissionService,
        ):
            mock_dm_instance = MockDataManager.return_value
            mock_user_dm_instance = MockUserDataManager.return_value
            mock_permission_service = MockPermissionService.return_value

            # User doesn't have a CLIENT_APP project with this name
            mock_dm_instance.check_duplicate_name_for_user_projects = AsyncMock(return_value=False)

            # Mock the insert operation
            mock_project = Mock(spec=ProjectModel)
            mock_project.id = uuid4()
            mock_dm_instance.insert_one = AsyncMock(return_value=mock_project)

            # Mock user retrieval
            mock_user_dm_instance.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock permission creation
            mock_permission_service.create_resource_permission_by_user = AsyncMock()

            # Mock add_users_to_project
            project_service.add_users_to_project = AsyncMock(return_value=mock_project)

            # Create CLIENT_APP project
            result = await project_service.create_project(client_project_data, mock_user.id)

            assert result is not None
            # Verify it checked for CLIENT_APP type specifically
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_called_with(
                "My Project", mock_user.id, ProjectTypeEnum.CLIENT_APP.value
            )

        # Now test creating an ADMIN_APP project with the same name
        admin_project_data = {
            "name": "My Project",
            "project_type": ProjectTypeEnum.ADMIN_APP.value,
        }

        with (
            patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager2,
            patch("budapp.project_ops.services.UserDataManager") as MockUserDataManager2,
            patch("budapp.project_ops.services.PermissionService") as MockPermissionService2,
        ):
            mock_dm_instance2 = MockDataManager2.return_value
            mock_user_dm_instance2 = MockUserDataManager2.return_value
            mock_permission_service2 = MockPermissionService2.return_value

            # No ADMIN_APP project exists globally with this name and type
            mock_dm_instance2.retrieve_by_fields = AsyncMock(return_value=None)

            # Mock the insert operation
            mock_admin_project = Mock(spec=ProjectModel)
            mock_admin_project.id = uuid4()
            mock_dm_instance2.insert_one = AsyncMock(return_value=mock_admin_project)

            # Mock user retrieval
            mock_user_dm_instance2.retrieve_by_fields = AsyncMock(return_value=mock_user)

            # Mock permission creation
            mock_permission_service2.create_resource_permission_by_user = AsyncMock()

            # Mock add_users_to_project
            project_service.add_users_to_project = AsyncMock(return_value=mock_admin_project)

            # Create ADMIN_APP project with same name (should succeed)
            result = await project_service.create_project(admin_project_data, mock_user.id)

            assert result is not None
            # Verify it checked globally for ADMIN_APP type specifically
            mock_dm_instance2.retrieve_by_fields.assert_called_once()
            call_args = mock_dm_instance2.retrieve_by_fields.call_args
            assert call_args[0][1]["project_type"] == ProjectTypeEnum.ADMIN_APP.value
            assert call_args[0][1]["name"] == "My Project"
