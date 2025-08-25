"""Tests for project credentials count feature."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session


class TestProjectCredentialsCount:
    """Test suite for project credentials count functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock(spec=Session)
        session.execute = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.refresh = Mock()
        session.add = Mock()
        return session

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        # Import here to avoid module-level import issues
        from budapp.commons.constants import UserRoleEnum, UserStatusEnum, UserTypeEnum
        from budapp.user_ops.schemas import User

        return User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            status=UserStatusEnum.ACTIVE,
            user_type=UserTypeEnum.ADMIN,
            color="#FF0000",
            role=UserRoleEnum.ADMIN,
            auth_id=uuid4(),
            password="hashed_password",
            created_at=datetime.now(timezone.utc),
            modified_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def mock_project_with_counts(self):
        """Create a mock project with associated counts."""
        from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum
        from budapp.project_ops.models import Project as ProjectModel

        project = Mock(spec=ProjectModel)
        project.id = uuid4()
        project.name = "Test Project"
        project.description = "Test Description"
        project.project_type = ProjectTypeEnum.CLIENT_APP.value
        project.status = ProjectStatusEnum.ACTIVE
        project.created_at = datetime.now(timezone.utc)
        project.modified_at = datetime.now(timezone.utc)
        project.created_by = uuid4()
        project.tags = []
        project.icon = None
        return project

    @pytest.mark.asyncio
    async def test_get_all_active_projects_returns_credentials_count(self, mock_session):
        """Test that get_all_active_projects returns credentials_count in tuple."""
        from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum
        from budapp.project_ops.crud import ProjectDataManager
        from budapp.project_ops.models import Project as ProjectModel

        crud = ProjectDataManager(mock_session)

        # Mock project
        mock_project = Mock(spec=ProjectModel)
        mock_project.id = uuid4()
        mock_project.name = "Test Project"
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value

        # Mock the execute_all to return project with counts
        # The query returns: Project, user_count, profile_colors, endpoint_count, credential_count
        mock_result = [
            (mock_project, 3, "red,blue,green", 5, 2),  # 2 credentials
        ]

        with patch.object(crud, 'execute_all', return_value=mock_result):
            with patch.object(crud, 'execute_scalar', return_value=1):
                with patch.object(crud, 'validate_fields', new_callable=AsyncMock):
                    result, count = await crud.get_all_active_projects(
                        offset=0,
                        limit=10,
                        filters={"status": ProjectStatusEnum.ACTIVE},
                        order_by=[],
                        search=False
                    )

                    assert count == 1
                    assert len(result) == 1
                    # Verify the tuple structure includes credentials_count
                    assert result[0][4] == 2  # credentials_count is at index 4

    @pytest.mark.asyncio
    async def test_get_all_participated_projects_returns_credentials_count(self, mock_session):
        """Test that get_all_participated_projects returns credentials_count in tuple."""
        from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum
        from budapp.project_ops.crud import ProjectDataManager
        from budapp.project_ops.models import Project as ProjectModel

        crud = ProjectDataManager(mock_session)
        user_id = uuid4()

        # Mock project
        mock_project = Mock(spec=ProjectModel)
        mock_project.id = uuid4()
        mock_project.name = "Participated Project"
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value

        # Mock the execute_all to return project with counts
        mock_result = [
            (mock_project, 4, "yellow,purple", 7, 3),  # 3 credentials
        ]

        with patch.object(crud, 'execute_all', return_value=mock_result):
            with patch.object(crud, 'execute_scalar', return_value=1):
                with patch.object(crud, 'validate_fields', new_callable=AsyncMock):
                    result, count = await crud.get_all_participated_projects(
                        user_id=user_id,
                        offset=0,
                        limit=10,
                        filters={"status": ProjectStatusEnum.ACTIVE},
                        order_by=[],
                        search=False
                    )

                    assert count == 1
                    assert len(result) == 1
                    # Verify the tuple structure includes credentials_count
                    assert result[0][4] == 3  # credentials_count is at index 4

    @pytest.mark.asyncio
    async def test_parse_project_list_results_includes_credentials_count(self, mock_session, mock_project_with_counts):
        """Test that parse_project_list_results correctly parses credentials_count."""
        from budapp.project_ops.schemas import ProjectListResponse
        from budapp.project_ops.services import ProjectService

        service = ProjectService(mock_session)

        # Create mock database results with credentials_count
        db_results = [
            (mock_project_with_counts, 5, "red,blue,green", 10, 4),  # 4 credentials
            (mock_project_with_counts, 2, "yellow", 3, 0),  # 0 credentials
        ]

        result = await service.parse_project_list_results(db_results)

        assert len(result) == 2
        assert isinstance(result[0], ProjectListResponse)
        assert result[0].credentials_count == 4
        assert result[0].users_count == 5
        assert result[0].endpoints_count == 10
        assert result[0].profile_colors == ["red", "blue", "green"]

        assert isinstance(result[1], ProjectListResponse)
        assert result[1].credentials_count == 0
        assert result[1].users_count == 2
        assert result[1].endpoints_count == 3
        assert result[1].profile_colors == ["yellow"]

    @pytest.mark.asyncio
    async def test_get_all_active_projects_service_returns_credentials_count(self, mock_session, mock_user, mock_project_with_counts):
        """Test that ProjectService.get_all_active_projects returns projects with credentials_count."""
        from budapp.project_ops.crud import ProjectDataManager
        from budapp.project_ops.schemas import ProjectListResponse
        from budapp.project_ops.services import ProjectService

        service = ProjectService(mock_session)

        # Mock the CRUD layer response
        mock_crud_result = [
            (mock_project_with_counts, 3, "red,blue", 5, 2),  # 2 credentials
        ]

        with patch.object(ProjectDataManager, '__init__', return_value=None):
            with patch.object(ProjectDataManager, 'get_all_active_projects', new_callable=AsyncMock) as mock_get_all:
                mock_get_all.return_value = (mock_crud_result, 1)

                # Mock permission check
                with patch('budapp.project_ops.services.PermissionService') as mock_permission:
                    mock_permission_instance = mock_permission.return_value
                    mock_permission_instance.check_resource_permission_by_user = AsyncMock(return_value=True)

                    projects, count = await service.get_all_active_projects(
                        current_user=mock_user,
                        offset=0,
                        limit=10,
                        filters={},
                        order_by=[],
                        search=False
                    )

                    assert count == 1
                    assert len(projects) == 1
                    assert isinstance(projects[0], ProjectListResponse)
                    assert projects[0].credentials_count == 2
                    assert projects[0].users_count == 3
                    assert projects[0].endpoints_count == 5

    @pytest.mark.asyncio
    async def test_credentials_count_with_search(self, mock_session):
        """Test that credentials_count is included when using search functionality."""
        from budapp.commons.constants import ProjectTypeEnum
        from budapp.project_ops.crud import ProjectDataManager
        from budapp.project_ops.models import Project as ProjectModel

        crud = ProjectDataManager(mock_session)

        mock_project = Mock(spec=ProjectModel)
        mock_project.id = uuid4()
        mock_project.name = "Searchable Project"
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value

        # Mock search result with credentials_count
        mock_result = [
            (mock_project, 1, "green", 2, 6),  # 6 credentials
        ]

        with patch.object(crud, 'execute_all', return_value=mock_result):
            with patch.object(crud, 'execute_scalar', return_value=1):
                with patch.object(crud, 'validate_fields', new_callable=AsyncMock):
                    with patch.object(ProjectDataManager, '_generate_global_search_stmt', new_callable=AsyncMock) as mock_search:
                        mock_search.return_value = []

                        result, count = await crud.get_all_active_projects(
                            offset=0,
                            limit=10,
                            filters={"name": "Searchable"},
                            order_by=[],
                            search=True
                        )

                        assert count == 1
                        assert len(result) == 1
                        assert result[0][4] == 6  # credentials_count

    @pytest.mark.asyncio
    async def test_credentials_count_null_handling(self, mock_session, mock_project_with_counts):
        """Test that NULL credentials_count is handled properly."""
        from budapp.project_ops.services import ProjectService

        service = ProjectService(mock_session)

        # Create mock database results with NULL credentials_count
        db_results = [
            (mock_project_with_counts, 5, "red", 10, None),  # NULL credentials_count
        ]

        result = await service.parse_project_list_results(db_results)

        assert len(result) == 1
        # The field_validator should convert None to 0
        assert result[0].credentials_count == 0

    @pytest.mark.asyncio
    async def test_client_app_projects_have_credentials_count(self, mock_session, mock_user):
        """Test that CLIENT_APP projects include credentials_count."""
        from budapp.commons.constants import UserTypeEnum, ProjectTypeEnum
        from budapp.project_ops.crud import ProjectDataManager
        from budapp.project_ops.models import Project as ProjectModel
        from budapp.project_ops.services import ProjectService

        mock_user.user_type = UserTypeEnum.CLIENT
        service = ProjectService(mock_session)

        mock_project = Mock(spec=ProjectModel)
        mock_project.id = uuid4()
        mock_project.name = "Client App Project"
        mock_project.project_type = ProjectTypeEnum.CLIENT_APP.value

        mock_crud_result = [
            (mock_project, 2, "blue", 3, 5),  # 5 credentials for CLIENT_APP
        ]

        with patch.object(ProjectDataManager, '__init__', return_value=None):
            with patch.object(ProjectDataManager, 'get_all_participated_projects', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = (mock_crud_result, 1)

                projects, count = await service.get_all_active_projects(
                    current_user=mock_user,
                    offset=0,
                    limit=10,
                    filters={},
                    order_by=[],
                    search=False
                )

                assert count == 1
                assert len(projects) == 1
                assert projects[0].credentials_count == 5

    @pytest.mark.asyncio
    async def test_admin_app_projects_have_credentials_count(self, mock_session, mock_user):
        """Test that ADMIN_APP projects also include credentials_count (should be 0 for admin apps)."""
        from budapp.commons.constants import ProjectTypeEnum
        from budapp.project_ops.crud import ProjectDataManager
        from budapp.project_ops.models import Project as ProjectModel
        from budapp.project_ops.services import ProjectService

        service = ProjectService(mock_session)

        mock_project = Mock(spec=ProjectModel)
        mock_project.id = uuid4()
        mock_project.name = "Admin App Project"
        mock_project.project_type = ProjectTypeEnum.ADMIN_APP.value

        # Admin apps typically don't have credentials, but the field should still be present
        mock_crud_result = [
            (mock_project, 3, "green", 4, 0),  # 0 credentials for ADMIN_APP
        ]

        with patch.object(ProjectDataManager, '__init__', return_value=None):
            with patch.object(ProjectDataManager, 'get_all_active_projects', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = (mock_crud_result, 1)

                with patch('budapp.project_ops.services.PermissionService') as mock_permission:
                    mock_permission_instance = mock_permission.return_value
                    mock_permission_instance.check_resource_permission_by_user = AsyncMock(return_value=True)

                    projects, count = await service.get_all_active_projects(
                        current_user=mock_user,
                        offset=0,
                        limit=10,
                        filters={"project_type": ProjectTypeEnum.ADMIN_APP.value},
                        order_by=[],
                        search=False
                    )

                    assert count == 1
                    assert len(projects) == 1
                    assert projects[0].credentials_count == 0

    def test_project_list_response_schema_includes_credentials_count(self):
        """Test that ProjectListResponse schema properly includes credentials_count."""
        from budapp.commons.constants import ProjectTypeEnum
        from budapp.project_ops.schemas import ProjectListResponse

        base_time = datetime.now(timezone.utc)
        project_data = {
            "project": {
                "id": str(uuid4()),
                "name": "Test Project",
                "description": "Test Description",
                "project_type": ProjectTypeEnum.CLIENT_APP.value,
                "created_at": base_time,
                "modified_at": base_time,
                "created_by": str(uuid4()),
                "tags": [],
                "icon": None,
            },
            "users_count": 3,
            "endpoints_count": 5,
            "credentials_count": 2,
            "profile_colors": ["#FF0000", "#00FF00"],
        }

        response = ProjectListResponse(**project_data)
        assert response.credentials_count == 2
        assert response.users_count == 3
        assert response.endpoints_count == 5

    def test_project_list_response_schema_converts_none_to_zero(self):
        """Test that ProjectListResponse converts None values to 0."""
        from budapp.commons.constants import ProjectTypeEnum
        from budapp.project_ops.schemas import ProjectListResponse

        base_time = datetime.now(timezone.utc)
        project_data = {
            "project": {
                "id": str(uuid4()),
                "name": "Test Project",
                "description": "Test Description",
                "project_type": ProjectTypeEnum.CLIENT_APP.value,
                "created_at": base_time,
                "modified_at": base_time,
                "created_by": str(uuid4()),
                "tags": [],
                "icon": None,
            },
            "users_count": None,
            "endpoints_count": None,
            "credentials_count": None,
            "profile_colors": [],
        }

        response = ProjectListResponse(**project_data)
        assert response.credentials_count == 0
        assert response.users_count == 0
        assert response.endpoints_count == 0

    def test_paginated_projects_response_includes_credentials_count(self):
        """Test that PaginatedProjectsResponse properly includes projects with credentials_count."""
        from budapp.commons.constants import ProjectTypeEnum
        from budapp.project_ops.schemas import ProjectListResponse, PaginatedProjectsResponse

        base_time = datetime.now(timezone.utc)
        projects = []

        for i in range(3):
            project_data = {
                "project": {
                    "id": str(uuid4()),
                    "name": f"Project {i}",
                    "description": f"Description {i}",
                    "project_type": ProjectTypeEnum.CLIENT_APP.value,
                    "created_at": base_time,
                    "modified_at": base_time,
                    "created_by": str(uuid4()),
                    "tags": [],
                    "icon": None,
                },
                "users_count": i + 1,
                "endpoints_count": i * 2,
                "credentials_count": i * 3,
                "profile_colors": [],
            }
            projects.append(ProjectListResponse(**project_data))

        response = PaginatedProjectsResponse(
            message="Success",
            projects=projects,
            total_record=3,
            page=1,
            limit=10,
            code=status.HTTP_200_OK,
            object="project.list",
        )

        assert len(response.projects) == 3
        assert response.projects[0].credentials_count == 0
        assert response.projects[1].credentials_count == 3
        assert response.projects[2].credentials_count == 6
