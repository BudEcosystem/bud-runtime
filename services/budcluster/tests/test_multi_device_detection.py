"""Tests for multi-device detection in NFD integration."""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID

from budcluster.cluster_ops.services import ClusterOpsService
from budcluster.cluster_ops.nfd_handler import NFDSchedulableResourceDetector
from budcluster.cluster_ops.device_extractor import DeviceExtractor


class TestMultiDeviceDetection:
    """Test suite for nodes with multiple device types."""

    @pytest.fixture
    def mock_nfd_labels_cpu_gpu(self):
        """Mock NFD labels for a node with both CPU and GPU."""
        return {
            # CPU labels
            "feature.node.kubernetes.io/cpu-model.vendor_id": "AMD",
            "feature.node.kubernetes.io/cpu-model.family": "23",
            "feature.node.kubernetes.io/cpu-model.id": "49",
            "kubernetes.io/arch": "amd64",
            "feature.node.kubernetes.io/cpu-cpuid.AVX": "true",
            "feature.node.kubernetes.io/cpu-cpuid.AVX2": "true",

            # GPU labels (NVIDIA)
            "nvidia.com/gpu.present": "true",
            "nvidia.com/gpu.count": "8",
            "nvidia.com/gpu.product": "NVIDIA-A100-SXM4-80GB",
            "nvidia.com/gpu.memory": "81251",
            "nvidia.com/cuda.runtime.major": "12",
            "nvidia.com/cuda.runtime.minor": "4",
            "nvidia.com/gpu.compute.major": "8",
            "nvidia.com/gpu.compute.minor": "0",
        }

    @pytest.fixture
    def mock_nfd_labels_cpu_hpu(self):
        """Mock NFD labels for a node with both CPU and HPU."""
        return {
            # CPU labels
            "feature.node.kubernetes.io/cpu-model.vendor_id": "Intel",
            "feature.node.kubernetes.io/cpu-model.family": "6",
            "feature.node.kubernetes.io/cpu-model.id": "143",
            "kubernetes.io/arch": "amd64",
            "feature.node.kubernetes.io/cpu-cpuid.AVX512F": "true",

            # HPU labels (Intel Gaudi)
            "intel.com/intel_gaudi": "8",
            "intel.com/gaudi-driver-version": "1.12.0",
            "feature.node.kubernetes.io/kernel.loadedmodule.habana": "true",
        }

    @pytest.fixture
    def mock_nfd_labels_all_devices(self):
        """Mock NFD labels for a node with CPU, GPU, and HPU."""
        return {
            # CPU labels
            "feature.node.kubernetes.io/cpu-model.vendor_id": "Intel",
            "feature.node.kubernetes.io/cpu-model.family": "6",
            "feature.node.kubernetes.io/cpu-model.id": "106",
            "kubernetes.io/arch": "amd64",

            # GPU labels
            "nvidia.com/gpu.present": "true",
            "nvidia.com/gpu.count": "4",
            "nvidia.com/gpu.product": "Tesla-V100-PCIE-32GB",

            # HPU labels
            "intel.com/intel_gaudi": "2",
        }

    def test_extract_cpu_gpu_devices(self, mock_nfd_labels_cpu_gpu):
        """Test extraction of both CPU and GPU devices from NFD labels."""
        extractor = DeviceExtractor()
        node_info = {"labels": mock_nfd_labels_cpu_gpu}

        devices = extractor.extract_from_node_info(node_info)

        # Should have both CPUs and GPUs
        assert "cpus" in devices
        assert "gpus" in devices
        assert "hpus" in devices

        # Check CPU extraction
        assert len(devices["cpus"]) > 0
        cpu = devices["cpus"][0]
        assert "AMD" in cpu["raw_name"]
        assert cpu["vendor"] == "AMD"
        assert cpu["architecture"] == "amd64"
        assert cpu["family"] == "Family 23"
        assert cpu["model"] == "Model 49"

        # Check GPU extraction
        assert len(devices["gpus"]) > 0
        gpu = devices["gpus"][0]
        assert gpu["raw_name"] == "NVIDIA-A100-SXM4-80GB"
        assert gpu["count"] == 8
        assert gpu["memory_gb"] == 80  # 81251 MB = ~80 GB
        assert gpu["cuda_version"] == "12.4"

        # Check we have both device types
        assert len(devices["cpus"]) > 0
        assert len(devices["gpus"]) > 0

    def test_extract_cpu_hpu_devices(self, mock_nfd_labels_cpu_hpu):
        """Test extraction of both CPU and HPU devices from NFD labels."""
        extractor = DeviceExtractor()
        node_info = {"labels": mock_nfd_labels_cpu_hpu}

        devices = extractor.extract_from_node_info(node_info)

        # Should have both CPUs and HPUs
        assert "cpus" in devices
        assert "hpus" in devices

        # Check CPU extraction
        assert len(devices["cpus"]) > 0
        cpu = devices["cpus"][0]
        assert "Intel" in cpu["raw_name"]
        assert cpu["vendor"] == "Intel"
        assert cpu["family"] == "Family 6"
        assert cpu["model"] == "Model 143"

        # Check HPU extraction
        assert len(devices["hpus"]) > 0
        # HPU detection needs work based on NFD labels

    def test_extract_all_device_types(self, mock_nfd_labels_all_devices):
        """Test extraction of CPU, GPU, and HPU devices from NFD labels."""
        extractor = DeviceExtractor()
        node_info = {"labels": mock_nfd_labels_all_devices}

        devices = extractor.extract_from_node_info(node_info)

        # Should have all three device types
        assert "cpus" in devices
        assert "gpus" in devices
        assert "hpus" in devices

        # Verify each type has devices
        assert len(devices["cpus"]) > 0
        assert len(devices["gpus"]) > 0
        assert len(devices["hpus"]) > 0

        # Check device details
        assert "Intel" in devices["cpus"][0]["raw_name"]
        assert devices["gpus"][0]["count"] == 4
        assert devices["hpus"][0]["count"] == 2

    def test_determine_primary_device_type_structured(self):
        """Test primary device type determination with structured format."""
        # Test with GPUs present
        devices_with_gpu = {
            "gpus": [{"type": "cuda"}],
            "cpus": [{"type": "cpu"}],
            "hpus": [],
            "legacy_devices": [
                {"type": "cuda", "name": "A100"},
                {"type": "cpu", "name": "EPYC"}
            ]
        }

        device_type = ClusterOpsService._determine_primary_device_type(devices_with_gpu)
        assert device_type == "cuda"

        # Test with HPUs but no GPUs
        devices_with_hpu = {
            "gpus": [],
            "cpus": [{"type": "cpu"}],
            "hpus": [{"type": "hpu"}],
            "legacy_devices": [
                {"type": "hpu", "name": "Gaudi"},
                {"type": "cpu", "name": "Xeon"}
            ]
        }

        device_type = ClusterOpsService._determine_primary_device_type(devices_with_hpu)
        assert device_type == "hpu"

        # Test with only CPUs
        devices_cpu_only = {
            "gpus": [],
            "cpus": [{"type": "cpu"}],
            "hpus": [],
            "legacy_devices": [
                {"type": "cpu", "name": "Xeon"}
            ]
        }

        device_type = ClusterOpsService._determine_primary_device_type(devices_cpu_only)
        assert device_type == "cpu"

    def test_determine_primary_device_type_legacy(self):
        """Test primary device type determination with legacy list format."""
        # Test with GPUs present
        devices_with_gpu = [
            {"type": "cuda", "name": "A100"},
            {"type": "cpu", "name": "EPYC"}
        ]

        device_type = ClusterOpsService._determine_primary_device_type(devices_with_gpu)
        assert device_type == "cuda"

        # Test with HPUs but no GPUs
        devices_with_hpu = [
            {"type": "hpu", "name": "Gaudi"},
            {"type": "cpu", "name": "Xeon"}
        ]

        device_type = ClusterOpsService._determine_primary_device_type(devices_with_hpu)
        assert device_type == "hpu"

    def test_convert_nfd_to_hardware_info_multiple_devices(self):
        """Test conversion of NFD data with multiple devices to hardware info format."""
        node_info = {
            "devices": {
                "gpus": [],
                "cpus": [],
                "hpus": [],
                "legacy_devices": [
                    {
                        "name": "NVIDIA_A100_SXM4_80GB",
                        "type": "cuda",
                        "mem_per_gpu_in_gb": 80,
                        "available_count": 8,
                        "total_count": 8,
                        "cuda_version": "12.4",
                        "compute_capability": "8.0"
                    },
                    {
                        "name": "AMD EPYC 7V12 64-Core Processor",
                        "type": "cpu",
                        "cores": 64,
                        "available_count": 1,
                        "total_count": 1,
                        "features": ["AVX", "AVX2"],
                    }
                ]
            }
        }

        hardware_info = ClusterOpsService._convert_nfd_to_hardware_info(node_info)

        # Should have both devices
        assert len(hardware_info) == 2

        # Find GPU and CPU devices
        gpu_info = next((h for h in hardware_info if h["device_config"]["type"] == "cuda"), None)
        cpu_info = next((h for h in hardware_info if h["device_config"]["type"] == "cpu"), None)

        assert gpu_info is not None
        assert cpu_info is not None

        # Check GPU details
        assert gpu_info["device_config"]["name"] == "NVIDIA_A100_SXM4_80GB"
        assert gpu_info["device_config"]["mem_per_gpu_in_gb"] == 80
        assert gpu_info["available_count"] == 8
        assert gpu_info["cuda_version"] == "12.4"

        # Check CPU details
        assert "AMD EPYC" in cpu_info["device_config"]["name"]
        assert cpu_info["device_config"]["cores"] == 64
        assert cpu_info["available_count"] == 1
        assert "AVX" in cpu_info["features"]

    def test_extract_helpers_with_structured_format(self):
        """Test helper methods with structured device format."""
        node_info = {
            "devices": {
                "cpus": [
                    {
                        "type": "cpu",
                        "cores": 32,
                        "threads_per_core": 2
                    }
                ],
                "gpus": [],
                "hpus": [],
                "legacy_devices": []
            }
        }

        # Test thread extraction
        threads = ClusterOpsService._extract_threads_per_core(node_info)
        assert threads == 2

        # Test core extraction
        cores = ClusterOpsService._extract_core_count(node_info)
        assert cores == 32

    def test_extract_helpers_with_legacy_format(self):
        """Test helper methods with legacy device format."""
        node_info = {
            "devices": [
                {
                    "type": "cpu",
                    "cores": 16,
                    "threads_per_core": 4
                },
                {
                    "type": "cuda",
                    "name": "A100"
                }
            ]
        }

        # Test thread extraction
        threads = ClusterOpsService._extract_threads_per_core(node_info)
        assert threads == 4

        # Test core extraction
        cores = ClusterOpsService._extract_core_count(node_info)
        assert cores == 16

    def test_cpu_fallback_detection(self):
        """Test CPU detection with various fallback scenarios."""
        extractor = DeviceExtractor()

        # Test with minimal labels
        minimal_labels = {
            "kubernetes.io/arch": "amd64"
        }

        node_info = {"labels": minimal_labels}
        devices = extractor.extract_from_node_info(node_info)

        # Should still detect a CPU
        assert len(devices["cpus"]) > 0
        cpu = devices["cpus"][0]
        assert cpu.architecture == "amd64"
        assert "CPU" in cpu.raw_name  # Should have generic CPU name

        # Test with vendor but no model
        vendor_only_labels = {
            "feature.node.kubernetes.io/cpu-model.vendor_id": "Intel",
            "kubernetes.io/arch": "x86_64"
        }

        node_info = {"labels": vendor_only_labels}
        devices = extractor.extract_from_node_info(node_info)

        assert len(devices["cpus"]) > 0
        cpu = devices["cpus"][0]
        assert "Intel" in cpu["raw_name"]
        assert cpu["vendor"] == "Intel"
