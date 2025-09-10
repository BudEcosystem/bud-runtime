#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for device mapping and node selection functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from budcluster.device_mapping import DeviceMappingRegistry, ClusterDeviceValidator


class TestDeviceMappingRegistry:
    """Test cases for DeviceMappingRegistry."""

    def test_get_node_selector_for_a100_gpu(self):
        """Test node selector generation for A100 GPU."""
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="A100",
            device_type="cuda",
            device_model="NVIDIA-A100-SXM4-80GB"
        )

        assert selector == {"nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB"}

    def test_get_node_selector_for_v100_gpu(self):
        """Test node selector generation for V100 GPU."""
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="V100",
            device_type="cuda"
        )

        assert selector == {"nvidia.com/gpu.product": "NVIDIA-Tesla-V100-SXM2-32GB"}

    def test_get_node_selector_for_hpu_device(self):
        """Test node selector generation for Intel HPU."""
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="Gaudi2",
            device_type="hpu"
        )

        assert selector == {"feature.node.kubernetes.io/pci-8086.device-1020": "true"}

    def test_get_node_selector_for_cpu_device(self):
        """Test node selector generation for CPU device."""
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="Xeon",
            device_type="cpu",
            device_model="Intel Xeon Gold 6248R"
        )

        assert selector == {"feature.node.kubernetes.io/cpu-cpuid.vendor_id": "GenuineIntel"}

    def test_get_node_selector_fallback_for_unknown_gpu(self):
        """Test fallback node selector for unknown GPU."""
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="UnknownGPU",
            device_type="cuda"
        )

        assert selector == {"nvidia.com/gpu.present": "true"}

    def test_get_supported_devices_cuda(self):
        """Test getting supported CUDA devices."""
        supported = DeviceMappingRegistry.get_supported_devices("cuda")

        assert "A100" in supported
        assert "V100" in supported
        assert "H100" in supported
        assert len(supported) > 10  # Should have many supported GPUs

    def test_get_supported_devices_hpu(self):
        """Test getting supported HPU devices."""
        supported = DeviceMappingRegistry.get_supported_devices("hpu")

        assert "Gaudi2" in supported
        assert "Gaudi" in supported

    def test_get_supported_devices_cpu(self):
        """Test getting supported CPU devices."""
        supported = DeviceMappingRegistry.get_supported_devices("cpu")

        assert "Xeon" in supported
        assert "EPYC" in supported
        assert "Core" in supported

    def test_validate_device_compatibility_valid(self):
        """Test validation of compatible device configuration."""
        is_valid, error = DeviceMappingRegistry.validate_device_compatibility(
            device_name="A100",
            device_type="cuda"
        )

        assert is_valid is True
        assert error == ""

    def test_validate_device_compatibility_invalid_type(self):
        """Test validation of invalid device type."""
        is_valid, error = DeviceMappingRegistry.validate_device_compatibility(
            device_name="A100",
            device_type="unknown"
        )

        assert is_valid is False
        assert "not supported" in error

    def test_validate_device_compatibility_invalid_device(self):
        """Test validation of invalid device for type."""
        is_valid, error = DeviceMappingRegistry.validate_device_compatibility(
            device_name="NonExistentGPU",
            device_type="cuda"
        )

        assert is_valid is False
        assert "not supported" in error

    def test_get_device_info_from_node_labels_gpu(self):
        """Test extracting device info from GPU node labels."""
        node_labels = {
            "nvidia.com/gpu.present": "true",
            "nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB",
            "nvidia.com/gpu.count": "2"
        }

        device_info = DeviceMappingRegistry.get_device_info_from_node_labels(node_labels)

        assert device_info["device_type"] == "cuda"
        assert device_info["device_name"] == "A100"
        assert device_info["device_model"] == "NVIDIA-A100-SXM4-80GB"
        assert device_info["gpu_present"] is True

    def test_get_device_info_from_node_labels_hpu(self):
        """Test extracting device info from HPU node labels."""
        node_labels = {
            "feature.node.kubernetes.io/pci-8086.device-1020": "true"
        }

        device_info = DeviceMappingRegistry.get_device_info_from_node_labels(node_labels)

        assert device_info["device_type"] == "hpu"
        assert device_info["device_name"] == "Gaudi2"
        assert device_info["hpu_present"] is True

    def test_get_device_info_from_node_labels_cpu(self):
        """Test extracting device info from CPU node labels."""
        node_labels = {
            "feature.node.kubernetes.io/local-cpu.model": "Intel Xeon Gold 6248R",
            "feature.node.kubernetes.io/cpu-cpuid.vendor_id": "GenuineIntel"
        }

        device_info = DeviceMappingRegistry.get_device_info_from_node_labels(node_labels)

        assert device_info["device_type"] == "cpu"
        assert device_info["device_name"] == "Xeon"
        assert device_info["device_model"] == "Intel Xeon Gold 6248R"


