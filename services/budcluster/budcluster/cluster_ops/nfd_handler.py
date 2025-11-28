"""NFD-based schedulable resource detection handler."""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from budmicroframe.commons.logging import get_logger
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ..commons.exceptions import KubernetesException
from .device_extractor import DeviceExtractor


logger = get_logger(__name__)


class NFDSchedulableResourceDetector:
    """Enhanced schedulable resource detection using NFD + Kubernetes APIs."""

    def __init__(self, kube_config: Dict):
        """Initialize NFD resource detector with Kubernetes config."""
        self.kube_config = kube_config
        self._load_kube_config()
        self.device_extractor = DeviceExtractor()

    def _load_kube_config(self) -> None:
        """Load kubernetes config from dict."""
        try:
            config.load_kube_config_from_dict(self.kube_config)
            # Get the default configuration
            configuration = client.Configuration.get_default_copy()
            # Disable SSL cert validation if needed
            configuration.verify_ssl = True  # Configure based on your needs
            client.Configuration.set_default(configuration)
        except config.ConfigException as err:
            logger.error(f"Error loading Kubernetes config: {err}")
            raise KubernetesException("Invalid Kubernetes config") from err

    async def get_schedulable_nodes(self) -> List[Dict[str, Any]]:
        """Get nodes with schedulability and device info from NFD labels."""
        try:
            v1 = client.CoreV1Api()

            # Get all nodes with their labels and status
            nodes = v1.list_node()
            schedulable_nodes = []

            logger.info(f"Processing {len(nodes.items)} nodes for schedulability")

            for node in nodes.items:
                node_info = await self._process_node_with_nfd(node)
                if node_info:
                    schedulable_nodes.append(node_info)

            logger.info(f"Found {len(schedulable_nodes)} schedulable nodes")
            return schedulable_nodes

        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")
            raise KubernetesException(f"Failed to list nodes: {e}") from e
        except Exception as e:
            logger.error(f"Error getting schedulable nodes: {e}")
            raise KubernetesException(f"Node detection failed: {e}") from e

    async def _process_node_with_nfd(self, node) -> Optional[Dict[str, Any]]:
        """Process individual node for schedulability and devices."""
        node_name = node.metadata.name
        labels = node.metadata.labels or {}

        logger.debug(f"Processing node: {node_name}")

        # Check node schedulability
        schedulability_info = self._get_node_schedulability(node)

        # Get node capacity for CPU/memory info
        capacity = {}
        if node.status and node.status.capacity:
            capacity = {
                "cpu": node.status.capacity.get("cpu"),
                "memory": node.status.capacity.get("memory"),
                "nvidia.com/gpu": node.status.capacity.get("nvidia.com/gpu"),
                "amd.com/gpu": node.status.capacity.get("amd.com/gpu"),
            }

        # Extract device information from NFD labels with capacity info
        devices = self._extract_devices_from_nfd_labels(labels, node_name, capacity)

        # Only return nodes that have devices or are explicitly needed
        if not devices and not schedulability_info["ready"]:
            logger.debug(f"Skipping node {node_name}: no devices and not ready")
            return None

        return {
            "name": node_name,
            "id": self._generate_node_id(node_name),
            "status": schedulability_info["ready"],
            "devices": devices,
            "schedulability": schedulability_info,
            "capacity": capacity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_node_schedulability(self, node) -> Dict[str, Any]:
        """Get comprehensive node schedulability information."""
        ready_status = self._get_node_ready_status(node)
        is_schedulable = self._is_node_schedulable(node)
        conditions = self._get_node_conditions(node)
        taints = [self._taint_to_dict(t) for t in (node.spec.taints or [])]

        return {
            "ready": ready_status,
            "schedulable": is_schedulable,
            "unschedulable": node.spec.unschedulable or False,
            "conditions": conditions,
            "taints": taints,
            "pressure": self._get_pressure_conditions(conditions),
        }

    def _is_node_schedulable(self, node) -> bool:
        """Check if node can accept new workloads."""
        # Check if node is cordoned
        if node.spec.unschedulable:
            logger.debug(f"Node {node.metadata.name} is unschedulable (cordoned)")
            return False

        # Check node conditions
        conditions = node.status.conditions or []
        for condition in conditions:
            if condition.type == "Ready" and condition.status != "True":
                logger.debug(f"Node {node.metadata.name} is not ready")
                return False

            # Check pressure conditions
            if condition.type in ["MemoryPressure", "DiskPressure", "PIDPressure"] and condition.status == "True":
                logger.debug(f"Node {node.metadata.name} has {condition.type}")
                return False

        # Check for NoSchedule taints
        if node.spec.taints:
            for taint in node.spec.taints:
                if taint.effect == "NoSchedule":
                    logger.debug(f"Node {node.metadata.name} has NoSchedule taint: {taint.key}")
                    return False

        return True

    def _get_node_ready_status(self, node) -> bool:
        """Get node ready status."""
        conditions = node.status.conditions or []
        for condition in conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False

    def _get_node_conditions(self, node) -> List[Dict[str, Any]]:
        """Get node conditions."""
        conditions = []
        for condition in node.status.conditions or []:
            conditions.append(
                {
                    "type": condition.type,
                    "status": condition.status,
                    "reason": condition.reason,
                    "message": condition.message,
                    "last_transition_time": condition.last_transition_time.isoformat()
                    if condition.last_transition_time
                    else None,
                }
            )
        return conditions

    def _get_pressure_conditions(self, conditions: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Extract pressure conditions."""
        pressure = {"memory": False, "disk": False, "pid": False}

        for condition in conditions:
            if condition["type"] == "MemoryPressure" and condition["status"] == "True":
                pressure["memory"] = True
            elif condition["type"] == "DiskPressure" and condition["status"] == "True":
                pressure["disk"] = True
            elif condition["type"] == "PIDPressure" and condition["status"] == "True":
                pressure["pid"] = True

        return pressure

    def _taint_to_dict(self, taint) -> Dict[str, Any]:
        """Convert Kubernetes taint to dict."""
        return {
            "key": taint.key,
            "value": taint.value,
            "effect": taint.effect,
            "time_added": taint.time_added.isoformat() if taint.time_added else None,
        }

    def _generate_node_id(self, node_name: str) -> str:
        """Generate consistent node ID."""
        # Use name-based UUID for consistency
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"node.{node_name}"))

    def _extract_devices_from_nfd_labels(
        self, labels: Dict[str, str], node_name: str, capacity: Dict[str, Any] = None
    ) -> Dict[str, List[Dict]]:
        """Extract device configs from NFD labels using DeviceExtractor."""
        devices = {"gpus": [], "cpus": [], "hpus": []}

        try:
            # Use DeviceExtractor to get structured device info with capacity
            node_info = {"labels": labels, "capacity": capacity or {}}
            extracted_devices = self.device_extractor.extract_from_node_info(node_info)

            # Merge with existing format for backward compatibility
            devices.update(extracted_devices)

            # Also keep legacy format for backward compatibility if needed
            # GPU devices from NFD/GFD
            gpu_devices = self._extract_gpu_devices(labels, node_name)

            # CPU devices from NFD
            cpu_devices = self._extract_cpu_devices(labels, node_name)

            # HPU devices from NFD (Intel Gaudi)
            hpu_devices = self._extract_hpu_devices(labels, node_name)

            # Add legacy format data as "legacy_devices" for compatibility
            devices["legacy_devices"] = gpu_devices + cpu_devices + hpu_devices

        except Exception as e:
            logger.error(f"Error extracting devices for node {node_name}: {e}")

        return devices

    def _extract_gpu_devices(self, labels: Dict[str, str], node_name: str) -> List[Dict]:
        """Extract GPU device info from NVIDIA GFD labels."""
        devices = []

        try:
            # Check if node has GPUs
            gpu_count = int(labels.get("nvidia.com/gpu.count", "0"))
            if gpu_count == 0:
                return devices

            # Extract GPU specifications
            gpu_product = labels.get("nvidia.com/gpu.product", "Unknown-GPU")
            gpu_memory = int(labels.get("nvidia.com/gpu.memory", "0"))  # MB
            cuda_major = labels.get("nvidia.com/cuda.driver.major", "0")
            cuda_minor = labels.get("nvidia.com/cuda.driver.minor", "0")
            compute_major = labels.get("nvidia.com/gpu.compute.major", "0")
            compute_minor = labels.get("nvidia.com/gpu.compute.minor", "0")

            # Get available (unallocated) GPU count
            available_count = self._get_available_gpu_count(node_name, gpu_count)

            device_config = {
                "name": self._normalize_gpu_name(gpu_product),
                "type": "cuda",
                "mem_per_gpu_in_gb": gpu_memory / 1024,  # Convert MB to GB
                "available_count": available_count,
                "total_count": gpu_count,
                "product_name": gpu_product,
                "cuda_version": f"{cuda_major}.{cuda_minor}",
                "compute_capability": f"{compute_major}.{compute_minor}",
                "schedulable": available_count > 0,
                # Enhanced NFD information
                "driver_support": self._check_gpu_driver_support(labels),
                "kernel_modules": self._get_gpu_kernel_modules(labels),
            }

            devices.append(device_config)
            logger.debug(
                f"Found GPU device on {node_name}: {device_config['name']}, available: {available_count}/{gpu_count}"
            )

        except Exception as e:
            logger.error(f"Error extracting GPU devices for {node_name}: {e}")

        return devices

    def _extract_cpu_devices(self, labels: Dict[str, str], node_name: str) -> List[Dict]:
        """Extract CPU device info from NFD labels."""
        devices = []

        try:
            # Get CPU information from NFD
            cpu_model = labels.get("feature.node.kubernetes.io/cpu-model", "Unknown-CPU")

            # Get available and utilized resources
            resources = self._get_resource_utilization(node_name)
            total_cores = resources["total_cpu_cores"]
            available_cores = resources["available_cpu_cores"]
            utilized_cores = resources["allocated_cpu_cores"]
            utilized_memory_gb = resources["allocated_memory_gb"]

            if total_cores == 0:
                return devices

            # Detect CPU instruction set extensions
            cpu_features = self._extract_cpu_features(labels)

            # Determine device type based on Vendor and AMX/AVX2 support
            vendor_id = labels.get("feature.node.kubernetes.io/cpu-model.vendor_id", "unknown")
            # NFD returns "GenuineIntel" for Intel CPUs, not "Intel"
            is_intel = vendor_id in ("GenuineIntel", "Intel")
            has_high_perf_features = "AMX" in cpu_features or "AVX2" in cpu_features

            device_type = "cpu_high" if is_intel and has_high_perf_features else "cpu"

            # Calculate physical cores based on hyperthreading
            has_hyperthreading = labels.get("feature.node.kubernetes.io/cpu-hardware_multithreading") == "true"
            physical_cores = total_cores // 2 if has_hyperthreading and total_cores > 0 else total_cores

            device_config = {
                "name": self._normalize_cpu_name(cpu_model),
                "type": device_type,
                "physical_cores": physical_cores,
                "cores": total_cores,  # Actual capacity for utilization comparison
                "available_count": available_cores,
                "total_count": total_cores,
                "product_name": cpu_model,
                "features": cpu_features,  # AVX512, VNNI, etc.
                "schedulable": available_cores > 0,
                # Enhanced NFD information
                "kernel_support": self._get_cpu_kernel_support(labels),
                "architecture": labels.get("kubernetes.io/arch", "unknown"),
                "utilized_cores": utilized_cores,
                "utilized_memory_gb": utilized_memory_gb,
            }

            devices.append(device_config)
            logger.debug(
                f"Found CPU device on {node_name}: {device_config['name']}, available: {available_cores}/{total_cores} cores"
            )

        except Exception as e:
            logger.error(f"Error extracting CPU devices for {node_name}: {e}")

        return devices

    def _extract_hpu_devices(self, labels: Dict[str, str], node_name: str) -> List[Dict]:
        """Extract HPU device info from Intel device plugin labels."""
        devices = []

        try:
            # Check for Intel Gaudi HPUs
            hpu_count = int(labels.get("intel.com/intel_gaudi", "0"))
            if hpu_count == 0:
                return devices

            # Get available HPU count
            available_count = self._get_available_hpu_count(node_name, hpu_count)

            device_config = {
                "name": "gaudi2",  # Assuming Gaudi2 for now
                "type": "hpu",
                "available_count": available_count,
                "total_count": hpu_count,
                "product_name": "Intel Gaudi",
                "schedulable": available_count > 0,
                # Enhanced information
                "driver_support": self._check_hpu_driver_support(labels),
                "kernel_modules": self._get_hpu_kernel_modules(labels),
            }

            devices.append(device_config)
            logger.debug(f"Found HPU device on {node_name}: available {available_count}/{hpu_count}")

        except Exception as e:
            logger.error(f"Error extracting HPU devices for {node_name}: {e}")

        return devices

    def _get_available_gpu_count(self, node_name: str, total_gpus: int) -> int:
        """Calculate available (unallocated) GPUs on node."""
        try:
            v1 = client.CoreV1Api()

            # Get all pods on this node
            field_selector = f"spec.nodeName={node_name}"
            pods = v1.list_pod_for_all_namespaces(field_selector=field_selector)

            allocated_gpus = 0
            for pod in pods.items:
                if pod.status.phase in ["Running", "Pending"]:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            gpu_request = container.resources.requests.get("nvidia.com/gpu", "0")
                            allocated_gpus += int(gpu_request)

            available = max(0, total_gpus - allocated_gpus)
            logger.debug(f"Node {node_name}: {available}/{total_gpus} GPUs available")
            return available

        except Exception as e:
            logger.warning(f"Failed to calculate available GPU count for {node_name}: {e}")
            return total_gpus  # Fallback to total if calculation fails

    def _get_resource_utilization(self, node_name: str) -> Dict[str, Any]:
        """Get total, available, and utilized resources (CPU/Memory)."""
        result = {
            "total_cpu_cores": 0,
            "available_cpu_cores": 0,
            "allocated_cpu_cores": 0.0,
            "allocated_memory_gb": 0.0,
        }
        
        try:
            v1 = client.CoreV1Api()

            # Get node allocatable resources
            node = v1.read_node(node_name)
            allocatable_cpu = node.status.allocatable.get("cpu", "0")
            total_cpu_millicores = self._parse_cpu_resource(allocatable_cpu)

            # Get allocated resources from all pods
            field_selector = f"spec.nodeName={node_name}"
            pods = v1.list_pod_for_all_namespaces(field_selector=field_selector)

            allocated_cpu_millicores = 0
            allocated_memory_bytes = 0.0
            
            for pod in pods.items:
                if pod.status.phase in ["Running", "Pending"]:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            # CPU
                            cpu_request = container.resources.requests.get("cpu", "0")
                            allocated_cpu_millicores += self._parse_cpu_resource(cpu_request)
                            
                            # Memory
                            memory_request = container.resources.requests.get("memory", "0")
                            allocated_memory_bytes += self._parse_memory_resource(memory_request)

            available_millicores = max(0, total_cpu_millicores - allocated_cpu_millicores)

            result["total_cpu_cores"] = total_cpu_millicores // 1000
            result["available_cpu_cores"] = available_millicores // 1000
            result["allocated_cpu_cores"] = allocated_cpu_millicores / 1000.0
            result["allocated_memory_gb"] = allocated_memory_bytes / (1024**3)

            logger.debug(f"Node {node_name}: {result['available_cpu_cores']}/{result['total_cpu_cores']} CPU cores available")
            return result

        except Exception as e:
            logger.warning(f"Failed to get resource utilization for {node_name}: {e}")
            # Fallback to defaults
            result["total_cpu_cores"] = 1
            result["available_cpu_cores"] = 1
            return result

    def _get_available_hpu_count(self, node_name: str, total_hpus: int) -> int:
        """Calculate available HPUs."""
        try:
            v1 = client.CoreV1Api()

            field_selector = f"spec.nodeName={node_name}"
            pods = v1.list_pod_for_all_namespaces(field_selector=field_selector)

            allocated_hpus = 0
            for pod in pods.items:
                if pod.status.phase in ["Running", "Pending"]:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            hpu_request = container.resources.requests.get("intel.com/intel_gaudi", "0")
                            allocated_hpus += int(hpu_request)

            return max(0, total_hpus - allocated_hpus)

        except Exception:
            return total_hpus

    def _parse_cpu_resource(self, cpu_str: str) -> int:
        """Parse Kubernetes CPU resource string to millicores."""
        if not cpu_str:
            return 0
        if cpu_str.endswith("m"):
            return int(cpu_str[:-1])
        else:
            return int(float(cpu_str) * 1000)

    def _parse_memory_resource(self, memory_str: str) -> float:
        """Parse Kubernetes memory resource string to bytes."""
        if not memory_str:
            return 0.0
            
        try:
            if "Ki" in memory_str:
                return float(memory_str.replace("Ki", "")) * 1024
            elif "Mi" in memory_str:
                return float(memory_str.replace("Mi", "")) * 1024 * 1024
            elif "Gi" in memory_str:
                return float(memory_str.replace("Gi", "")) * 1024 * 1024 * 1024
            elif "Ti" in memory_str:
                return float(memory_str.replace("Ti", "")) * 1024 * 1024 * 1024 * 1024
            elif "m" in memory_str:  # millibytes? unlikely but possible in k8s resource math
                return float(memory_str.replace("m", "")) / 1000
            else:
                return float(memory_str)
        except (ValueError, TypeError):
            return 0.0

    def _extract_cpu_features(self, labels: Dict[str, str]) -> List[str]:
        """Extract CPU instruction set features from NFD labels."""
        features = []

        # Check for common CPU features
        feature_map = {
            "feature.node.kubernetes.io/cpu-cpuid.AVX": "AVX",
            "feature.node.kubernetes.io/cpu-cpuid.AVX2": "AVX2",
            "feature.node.kubernetes.io/cpu-cpuid.AVX512F": "AVX512F",
            "feature.node.kubernetes.io/cpu-cpuid.VNNI": "VNNI",
            "feature.node.kubernetes.io/cpu-cpuid.AMX": "AMX",
            "feature.node.kubernetes.io/cpu-cpuid.FMA": "FMA",
            "feature.node.kubernetes.io/cpu-cpuid.SSE4_2": "SSE4.2",
            "feature.node.kubernetes.io/cpu-cpuid.AES": "AES",
        }

        for label, feature in feature_map.items():
            if labels.get(label) == "true":
                features.append(feature)

        return features

    def _normalize_gpu_name(self, product_name: str) -> str:
        """Normalize GPU product name to standard format."""
        # Convert "NVIDIA-A100-SXM4-40GB" -> "A100"
        if "A100" in product_name:
            return "A100"
        elif "H100" in product_name:
            return "H100"
        elif "V100" in product_name:
            return "V100"
        elif "RTX" in product_name:
            # Extract RTX model
            match = re.search(r"RTX\s*(\d+)", product_name)
            if match:
                return f"RTX{match.group(1)}"

        # Fallback: try to extract model number
        match = re.search(r"([A-Z]+\d+)", product_name.upper())
        if match:
            return match.group(1)

        return "Unknown_GPU"

    def _normalize_cpu_name(self, cpu_model: str) -> str:
        """Normalize CPU model name."""
        if "Xeon" in cpu_model:
            return "Xeon"
        elif "EPYC" in cpu_model:
            return "EPYC"
        elif "Core" in cpu_model:
            return "Core"
        else:
            return "CPU"

    def _check_gpu_driver_support(self, labels: Dict[str, str]) -> Dict[str, Any]:
        """Check GPU driver support information."""
        return {
            "cuda_driver": labels.get("nvidia.com/cuda.driver.major", "")
            + "."
            + labels.get("nvidia.com/cuda.driver.minor", ""),
            "cuda_runtime": labels.get("nvidia.com/cuda.runtime.major", "")
            + "."
            + labels.get("nvidia.com/cuda.runtime.minor", ""),
            "driver_ready": labels.get("nvidia.com/gpu.present", "false") == "true",
        }

    def _get_gpu_kernel_modules(self, labels: Dict[str, str]) -> List[str]:
        """Get loaded GPU kernel modules."""
        modules = []

        # Check for NVIDIA kernel modules from NFD
        nvidia_labels = [
            key for key in labels if key.startswith("feature.node.kubernetes.io/kernel.loadedmodule.nvidia")
        ]
        for label in nvidia_labels:
            if labels.get(label) == "true":
                module = label.split(".")[-1]
                modules.append(module)

        return modules

    def _get_cpu_kernel_support(self, labels: Dict[str, str]) -> Dict[str, Any]:
        """Get CPU kernel support information."""
        return {
            "kernel_version": labels.get("feature.node.kubernetes.io/kernel.version", "unknown"),
            "os_release": labels.get("feature.node.kubernetes.io/system-os_release.ID", "unknown"),
            "architecture": labels.get("kubernetes.io/arch", "unknown"),
        }

    def _check_hpu_driver_support(self, labels: Dict[str, str]) -> Dict[str, Any]:
        """Check HPU driver support."""
        return {
            "intel_gaudi_present": labels.get("intel.com/intel_gaudi", "0") != "0",
            "driver_version": labels.get("intel.com/gaudi-driver-version", "unknown"),
        }

    def _get_hpu_kernel_modules(self, labels: Dict[str, str]) -> List[str]:
        """Get HPU kernel modules."""
        modules = []

        # Check for Intel Gaudi kernel modules
        intel_labels = [
            key for key in labels if key.startswith("feature.node.kubernetes.io/kernel.loadedmodule.habana")
        ]
        for label in intel_labels:
            if labels.get(label) == "true":
                module = label.split(".")[-1]
                modules.append(module)

        return modules
