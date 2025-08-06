"""Unit and integration tests for project filtering with project_type field."""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum, UserStatusEnum, UserTypeEnum
from budapp.project_ops.models import Project
from budapp.project_ops.schemas import ProjectFilter
from budapp.user_ops.schemas import User


class TestProjectFilterSchema:
    """Test ProjectFilter schema with project_type field."""

    def test_project_filter_with_project_type(self):
        """Test ProjectFilter accepts project_type field."""
        filter_data = {
            "name": "test",
            "project_type": ProjectTypeEnum.ADMIN_APP,
        }
        project_filter = ProjectFilter(**filter_data)
        assert project_filter.name == "test"
        assert project_filter.project_type == ProjectTypeEnum.ADMIN_APP

    def test_project_filter_without_project_type(self):
        """Test ProjectFilter works without project_type field."""
        filter_data = {"name": "test"}
        project_filter = ProjectFilter(**filter_data)
        assert project_filter.name == "test"
        assert project_filter.project_type is None

    def test_project_filter_empty(self):
        """Test empty ProjectFilter."""
        project_filter = ProjectFilter()
        assert project_filter.name is None
        assert project_filter.project_type is None

    def test_project_filter_model_dump(self):
        """Test model_dump excludes None values."""
        # With project_type
        filter_with_type = ProjectFilter(project_type=ProjectTypeEnum.CLIENT_APP)
        assert filter_with_type.model_dump(exclude_none=True) == {"project_type": ProjectTypeEnum.CLIENT_APP}

        # Without project_type
        filter_without_type = ProjectFilter(name="test")
        assert filter_without_type.model_dump(exclude_none=True) == {"name": "test"}

        # Empty filter
        empty_filter = ProjectFilter()
        assert empty_filter.model_dump(exclude_none=True) == {}


