"""Node information collection service using Python Kubernetes client.

This service replaces the Ansible-based node info collection,
providing better performance and lower memory usage.
"""

import contextlib
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

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

    try:
        # Create Kubernetes client from kubeconfig dict
        api_client = _create_k8s_client_from_dict(kubeconfig_dict)
        v1 = client.CoreV1Api(api_client)

        # List all nodes
        logger.debug("Listing all nodes")
        nodes = v1.list_node()

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

        # Parse each node
        node_info_list = []
        for node in nodes.items:
            try:
                node_info = NFDLabelParser.parse_node_info(node)

                # Format devices as JSON string (for compatibility with existing code)
                devices = _format_devices(node_info)
                node_info["devices"] = json.dumps(devices)

                node_info_list.append(node_info)
                logger.debug(f"Parsed node: {node_info['node_name']}")
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
        Kubernetes API client
    """
    # Write kubeconfig to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(kubeconfig_dict, f)
        kubeconfig_path = f.name

    try:
        # Load kubeconfig from file
        config.load_kube_config(config_file=kubeconfig_path)
        return client.ApiClient()
    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(kubeconfig_path)


def _format_devices(node_info: Dict[str, Any]) -> Dict[str, Any]:
    """Format device information for compatibility with existing code.

    Args:
        node_info: Parsed node information

    Returns:
        Formatted devices dictionary
    """
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

    # Format CPU information
    if cpu_info.get("cpu_name"):
        devices["cpus"].append(
            {
                "name": cpu_info.get("cpu_name", ""),
                "model": cpu_info.get("cpu_model_raw", ""),
                "vendor": cpu_info.get("cpu_vendor", ""),
                "architecture": cpu_info.get("architecture", ""),
                "cores": cpu_info.get("cores", 0),
                "threads": cpu_info.get("threads", 0),
            }
        )

    return devices


def _parse_memory_string(memory_str: str) -> float:
    """Parse memory string (e.g., '16384MiB') to GB.

    Args:
        memory_str: Memory string

    Returns:
        Memory in GB
    """
    if not memory_str:
        return 0.0

    try:
        # Remove units and convert
        if "MiB" in memory_str:
            return float(memory_str.replace("MiB", "")) / 1024
        elif "GiB" in memory_str:
            return float(memory_str.replace("GiB", ""))
        elif "GB" in memory_str:
            return float(memory_str.replace("GB", ""))
        else:
            return float(memory_str) / 1024  # Assume MiB
    except (ValueError, TypeError):
        return 0.0
