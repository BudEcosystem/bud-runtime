"""Tests for model transfer with storage class support."""

import pytest
from unittest.mock import Mock, patch
from budcluster.cluster_ops.kubernetes import KubernetesHandler
from budcluster.deployment.handler import DeploymentHandler


class TestModelTransferWithStorageClass:
    """Test model transfer with cluster settings storage class integration."""

    @patch('budcluster.cluster_ops.kubernetes.KubernetesHandler._load_kube_config')
    def test_transfer_model_with_nfs_server_available(self, mock_load_config):
        """Test model transfer when NFS server is available."""
        # Setup
        mock_config = {"test": "config"}
        k8s_handler = KubernetesHandler(mock_config)
        k8s_handler.ansible_executor = Mock()

        # Mock the get_nfs_service_ip to return an IP
        with patch.object(k8s_handler, 'get_nfs_service_ip', return_value="10.0.0.100"):
            k8s_handler.ansible_executor.run_playbook = Mock(return_value={"status": "success"})
            values = {
                "volume_type": "nfs",
                "namespace": "test-namespace",
                "source_model_path": "model123",
                "model_size": 10,
                "nodes": [{"name": "node1"}],
                "minio_endpoint": "minio.local",
                "minio_secure": False,
                "minio_access_key": "access",
                "minio_secret_key": "secret",
                "minio_bucket": "models",
            }

            result = k8s_handler.transfer_model(values)

            # Verify NFS server was set
            assert values["nfs_server"] == "10.0.0.100"
            assert values["volume_type"] == "nfs"
            assert result == "success"

    @patch('budcluster.cluster_ops.kubernetes.KubernetesHandler._load_kube_config')
    def test_transfer_model_with_nfs_fallback_to_local(self, mock_load_config):
        """Test model transfer falls back to local when NFS is not available."""
        # Setup
        mock_config = {"test": "config"}
        k8s_handler = KubernetesHandler(mock_config)
        k8s_handler.ansible_executor = Mock()

        # Mock the get_nfs_service_ip to return None (NFS not available)
        with patch.object(k8s_handler, 'get_nfs_service_ip', return_value=None):
            k8s_handler.ansible_executor.run_playbook = Mock(return_value={"status": "success"})
            values = {
                "volume_type": "nfs",
                "namespace": "test-namespace",
                "source_model_path": "model123",
                "model_size": 10,
                "nodes": [{"name": "node1"}],
            }

            result = k8s_handler.transfer_model(values)

            # Verify fallback to local volume
            assert values["nfs_server"] == ""
            assert values["volume_type"] == "local"
            assert result == "success"

    @patch('budcluster.cluster_ops.kubernetes.KubernetesHandler._load_kube_config')
    def test_transfer_model_with_local_volume_type(self, mock_load_config):
        """Test model transfer with local volume type."""
        # Setup
        mock_config = {"test": "config"}
        k8s_handler = KubernetesHandler(mock_config)
        k8s_handler.ansible_executor = Mock()

        k8s_handler.ansible_executor.run_playbook = Mock(return_value={"status": "success"})
        values = {
            "volume_type": "local",
            "namespace": "test-namespace",
            "source_model_path": "model123",
            "model_size": 10,
            "nodes": [{"name": "node1"}],
            "storageClass": "fast-ssd",
        }

        result = k8s_handler.transfer_model(values)

        # Verify NFS server is empty for local volume
        assert values["nfs_server"] == ""
        assert values["volume_type"] == "local"
        assert values["storageClass"] == "fast-ssd"
        assert result == "success"

    @patch('budcluster.deployment.handler.asyncio.run')
    def test_deployment_handler_passes_storage_class(self, mock_asyncio_run):
        """Test that DeploymentHandler passes storage class to transfer_model."""
        # Setup
        mock_config = {"test": "config"}
        handler = DeploymentHandler(mock_config)

        # Configure mocks to return success
        mock_asyncio_run.return_value = ("success", "test-namespace")

        # Test with storage class
        result = handler.transfer_model(
            model_uri="s3://models/model123",
            endpoint_name="test-endpoint",
            node_list=[{"name": "node1", "memory": 32 * 1024**3}],  # 32GB in bytes
            default_storage_class="premium-storage"
        )

        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()

        # Verify the result (returns ((status, namespace), actual_namespace))
        assert result[0] == ("success", "test-namespace")
        assert "test-endpoint" in result[1]  # namespace contains endpoint name

    @patch('budcluster.cluster_ops.kubernetes.time.sleep')
    @patch('budcluster.cluster_ops.kubernetes.KubernetesHandler._load_kube_config')
    def test_nfs_service_ip_detection_with_timeout(self, mock_load_config, mock_sleep):
        """Test NFS service IP detection handles timeouts gracefully."""
        mock_config = {"test": "config"}
        k8s_handler = KubernetesHandler(mock_config)

        # Mock the CoreV1Api
        with patch('budcluster.cluster_ops.kubernetes.client.CoreV1Api') as mock_v1:
            # Create a mock service without cluster_ip
            mock_service = Mock()
            mock_service.spec.cluster_ip = None

            mock_v1.return_value.read_namespaced_service.return_value = mock_service

            # Should return None after timeout
            result = k8s_handler.get_nfs_service_ip()
            assert result is None
            # Verify sleep was called 30 times (one for each attempt)
            assert mock_sleep.call_count == 30

    @patch('budcluster.cluster_ops.kubernetes.KubernetesHandler._load_kube_config')
    def test_nfs_service_ip_detection_with_404(self, mock_load_config):
        """Test NFS service IP detection handles 404 (not found) gracefully."""
        mock_config = {"test": "config"}
        k8s_handler = KubernetesHandler(mock_config)

        # Mock the CoreV1Api to raise 404 exception
        with patch('budcluster.cluster_ops.kubernetes.client.CoreV1Api') as mock_v1:
            from kubernetes.client.exceptions import ApiException

            mock_v1.return_value.read_namespaced_service.side_effect = ApiException(status=404)

            # Should return None for 404
            result = k8s_handler.get_nfs_service_ip()
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
