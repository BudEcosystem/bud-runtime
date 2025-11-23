"""Tests for PVC sizing logic in model deployment."""

import math
from unittest.mock import MagicMock, patch

import pytest

from budcluster.deployment.handler import DeploymentHandler


class TestPVCSizing:
    """Test PVC sizing calculations for model transfer."""

    @pytest.fixture
    def deployment_handler(self):
        """Create a deployment handler with mock config."""
        config = {"server": "https://test-cluster", "token": "test-token"}
        return DeploymentHandler(config=config)

    @pytest.fixture
    def single_node_config(self):
        """Single node configuration with 8GB memory."""
        return [{"name": "node-1", "memory": 8 * (1024**3), "replicas": 1}]

    @pytest.fixture
    def multi_node_config(self):
        """Multi-node configuration with varying memory sizes."""
        return [
            {"name": "node-1", "memory": 8 * (1024**3), "replicas": 1},
            {"name": "node-2", "memory": 16 * (1024**3), "replicas": 1},
            {"name": "node-3", "memory": 12 * (1024**3), "replicas": 1},
        ]

    @pytest.fixture
    def shared_hardware_config(self):
        """Shared hardware configuration with multiple replicas."""
        return [
            {"name": "node-1", "memory": 10 * (1024**3), "replicas": 3, "hardware_mode": "shared"},
        ]

    def test_get_memory_size_single_node(self, deployment_handler, single_node_config):
        """Test memory size calculation for single node."""
        memory_gb = deployment_handler._get_memory_size(single_node_config)
        assert memory_gb == 8.0

    def test_get_memory_size_multi_node_takes_maximum(self, deployment_handler, multi_node_config):
        """Test that maximum memory is selected from multiple nodes."""
        memory_gb = deployment_handler._get_memory_size(multi_node_config)
        assert memory_gb == 16.0  # Maximum from node-2

    def test_get_memory_size_shared_hardware(self, deployment_handler, shared_hardware_config):
        """Test memory size calculation for shared hardware mode."""
        memory_gb = deployment_handler._get_memory_size(shared_hardware_config)
        assert memory_gb == 10.0  # Memory from single node (replicas share PVC)

    def test_get_memory_size_no_memory_info(self, deployment_handler):
        """Test default fallback when no memory information is available."""
        nodes = [{"name": "node-1"}]  # No memory field
        memory_gb = deployment_handler._get_memory_size(nodes)
        assert memory_gb == 10.0  # Default 10GB

    def test_get_memory_size_legacy_devices_format(self, deployment_handler):
        """Test memory extraction from legacy devices format."""
        nodes = [{"name": "node-1", "devices": [{"memory": 12 * (1024**3)}]}]
        memory_gb = deployment_handler._get_memory_size(nodes)
        assert memory_gb == 12.0

    @patch("budcluster.deployment.handler.transfer_model")
    @patch("budcluster.deployment.handler.app_settings")
    @patch("budcluster.deployment.handler.secrets_settings")
    def test_transfer_model_with_storage_size(
        self, mock_secrets, mock_app_settings, mock_transfer, deployment_handler, single_node_config
    ):
        """Test PVC sizing when storage_size_gb is provided."""
        mock_app_settings.minio_endpoint = "minio:9000"
        mock_app_settings.minio_secure = False
        mock_app_settings.minio_bucket = "models"
        mock_app_settings.volume_type = "local"
        mock_secrets.minio_access_key = "minioadmin"
        mock_secrets.minio_secret_key = "minioadmin"
        mock_transfer.return_value = ("success", "test-namespace")

        result = deployment_handler.transfer_model(
            model_uri="test-model",
            endpoint_name="test-endpoint",
            node_list=single_node_config,
            storage_size_gb=35.7,  # Actual model file size from MinIO
        )

        # Should use actual storage size with 20% buffer
        expected_pvc_size = math.ceil(35.7 * 1.2)  # = 43 GB
        assert mock_transfer.call_count == 1
        call_args = mock_transfer.call_args
        values = call_args[0][1]  # Second positional argument
        assert values["model_size"] == expected_pvc_size

    @patch("budcluster.deployment.handler.transfer_model")
    @patch("budcluster.deployment.handler.app_settings")
    @patch("budcluster.deployment.handler.secrets_settings")
    def test_transfer_model_fallback_to_memory_calculation(
        self, mock_secrets, mock_app_settings, mock_transfer, deployment_handler, single_node_config
    ):
        """Test PVC sizing falls back to memory calculation when storage_size_gb is None."""
        mock_app_settings.minio_endpoint = "minio:9000"
        mock_app_settings.minio_secure = False
        mock_app_settings.minio_bucket = "models"
        mock_app_settings.volume_type = "local"
        mock_secrets.minio_access_key = "minioadmin"
        mock_secrets.minio_secret_key = "minioadmin"
        mock_transfer.return_value = ("success", "test-namespace")

        result = deployment_handler.transfer_model(
            model_uri="test-model",
            endpoint_name="test-endpoint",
            node_list=single_node_config,
            storage_size_gb=None,  # No storage size provided
        )

        # Should fall back to memory-based calculation with 10% buffer
        expected_pvc_size = math.ceil(8.0 * 1.1)  # = 9 GB
        assert mock_transfer.call_count == 1
        call_args = mock_transfer.call_args
        values = call_args[0][1]
        assert values["model_size"] == expected_pvc_size

    @patch("budcluster.deployment.handler.transfer_model")
    @patch("budcluster.deployment.handler.app_settings")
    @patch("budcluster.deployment.handler.secrets_settings")
    def test_transfer_model_validation_too_small(
        self, mock_secrets, mock_app_settings, mock_transfer, deployment_handler
    ):
        """Test validation fails when PVC size is critically small."""
        mock_app_settings.minio_endpoint = "minio:9000"
        mock_app_settings.minio_secure = False
        mock_app_settings.minio_bucket = "models"
        mock_app_settings.volume_type = "local"
        mock_secrets.minio_access_key = "minioadmin"
        mock_secrets.minio_secret_key = "minioadmin"

        nodes = [{"name": "node-1", "memory": 500 * (1024**2)}]  # 500 MB

        with pytest.raises(ValueError, match="too small"):
            deployment_handler.transfer_model(
                model_uri="test-model",
                endpoint_name="test-endpoint",
                node_list=nodes,
                storage_size_gb=None,
            )

    @patch("budcluster.deployment.handler.transfer_model")
    @patch("budcluster.deployment.handler.app_settings")
    @patch("budcluster.deployment.handler.secrets_settings")
    def test_transfer_model_warning_for_small_size(
        self, mock_secrets, mock_app_settings, mock_transfer, deployment_handler, caplog
    ):
        """Test warning is logged when PVC size is below recommended minimum."""
        mock_app_settings.minio_endpoint = "minio:9000"
        mock_app_settings.minio_secure = False
        mock_app_settings.minio_bucket = "models"
        mock_app_settings.volume_type = "local"
        mock_secrets.minio_access_key = "minioadmin"
        mock_secrets.minio_secret_key = "minioadmin"
        mock_transfer.return_value = ("success", "test-namespace")

        result = deployment_handler.transfer_model(
            model_uri="test-model",
            endpoint_name="test-endpoint",
            node_list=[{"name": "node-1", "memory": 3 * (1024**3)}],
            storage_size_gb=None,
        )

        # Should warn for PVC size below 5 GB
        assert any("below recommended minimum" in record.message for record in caplog.records)

    def test_pvc_size_calculation_accuracy(self, deployment_handler):
        """Test PVC size calculations with various inputs."""
        test_cases = [
            # (storage_size_gb, expected_pvc_size_with_20%_buffer)
            (10.0, 12),  # 10 * 1.2 = 12
            (35.7, 43),  # 35.7 * 1.2 = 42.84, ceil = 43
            (100.5, 121),  # 100.5 * 1.2 = 120.6, ceil = 121
            (7.1, 9),  # 7.1 * 1.2 = 8.52, ceil = 9
        ]

        for storage_size, expected_pvc in test_cases:
            pvc_size = math.ceil(storage_size * 1.2)
            assert pvc_size == expected_pvc, f"Failed for storage_size={storage_size}"