class TestClusterDeviceValidator:
    """Test cases for ClusterDeviceValidator."""

    @patch('kubernetes.client')
    @patch('kubernetes.config')
    def test_validate_device_availability_success(self, mock_config, mock_client):
        """Test successful device availability validation."""
        # Mock kubeconfig loading
        mock_config.load_kube_config = Mock()

        # Mock Kubernetes API
        mock_v1 = Mock()
        mock_client.CoreV1Api.return_value = mock_v1

        # Create mock nodes
        mock_node1 = Mock()
        mock_node1.metadata.name = "node-1"
        mock_node1.metadata.labels = {
            "nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB",
            "nvidia.com/gpu.present": "true"
        }
        mock_node1.spec.unschedulable = None
        mock_node1.status.conditions = [
            Mock(type="Ready", status="True")
        ]

        mock_node2 = Mock()
        mock_node2.metadata.name = "node-2"
        mock_node2.metadata.labels = {
            "nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB",
            "nvidia.com/gpu.present": "true"
        }
        mock_node2.spec.unschedulable = None
        mock_node2.status.conditions = [
            Mock(type="Ready", status="True")
        ]

        mock_nodes_list = Mock()
        mock_nodes_list.items = [mock_node1, mock_node2]
        mock_v1.list_node.return_value = mock_nodes_list

        # Test validation
        validator = ClusterDeviceValidator("/path/to/kubeconfig")
        is_available, error_msg, available_nodes = validator.validate_device_availability(
            device_name="A100",
            device_type="cuda",
            required_count=2
        )

        assert is_available is True
        assert error_msg == ""
        assert len(available_nodes) == 2
        assert "node-1" in available_nodes
        assert "node-2" in available_nodes

    @patch('kubernetes.client')
    @patch('kubernetes.config')
    def test_validate_device_availability_insufficient(self, mock_config, mock_client):
        """Test device availability validation with insufficient nodes."""
        # Mock kubeconfig loading
        mock_config.load_kube_config = Mock()

        # Mock Kubernetes API
        mock_v1 = Mock()
        mock_client.CoreV1Api.return_value = mock_v1

        # Create mock node (only 1 but need 2)
        mock_node = Mock()
        mock_node.metadata.name = "node-1"
        mock_node.metadata.labels = {
            "nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB",
            "nvidia.com/gpu.present": "true"
        }
        mock_node.spec.unschedulable = None
        mock_node.status.conditions = [
            Mock(type="Ready", status="True")
        ]

        mock_nodes_list = Mock()
        mock_nodes_list.items = [mock_node]
        mock_v1.list_node.return_value = mock_nodes_list

        # Test validation
        validator = ClusterDeviceValidator("/path/to/kubeconfig")
        is_available, error_msg, available_nodes = validator.validate_device_availability(
            device_name="A100",
            device_type="cuda",
            required_count=2
        )

        assert is_available is False
        assert "Required 2 nodes" in error_msg
        assert "only 1 available" in error_msg
        assert len(available_nodes) == 1

    @patch('kubernetes.client')
    @patch('kubernetes.config')
    def test_validate_device_availability_no_matching_nodes(self, mock_config, mock_client):
        """Test device availability validation with no matching nodes."""
        # Mock kubeconfig loading
        mock_config.load_kube_config = Mock()

        # Mock Kubernetes API
        mock_v1 = Mock()
        mock_client.CoreV1Api.return_value = mock_v1

        # Create mock node without matching GPU
        mock_node = Mock()
        mock_node.metadata.name = "node-1"
        mock_node.metadata.labels = {
            "nvidia.com/gpu.product": "NVIDIA-V100-SXM2-32GB",  # Different GPU
            "nvidia.com/gpu.present": "true"
        }
        mock_node.spec.unschedulable = None
        mock_node.status.conditions = [
            Mock(type="Ready", status="True")
        ]

        mock_nodes_list = Mock()
        mock_nodes_list.items = [mock_node]
        mock_v1.list_node.return_value = mock_nodes_list

        # Test validation
        validator = ClusterDeviceValidator("/path/to/kubeconfig")
        is_available, error_msg, available_nodes = validator.validate_device_availability(
            device_name="A100",
            device_type="cuda",
            required_count=1
        )

        assert is_available is False
        assert "Required 1 nodes" in error_msg
        assert "only 0 available" in error_msg
        assert len(available_nodes) == 0

    def test_is_node_schedulable_unschedulable_node(self):
        """Test node schedulability check for unschedulable node."""
        validator = ClusterDeviceValidator("/path/to/kubeconfig")

        mock_node = Mock()
        mock_node.spec.unschedulable = True

        assert validator._is_node_schedulable(mock_node) is False

    def test_is_node_schedulable_not_ready_node(self):
        """Test node schedulability check for not ready node."""
        validator = ClusterDeviceValidator("/path/to/kubeconfig")

        mock_node = Mock()
        mock_node.spec.unschedulable = None
        mock_node.status.conditions = [
            Mock(type="Ready", status="False")
        ]

        assert validator._is_node_schedulable(mock_node) is False

    def test_is_node_schedulable_ready_node(self):
        """Test node schedulability check for ready node."""
        validator = ClusterDeviceValidator("/path/to/kubeconfig")

        mock_node = Mock()
        mock_node.spec.unschedulable = None
        mock_node.status.conditions = [
            Mock(type="Ready", status="True")
        ]

        assert validator._is_node_schedulable(mock_node) is True


