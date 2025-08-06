"""Test that default projects created for client users have CLIENT_APP type."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budapp.auth.schemas import UserCreate
from budapp.auth.services import AuthService
from budapp.commons.constants import ProjectTypeEnum, UserColorEnum, UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.project_ops.models import Project as ProjectModel
from budapp.user_ops.models import User as UserModel


class TestDefaultProjectType:
    """Test default project creation with correct project_type."""

    @pytest.mark.asyncio
    async def test_client_user_default_project_has_client_app_type(self):
        """Test that when a client user is registered, their default project has CLIENT_APP type."""
        # Mock session
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Create test user data
        user_data = UserCreate(
            name="Test Client",
            email="testclient@example.com",
            password="TestPassword123!",
            role=UserRoleEnum.DEVELOPER,
            user_type=UserTypeEnum.CLIENT,
        )

        # Mock the created user
        mock_user = UserModel(
            id=uuid4(),
            name=user_data.name,
            email=user_data.email,
            user_type=UserTypeEnum.CLIENT.value,
            status=UserStatusEnum.ACTIVE.value,
            color=UserColorEnum.COLOR_1.value,
            is_superuser=False,
        )

        # Mock the created project
        mock_project = None

        async def capture_project(obj):
            """Capture the project being inserted."""
            nonlocal mock_project
            if isinstance(obj, ProjectModel):
                mock_project = obj
                # Set an ID for the project
                obj.id = uuid4()
            return obj

        with patch("budapp.auth.services.UserDataManager") as MockUserDataManager:
            with patch("budapp.auth.services.PermissionService") as MockPermissionService:
                # Setup mocks
                mock_user_dm = MockUserDataManager.return_value
                mock_user_dm.insert_one = AsyncMock(side_effect=capture_project)
                mock_user_dm.get_user_by_email = AsyncMock(return_value=None)
                mock_user_dm.insert_user = AsyncMock(return_value=mock_user)
                mock_user_dm.update_subscriber_status = AsyncMock(return_value=True)

                mock_permission_service = MockPermissionService.return_value
                mock_permission_service.create_resource_permission_by_user = AsyncMock()

                # Create auth service and register user
                auth_service = AuthService(mock_session)
                result = await auth_service.register_user(user_data)

                # Verify user was created
                assert result is not None
                assert result.email == user_data.email
                assert result.user_type == UserTypeEnum.CLIENT.value

                # Verify default project was created with CLIENT_APP type
                assert mock_project is not None
                assert mock_project.name == "My First Project"
                assert mock_project.description == "This is your default project."
                assert mock_project.project_type == ProjectTypeEnum.CLIENT_APP.value
                assert mock_project.benchmark is False

                # Verify permissions were created for the project
                mock_permission_service.create_resource_permission_by_user.assert_called_once()
                call_args = mock_permission_service.create_resource_permission_by_user.call_args
                assert call_args[0][0] == mock_user  # First arg is the user
                resource_payload = call_args[0][1]  # Second arg is the ResourceCreate payload
                assert resource_payload.resource_type == "project"
                assert resource_payload.scopes == ["view", "manage"]

    @pytest.mark.asyncio
    async def test_admin_user_no_default_project(self):
        """Test that admin users don't get a default project created."""
        # Mock session
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Create test admin user data
        user_data = UserCreate(
            name="Test Admin",
            email="testadmin@example.com",
            password="TestPassword123!",
            role=UserRoleEnum.ADMIN,
            user_type=UserTypeEnum.ADMIN,
        )

        # Mock the created user
        mock_user = UserModel(
            id=uuid4(),
            name=user_data.name,
            email=user_data.email,
            user_type=UserTypeEnum.ADMIN.value,
            status=UserStatusEnum.ACTIVE.value,
            color=UserColorEnum.COLOR_2.value,
            is_superuser=True,
        )

        # Track if a project was created
        project_created = False

        async def track_project_creation(obj):
            """Track if a project is being created."""
            nonlocal project_created
            if isinstance(obj, ProjectModel):
                project_created = True
            return obj

        with patch("budapp.auth.services.UserDataManager") as MockUserDataManager:
            with patch("budapp.auth.services.PermissionService") as MockPermissionService:
                # Setup mocks
                mock_user_dm = MockUserDataManager.return_value
                mock_user_dm.insert_one = AsyncMock(side_effect=track_project_creation)
                mock_user_dm.get_user_by_email = AsyncMock(return_value=None)
                mock_user_dm.insert_user = AsyncMock(return_value=mock_user)
                mock_user_dm.update_subscriber_status = AsyncMock(return_value=True)

                mock_permission_service = MockPermissionService.return_value
                mock_permission_service.create_resource_permission_by_user = AsyncMock()

                # Create auth service and register user
                auth_service = AuthService(mock_session)
                result = await auth_service.register_user(user_data)

                # Verify user was created
                assert result is not None
                assert result.email == user_data.email
                assert result.user_type == UserTypeEnum.ADMIN.value

                # Verify NO default project was created for admin user
                assert project_created is False

                # Verify permissions were NOT created (no project to create permissions for)
                mock_permission_service.create_resource_permission_by_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_client_user_project_creation_failure_doesnt_fail_registration(self):
        """Test that if default project creation fails, user registration still succeeds."""
        # Mock session
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Create test user data
        user_data = UserCreate(
            name="Test Client",
            email="testclient@example.com",
            password="TestPassword123!",
            role=UserRoleEnum.DEVELOPER,
            user_type=UserTypeEnum.CLIENT,
        )

        # Mock the created user
        mock_user = UserModel(
            id=uuid4(),
            name=user_data.name,
            email=user_data.email,
            user_type=UserTypeEnum.CLIENT.value,
            status=UserStatusEnum.ACTIVE.value,
            color=UserColorEnum.COLOR_3.value,
            is_superuser=False,
        )

        with patch("budapp.auth.services.UserDataManager") as MockUserDataManager:
            with patch("budapp.auth.services.PermissionService") as MockPermissionService:
                # Setup mocks
                mock_user_dm = MockUserDataManager.return_value
                # Make project creation fail
                mock_user_dm.insert_one = AsyncMock(side_effect=Exception("Database error"))
                mock_user_dm.get_user_by_email = AsyncMock(return_value=None)
                mock_user_dm.insert_user = AsyncMock(return_value=mock_user)
                mock_user_dm.update_subscriber_status = AsyncMock(return_value=True)

                mock_permission_service = MockPermissionService.return_value
                mock_permission_service.create_resource_permission_by_user = AsyncMock()

                # Create auth service and register user
                auth_service = AuthService(mock_session)

                # User registration should still succeed even if project creation fails
                result = await auth_service.register_user(user_data)

                # Verify user was created successfully
                assert result is not None
                assert result.email == user_data.email
                assert result.user_type == UserTypeEnum.CLIENT.value

                # Verify project creation was attempted but failed
                mock_user_dm.insert_one.assert_called()

                # Verify permissions were NOT created (project creation failed)
                mock_permission_service.create_resource_permission_by_user.assert_not_called()


class TestProjectCreationEndpoint:
    """Test that projects created via API endpoint have correct default type."""

    @pytest.mark.asyncio
    async def test_create_project_default_type_is_client_app(self):
        """Test that when project_type is not specified, it defaults to CLIENT_APP."""
        from budapp.project_ops.schemas import ProjectCreateRequest

        # Create project without specifying project_type
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
        }

        project = ProjectCreateRequest(**project_data)

        # Should default to CLIENT_APP
        assert project.project_type == ProjectTypeEnum.CLIENT_APP

    @pytest.mark.asyncio
    async def test_create_project_with_explicit_admin_type(self):
        """Test that admin users can create ADMIN_APP projects."""
        from budapp.project_ops.schemas import ProjectCreateRequest

        # Create project with explicit ADMIN_APP type
        project_data = {
            "name": "Admin Project",
            "description": "Admin Description",
            "project_type": ProjectTypeEnum.ADMIN_APP,
        }

        project = ProjectCreateRequest(**project_data)

        # Should be ADMIN_APP as specified
        assert project.project_type == ProjectTypeEnum.ADMIN_APP
