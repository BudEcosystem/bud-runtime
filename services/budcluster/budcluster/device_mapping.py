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

"""Device mapping registry for translating budsim device identification to Kubernetes node selectors."""

from typing import Dict, List, Optional, Tuple

from budmicroframe.commons import logging


logger = logging.get_logger(__name__)


class DeviceMappingRegistry:
    """Registry for mapping device names to Kubernetes node selector labels."""

    # NVIDIA GPU mappings from device names to NFD labels
    NVIDIA_GPU_MAPPINGS = {
        # A-series GPUs
        "A100": ["NVIDIA-A100-SXM4-80GB", "NVIDIA-A100-PCIE-40GB", "NVIDIA-A100-PCIE-80GB"],
        "A40": ["NVIDIA-A40"],
        "A30": ["NVIDIA-A30"],
        "A10": ["NVIDIA-A10"],
        "A6000": ["NVIDIA-RTX-A6000"],
        "A5000": ["NVIDIA-RTX-A5000"],
        "A4000": ["NVIDIA-RTX-A4000"],
        # H-series GPUs (Hopper)
        "H100": ["NVIDIA-H100-PCIE-80GB", "NVIDIA-H100-SXM5-80GB"],
        # V-series GPUs
        "V100": ["NVIDIA-Tesla-V100-SXM2-32GB", "NVIDIA-Tesla-V100-PCIE-32GB", "NVIDIA-Tesla-V100-SXM2-16GB"],
        # T-series GPUs
        "T4": ["NVIDIA-Tesla-T4"],
        # RTX series GPUs
        "RTX4090": ["NVIDIA-GeForce-RTX-4090"],
        "RTX4080": ["NVIDIA-GeForce-RTX-4080"],
        "RTX3090": ["NVIDIA-GeForce-RTX-3090"],
        "RTX3080": ["NVIDIA-GeForce-RTX-3080"],
        # L-series GPUs
        "L40": ["NVIDIA-L40S", "NVIDIA-L40"],
        "L4": ["NVIDIA-L4"],
    }

    # Intel HPU mappings
    INTEL_HPU_MAPPINGS = {
        "Gaudi2": ["Intel-Gaudi2"],
        "Gaudi": ["Intel-Gaudi"],
    }

    # CPU architecture mappings
    CPU_ARCH_MAPPINGS = {
        "Xeon": ["Intel-Xeon"],
        "EPYC": ["AMD-EPYC"],
        "Core": ["Intel-Core"],
    }

    @classmethod
    def get_node_selector_for_device(
        cls, device_name: str, device_type: str, device_model: Optional[str] = None, raw_name: Optional[str] = None
    ) -> Dict[str, str]:
        """Get Kubernetes node selector labels for a device.

        Args:
            device_name: Device name from budsim (e.g., "A100", "Gaudi2")
            device_type: Device type ("cpu", "cuda", "hpu")
            device_model: Optional full device model name
            raw_name: Optional raw device name from NFD labels (e.g., "Tesla-V100-PCIE-16GB")

        Returns:
            Dictionary of node selector labels
        """
        node_selector = {}

        if device_type == "cuda":
            # Prefer raw_name from NFD labels if available - this is the actual cluster GPU label
            if raw_name and raw_name.strip() and raw_name != "Unknown NVIDIA GPU":
                # Use the exact GPU product name from cluster NFD labels as-is
                # NFD already provides the correct format that matches node labels
                # No normalization needed - any modification could cause mismatches
                node_selector["nvidia.com/gpu.product"] = raw_name.strip()
                logger.info(f"Using exact GPU product name from cluster NFD: {raw_name.strip()}")
            else:
                node_selector["nvidia.com/gpu.present"] = "true"

        elif device_type == "hpu":
            hpu_products = cls._get_hpu_products(device_name, device_model)
            if hpu_products:
                # For HPU devices, use feature node labels for detection
                node_selector["feature.node.kubernetes.io/pci-8086.device-1020"] = "true"
            else:
                logger.warning(f"No HPU product mapping found for device: {device_name}")

        elif device_type in ("cpu", "cpu_high"):
            cpu_selector = cls._get_cpu_selector(device_name, device_model)
            node_selector.update(cpu_selector)

        else:
            logger.warning(f"Unknown device type: {device_type}")

        return node_selector

    @classmethod
    def _get_hpu_products(cls, device_name: str, device_model: Optional[str] = None) -> List[str]:
        """Get list of possible HPU product names for a device."""
        # First try exact device name match
        if device_name in cls.INTEL_HPU_MAPPINGS:
            return cls.INTEL_HPU_MAPPINGS[device_name]

        # Try to extract device name from model if provided
        if device_model:
            for hpu_name, products in cls.INTEL_HPU_MAPPINGS.items():
                if hpu_name.lower() in device_model.lower():
                    return products

        return []

    @classmethod
    def _get_cpu_selector(cls, device_name: str, device_model: Optional[str] = None) -> Dict[str, str]:
        """Get CPU-specific node selector labels."""
        node_selector = {}

        # For CPU devices, we typically don't need specific product matching
        # but we can add architecture-specific requirements
        if device_model:
            if "Xeon" in device_model:
                node_selector["feature.node.kubernetes.io/cpu-cpuid.vendor_id"] = "GenuineIntel"
            elif "EPYC" in device_model:
                node_selector["feature.node.kubernetes.io/cpu-cpuid.vendor_id"] = "AuthenticAMD"

        return node_selector

    @classmethod
    def get_supported_devices(cls, device_type: str) -> List[str]:
        """Get list of supported device names for a given device type."""
        if device_type == "cuda":
            return list(cls.NVIDIA_GPU_MAPPINGS.keys())
        elif device_type == "hpu":
            return list(cls.INTEL_HPU_MAPPINGS.keys())
        elif device_type in ("cpu", "cpu_high"):
            return list(cls.CPU_ARCH_MAPPINGS.keys())
        else:
            return []

    @classmethod
    def validate_device_compatibility(
        cls, device_name: str, device_type: str, device_model: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Validate if a device configuration is supported.

        Returns:
            Tuple of (is_valid, error_message)
        """
        supported_devices = cls.get_supported_devices(device_type)

        if not supported_devices:
            return False, f"Device type '{device_type}' is not supported"

        # Check exact match first
        if device_name in supported_devices:
            return True, ""

        # Check partial match
        for supported_device in supported_devices:
            if supported_device.lower() in device_name.lower() or device_name.lower() in supported_device.lower():
                return True, ""

        return (
            False,
            f"Device '{device_name}' is not supported for type '{device_type}'. Supported devices: {supported_devices}",
        )

    @classmethod
    def get_device_info_from_node_labels(cls, node_labels: Dict[str, str]) -> Dict[str, str]:
        """Extract device information from Kubernetes node labels.

        This is useful for reverse mapping from cluster nodes to device capabilities.
        """
        device_info = {
            "device_type": "cpu",  # default
            "device_name": "unknown",
            "device_model": "",
            "gpu_present": False,
            "hpu_present": False,
        }

        # Check for NVIDIA GPU
        if node_labels.get("nvidia.com/gpu.present") == "true":
            device_info["device_type"] = "cuda"
            device_info["gpu_present"] = True
            gpu_product = node_labels.get("nvidia.com/gpu.product", "")
            if gpu_product:
                device_info["device_model"] = gpu_product
                # Try to map back to device name
                for device_name, products in cls.NVIDIA_GPU_MAPPINGS.items():
                    if gpu_product in products:
                        device_info["device_name"] = device_name
                        break

        # Check for Intel HPU
        elif (
            node_labels.get("feature.node.kubernetes.io/pci-8086.device-1020") == "true"
            or node_labels.get("feature.node.kubernetes.io/pci-8086.device-1021") == "true"
            or node_labels.get("feature.node.kubernetes.io/pci-8086.device-1022") == "true"
        ):
            device_info["device_type"] = "hpu"
            device_info["hpu_present"] = True
            device_info["device_name"] = "Gaudi2"  # Default assumption for Intel HPU

        # For CPU, extract architecture info
        else:
            cpu_model = node_labels.get("feature.node.kubernetes.io/local-cpu.model", "")
            if cpu_model:
                device_info["device_model"] = cpu_model
                if "Xeon" in cpu_model:
                    device_info["device_name"] = "Xeon"
                elif "EPYC" in cpu_model:
                    device_info["device_name"] = "EPYC"
                elif "Core" in cpu_model:
                    device_info["device_name"] = "Core"

        return device_info


class ClusterDeviceValidator:
    """Validates device availability against actual cluster resources."""

    def __init__(self, kubeconfig_path: str):
        """Initialize with kubeconfig for cluster access."""
        self.kubeconfig_path = kubeconfig_path

    def validate_device_availability(
        self, device_name: str, device_type: str, required_count: int = 1
    ) -> Tuple[bool, str, List[str]]:
        """Validate if requested devices are available in the cluster.

        Returns:
            Tuple of (is_available, error_message, available_nodes)
        """
        try:
            from kubernetes import client, config

            # Load kubeconfig
            config.load_kube_config(self.kubeconfig_path)
            v1 = client.CoreV1Api()

            # Get all nodes
            nodes = v1.list_node()
            available_nodes = []

            # Get node selector for the device
            node_selector = DeviceMappingRegistry.get_node_selector_for_device(device_name, device_type)

            if not node_selector:
                return False, f"No node selector mapping found for device {device_name}", []

            # Check each node for matching labels
            for node in nodes.items:
                node_labels = node.metadata.labels or {}

                # Check if node matches all selector criteria
                matches = True
                for selector_key, selector_value in node_selector.items():
                    if node_labels.get(selector_key) != selector_value:
                        matches = False
                        break

                if matches and self._is_node_schedulable(node):
                    available_nodes.append(node.metadata.name)

            available_count = len(available_nodes)
            if available_count >= required_count:
                return True, "", available_nodes
            else:
                return (
                    False,
                    f"Required {required_count} nodes with device {device_name}, but only {available_count} available",
                    available_nodes,
                )

        except Exception as e:
            logger.exception(f"Error validating device availability: {e}")
            return False, f"Cluster validation failed: {str(e)}", []

    def _is_node_schedulable(self, node) -> bool:
        """Check if a node is schedulable (not cordoned or in bad state)."""
        # Check if node is unschedulable
        if node.spec.unschedulable:
            return False

        # Check node conditions
        conditions = node.status.conditions or []
        return all(not (condition.type == "Ready" and condition.status != "True") for condition in conditions)
