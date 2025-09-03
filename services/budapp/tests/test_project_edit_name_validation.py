"""Test project edit name validation fix."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.project_ops.models import Project as ProjectModel
from budapp.project_ops.services import ProjectService


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock()
    # Mock execute to return an object with scalar_one_or_none method
    mock_result = Mock()
    mock_result.scalar_one_or_none = Mock(return_value=0)  # Return 0 count by default
    session.execute = Mock(return_value=mock_result)
    session.rollback = Mock()
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


@pytest.fixture
def client_project():
    """Create a mock CLIENT_APP project."""
    project = Mock(spec=ProjectModel)
    project.id = uuid4()
    project.name = "Test Client Project"
    project.description = "Test description"
    project.project_type = ProjectTypeEnum.CLIENT_APP.value
    project.status = ProjectStatusEnum.ACTIVE
    return project


@pytest.fixture
def admin_project():
    """Create a mock ADMIN_APP project."""
    project = Mock(spec=ProjectModel)
    project.id = uuid4()
    project.name = "Test Admin Project"
    project.description = "Test description"
    project.project_type = ProjectTypeEnum.ADMIN_APP.value
    project.status = ProjectStatusEnum.ACTIVE
    return project


class TestProjectEditNameValidation:
    """Test suite for project edit name validation fix."""

    @pytest.mark.asyncio
    async def test_edit_client_project_same_name_should_succeed(self, project_service, mock_user, client_project):
        """Test that editing a CLIENT_APP project with the same name should succeed."""
        update_data = {"name": client_project.name}  # Same name

        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value

            # First call: retrieve existing project
            mock_dm_instance.retrieve_by_fields = AsyncMock(return_value=client_project)

            # Mock the CRUD method to return False (no duplicate excluding current)
            mock_dm_instance.check_duplicate_name_for_user_projects = AsyncMock(return_value=False)

            # Mock update operation
            mock_dm_instance.update_by_fields = AsyncMock(return_value=client_project)

            # This should succeed
            result = await project_service.edit_project(
                project_id=client_project.id,
                data=update_data,
                current_user_id=mock_user.id
            )

            assert result == client_project
            # Verify the CRUD method was called with correct parameters including exclude_project_id
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_called_once_with(
                client_project.name,
                mock_user.id,
                ProjectTypeEnum.CLIENT_APP.value,
                exclude_project_id=client_project.id
            )

    @pytest.mark.asyncio
    async def test_edit_client_project_duplicate_name_should_fail(self, project_service, mock_user, client_project):
        """Test that editing a CLIENT_APP project to a name used by another user project should fail."""
        update_data = {"name": "Another User Project"}

        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value

            # First call: retrieve existing project
            mock_dm_instance.retrieve_by_fields = AsyncMock(return_value=client_project)

            # Mock the CRUD method to return True (duplicate exists excluding current)
            mock_dm_instance.check_duplicate_name_for_user_projects = AsyncMock(return_value=True)

            # This should fail
            with pytest.raises(ClientException) as exc_info:
                await project_service.edit_project(
                    project_id=client_project.id,
                    data=update_data,
                    current_user_id=mock_user.id
                )

            assert "Project name already exists" in str(exc_info.value)
            # Verify the CRUD method was called
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_called_once_with(
                "Another User Project",
                mock_user.id,
                ProjectTypeEnum.CLIENT_APP.value,
                exclude_project_id=client_project.id
            )

    @pytest.mark.asyncio
    async def test_edit_admin_project_same_name_should_succeed(self, project_service, mock_user, admin_project):
        """Test that editing an ADMIN_APP project with the same name should succeed."""
        update_data = {"name": admin_project.name}  # Same name

        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value

            # First call: retrieve existing project
            # Second call: check for duplicates (should return None when excluding current project)
            mock_dm_instance.retrieve_by_fields = AsyncMock(side_effect=[admin_project, None])

            # Mock update operation
            mock_dm_instance.update_by_fields = AsyncMock(return_value=admin_project)

            # This should succeed
            result = await project_service.edit_project(
                project_id=admin_project.id,
                data=update_data,
                current_user_id=mock_user.id
            )

            assert result == admin_project
            # Verify the second call checked for duplicates with correct exclude_fields
            calls = mock_dm_instance.retrieve_by_fields.call_args_list
            assert len(calls) == 2
            second_call_kwargs = calls[1][1]  # kwargs from second call
            assert second_call_kwargs["exclude_fields"] == {"id": admin_project.id}
            assert second_call_kwargs["fields"]["project_type"] == ProjectTypeEnum.ADMIN_APP.value

    @pytest.mark.asyncio
    async def test_edit_admin_project_duplicate_name_should_fail(self, project_service, mock_user, admin_project):
        """Test that editing an ADMIN_APP project to a name used by another admin project should fail."""
        update_data = {"name": "Another Admin Project"}

        # Create another project that would be found as duplicate
        other_project = Mock(spec=ProjectModel)
        other_project.id = uuid4()  # Different ID
        other_project.name = "Another Admin Project"
        other_project.project_type = ProjectTypeEnum.ADMIN_APP.value

        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value

            # First call: retrieve existing project
            # Second call: find duplicate project (different from current)
            mock_dm_instance.retrieve_by_fields = AsyncMock(side_effect=[admin_project, other_project])

            # This should fail
            with pytest.raises(ClientException) as exc_info:
                await project_service.edit_project(
                    project_id=admin_project.id,
                    data=update_data,
                    current_user_id=mock_user.id
                )

            assert "Project name already exists" in str(exc_info.value)
            # Verify the second call checked for duplicates correctly
            calls = mock_dm_instance.retrieve_by_fields.call_args_list
            assert len(calls) == 2
            second_call_kwargs = calls[1][1]  # kwargs from second call
            assert second_call_kwargs["exclude_fields"] == {"id": admin_project.id}
            assert second_call_kwargs["fields"]["name"] == "Another Admin Project"
            assert second_call_kwargs["fields"]["project_type"] == ProjectTypeEnum.ADMIN_APP.value

    @pytest.mark.asyncio
    async def test_edit_project_without_name_change_should_succeed(self, project_service, mock_user, client_project):
        """Test that editing a project without changing the name should succeed."""
        update_data = {"description": "Updated description"}

        with patch("budapp.project_ops.services.ProjectDataManager") as MockDataManager:
            mock_dm_instance = MockDataManager.return_value

            # First call: retrieve existing project
            mock_dm_instance.retrieve_by_fields = AsyncMock(return_value=client_project)

            # Mock update operation
            mock_dm_instance.update_by_fields = AsyncMock(return_value=client_project)

            # This should succeed without any name validation
            result = await project_service.edit_project(
                project_id=client_project.id,
                data=update_data,
                current_user_id=mock_user.id
            )

            assert result == client_project
            # Should not call name validation methods since name wasn't changed
            mock_dm_instance.check_duplicate_name_for_user_projects.assert_not_called()
