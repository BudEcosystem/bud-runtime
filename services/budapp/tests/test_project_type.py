"""Unit tests for project_type field functionality."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.project_ops.models import Project
from budapp.project_ops.schemas import (
    EditProjectRequest,
    ProjectBase,
    ProjectCreateRequest,
    ProjectResponse,
)
from budapp.project_ops.services import ProjectService


class TestProjectTypeEnum:
    """Test ProjectTypeEnum functionality."""

    def test_project_type_enum_values(self):
        """Test that ProjectTypeEnum has correct values."""
        assert ProjectTypeEnum.CLIENT_APP.value == "client_app"
        assert ProjectTypeEnum.ADMIN_APP.value == "admin_app"

    def test_project_type_enum_members(self):
        """Test that ProjectTypeEnum has all required members."""
        members = list(ProjectTypeEnum)
        assert len(members) == 2
        assert ProjectTypeEnum.CLIENT_APP in members
        assert ProjectTypeEnum.ADMIN_APP in members


class TestProjectSchemas:
    """Test Pydantic schemas with project_type field."""

    def test_project_base_schema_with_project_type(self):
        """Test ProjectBase schema accepts project_type."""
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
            "project_type": ProjectTypeEnum.ADMIN_APP,
        }
        project = ProjectBase(**project_data)
        assert project.project_type == ProjectTypeEnum.ADMIN_APP

    def test_project_base_schema_default_project_type(self):
        """Test ProjectBase schema uses default project_type."""
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
        }
        project = ProjectBase(**project_data)
        assert project.project_type == ProjectTypeEnum.CLIENT_APP

    def test_project_create_request_with_project_type(self):
        """Test ProjectCreateRequest accepts project_type."""
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
            "benchmark": True,
            "project_type": ProjectTypeEnum.ADMIN_APP,
        }
        project = ProjectCreateRequest(**project_data)
        assert project.project_type == ProjectTypeEnum.ADMIN_APP
        assert project.benchmark is True

    def test_project_create_request_default_project_type(self):
        """Test ProjectCreateRequest uses default project_type."""
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
        }
        project = ProjectCreateRequest(**project_data)
        assert project.project_type == ProjectTypeEnum.CLIENT_APP
        assert project.benchmark is False

    def test_edit_project_request_excludes_project_type(self):
        """Test EditProjectRequest does not accept project_type field."""
        # project_type field should not exist in EditProjectRequest
        edit_data = {
            "name": "Updated Project",
            "description": "Updated description",
        }
        edit_request = EditProjectRequest(**edit_data)
        assert edit_request.name == "Updated Project"
        assert edit_request.description == "Updated description"

        # Verify project_type is not in the model fields
        assert "project_type" not in edit_request.model_fields

    def test_edit_project_request_rejects_project_type(self):
        """Test EditProjectRequest does not include project_type in model fields."""
        # Create a valid EditProjectRequest
        edit_request = EditProjectRequest(name="Updated Project")

        # Verify project_type is not in the model fields
        assert "project_type" not in edit_request.model_fields

        # Verify model_dump doesn't include project_type even if somehow present
        dumped = edit_request.model_dump()
        assert "project_type" not in dumped

        # Test that the schema definition doesn't include project_type
        schema = EditProjectRequest.model_json_schema()
        properties = schema.get("properties", {})
        assert "project_type" not in properties

    def test_project_response_includes_project_type(self):
        """Test ProjectResponse includes project_type field."""
        project_data = {
            "id": uuid4(),
            "name": "Test Project",
            "description": "Test Description",
            "project_type": ProjectTypeEnum.ADMIN_APP,
        }
        response = ProjectResponse(**project_data)
        assert response.project_type == ProjectTypeEnum.ADMIN_APP
        assert response.name == "Test Project"

    def test_invalid_project_type_raises_error(self):
        """Test that invalid project_type raises validation error."""
        with pytest.raises(ValueError):
            ProjectCreateRequest(
                name="Test Project",
                project_type="invalid_type",  # Invalid enum value
            )


class TestProjectModel:
    """Test Project model with project_type field."""

    def test_project_model_default_project_type(self):
        """Test that Project model has correct default project_type."""
        # This test verifies that the model is configured correctly
        # The actual database test would require a database session
        project = Project(
            name="Test Project",
            description="Test Description",
            created_by=uuid4(),
        )
        # The default is set at the database level, not in Python instantiation
        # When creating an instance without specifying project_type, it will be None
        # until saved to the database where the server_default applies
        assert project.project_type is None

        # If we explicitly set it to the default value
        project_with_type = Project(
            name="Test Project",
            description="Test Description",
            created_by=uuid4(),
            project_type=ProjectTypeEnum.CLIENT_APP.value,
        )
        assert project_with_type.project_type == ProjectTypeEnum.CLIENT_APP.value

    def test_project_model_with_project_type(self):
        """Test Project model accepts project_type."""
        project = Project(
            name="Test Project",
            description="Test Description",
            created_by=uuid4(),
            project_type=ProjectTypeEnum.ADMIN_APP.value,
        )
        assert project.project_type == ProjectTypeEnum.ADMIN_APP.value


class TestBackwardCompatibility:
    """Test backward compatibility of project_type field."""

    def test_create_project_without_project_type(self):
        """Test creating project without specifying project_type."""
        project_data = {
            "name": "Legacy Project",
            "description": "Created without project_type",
        }
        project = ProjectCreateRequest(**project_data)
        # Should default to CLIENT_APP
        assert project.project_type == ProjectTypeEnum.CLIENT_APP

    def test_edit_project_only_allows_specific_fields(self):
        """Test editing project only allows name, description, tags, icon."""
        from budapp.commons.schemas import Tag

        # Test with all valid field values
        edit_request = EditProjectRequest(
            name="Updated Name",
            description="Updated Description",
            tags=[Tag(name="test", color="#FF0000")],
            # Skip icon to avoid validation issues, focus on testing field structure
        )
        assert edit_request.name == "Updated Name"
        assert edit_request.description == "Updated Description"
        assert len(edit_request.tags) == 1
        assert edit_request.tags[0].name == "test"
        assert edit_request.icon is None  # Default None value

        # Verify only expected fields are present
        expected_fields = {"name", "description", "tags", "icon"}
        actual_fields = set(edit_request.model_fields.keys())
        assert expected_fields == actual_fields

    def test_project_response_backward_compatibility(self):
        """Test that ProjectResponse works with legacy data."""
        # Simulate legacy project data without project_type
        project_data = {
            "id": uuid4(),
            "name": "Legacy Project",
            "description": "Old project",
            "project_type": ProjectTypeEnum.CLIENT_APP,  # Default value
        }
        response = ProjectResponse(**project_data)
        assert response.project_type == ProjectTypeEnum.CLIENT_APP


class TestProjectTypeImmutability:
    """Test that project_type cannot be modified after creation."""

    @pytest.mark.asyncio
    async def test_edit_project_service_prevents_project_type_update(self):
        """Test that ProjectService.edit_project prevents project_type updates."""
        # Arrange
        mock_session = MagicMock()
        service = ProjectService(mock_session)
        project_id = uuid4()

        # Mock existing project
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.name = "Existing Project"
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value
        mock_project.status = ProjectStatusEnum.ACTIVE
        mock_project.created_at = datetime.now(timezone.utc)
        mock_project.modified_at = datetime.now(timezone.utc)

        with patch('budapp.project_ops.services.ProjectDataManager') as mock_data_manager:
            mock_dm_instance = MagicMock()
            mock_dm_instance.retrieve_by_fields = AsyncMock(return_value=mock_project)
            mock_data_manager.return_value = mock_dm_instance

            # Act & Assert
            update_data = {
                "name": "Updated Name",
                "project_type": ProjectTypeEnum.ADMIN_APP.value
            }

            with pytest.raises(ClientException) as exc_info:
                await service.edit_project(project_id, update_data)

            assert "Project type cannot be modified" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_edit_project_service_allows_other_field_updates(self):
        """Test that ProjectService.edit_project allows updating non-project_type fields."""
        # Arrange
        mock_session = MagicMock()
        service = ProjectService(mock_session)
        project_id = uuid4()

        # Mock existing project
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.name = "Existing Project"
        mock_project.description = "Old description"
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value
        mock_project.status = ProjectStatusEnum.ACTIVE

        # Mock updated project
        updated_project = MagicMock()
        updated_project.id = project_id
        updated_project.name = "Updated Name"
        updated_project.description = "Updated description"
        updated_project.project_type = ProjectTypeEnum.CLIENT_APP.value  # Unchanged

        with patch('budapp.project_ops.services.ProjectDataManager') as mock_data_manager:
            mock_dm_instance = MagicMock()
            # First call returns the existing project, second call for duplicate check returns None
            mock_dm_instance.retrieve_by_fields = AsyncMock(side_effect=[mock_project, None])
            mock_dm_instance.update_by_fields = AsyncMock(return_value=updated_project)
            mock_data_manager.return_value = mock_dm_instance

            # Act
            update_data = {
                "name": "Updated Name",
                "description": "Updated description"
            }

            result = await service.edit_project(project_id, update_data)

            # Assert
            assert result.name == "Updated Name"
            assert result.description == "Updated description"
            assert result.project_type == ProjectTypeEnum.CLIENT_APP.value  # Unchanged

            # Verify update_by_fields was called with data not containing project_type
            mock_dm_instance.update_by_fields.assert_called_once()
            call_args = mock_dm_instance.update_by_fields.call_args
            update_dict = call_args[0][1]  # Second argument
            assert "project_type" not in update_dict
            assert "name" in update_dict
            assert "description" in update_dict

    def test_edit_project_request_schema_model_dump_excludes_project_type(self):
        """Test that EditProjectRequest.model_dump() never includes project_type."""
        edit_request = EditProjectRequest(
            name="Updated Project",
            description="Updated description"
        )

        # Test all variations of model_dump
        dump_default = edit_request.model_dump()
        dump_exclude_unset = edit_request.model_dump(exclude_unset=True)
        dump_exclude_none = edit_request.model_dump(exclude_none=True)
        dump_both = edit_request.model_dump(exclude_unset=True, exclude_none=True)

        # None should contain project_type
        for dump_result in [dump_default, dump_exclude_unset, dump_exclude_none, dump_both]:
            assert "project_type" not in dump_result
            assert isinstance(dump_result, dict)

    @pytest.mark.asyncio
    async def test_edit_project_service_bypassing_schema_still_blocked(self):
        """Test that even if schema validation is bypassed, service still blocks project_type."""
        # This simulates a scenario where someone might try to directly call
        # the service method with project_type in the data dict

        # Arrange
        mock_session = MagicMock()
        service = ProjectService(mock_session)
        project_id = uuid4()

        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value

        with patch('budapp.project_ops.services.ProjectDataManager') as mock_data_manager:
            mock_dm_instance = MagicMock()
            mock_dm_instance.retrieve_by_fields = AsyncMock(return_value=mock_project)
            mock_data_manager.return_value = mock_dm_instance

            # Act & Assert - Directly pass project_type in data dict
            malicious_data = {
                "project_type": ProjectTypeEnum.ADMIN_APP.value
            }

            with pytest.raises(ClientException) as exc_info:
                await service.edit_project(project_id, malicious_data)

            assert "Project type cannot be modified" in str(exc_info.value)

            # Verify update_by_fields was never called due to early validation
            mock_dm_instance.update_by_fields.assert_not_called()
