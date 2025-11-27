"""NFD (Node Feature Discovery) label parser.

Parses Kubernetes node labels created by NFD to extract hardware information.
"""

from typing import Any, Dict


class NFDLabelParser:
    """Parser for Node Feature Discovery labels."""

    @staticmethod
    def parse_gpu_info(labels: Dict[str, str]) -> Dict[str, Any]:
        """Extract GPU information from NFD labels.

        Args:
            labels: Node labels dictionary

        Returns:
            Dictionary with GPU information
        """
        # NVIDIA GPU detection
        nvidia_present = (
            labels.get("nvidia.com/gpu.present") == "true"
            or labels.get("feature.node.kubernetes.io/pci-10de.present") == "true"
        )

        nvidia_gpus = int(labels.get("nvidia.com/gpu.count", "0"))

        # AMD GPU detection (PCI vendor ID 1002)
        amd_present = labels.get("feature.node.kubernetes.io/pci-1002.present") == "true"

        # Intel HPU detection (Gaudi/Habana)
        intel_hpu_present = (
            labels.get("feature.node.kubernetes.io/pci-8086.device-1020") == "true"
            or labels.get("feature.node.kubernetes.io/pci-8086.device-1021") == "true"
            or labels.get("feature.node.kubernetes.io/pci-8086.device-1022") == "true"
        )

        # CUDA version
        cuda_major = labels.get("nvidia.com/cuda.runtime.major", "")
        cuda_minor = labels.get("nvidia.com/cuda.runtime.minor", "")
        cuda_version = f"{cuda_major}.{cuda_minor}" if cuda_major and cuda_minor else cuda_major

        # Compute capability
        compute_major = labels.get("nvidia.com/gpu.compute.major", "")
        compute_minor = labels.get("nvidia.com/gpu.compute.minor", "")
        compute_capability = f"{compute_major}.{compute_minor}" if compute_major and compute_minor else compute_major

        return {
            "nvidia_present": nvidia_present,
            "nvidia_gpus": nvidia_gpus,
            "gpu_product": labels.get("nvidia.com/gpu.product", ""),
            "gpu_memory": labels.get("nvidia.com/gpu.memory", ""),
            "gpu_family": labels.get("nvidia.com/gpu.family", ""),
            "cuda_version": cuda_version,
            "compute_capability": compute_capability,
            "amd_present": amd_present,
            "intel_hpu_present": intel_hpu_present,
            "pci_vendor_id": labels.get("feature.node.kubernetes.io/pci-vendor", ""),
            "pci_device_id": labels.get("feature.node.kubernetes.io/pci-device", ""),
            "driver_version": labels.get("nvidia.com/cuda.driver.major", ""),
        }

    @staticmethod
    def parse_cpu_info(labels: Dict[str, str]) -> Dict[str, Any]:
        """Extract CPU information from NFD labels.

        Args:
            labels: Node labels dictionary

        Returns:
            Dictionary with CPU information
        """
        # Try to get CPU model from local hook first (if configured)
        cpu_model_raw = labels.get("feature.node.kubernetes.io/local-cpu.model", "")

        # Fallback to constructing from standard NFD labels
        if not cpu_model_raw:
            vendor_id = labels.get("feature.node.kubernetes.io/cpu-model.vendor_id", "")
            family = labels.get("feature.node.kubernetes.io/cpu-model.family", "")
            model_id = labels.get("feature.node.kubernetes.io/cpu-model.id", "")

            # Map vendor ID to readable name
            vendor_map = {
                "GenuineIntel": "Intel",
                "AuthenticAMD": "AMD",
            }
            vendor_name = vendor_map.get(vendor_id, vendor_id)

            if vendor_name:
                parts = [vendor_name]
                if family:
                    parts.append(f"Family {family}")
                if model_id:
                    parts.append(f"Model {model_id}")
                cpu_model_raw = " ".join(parts) + " CPU" if parts else ""

        # Determine CPU name from model string
        cpu_name = "CPU"  # Default
        if "Xeon" in cpu_model_raw:
            cpu_name = "Xeon"
        elif "EPYC" in cpu_model_raw:
            cpu_name = "EPYC"
        elif "Core" in cpu_model_raw:
            cpu_name = "Core"
        elif "Ryzen" in cpu_model_raw:
            cpu_name = "Ryzen"

        # Determine vendor from vendor_id or model string
        # NFD exposes vendor under cpuid prefix, not cpu-model prefix
        cpu_vendor = ""
        vendor_id = labels.get("feature.node.kubernetes.io/cpu-cpuid.vendor_id", "")
        if vendor_id in ["GenuineIntel", "Intel"]:
            cpu_vendor = "Intel"
        elif vendor_id in ["AuthenticAMD", "AMD"]:
            cpu_vendor = "AMD"
        elif "Intel" in cpu_model_raw or "Xeon" in cpu_model_raw or "Core" in cpu_model_raw:
            cpu_vendor = "Intel"
        elif "AMD" in cpu_model_raw or "EPYC" in cpu_model_raw or "Ryzen" in cpu_model_raw:
            cpu_vendor = "AMD"

        return {
            "architecture": labels.get("kubernetes.io/arch", ""),
            "cpu_family": labels.get("feature.node.kubernetes.io/cpu-model.family", ""),
            "cpu_model_id": labels.get("feature.node.kubernetes.io/cpu-model.id", ""),
            "cpu_model_raw": cpu_model_raw,
            "cpu_name": cpu_name,
            "cpu_vendor": cpu_vendor,
            # Cores and threads will be populated from node capacity, not from NFD labels
            "cores": 0,
            "threads": 0,
        }

    @staticmethod
    def check_nfd_available(labels: Dict[str, str]) -> bool:
        """Check if NFD labels are present.

        Args:
            labels: Node labels dictionary

        Returns:
            True if NFD labels are found
        """
        for key in labels:
            if key.startswith("feature.node.kubernetes.io/") or key.startswith("nfd.node.kubernetes.io/"):
                return True
        return False

    @staticmethod
    def parse_node_info(node: Any) -> Dict[str, Any]:
        """Parse all node information from a Kubernetes node object.

        Args:
            node: Kubernetes V1Node object

        Returns:
            Dictionary with complete node information
        """
        labels = node.metadata.labels or {}
        status = node.status

        # Parse hardware info
        gpu_info = NFDLabelParser.parse_gpu_info(labels)
        cpu_info = NFDLabelParser.parse_cpu_info(labels)

        # Get capacity and allocatable resources
        capacity = status.capacity or {}
        allocatable = status.allocatable or {}

        # Get node addresses
        addresses = []
        if status.addresses:
            for addr in status.addresses:
                addresses.append({"type": addr.type, "address": addr.address})

        # Determine node status (ready/not ready)
        node_ready = False
        if status.conditions:
            for condition in status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    node_ready = True
                    break

        return {
            "node_name": node.metadata.name,
            "node_id": node.metadata.uid,
            "node_status": node_ready,
            "gpu_info": gpu_info,
            "cpu_info": cpu_info,
            "capacity": {k: str(v) for k, v in capacity.items()},
            "allocatable": {k: str(v) for k, v in allocatable.items()},
            "addresses": addresses,
            "labels": labels,
        }