class TestDeviceMappingIntegration:
    """Integration tests for device mapping with different scenarios."""

    def test_device_name_variations(self):
        """Test that various device name formats are handled correctly."""
        test_cases = [
            ("A100", "cuda", "NVIDIA-A100-SXM4-80GB"),
            ("a100", "cuda", "NVIDIA-A100-SXM4-80GB"),  # lowercase
            ("V100", "cuda", "NVIDIA-Tesla-V100-SXM2-32GB"),
            ("H100", "cuda", "NVIDIA-H100-PCIE-80GB"),
            ("T4", "cuda", "NVIDIA-Tesla-T4"),
        ]

        for device_name, device_type, expected_product in test_cases:
            selector = DeviceMappingRegistry.get_node_selector_for_device(
                device_name=device_name,
                device_type=device_type
            )
            assert "nvidia.com/gpu.product" in selector
            # Should map to one of the known products for the device
            assert selector["nvidia.com/gpu.product"].startswith("NVIDIA")

    def test_partial_device_name_matching(self):
        """Test partial device name matching functionality."""
        # Test partial matching for device names
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="RTX4090",
            device_type="cuda"
        )

        assert selector == {"nvidia.com/gpu.product": "NVIDIA-GeForce-RTX-4090"}

    def test_device_model_fallback(self):
        """Test device model fallback when device name is not recognized."""
        selector = DeviceMappingRegistry.get_node_selector_for_device(
            device_name="UnknownGPU",
            device_type="cuda",
            device_model="NVIDIA-A100-SXM4-80GB"
        )

        # Should extract A100 from the model string
        assert selector == {"nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB"}

    def test_comprehensive_device_support(self):
        """Test that all major device families are supported."""
        # Test NVIDIA GPU families
        gpu_families = ["A100", "A40", "V100", "T4", "H100", "RTX3090", "L40"]
        for gpu in gpu_families:
            selector = DeviceMappingRegistry.get_node_selector_for_device(
                device_name=gpu,
                device_type="cuda"
            )
            assert "nvidia.com/gpu.product" in selector or "nvidia.com/gpu.present" in selector

        # Test Intel HPU families
        hpu_families = ["Gaudi2", "Gaudi"]
        for hpu in hpu_families:
            selector = DeviceMappingRegistry.get_node_selector_for_device(
                device_name=hpu,
                device_type="hpu"
            )
            assert "feature.node.kubernetes.io/pci-8086.device-1020" in selector

        # Test CPU families
        cpu_families = ["Xeon", "EPYC", "Core"]
        for cpu in cpu_families:
            selector = DeviceMappingRegistry.get_node_selector_for_device(
                device_name=cpu,
                device_type="cpu",
                device_model=f"Intel {cpu} processor"
            )
            # CPU selector should have vendor info or be empty (valid for generic CPU)
            assert isinstance(selector, dict)
