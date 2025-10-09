"""Tests for cluster settings functionality."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from budapp.commons.exceptions import ClientException
from budapp.cluster_ops.schemas import (
    ClusterSettingsResponse,
    CreateClusterSettingsRequest,
    UpdateClusterSettingsRequest,
)
from budapp.user_ops.models import User

# Import test helpers after the models to avoid circular imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'test_helpers'))
from cluster_settings_helpers import MockFactory, TestDataBuilder, AssertionHelpers


class TestClusterSettingsDataManager:
    """Test ClusterSettingsDataManager methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def data_manager(self, mock_session):
        """Create a ClusterSettingsDataManager instance with mock session."""
        from budapp.cluster_ops.crud import ClusterSettingsDataManager
        return ClusterSettingsDataManager(mock_session)

    @pytest.fixture
    def mock_factory(self):
        """Create a mock factory instance."""
        return MockFactory()

    @pytest.mark.asyncio
    async def test_get_cluster_settings_found(self, data_manager, mock_factory):
        """Test getting cluster settings by cluster ID when found."""
        cluster_id = uuid4()

        mock_settings = mock_factory.create_mock_cluster_settings(
            cluster_id=cluster_id,
            default_storage_class="gp2"
        )

        data_manager.scalar_one_or_none = Mock(return_value=mock_settings)

        result = await data_manager.get_cluster_settings(cluster_id)

        assert result == mock_settings
        data_manager.scalar_one_or_none.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cluster_settings_not_found(self, data_manager):
        """Test getting cluster settings by cluster ID when not found."""
        cluster_id = uuid4()

        data_manager.scalar_one_or_none = Mock(return_value=None)

        result = await data_manager.get_cluster_settings(cluster_id)

        assert result is None
        data_manager.scalar_one_or_none.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_cluster_settings(self, data_manager, mock_factory):
        """Test creating cluster settings."""
        cluster_id = uuid4()
        user_id = uuid4()
        default_storage_class = "fast-ssd"

        mock_settings = mock_factory.create_mock_cluster_settings(
            cluster_id=cluster_id,
            default_storage_class=default_storage_class,
            created_by=user_id
        )

        data_manager.add_one = Mock(return_value=mock_settings)

        result = await data_manager.create_cluster_settings(
            cluster_id=cluster_id,
            created_by=user_id,
            default_storage_class=default_storage_class,
            default_access_mode=None
        )

        assert result == mock_settings
        data_manager.add_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_cluster_settings(self, data_manager):
        """Test updating cluster settings."""
        cluster_id = uuid4()
        new_storage_class = "nfs-storage"

        mock_settings = Mock()
        mock_settings.id = uuid4()
        mock_settings.cluster_id = cluster_id
        mock_settings.default_storage_class = "old-storage"

        # Mock get_cluster_settings to return the mock
        with patch.object(data_manager, 'get_cluster_settings', new_callable=AsyncMock, return_value=mock_settings):
            data_manager.update_one = Mock(return_value=mock_settings)

            result = await data_manager.update_cluster_settings(
                cluster_id=cluster_id,
                default_storage_class=new_storage_class
            )

            assert result == mock_settings
            assert mock_settings.default_storage_class == new_storage_class
            data_manager.update_one.assert_called_once_with(mock_settings)

    @pytest.mark.asyncio
    async def test_update_cluster_settings_not_found(self, data_manager):
        """Test updating cluster settings when not found."""
        cluster_id = uuid4()

        # Mock get_cluster_settings to return None
        with patch.object(data_manager, 'get_cluster_settings', new_callable=AsyncMock, return_value=None):
            result = await data_manager.update_cluster_settings(
                cluster_id=cluster_id,
                default_storage_class="new-storage"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_delete_cluster_settings(self, data_manager):
        """Test deleting cluster settings."""
        cluster_id = uuid4()

        mock_settings = Mock()

        # Mock get_cluster_settings to return the mock
        with patch.object(data_manager, 'get_cluster_settings', new_callable=AsyncMock, return_value=mock_settings):
            with patch.object(data_manager, 'delete_model', new_callable=AsyncMock) as mock_delete:
                result = await data_manager.delete_cluster_settings(cluster_id)

                assert result is True
                mock_delete.assert_called_once_with(mock_settings)

    @pytest.mark.asyncio
    async def test_delete_cluster_settings_not_found(self, data_manager):
        """Test deleting cluster settings when not found."""
        cluster_id = uuid4()

        # Mock get_cluster_settings to return None
        with patch.object(data_manager, 'get_cluster_settings', new_callable=AsyncMock, return_value=None):
            result = await data_manager.delete_cluster_settings(cluster_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_upsert_cluster_settings_create_new(self, data_manager):
        """Test upsert when settings don't exist (create new)."""
        cluster_id = uuid4()
        user_id = uuid4()
        default_storage_class = "premium-ssd"

        # First call returns None (no existing settings)
        # Second call after create returns the new settings
        mock_new_settings = Mock()
        mock_new_settings.id = uuid4()
        mock_new_settings.cluster_id = cluster_id

        # Mock get_cluster_settings to return None (no existing settings)
        with patch.object(data_manager, 'get_cluster_settings', new_callable=AsyncMock, return_value=None):
            with patch.object(data_manager, 'create_cluster_settings', new_callable=AsyncMock, return_value=mock_new_settings):
                result = await data_manager.upsert_cluster_settings(
                    cluster_id=cluster_id,
                    created_by=user_id,
                    default_storage_class=default_storage_class,
                    default_access_mode=None
                )

                assert result == mock_new_settings
                data_manager.create_cluster_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_cluster_settings_update_existing(self, data_manager):
        """Test upsert when settings exist (update)."""
        cluster_id = uuid4()
        user_id = uuid4()
        default_storage_class = "ultra-ssd"

        mock_existing_settings = Mock()
        mock_existing_settings.id = uuid4()
        mock_existing_settings.cluster_id = cluster_id
        mock_existing_settings.default_storage_class = "old-storage"

        # Mock get_cluster_settings to return existing settings
        with patch.object(data_manager, 'get_cluster_settings', new_callable=AsyncMock, return_value=mock_existing_settings):
            data_manager.update_one = Mock(return_value=mock_existing_settings)

            result = await data_manager.upsert_cluster_settings(
                cluster_id=cluster_id,
                created_by=user_id,
                default_storage_class=default_storage_class,
                default_access_mode=None
            )

            assert result == mock_existing_settings
            assert mock_existing_settings.default_storage_class == default_storage_class
            data_manager.update_one.assert_called_once_with(mock_existing_settings)


class TestClusterService:
    """Test ClusterService methods for cluster settings."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def cluster_service(self, mock_session):
        """Create a ClusterService instance with mock session."""
        from budapp.cluster_ops.services import ClusterService
        service = ClusterService(mock_session)
        service._resolve_default_access_mode = AsyncMock(return_value=None)
        return service

    @pytest.mark.asyncio
    async def test_get_cluster_settings_success(self, cluster_service):
        """Test getting cluster settings successfully."""
        cluster_id = uuid4()
        user_id = uuid4()

        mock_settings = Mock()
        mock_settings.id = uuid4()
        mock_settings.cluster_id = cluster_id
        mock_settings.default_storage_class = "gp3"
        mock_settings.default_access_mode = None
        mock_settings.created_by = user_id
        mock_settings.created_at = datetime.now(timezone.utc)
        mock_settings.modified_at = datetime.now(timezone.utc)

        with patch('budapp.cluster_ops.services.ClusterSettingsDataManager') as mock_manager_class:
            mock_manager = mock_manager_class.return_value
            mock_manager.get_cluster_settings = AsyncMock(return_value=mock_settings)

            result = await cluster_service.get_cluster_settings(cluster_id)

            assert isinstance(result, ClusterSettingsResponse)
            assert result.cluster_id == cluster_id
            assert result.default_storage_class == "gp3"

    @pytest.mark.asyncio
    async def test_get_cluster_settings_not_found(self, cluster_service):
        """Test getting cluster settings when settings don't exist."""
        cluster_id = uuid4()

        with patch('budapp.cluster_ops.services.ClusterSettingsDataManager') as mock_manager_class:
            mock_manager = mock_manager_class.return_value
            mock_manager.get_cluster_settings = AsyncMock(return_value=None)

            result = await cluster_service.get_cluster_settings(cluster_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_create_cluster_settings_success(self, cluster_service):
        """Test creating cluster settings successfully."""
        cluster_id = uuid4()
        user_id = uuid4()

        mock_cluster = Mock()
        mock_cluster.id = cluster_id

        mock_settings = Mock()
        mock_settings.id = uuid4()
        mock_settings.cluster_id = cluster_id
        mock_settings.default_storage_class = "premium-storage"
        mock_settings.default_access_mode = None
        mock_settings.created_by = user_id
        mock_settings.created_at = datetime.now(timezone.utc)
        mock_settings.modified_at = datetime.now(timezone.utc)

        with patch('budapp.cluster_ops.services.ClusterDataManager') as mock_cluster_manager_class, \
             patch('budapp.cluster_ops.services.ClusterSettingsDataManager') as mock_settings_manager_class:

            mock_cluster_manager = mock_cluster_manager_class.return_value
            mock_cluster_manager.retrieve_by_fields = AsyncMock(return_value=mock_cluster)

            mock_settings_manager = mock_settings_manager_class.return_value
            mock_settings_manager.create_cluster_settings = AsyncMock(return_value=mock_settings)

            result = await cluster_service.create_cluster_settings(
                cluster_id=cluster_id,
                created_by=user_id,
                default_storage_class="premium-storage"
            )

            assert isinstance(result, ClusterSettingsResponse)
            assert result.cluster_id == cluster_id
            assert result.default_storage_class == "premium-storage"

    @pytest.mark.asyncio
    async def test_create_cluster_settings_cluster_not_found(self, cluster_service):
        """Test creating cluster settings when cluster doesn't exist."""
        cluster_id = uuid4()
        user_id = uuid4()

        with patch('budapp.cluster_ops.services.ClusterDataManager') as mock_cluster_manager_class:
            mock_cluster_manager = mock_cluster_manager_class.return_value
            mock_cluster_manager.retrieve_by_fields = AsyncMock(return_value=None)

            with pytest.raises(ClientException) as exc_info:
                await cluster_service.create_cluster_settings(
                    cluster_id=cluster_id,
                    created_by=user_id,
                    default_storage_class="premium-storage"
                )

            assert "Cluster not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_cluster_settings_success(self, cluster_service):
        """Test updating cluster settings successfully."""
        cluster_id = uuid4()

        mock_settings = Mock()
        mock_settings.id = uuid4()
        mock_settings.cluster_id = cluster_id
        mock_settings.default_storage_class = "updated-storage"
        mock_settings.default_access_mode = None
        mock_settings.created_by = uuid4()
        mock_settings.created_at = datetime.now(timezone.utc)
        mock_settings.modified_at = datetime.now(timezone.utc)

        with patch('budapp.cluster_ops.services.ClusterSettingsDataManager') as mock_manager_class:
            mock_manager = mock_manager_class.return_value
            mock_manager.update_cluster_settings = AsyncMock(return_value=mock_settings)

            result = await cluster_service.update_cluster_settings(
                cluster_id=cluster_id,
                default_storage_class="updated-storage"
            )

            assert isinstance(result, ClusterSettingsResponse)
            assert result.cluster_id == cluster_id
            assert result.default_storage_class == "updated-storage"

    @pytest.mark.asyncio
    async def test_delete_cluster_settings_success(self, cluster_service):
        """Test deleting cluster settings successfully."""
        cluster_id = uuid4()

        with patch('budapp.cluster_ops.services.ClusterSettingsDataManager') as mock_manager_class:
            mock_manager = mock_manager_class.return_value
            mock_manager.delete_cluster_settings = AsyncMock(return_value=True)

            result = await cluster_service.delete_cluster_settings(cluster_id)

            assert result is True

    @pytest.mark.asyncio
    async def test_delete_cluster_settings_not_found(self, cluster_service):
        """Test deleting cluster settings when they don't exist."""
        cluster_id = uuid4()

        with patch('budapp.cluster_ops.services.ClusterSettingsDataManager') as mock_manager_class:
            mock_manager = mock_manager_class.return_value
            mock_manager.delete_cluster_settings = AsyncMock(return_value=False)

            result = await cluster_service.delete_cluster_settings(cluster_id)

            assert result is False


class TestClusterSettingsSchemas:
    """Test Pydantic schemas for cluster settings."""

    def test_create_cluster_settings_request_valid(self):
        """Test creating valid cluster settings request."""
        request = CreateClusterSettingsRequest(
            default_storage_class="gp2"
        )
        assert request.default_storage_class == "gp2"

    def test_create_cluster_settings_request_none(self):
        """Test creating cluster settings request with None."""
        request = CreateClusterSettingsRequest(
            default_storage_class=None
        )
        assert request.default_storage_class is None

    def test_create_cluster_settings_request_empty_string(self):
        """Test creating cluster settings request with empty string."""
        request = CreateClusterSettingsRequest(
            default_storage_class=""
        )
        assert request.default_storage_class is None

    def test_create_cluster_settings_request_invalid_characters(self):
        """Test creating cluster settings request with invalid characters."""
        with pytest.raises(ValueError, match="Storage class name can only contain"):
            CreateClusterSettingsRequest(
                default_storage_class="invalid@storage"
            )

    def test_create_cluster_settings_request_invalid_start_hyphen(self):
        """Test creating cluster settings request starting with hyphen."""
        with pytest.raises(ValueError, match="Storage class name cannot start or end"):
            CreateClusterSettingsRequest(
                default_storage_class="-invalid-storage"
            )

    def test_create_cluster_settings_request_invalid_end_hyphen(self):
        """Test creating cluster settings request ending with hyphen."""
        with pytest.raises(ValueError, match="Storage class name cannot start or end"):
            CreateClusterSettingsRequest(
                default_storage_class="invalid-storage-"
            )

    def test_cluster_settings_response(self):
        """Test cluster settings response schema."""
        cluster_id = uuid4()
        settings_id = uuid4()
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        response = ClusterSettingsResponse(
            id=settings_id,
            cluster_id=cluster_id,
            default_storage_class="gp3",
            created_by=user_id,
            created_at=now,
            modified_at=now
        )

        assert response.id == settings_id
        assert response.cluster_id == cluster_id
        assert response.default_storage_class == "gp3"
        assert response.created_by == user_id
        assert response.created_at == now
        assert response.modified_at == now