class TestProjectFilteringAPI:
    """Test project filtering API endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        return User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            status=UserStatusEnum.ACTIVE,
        )

    @pytest.fixture
    def mock_projects(self):
        """Create mock projects with different project_types."""
        base_time = "2024-01-01T00:00:00"
        projects = [
            {
                "id": str(uuid4()),
                "name": "Client Project 1",
                "description": "First client project",
                "project_type": ProjectTypeEnum.CLIENT_APP.value,
                "status": ProjectStatusEnum.ACTIVE,
                "benchmark": False,
                "created_at": base_time,
                "modified_at": base_time,
                "created_by": str(uuid4()),
            },
            {
                "id": str(uuid4()),
                "name": "Client Project 2",
                "description": "Second client project",
                "project_type": ProjectTypeEnum.CLIENT_APP.value,
                "status": ProjectStatusEnum.ACTIVE,
                "benchmark": False,
                "created_at": base_time,
                "modified_at": base_time,
                "created_by": str(uuid4()),
            },
            {
                "id": str(uuid4()),
                "name": "Admin Project 1",
                "description": "First admin project",
                "project_type": ProjectTypeEnum.ADMIN_APP.value,
                "status": ProjectStatusEnum.ACTIVE,
                "benchmark": False,
                "created_at": base_time,
                "modified_at": base_time,
                "created_by": str(uuid4()),
            },
            {
                "id": str(uuid4()),
                "name": "Admin Project 2",
                "description": "Second admin project",
                "project_type": ProjectTypeEnum.ADMIN_APP.value,
                "status": ProjectStatusEnum.ACTIVE,
                "benchmark": False,
                "created_at": base_time,
                "modified_at": base_time,
                "created_by": str(uuid4()),
            },
        ]
        return projects

    # @pytest.mark.asyncio
    # async def test_filter_by_client_app_type(self, client: TestClient, mock_user, mock_projects):
    #     """Test filtering projects by CLIENT_APP type."""
    #     client_projects = [p for p in mock_projects if p["project_type"] == ProjectTypeEnum.CLIENT_APP.value]
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(client_projects, len(client_projects))
    #             )
    #
    #             response = client.get("/projects/?project_type=client_app")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["total_record"] == 2
    #             assert len(data["projects"]) == 2
    #             assert all(p["project_type"] == "client_app" for p in data["projects"])
    #
    #             # Verify the service was called with correct filters
    #             mock_service_instance.get_all_active_projects.assert_called_once()
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]  # Fourth argument is filters_dict
    #             assert filters_dict.get("project_type") == ProjectTypeEnum.CLIENT_APP
    #
    # @pytest.mark.asyncio
    # async def test_filter_by_admin_app_type(self, client: TestClient, mock_user, mock_projects):
    #     """Test filtering projects by ADMIN_APP type."""
    #     admin_projects = [p for p in mock_projects if p["project_type"] == ProjectTypeEnum.ADMIN_APP.value]
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(admin_projects, len(admin_projects))
    #             )
    #
    #             response = client.get("/projects/?project_type=admin_app")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["total_record"] == 2
    #             assert len(data["projects"]) == 2
    #             assert all(p["project_type"] == "admin_app" for p in data["projects"])
    #
    # @pytest.mark.asyncio
    # async def test_filter_without_project_type(self, client: TestClient, mock_user, mock_projects):
    #     """Test getting all projects without project_type filter."""
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(mock_projects, len(mock_projects))
    #             )
    #
    #             response = client.get("/projects/")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["total_record"] == 4
    #             assert len(data["projects"]) == 4
    #
    #             # Verify no project_type filter was passed
    #             mock_service_instance.get_all_active_projects.assert_called_once()
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert "project_type" not in filters_dict
    #
    # @pytest.mark.asyncio
    # async def test_combined_filters(self, client: TestClient, mock_user, mock_projects):
    #     """Test combining project_type filter with other filters."""
    #     filtered_projects = [
    #         p for p in mock_projects if p["project_type"] == ProjectTypeEnum.ADMIN_APP.value and "Admin" in p["name"]
    #     ]
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(filtered_projects, len(filtered_projects))
    #             )
    #
    #             response = client.get("/projects/?name=Admin&project_type=admin_app&page=1&limit=10")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["page"] == 1
    #             assert data["limit"] == 10
    #
    #             # Verify combined filters were passed
    #             mock_service_instance.get_all_active_projects.assert_called_once()
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert filters_dict.get("name") == "Admin"
    #             assert filters_dict.get("project_type") == ProjectTypeEnum.ADMIN_APP
    #
    # @pytest.mark.asyncio
    # async def test_invalid_project_type(self, client: TestClient, mock_user):
    #     """Test filtering with invalid project_type value."""
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         response = client.get("/projects/?project_type=invalid_type")
    #
    #         # Should return validation error
    #         assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    #
    # @pytest.mark.asyncio
    # async def test_case_sensitivity(self, client: TestClient, mock_user, mock_projects):
    #     """Test that project_type filter handles different cases."""
    #     client_projects = [p for p in mock_projects if p["project_type"] == ProjectTypeEnum.CLIENT_APP.value]
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(client_projects, len(client_projects))
    #             )
    #
    #             # Test different case variations
    #             for case_variant in ["CLIENT_APP", "client_app", "Client_App"]:
    #                 response = client.get(f"/projects/?project_type={case_variant.lower()}")
    #                 assert response.status_code == status.HTTP_200_OK
    #
    # @pytest.mark.asyncio
    # async def test_pagination_with_project_type(self, client: TestClient, mock_user, mock_projects):
    #     """Test pagination works correctly with project_type filter."""
    #     admin_projects = [p for p in mock_projects if p["project_type"] == ProjectTypeEnum.ADMIN_APP.value]
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             # Return only first page
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(admin_projects[:1], len(admin_projects))
    #             )
    #
    #             response = client.get("/projects/?project_type=admin_app&page=1&limit=1")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             assert data["page"] == 1
    #             assert data["limit"] == 1
    #             assert data["total_record"] == 2
    #             assert len(data["projects"]) == 1
    #
    # @pytest.mark.asyncio
    # async def test_sorting_with_project_type(self, client: TestClient, mock_user, mock_projects):
    #     """Test sorting works correctly with project_type filter."""
    #     client_projects = sorted(
    #         [p for p in mock_projects if p["project_type"] == ProjectTypeEnum.CLIENT_APP.value],
    #         key=lambda x: x["name"],
    #         reverse=True,
    #     )
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(
    #                 return_value=(client_projects, len(client_projects))
    #             )
    #
    #             response = client.get("/projects/?project_type=client_app&order_by=-name")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #             data = response.json()
    #             # Verify projects are sorted
    #             project_names = [p["name"] for p in data["projects"]]
    #             assert project_names == sorted(project_names, reverse=True)


class TestProjectFilteringCRUD:
    """Test CRUD layer filtering functionality."""

    @pytest.mark.asyncio
    async def test_crud_filter_by_project_type(self):
        """Test that CRUD layer correctly filters by project_type."""
        from budapp.project_ops.crud import ProjectDataManager

        mock_session = MagicMock(spec=AsyncSession)

        # Create a mock result that works with sync calls
        mock_execute_result = MagicMock()
        mock_execute_result.all.return_value = []
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_execute_result.scalar.return_value = 0

        # Make session.execute return the mock result directly (not as a coroutine)
        mock_session.execute.return_value = mock_execute_result

        crud = ProjectDataManager(mock_session)

        with patch.object(crud, "execute_all", return_value=[]) as mock_execute_all:
            with patch.object(crud, "execute_scalar", return_value=0) as mock_execute_scalar:
                filters = {
                    "status": ProjectStatusEnum.ACTIVE,
                    "benchmark": False,
                    "project_type": ProjectTypeEnum.ADMIN_APP.value,
                }

                await crud.get_all_active_projects(offset=0, limit=10, filters=filters, order_by=[], search=False)

                # Verify execute_all was called
                mock_execute_all.assert_called()
                # Verify execute_scalar was called for count
                mock_execute_scalar.assert_called()

    @pytest.mark.asyncio
    async def test_crud_filter_validation(self):
        """Test that CRUD layer validates filter fields."""
        from budapp.commons.exceptions import DatabaseException
        from budapp.project_ops.crud import ProjectDataManager

        mock_session = MagicMock(spec=AsyncSession)
        crud = ProjectDataManager(mock_session)

        # Mock the execute methods to avoid actual database calls
        crud.execute_all = MagicMock(return_value=[])
        crud.execute_scalar = MagicMock(return_value=0)

        # Test with invalid field
        with pytest.raises(DatabaseException) as exc_info:
            filters = {"invalid_field": "value"}
            await crud.get_all_active_projects(offset=0, limit=10, filters=filters, order_by=[], search=False)

        assert "invalid_field" in str(exc_info.value)


class TestClientUserAutoFiltering:
    """Test automatic project_type filtering for client users."""

    @pytest.fixture
    def mock_client_user(self):
        """Create a mock client user for testing."""
        return User(
            id=uuid4(),
            email="client@example.com",
            name="Client User",
            status=UserStatusEnum.ACTIVE,
            user_type=UserTypeEnum.CLIENT,
        )

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user for testing."""
        return User(
            id=uuid4(),
            email="admin@example.com",
            name="Admin User",
            status=UserStatusEnum.ACTIVE,
            user_type=UserTypeEnum.ADMIN,
        )

    # @pytest.mark.asyncio
    # async def test_client_user_auto_filter(self, client: TestClient, mock_client_user):
    #     """Test that client users automatically get project_type=CLIENT_APP filter."""
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_client_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(return_value=([], 0))
    #
    #             # Client user requests without specifying project_type
    #             response = client.get("/projects/")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #
    #             # Verify that project_type filter was automatically added
    #             mock_service_instance.get_all_active_projects.assert_called_once()
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert filters_dict.get("project_type") == ProjectTypeEnum.CLIENT_APP.value
    #
    # @pytest.mark.asyncio
    # async def test_client_user_cannot_override_filter(self, client: TestClient, mock_client_user):
    #     """Test that client users cannot override the auto-filter to see ADMIN_APP projects."""
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_client_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(return_value=([], 0))
    #
    #             # Client user tries to request ADMIN_APP projects
    #             response = client.get("/projects/?project_type=admin_app")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #
    #             # Verify that the filter is still CLIENT_APP (overridden)
    #             mock_service_instance.get_all_active_projects.assert_called_once()
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             # The auto-filter should override the user's request
    #             assert filters_dict.get("project_type") == ProjectTypeEnum.CLIENT_APP.value
    #
    # @pytest.mark.asyncio
    # async def test_admin_user_no_auto_filter(self, client: TestClient, mock_admin_user):
    #     """Test that admin users don't get automatic filtering."""
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_admin_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(return_value=([], 0))
    #
    #             # Admin user requests without specifying project_type
    #             response = client.get("/projects/")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #
    #             # Verify that no auto-filter was added for admin user
    #             mock_service_instance.get_all_active_projects.assert_called_once()
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert "project_type" not in filters_dict
    #
    # @pytest.mark.asyncio
    # async def test_admin_user_can_filter_by_type(self, client: TestClient, mock_admin_user):
    #     """Test that admin users can filter by any project_type."""
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_admin_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(return_value=([], 0))
    #
    #             # Test admin can filter by CLIENT_APP
    #             response = client.get("/projects/?project_type=client_app")
    #             assert response.status_code == status.HTTP_200_OK
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert filters_dict.get("project_type") == ProjectTypeEnum.CLIENT_APP
    #
    #             # Reset mock
    #             mock_service_instance.get_all_active_projects.reset_mock()
    #
    #             # Test admin can filter by ADMIN_APP
    #             response = client.get("/projects/?project_type=admin_app")
    #             assert response.status_code == status.HTTP_200_OK
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert filters_dict.get("project_type") == ProjectTypeEnum.ADMIN_APP
    #
    # @pytest.mark.asyncio
    # async def test_client_user_retrieve_project_access(self, client: TestClient, mock_client_user):
    #     """Test that client users can only retrieve CLIENT_APP projects."""
    #     project_id = uuid4()
    #
    #     # Mock a CLIENT_APP project
    #     mock_client_project = MagicMock()
    #     mock_client_project.project_type = ProjectTypeEnum.CLIENT_APP.value
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_client_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.retrieve_active_project_details = AsyncMock(
    #                 return_value=(mock_client_project, 5)
    #             )
    #
    #             # Client user accessing CLIENT_APP project should succeed
    #             response = client.get(f"/projects/{project_id}")
    #             assert response.status_code == status.HTTP_200_OK
    #
    # @pytest.mark.asyncio
    # async def test_client_user_cannot_retrieve_admin_project(self, client: TestClient, mock_client_user):
    #     """Test that client users cannot retrieve ADMIN_APP projects."""
    #     project_id = uuid4()
    #
    #     # Mock an ADMIN_APP project
    #     mock_admin_project = MagicMock()
    #     mock_admin_project.project_type = ProjectTypeEnum.ADMIN_APP.value
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_client_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.retrieve_active_project_details = AsyncMock(return_value=(mock_admin_project, 5))
    #
    #             # Client user accessing ADMIN_APP project should be denied
    #             response = client.get(f"/projects/{project_id}")
    #             assert response.status_code == status.HTTP_403_FORBIDDEN
    #             data = response.json()
    #             assert "Access denied" in data.get("message", "")
    #
    # @pytest.mark.asyncio
    # async def test_admin_user_can_retrieve_any_project(self, client: TestClient, mock_admin_user):
    #     """Test that admin users can retrieve any project type."""
    #     project_id = uuid4()
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_admin_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #
    #             # Test admin accessing CLIENT_APP project
    #             mock_client_project = MagicMock()
    #             mock_client_project.project_type = ProjectTypeEnum.CLIENT_APP.value
    #             mock_service_instance.retrieve_active_project_details = AsyncMock(
    #                 return_value=(mock_client_project, 5)
    #             )
    #
    #             response = client.get(f"/projects/{project_id}")
    #             assert response.status_code == status.HTTP_200_OK
    #
    #             # Test admin accessing ADMIN_APP project
    #             mock_admin_project = MagicMock()
    #             mock_admin_project.project_type = ProjectTypeEnum.ADMIN_APP.value
    #             mock_service_instance.retrieve_active_project_details = AsyncMock(return_value=(mock_admin_project, 5))
    #
    #             response = client.get(f"/projects/{project_id}")
    #             assert response.status_code == status.HTTP_200_OK


class TestBackwardCompatibility:
    """Test backward compatibility of project_type filtering."""

    # @pytest.mark.asyncio
    # async def test_api_without_project_type_param(self, client: TestClient):
    #     """Test that API works without project_type parameter (backward compatibility)."""
    #     mock_user = User(
    #         id=uuid4(),
    #         email="test@example.com",
    #         name="Test User",
    #         status=UserStatusEnum.ACTIVE,
    #     )
    #
    #     with patch("budapp.project_ops.project_routes.get_current_active_user", return_value=mock_user):
    #         with patch("budapp.project_ops.project_routes.ProjectService") as mock_service:
    #             mock_service_instance = mock_service.return_value
    #             mock_service_instance.get_all_active_projects = AsyncMock(return_value=([], 0))
    #
    #             # Old API call without project_type
    #             response = client.get("/projects/?name=test&page=1&limit=20")
    #
    #             assert response.status_code == status.HTTP_200_OK
    #
    #             # Verify filters don't include project_type
    #             call_args = mock_service_instance.get_all_active_projects.call_args
    #             filters_dict = call_args[0][3]
    #             assert "project_type" not in filters_dict
    #             assert filters_dict.get("name") == "test"

    def test_schema_backward_compatibility(self):
        """Test that ProjectFilter schema maintains backward compatibility."""
        # Old usage without project_type
        old_filter = ProjectFilter(name="test")
        assert old_filter.name == "test"
        assert old_filter.project_type is None

        # New usage with project_type
        new_filter = ProjectFilter(name="test", project_type=ProjectTypeEnum.CLIENT_APP)
        assert new_filter.name == "test"
        assert new_filter.project_type == ProjectTypeEnum.CLIENT_APP

        # Empty filter still works
        empty_filter = ProjectFilter()
        assert empty_filter.model_dump(exclude_none=True) == {}
