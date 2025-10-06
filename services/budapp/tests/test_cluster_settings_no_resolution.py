"""Test to verify get_cluster_settings doesn't auto-resolve access mode."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from budapp.cluster_ops.models import ClusterSettings
from budapp.cluster_ops.services import ClusterService
from budapp.cluster_ops.schemas import ClusterSettingsResponse


@pytest.mark.asyncio
async def test_get_cluster_settings_returns_none_for_unset_access_mode():
    """Test that get_cluster_settings returns None for access_mode when not set in DB."""

    # Setup
    cluster_id = uuid4()
    user_id = uuid4()

    # Mock ClusterSettings with storage class but NO access mode
    mock_settings = Mock(spec=ClusterSettings)
    mock_settings.id = uuid4()
    mock_settings.cluster_id = cluster_id
    mock_settings.default_storage_class = "nfs-dynamic"
    mock_settings.default_access_mode = None  # This is the key - access mode is NOT set
    mock_settings.created_by = user_id
    mock_settings.created_at = datetime.now(timezone.utc)
    mock_settings.modified_at = datetime.now(timezone.utc)

    # Create service with mocked session
    mock_session = Mock()
    service = ClusterService(mock_session)

    # Mock the data manager to return our settings
    service.get_cluster_settings = AsyncMock(wraps=service.get_cluster_settings)
    mock_data_manager = Mock()
    mock_data_manager.get_cluster_settings = AsyncMock(return_value=mock_settings)

    # Monkey patch the data manager creation
    original_init = service.get_cluster_settings

    async def patched_get_cluster_settings(cluster_id_param):
        from budapp.cluster_ops.crud import ClusterSettingsDataManager
        # Mock the data manager
        with Mock() as mock_dm:
            mock_dm.get_cluster_settings = AsyncMock(return_value=mock_settings)
            ClusterSettingsDataManager.__new__ = Mock(return_value=mock_dm)
            ClusterSettingsDataManager.__init__ = Mock(return_value=None)
            return await original_init(cluster_id_param)

    service.get_cluster_settings = patched_get_cluster_settings

    # Act
    result = await service.get_cluster_settings(cluster_id)

    # Assert
    assert result is not None
    assert isinstance(result, ClusterSettingsResponse)
    assert result.cluster_id == cluster_id
    assert result.default_storage_class == "nfs-dynamic"
    assert result.default_access_mode is None  # Should be None, not auto-resolved

    print("✓ Test passed: get_cluster_settings returns None for unset access_mode")
    print(f"  - Storage class: {result.default_storage_class}")
    print(f"  - Access mode: {result.default_access_mode}")


@pytest.mark.asyncio
async def test_get_cluster_settings_preserves_existing_access_mode():
    """Test that get_cluster_settings preserves access_mode when it's set in DB."""

    # Setup
    cluster_id = uuid4()
    user_id = uuid4()

    # Mock ClusterSettings with both storage class AND access mode
    mock_settings = Mock(spec=ClusterSettings)
    mock_settings.id = uuid4()
    mock_settings.cluster_id = cluster_id
    mock_settings.default_storage_class = "nfs-csi"
    mock_settings.default_access_mode = "ReadWriteMany"  # Access mode IS set
    mock_settings.created_by = user_id
    mock_settings.created_at = datetime.now(timezone.utc)
    mock_settings.modified_at = datetime.now(timezone.utc)

    # Create service with mocked session
    mock_session = Mock()
    service = ClusterService(mock_session)

    # Mock the data manager to return our settings
    original_init = service.get_cluster_settings

    async def patched_get_cluster_settings(cluster_id_param):
        from budapp.cluster_ops.crud import ClusterSettingsDataManager
        # Mock the data manager
        mock_dm = Mock()
        mock_dm.get_cluster_settings = AsyncMock(return_value=mock_settings)
        ClusterSettingsDataManager.__new__ = Mock(return_value=mock_dm)
        ClusterSettingsDataManager.__init__ = Mock(return_value=None)
        return await original_init(cluster_id_param)

    service.get_cluster_settings = patched_get_cluster_settings

    # Act
    result = await service.get_cluster_settings(cluster_id)

    # Assert
    assert result is not None
    assert isinstance(result, ClusterSettingsResponse)
    assert result.cluster_id == cluster_id
    assert result.default_storage_class == "nfs-csi"
    assert result.default_access_mode == "ReadWriteMany"  # Should preserve the existing value

    print("✓ Test passed: get_cluster_settings preserves existing access_mode")
    print(f"  - Storage class: {result.default_storage_class}")
    print(f"  - Access mode: {result.default_access_mode}")


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        await test_get_cluster_settings_returns_none_for_unset_access_mode()
        await test_get_cluster_settings_preserves_existing_access_mode()
        print("\nAll tests passed! ✓")

    asyncio.run(run_tests())
