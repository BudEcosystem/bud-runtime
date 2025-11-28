"""Node information collection service using Python Kubernetes client.

This service replaces the Ansible-based node info collection,
providing better performance and lower memory usage.
"""

import asyncio
import contextlib
import json
import logging
import os
import tempfile
from collections import defaultdict
from typing import Any, Dict, List, Optional

import urllib3.exceptions
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .nfd_parser import NFDLabelParser


logger = logging.getLogger(__name__)


async def get_node_info_python(
    kubeconfig_dict: Dict[str, Any], platform: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get node information using Python Kubernetes client.

    This function replaces the Ansible-based get_node_info function.

    Args:
        kubeconfig_dict: Kubeconfig as a dictionary
        platform: Cluster platform (optional)

    Returns:
        List of node information dictionaries

    Raises:
        Exception: If NFD is not available or API call fails
    """
    logger.info("Collecting node info using Python Kubernetes client")

    api_client = None
    try:
        # Create Kubernetes client from kubeconfig dict
        api_client = _create_k8s_client_from_dict(kubeconfig_dict)
        v1 = client.CoreV1Api(api_client)

        # List all nodes - run in thread pool to avoid blocking event loop
        logger.debug("Listing all nodes")
        try:
            # Use asyncio.to_thread to run blocking API call in thread pool
            nodes = await asyncio.to_thread(v1.list_node)
        except Exception as e:
            # Handle connection timeouts and other network errors
            if isinstance(e.__cause__, (urllib3.exceptions.ConnectTimeoutError, urllib3.exceptions.ReadTimeoutError)):
                logger.error(f"Connection timeout while listing nodes: {e}")
                raise Exception(f"Connection timeout - cluster may be unreachable: {e}") from e
            raise

        if not nodes.items:
            logger.warning("No nodes found in cluster")
            return []

        # Check if NFD is available
        nfd_available = False
        for node in nodes.items:
            if NFDLabelParser.check_nfd_available(node.metadata.labels or {}):
                nfd_available = True
                break

        if not nfd_available:
            raise Exception(
                "Node Feature Discovery (NFD) is not installed on this cluster. "
                "Please install NFD for hardware detection and node information gathering."
            )

        # List all pods to calculate utilization
        logger.debug("Listing all pods for resource utilization calculation")
        pods = v1.list_pod_for_all_namespaces(field_selector="status.phase=Running")
        
        # Calculate utilization per node
        node_utilization = defaultdict(lambda: {"cpu": 0.0, "memory": 0.0})
        for pod in pods.items:
            node_name = pod.spec.node_name
            if not node_name:
                continue
                
            for container in pod.spec.containers:
                resources = container.resources
                if not resources or not resources.requests:
                    continue
                    
                # Aggregate CPU requests
                if "cpu" in resources.requests:
                    node_utilization[node_name]["cpu"] += _parse_cpu_string(resources.requests["cpu"])
                    
                # Aggregate Memory requests
                if "memory" in resources.requests:
                    node_utilization[node_name]["memory"] += _parse_memory_string(resources.requests["memory"])

        # Parse each node
        node_info_list = []
        for node in nodes.items:
            try:
                node_info = NFDLabelParser.parse_node_info(node)
                node_name = node_info["node_name"]

                # Check if node is a master/control-plane node
                node_labels = node.metadata.labels or {}
                is_master = (
                    "node-role.kubernetes.io/master" in node_labels
                    or "node-role.kubernetes.io/control-plane" in node_labels
                )
                node_info["is_master"] = is_master
                if is_master:
                    logger.debug(f"Node {node_name} identified as master/control-plane")

                # Format devices as JSON string (for compatibility with existing code)
                # Pass utilization data for this node
                utilization = node_utilization.get(node_name, {"cpu": 0.0, "memory": 0.0})
                devices = _format_devices(node_info, utilization)
                node_info["devices"] = json.dumps(devices)

                node_info_list.append(node_info)
                logger.debug(f"Parsed node: {node_info}")
            except Exception as e:
                logger.error(f"Failed to parse node {node.metadata.name}: {e}")
                continue

        logger.info(f"Successfully collected info for {len(node_info_list)} nodes")
        return node_info_list

    except ApiException as e:
        logger.error(f"Kubernetes API error: {e}")
        raise Exception(f"Failed to query Kubernetes API: {e}") from e
    except Exception as e:
        logger.error(f"Error collecting node info: {e}")
        raise
    finally:
        if api_client:
            api_client.close()


def _create_k8s_client_from_dict(kubeconfig_dict: Dict[str, Any]) -> client.ApiClient:
    """Create Kubernetes API client from kubeconfig dictionary.

    Args:
        kubeconfig_dict: Kubeconfig as a dictionary

    Returns:
        Kubernetes API client with timeout configured
    """
    # Write kubeconfig to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(kubeconfig_dict, f)
        kubeconfig_path = f.name

    try:
        # Create a new Configuration object
        configuration = client.Configuration()

        # Load kubeconfig into this specific configuration
        config.load_kube_config(config_file=kubeconfig_path, client_configuration=configuration)

        # Set connection timeout to prevent indefinite blocking
        # This prevents the event loop from hanging when clusters are unreachable
        configuration.connection_pool_maxsize = 10
        # CRITICAL: Set socket timeout (not just connection timeout)
        # This is a tuple: (connect_timeout, read_timeout) in seconds
        configuration.timeout = (30, 30)  # 30 seconds for connect and read

        # Create API client with this configuration
        api_client = client.ApiClient(configuration)

        return api_client
    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(kubeconfig_path)


def _format_devices(node_info: Dict[str, Any], utilization: Dict[str, float] = None) -> Dict[str, Any]:
    """Format device information for compatibility with existing code.

    Args:
        node_info: Parsed node information
        utilization: Dictionary containing 'cpu' and 'memory' utilization (requests)

    Returns:
        Formatted devices dictionary
    """
    if utilization is None:
        utilization = {"cpu": 0.0, "memory": 0.0}
    devices = {"gpus": [], "cpus": []}

    gpu_info = node_info.get("gpu_info", {})
    cpu_info = node_info.get("cpu_info", {})

    # Format GPU information
    if gpu_info.get("nvidia_present"):
        gpu_count = gpu_info.get("nvidia_gpus", 1)
        for _ in range(gpu_count):
            gpu_device = {
                "vendor": "NVIDIA",
                "model": gpu_info.get("gpu_product", ""),
                "raw_name": gpu_info.get("gpu_product", ""),
                "memory_gb": _parse_memory_string(gpu_info.get("gpu_memory", "")),
                "pci_vendor_id": gpu_info.get("pci_vendor_id", ""),
                "pci_device_id": gpu_info.get("pci_device_id", ""),
                "cuda_version": gpu_info.get("cuda_version", ""),
                "compute_capability": gpu_info.get("compute_capability", ""),
                "count": 1,
            }
            devices["gpus"].append(gpu_device)

    elif gpu_info.get("amd_present"):
        devices["gpus"].append(
            {
                "vendor": "AMD",
                "model": "AMD GPU",
                "raw_name": "AMD GPU",
                "memory_gb": 0,
                "count": 1,
            }
        )

    elif gpu_info.get("intel_hpu_present"):
        devices["gpus"].append(
            {
                "vendor": "Intel",
                "model": "Intel Gaudi",
                "raw_name": "Intel Gaudi HPU",
                "memory_gb": 0,
                "count": 1,
            }
        )

    # Format CPU information with type classification
    if cpu_info.get("cpu_name"):
        # Get labels for instruction set detection
        labels = node_info.get("labels", {})
        cpu_vendor = cpu_info.get("cpu_vendor", "")
        cpu_type = "cpu"  # Default type

        # Extract instruction sets from NFD labels
        INSTRUCTION_SET_MAP = {
            "AVX": ["feature.node.kubernetes.io/cpu-cpuid.AVX"],
            "AVX2": ["feature.node.kubernetes.io/cpu-cpuid.AVX2"],
            "AVX512": ["feature.node.kubernetes.io/cpu-cpuid.AVX512F"],
            "VNNI": ["feature.node.kubernetes.io/cpu-cpuid.VNNI"],
            "AMX": ["feature.node.kubernetes.io/cpu-cpuid.AMXTILE", "feature.node.kubernetes.io/cpu-cpuid.AMX"],
            "AMX-BF16": ["feature.node.kubernetes.io/cpu-cpuid.AMXBF16"],
            "AMX-INT8": ["feature.node.kubernetes.io/cpu-cpuid.AMXINT8"],
            "FMA3": ["feature.node.kubernetes.io/cpu-cpuid.FMA3"],
            "SSE4.2": ["feature.node.kubernetes.io/cpu-cpuid.SSE4.2", "feature.node.kubernetes.io/cpu-cpuid.SSE42"],
        }

        instruction_sets = [
            name
            for name, nfd_labels in INSTRUCTION_SET_MAP.items()
            if any(labels.get(label) == "true" for label in nfd_labels)
        ]

        # Check for Intel CPUs with high-performance features (AMX or AVX2)
        if cpu_vendor == "Intel":
            has_amx = any(s.startswith("AMX") for s in instruction_sets)
            has_avx2 = "AVX2" in instruction_sets

            if has_amx or has_avx2:
                cpu_type = "cpu_high"
        
        # Extract system memory from capacity
        capacity = node_info.get("capacity", {})
        memory_gb = _parse_memory_string(capacity.get("memory", ""))
        
        # Extract cores from capacity if not available from NFD labels
        cores = cpu_info.get("cores", 0)
        threads = cpu_info.get("threads", 0)
        if cores == 0 and "cpu" in capacity:
            # Capacity CPU is in string format like "48"
            cores = int(capacity.get("cpu", "0"))
            # If hyperthreading info not available, assume threads = cores
            if threads == 0:
                threads = cores

        # Get cores and threads from node capacity
        capacity = node_info.get("capacity", {})
        cpu_capacity_str = capacity.get("cpu", "0")
        try:
            cpu_cores = int(cpu_capacity_str)
        except (ValueError, TypeError):
            cpu_cores = 0

        # Check if hyperthreading is enabled
        has_hyperthreading = labels.get("feature.node.kubernetes.io/cpu-hardware_multithreading") == "true"
        if has_hyperthreading and cpu_cores > 0:
            # If hyperthreading is enabled, capacity shows threads, not cores
            # Physical cores = threads / 2
            cpu_threads = cpu_cores
            cpu_cores = cpu_cores // 2
        else:
            # No hyperthreading, cores == threads
            cpu_threads = cpu_cores

        # Determine generation from model ID for Intel CPUs
        generation = ""
        if cpu_vendor == "Intel":
            model_id = cpu_info.get("cpu_model_id", "")
            family_id = cpu_info.get("cpu_family", "")
            try:
                model_int = int(model_id) if model_id else 0
                family_int = int(family_id) if family_id else 0

                INTEL_GEN_MAP = {
                    # --- Xeon 6 generation ---
                    # Granite Rapids: P-core Xeon 6
                    (173, 174): "Xeon 6 (Granite Rapids, P-core)",

                    # Sierra Forest: E-core Xeon 6
                    (175,): "Xeon 6 (Sierra Forest, E-core)",

                    # --- 5th Gen Xeon Scalable ---
                    # Emerald Rapids
                    (207,): "5th Gen Xeon Scalable (Emerald Rapids)",

                    # --- 4th Gen Xeon Scalable ---
                    # Sapphire Rapids
                    (143,): "4th Gen Xeon Scalable (Sapphire Rapids)",

                    # --- 3rd Gen Xeon Scalable ---
                    # Ice Lake SP + Ice Lake DE
                    (106, 108): "3rd Gen Xeon Scalable (Ice Lake)",

                    # --- 1st & 2nd Gen Xeon Scalable (+ Cooper) ---
                    # Skylake-SP, Cascade Lake, Cooper Lake all share model 85
                    (85,): "Skylake/Cascade/Cooper (1st/2nd Gen Xeon Scalable)",

                    # --- Pre-Scalable server parts ---
                    # Broadwell server: classic EP/EX plus DE/Hewitt Lake
                    (79, 86): "Broadwell (Server)",

                    # Haswell server
                    (63,): "Haswell (Server)",

                    # Optional older gens if you still see them in the fleet:
                    # Ivy Bridge server
                    (62,): "Ivy Bridge (Server)",

                    # Sandy Bridge server
                    (45,): "Sandy Bridge (Server)",
                }

                if family_int == 6:  # Intel x86-64
                    for model_ids, gen_name in INTEL_GEN_MAP.items():
                        if model_int in model_ids:
                            generation = gen_name
                            break
            except (ValueError, TypeError):
                pass

        devices["cpus"].append(
            {
                "name": cpu_info.get("cpu_name", ""),
                "type": cpu_type,
                "model": cpu_info.get("cpu_model_raw", ""),
                "vendor": cpu_vendor,
                "family": cpu_info.get("cpu_family", ""),
                "generation": generation,
                "architecture": cpu_info.get("architecture", ""),
                "physical_cores": cpu_cores,
                "cores": cpu_threads,  # Actual capacity for utilization comparison
                "threads": cpu_threads,
                "raw_name": cpu_info.get("cpu_model_raw", "CPU") + " " + generation,
                "instruction_sets": instruction_sets,
                "memory_gb": memory_gb,  # Add system memory
                "utilized_cores": utilization.get("cpu", 0.0),
                "utilized_memory_gb": utilization.get("memory", 0.0),
            }
        )

    return devices


def _parse_memory_string(memory_str: str) -> float:
    """Parse memory string (e.g., '16384MiB', '128424816Ki') to GB.

    Args:
        memory_str: Memory string

    Returns:
        Memory in GB
    """
    if not memory_str:
        return 0.0

    try:
        # Remove units and convert
        if "Ki" in memory_str:
            # Kubernetes format (kibibytes)
            return float(memory_str.replace("Ki", "")) / (1024 * 1024)
        elif "Mi" in memory_str:
            # Kubernetes format (mebibytes)
            return float(memory_str.replace("Mi", "")) / 1024
        elif "Gi" in memory_str:
            # Kubernetes format (gibibytes)
            return float(memory_str.replace("Gi", ""))
        elif "MiB" in memory_str:
            return float(memory_str.replace("MiB", "")) / 1024
        elif "GiB" in memory_str:
            return float(memory_str.replace("GiB", ""))
        elif "GB" in memory_str:
            return float(memory_str.replace("GB", ""))
        else:
            return float(memory_str) / 1024  # Assume MiB
    except (ValueError, TypeError):
        return 0.0


def _parse_cpu_string(cpu_str: str) -> float:
    """Parse CPU string (e.g., '100m', '1') to cores.

    Args:
        cpu_str: CPU string

    Returns:
        CPU cores as float
    """
    if not cpu_str:
        return 0.0

    try:
        if cpu_str.endswith("m"):
            return float(cpu_str[:-1]) / 1000.0
        return float(cpu_str)
    except (ValueError, TypeError):
        return 0.0
