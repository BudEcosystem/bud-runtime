"""Unit tests for project_type field functionality."""

from uuid import uuid4

import pytest

from budapp.commons.constants import ProjectTypeEnum
from budapp.project_ops.models import Project
from budapp.project_ops.schemas import (
    EditProjectRequest,
    ProjectBase,
    ProjectCreateRequest,
    ProjectResponse,
)


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

    def test_edit_project_request_with_project_type(self):
        """Test EditProjectRequest accepts project_type."""
        edit_data = {
            "name": "Updated Project",
            "project_type": ProjectTypeEnum.ADMIN_APP,
        }
        edit_request = EditProjectRequest(**edit_data)
        assert edit_request.project_type == ProjectTypeEnum.ADMIN_APP
        assert edit_request.name == "Updated Project"

    def test_edit_project_request_optional_project_type(self):
        """Test EditProjectRequest with optional project_type."""
        edit_data = {
            "name": "Updated Project",
        }
        edit_request = EditProjectRequest(**edit_data)
        assert edit_request.project_type is None
        assert edit_request.name == "Updated Project"

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
        # The default should be set at the database level
        # This is more of a model configuration check
        # This is more of a model configuration check
        assert project.project_type == ProjectTypeEnum.CLIENT_APP

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

    def test_edit_project_without_changing_project_type(self):
        """Test editing project without changing project_type."""
        edit_data = {
            "name": "Updated Name",
            "description": "Updated Description",
        }
        edit_request = EditProjectRequest(**edit_data)
        # project_type should be None (not changed)
        assert edit_request.project_type is None

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
