"""Tests for model storage size calculation in MinIO."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from budapp.commons.exceptions import MinioException
from budapp.shared.minio_store import ModelStore


class TestModelStoreSizeCalculation:
    """Test storage size calculation for models in MinIO."""

    @pytest.fixture
    def model_store(self):
        """Create a ModelStore instance with mocked Minio client."""
        with patch("budapp.shared.minio_store.Minio") as mock_minio:
            store = ModelStore()
            store.client = mock_minio.return_value
            yield store

    def test_get_folder_size_single_file(self, model_store):
        """Test folder size calculation for a single file."""
        # Mock a single file of 1 GB
        mock_obj = Mock()
        mock_obj.size = 1024**3  # 1 GB in bytes
        model_store.client.list_objects.return_value = [mock_obj]

        size_gb = model_store.get_folder_size("models", "llama-2-7b")

        assert size_gb == 1.0
        model_store.client.list_objects.assert_called_once_with("models", "llama-2-7b", recursive=True)

    def test_get_folder_size_multiple_files(self, model_store):
        """Test folder size calculation for multiple files."""
        # Mock multiple files with different sizes
        files = [
            Mock(size=10 * (1024**3)),  # 10 GB
            Mock(size=5 * (1024**3)),  # 5 GB
            Mock(size=2.5 * (1024**3)),  # 2.5 GB
            Mock(size=500 * (1024**2)),  # 500 MB
        ]
        model_store.client.list_objects.return_value = files

        size_gb = model_store.get_folder_size("models", "llama-2-70b")

        # Total: 10 + 5 + 2.5 + 0.5 = 18 GB (approximately)
        assert 17.9 < size_gb < 18.1
        model_store.client.list_objects.assert_called_once_with("models", "llama-2-70b", recursive=True)

    def test_get_folder_size_empty_folder(self, model_store):
        """Test folder size calculation for empty folder."""
        model_store.client.list_objects.return_value = []

        size_gb = model_store.get_folder_size("models", "empty-model")

        assert size_gb == 0.0

    def test_get_folder_size_s3_error(self, model_store):
        """Test error handling when MinIO returns S3Error."""
        from minio.error import S3Error

        model_store.client.list_objects.side_effect = S3Error(
            "NoSuchBucket", "The specified bucket does not exist", "resource", "request_id", "host_id", "response"
        )

        with pytest.raises(MinioException, match="Error calculating folder size"):
            model_store.get_folder_size("nonexistent", "model")

    def test_get_folder_size_generic_exception(self, model_store):
        """Test error handling for generic exceptions."""
        model_store.client.list_objects.side_effect = Exception("Connection error")

        with pytest.raises(MinioException, match="Error calculating folder size"):
            model_store.get_folder_size("models", "model")

    def test_get_folder_size_large_model(self, model_store):
        """Test folder size calculation for large models with many files."""
        # Simulate a large model with 100 files averaging 1 GB each
        files = [Mock(size=1024**3) for _ in range(100)]
        model_store.client.list_objects.return_value = files

        size_gb = model_store.get_folder_size("models", "large-model")

        assert 99.9 < size_gb < 100.1
        assert model_store.client.list_objects.call_count == 1

    def test_get_folder_size_precision(self, model_store):
        """Test that size calculation maintains precision."""
        # Test with exact byte values
        mock_obj = Mock()
        mock_obj.size = 1234567890  # ~1.15 GB
        model_store.client.list_objects.return_value = [mock_obj]

        size_gb = model_store.get_folder_size("models", "test-model")

        expected_gb = 1234567890 / (1024**3)
        assert abs(size_gb - expected_gb) < 0.0001  # Very small tolerance


class TestModelUpdateWithStorageSize:
    """Test model update workflow with storage size calculation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def model_service(self, mock_session):
        """Create a CloudModelWorkflowService instance with mocked session."""
        from budapp.model_ops.services import CloudModelWorkflowService

        service = CloudModelWorkflowService(mock_session)
        return service

    @pytest.fixture
    def mock_model(self):
        """Create a mock model with local_path."""
        model = Mock()
        model.id = uuid4()
        model.local_path = "models/llama-2-7b"
        model.name = "Llama-2-7b"
        return model

    @patch("budapp.model_ops.services.ModelStore")
    @patch("budapp.model_ops.services.ModelDataManager")
    @patch("budapp.model_ops.services.app_settings")
    async def test_update_model_with_storage_size(
        self, mock_settings, mock_data_manager, mock_model_store_class, model_service, mock_model
    ):
        """Test that storage size is calculated and updated during model metadata update."""
        # Mock settings
        mock_settings.minio_bucket = "models"

        # Mock ModelStore
        mock_store_instance = Mock()
        mock_store_instance.get_folder_size.return_value = 35.7  # 35.7 GB
        mock_model_store_class.return_value = mock_store_instance

        # Mock DataManager
        mock_dm_instance = Mock()
        mock_dm_instance.update_by_fields = AsyncMock(return_value=mock_model)
        mock_data_manager.return_value = mock_dm_instance

        # Call the method
        extracted_metadata = {"description": "Test model"}
        await model_service._update_model_with_extracted_metadata(mock_model, extracted_metadata)

        # Verify ModelStore was instantiated
        assert mock_model_store_class.call_count == 1

        # Verify get_folder_size was called with correct parameters
        mock_store_instance.get_folder_size.assert_called_once_with("models", "models/llama-2-7b")

        # Verify update was called with storage_size_gb
        assert mock_dm_instance.update_by_fields.call_count == 1
        update_call_args = mock_dm_instance.update_by_fields.call_args
        update_fields = update_call_args[0][1]  # Second argument is update_fields
        assert "storage_size_gb" in update_fields
        assert update_fields["storage_size_gb"] == 35.7

    @patch("budapp.model_ops.services.ModelStore")
    @patch("budapp.model_ops.services.ModelDataManager")
    @patch("budapp.model_ops.services.app_settings")
    async def test_update_model_no_local_path(
        self, mock_settings, mock_data_manager, mock_model_store_class, model_service
    ):
        """Test that storage size is not calculated when model has no local_path."""
        # Model without local_path
        model = Mock()
        model.id = uuid4()
        model.local_path = None

        mock_dm_instance = Mock()
        mock_dm_instance.update_by_fields = AsyncMock(return_value=model)
        mock_data_manager.return_value = mock_dm_instance

        extracted_metadata = {"description": "Test model"}
        await model_service._update_model_with_extracted_metadata(model, extracted_metadata)

        # ModelStore should not be instantiated
        assert mock_model_store_class.call_count == 0

        # Update should still be called but without storage_size_gb
        assert mock_dm_instance.update_by_fields.call_count == 1
        update_call_args = mock_dm_instance.update_by_fields.call_args
        update_fields = update_call_args[0][1]
        assert "storage_size_gb" not in update_fields

    @patch("budapp.model_ops.services.ModelStore")
    @patch("budapp.model_ops.services.ModelDataManager")
    @patch("budapp.model_ops.services.app_settings")
    async def test_update_model_storage_size_calculation_fails(
        self, mock_settings, mock_data_manager, mock_model_store_class, model_service, mock_model, caplog
    ):
        """Test that model update continues even if storage size calculation fails."""
        mock_settings.minio_bucket = "models"

        # Mock ModelStore to raise exception
        mock_store_instance = Mock()
        mock_store_instance.get_folder_size.side_effect = MinioException("Failed to list objects")
        mock_model_store_class.return_value = mock_store_instance

        mock_dm_instance = Mock()
        mock_dm_instance.update_by_fields = AsyncMock(return_value=mock_model)
        mock_data_manager.return_value = mock_dm_instance

        extracted_metadata = {"description": "Test model"}
        await model_service._update_model_with_extracted_metadata(mock_model, extracted_metadata)

        # Update should still proceed without storage_size_gb
        assert mock_dm_instance.update_by_fields.call_count == 1
        update_call_args = mock_dm_instance.update_by_fields.call_args
        update_fields = update_call_args[0][1]
        assert "storage_size_gb" not in update_fields

        # Warning should be logged
        assert any("Failed to calculate storage size" in record.message for record in caplog.records)
