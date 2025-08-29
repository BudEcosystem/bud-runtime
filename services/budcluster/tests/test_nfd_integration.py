"""Tests for NFD-based schedulable resource detection integration."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from budcluster.cluster_ops.nfd_handler import NFDSchedulableResourceDetector
from budcluster.cluster_ops.fallback_handler import ResourceDetectionFallbackHandler
from budcluster.cluster_ops.services import ClusterOpsService


class TestNFDIntegration:
    """Test NFD integration functionality."""

    @pytest.fixture
    def mock_kube_config(self):
        """Mock Kubernetes configuration."""
        return {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"cluster": {"server": "https://test-cluster"}}],
            "users": [{"user": {"token": "test-token"}}],
        }

    @pytest.fixture
    def mock_node_info(self):
        """Mock NFD node information."""
        return {
            "name": "test-node-1",
            "id": "node-uuid-1",
            "status": True,
            "devices": [
                {
                    "name": "A100",
                    "type": "cuda",
                    "available_count": 6,
                    "total_count": 8,
                    "schedulable": True,
                    "mem_per_gpu_in_gb": 40.0,
                    "product_name": "NVIDIA-A100-SXM4-40GB",
                    "cuda_version": "12.4",
                    "compute_capability": "8.0",
                }
            ],
            "schedulability": {
                "ready": True,
                "schedulable": True,
                "unschedulable": False,
                "conditions": [{"type": "Ready", "status": "True"}],
                "taints": [],
                "pressure": {"memory": False, "disk": False, "pid": False}
            },
            "timestamp": "2025-01-15T10:00:00Z"
        }

    @pytest.mark.asyncio
    async def test_nfd_detector_initialization(self, mock_kube_config):
        """Test NFD detector can be initialized with Kubernetes config."""
        with patch('budcluster.cluster_ops.nfd_handler.config.load_kube_config_from_dict'):
            detector = NFDSchedulableResourceDetector(mock_kube_config)
            assert detector.kube_config == mock_kube_config

    @pytest.mark.asyncio
    async def test_nfd_schedulable_detection(self, mock_kube_config, mock_node_info):
        """Test NFD-based schedulable node detection."""
        with patch('budcluster.cluster_ops.nfd_handler.config.load_kube_config_from_dict'), \
             patch('budcluster.cluster_ops.nfd_handler.client.CoreV1Api') as mock_api:

            # Mock Kubernetes node response
            mock_node = MagicMock()
            mock_node.metadata.name = "test-node-1"
            mock_node.metadata.labels = {
                "nvidia.com/gpu.count": "8",
                "nvidia.com/gpu.product": "NVIDIA-A100-SXM4-40GB",
                "nvidia.com/gpu.memory": "40960",
                "feature.node.kubernetes.io/cpu-cpuid.AVX512F": "true"
            }
            mock_node.spec.unschedulable = False
            mock_node.spec.taints = []
            mock_node.status.conditions = [
                MagicMock(type="Ready", status="True")
            ]

            mock_api.return_value.list_node.return_value.items = [mock_node]
            mock_api.return_value.list_pod_for_all_namespaces.return_value.items = []
            mock_api.return_value.read_node.return_value.status.allocatable = {"cpu": "16"}

            detector = NFDSchedulableResourceDetector(mock_kube_config)
            nodes = await detector.get_schedulable_nodes()

            assert len(nodes) == 1
            assert nodes[0]["name"] == "test-node-1"
            assert nodes[0]["schedulability"]["schedulable"] is True
            assert len(nodes[0]["devices"]) > 0

    @pytest.mark.asyncio
    async def test_enhanced_cluster_info_conversion(self, mock_node_info):
        """Test conversion of NFD node info to existing format."""
        hardware_info = ClusterOpsService._convert_nfd_to_hardware_info(mock_node_info)

        assert len(hardware_info) == 1
        device = hardware_info[0]

        assert device["device_config"]["name"] == "A100"
        assert device["device_config"]["type"] == "cuda"
        assert device["available_count"] == 6
        assert device["total_count"] == 8
        assert device["schedulable"] is True

    @pytest.mark.asyncio
    async def test_fallback_handler_nfd_enabled(self, mock_kube_config):
        """Test fallback handler when NFD is enabled and working."""
        mock_request = MagicMock()
        mock_request.config_dict = mock_kube_config

        with patch('budcluster.cluster_ops.fallback_handler.app_settings.enable_nfd_detection', True), \
             patch.object(ClusterOpsService, 'fetch_cluster_info_enhanced') as mock_enhanced:

            mock_enhanced.return_value = json.dumps({
                "id": "test-cluster",
                "nodes": [{"name": "test-node", "detection_method": "nfd"}],
                "enhanced": True
            })

            result = await ResourceDetectionFallbackHandler.get_cluster_info_with_fallback(
                mock_request, "task1", "workflow1"
            )

            result_data = json.loads(result)
            assert result_data["enhanced"] is True
            mock_enhanced.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_handler_configmap_fallback(self, mock_kube_config):
        """Test fallback to ConfigMap when NFD fails."""
        mock_request = MagicMock()
        mock_request.config_dict = mock_kube_config

        with patch('budcluster.cluster_ops.fallback_handler.app_settings.enable_nfd_detection', True), \
             patch('budcluster.cluster_ops.fallback_handler.app_settings.nfd_fallback_to_configmap', True), \
             patch.object(ClusterOpsService, 'fetch_cluster_info_enhanced') as mock_enhanced, \
             patch.object(ClusterOpsService, 'fetch_cluster_info') as mock_standard:

            # NFD fails
            mock_enhanced.side_effect = Exception("NFD detection failed")

            # ConfigMap succeeds
            mock_standard.return_value = json.dumps({
                "id": "test-cluster",
                "nodes": [{"name": "test-node"}]
            })

            result = await ResourceDetectionFallbackHandler.get_cluster_info_with_fallback(
                mock_request, "task1", "workflow1"
            )

            result_data = json.loads(result)
            assert result_data["detection_method"] == "configmap_fallback"
            assert result_data["enhanced"] is False
            mock_enhanced.assert_called_once()
            mock_standard.assert_called_once()

    @pytest.mark.asyncio
    async def test_detection_method_info(self):
        """Test getting detection method configuration info."""
        with patch('budcluster.cluster_ops.fallback_handler.app_settings.enable_nfd_detection', True), \
             patch('budcluster.cluster_ops.fallback_handler.app_settings.nfd_fallback_to_configmap', True):

            info = ResourceDetectionFallbackHandler.get_detection_method_info()

            assert info["nfd_enabled"] is True
            assert info["fallback_enabled"] is True
            assert info["primary_method"] == "nfd"
            assert info["fallback_method"] == "configmap"

    def test_device_type_determination(self):
        """Test primary device type determination logic."""
        # GPU cluster
        gpu_devices = [{"type": "cuda"}, {"type": "cpu"}]
        assert ClusterOpsService._determine_primary_device_type(gpu_devices) == "cuda"

        # HPU cluster
        hpu_devices = [{"type": "hpu"}, {"type": "cpu"}]
        assert ClusterOpsService._determine_primary_device_type(hpu_devices) == "hpu"

        # CPU-only cluster
        cpu_devices = [{"type": "cpu"}]
        assert ClusterOpsService._determine_primary_device_type(cpu_devices) == "cpu"

        # Empty devices
        assert ClusterOpsService._determine_primary_device_type([]) == "cpu"

    def test_gpu_name_normalization(self):
        """Test GPU product name normalization."""
        detector = NFDSchedulableResourceDetector({})

        assert detector._normalize_gpu_name("NVIDIA-A100-SXM4-40GB") == "A100"
        assert detector._normalize_gpu_name("NVIDIA-H100-PCIe-80GB") == "H100"
        assert detector._normalize_gpu_name("NVIDIA-RTX-4090") == "RTX4090"
        assert detector._normalize_gpu_name("Unknown-Device") == "Unknown_GPU"

    def test_cpu_name_normalization(self):
        """Test CPU model name normalization."""
        detector = NFDSchedulableResourceDetector({})

        assert detector._normalize_cpu_name("Intel Xeon Gold 6248R") == "Xeon"
        assert detector._normalize_cpu_name("AMD EPYC 7742") == "EPYC"
        assert detector._normalize_cpu_name("Intel Core i9-12900K") == "Core"
        assert detector._normalize_cpu_name("Unknown Processor") == "CPU"

    def test_nfd_result_validation(self):
        """Test NFD result validation logic."""
        # Valid NFD result
        valid_result = json.dumps({
            "id": "cluster-id",
            "nodes": [
                {
                    "name": "node1",
                    "detection_method": "nfd",
                    "schedulable": True
                }
            ]
        })
        assert ResourceDetectionFallbackHandler._is_valid_nfd_result(valid_result) is True

        # Invalid result - missing required fields
        invalid_result = json.dumps({"nodes": []})
        assert ResourceDetectionFallbackHandler._is_valid_nfd_result(invalid_result) is False

        # Invalid result - no enhanced info
        basic_result = json.dumps({
            "id": "cluster-id",
            "nodes": [{"name": "node1"}]
        })
        assert ResourceDetectionFallbackHandler._is_valid_nfd_result(basic_result) is False

    @pytest.mark.asyncio
    async def test_node_schedulability_check(self):
        """Test node schedulability checking logic."""
        detector = NFDSchedulableResourceDetector({})

        # Ready and schedulable node
        ready_node = MagicMock()
        ready_node.spec.unschedulable = False
        ready_node.spec.taints = []
        ready_node.status.conditions = [
            MagicMock(type="Ready", status="True"),
            MagicMock(type="MemoryPressure", status="False")
        ]

        assert detector._is_node_schedulable(ready_node) is True

        # Cordoned node
        cordoned_node = MagicMock()
        cordoned_node.spec.unschedulable = True
        cordoned_node.spec.taints = []
        cordoned_node.status.conditions = [MagicMock(type="Ready", status="True")]

        assert detector._is_node_schedulable(cordoned_node) is False

        # Node with NoSchedule taint
        tainted_node = MagicMock()
        tainted_node.spec.unschedulable = False
        tainted_node.spec.taints = [MagicMock(effect="NoSchedule")]
        tainted_node.status.conditions = [MagicMock(type="Ready", status="True")]

        assert detector._is_node_schedulable(tainted_node) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
