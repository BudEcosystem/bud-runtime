"""HAMI GPU metrics parser for Prometheus text format.

This module parses HAMI (HAMi GPU Device Plugin) metrics from Prometheus
text format and structures them for device enrichment in cluster_info.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from budmicroframe.commons.logging import get_logger


logger = get_logger(__name__)


def parse_prometheus_metric_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single Prometheus metric line.

    Args:
        line: Single line from Prometheus text format (e.g., "metric{label="value"} 123")

    Returns:
        Dict with metric_name, labels, and value, or None if parsing fails

    Example:
        >>> parse_prometheus_metric_line('GPUDeviceCoreAllocated{deviceidx="0"} 100')
        {'metric_name': 'GPUDeviceCoreAllocated', 'labels': {'deviceidx': '0'}, 'value': 100.0}
    """
    # Skip comments and empty lines
    if not line or line.startswith("#"):
        return None

    # Pattern: metric_name{label1="value1",label2="value2"} value
    pattern = r"([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+(.+)"
    match = re.match(pattern, line.strip())

    if not match:
        # Try pattern without labels: metric_name value
        simple_pattern = r"([a-zA-Z_:][a-zA-Z0-9_:]*)\s+(.+)"
        simple_match = re.match(simple_pattern, line.strip())
        if simple_match:
            metric_name, value_str = simple_match.groups()
            try:
                value = float(value_str)
                return {"metric_name": metric_name, "labels": {}, "value": value}
            except ValueError:
                logger.warning(f"Failed to parse value: {value_str}")
                return None
        return None

    metric_name, labels_str, value_str = match.groups()

    # Parse labels
    labels = {}
    if labels_str:
        # Pattern for label pairs: label="value"
        label_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"'
        for label_match in re.finditer(label_pattern, labels_str):
            label_key, label_value = label_match.groups()
            labels[label_key] = label_value

    # Parse value
    try:
        value = float(value_str)
    except ValueError:
        logger.warning(f"Failed to parse metric value: {value_str}")
        return None

    return {"metric_name": metric_name, "labels": labels, "value": value}


def parse_prometheus_metrics(metrics_text: str) -> Dict[str, List[Dict[str, Any]]]:
    """Parse Prometheus metrics text into structured format.

    Args:
        metrics_text: Raw Prometheus metrics in text format

    Returns:
        Dict mapping metric names to lists of metric samples

    Example:
        >>> text = '''GPUDeviceCoreAllocated{deviceidx="0"} 100
        ... GPUDeviceCoreAllocated{deviceidx="1"} 50'''
        >>> result = parse_prometheus_metrics(text)
        >>> len(result["GPUDeviceCoreAllocated"])
        2
    """
    metrics_by_name: Dict[str, List[Dict[str, Any]]] = {}

    for line in metrics_text.split("\n"):
        parsed = parse_prometheus_metric_line(line)
        if parsed:
            metric_name = parsed["metric_name"]
            if metric_name not in metrics_by_name:
                metrics_by_name[metric_name] = []
            metrics_by_name[metric_name].append({"labels": parsed["labels"], "value": parsed["value"]})

    return metrics_by_name


def parse_hami_device_metrics(metrics_text: str) -> Dict[str, Dict[str, Any]]:
    """Parse HAMI device-level metrics and structure by device UUID.

    Args:
        metrics_text: Raw HAMI metrics from Prometheus endpoint

    Returns:
        Dict keyed by device UUID containing aggregated device metrics

    Example:
        >>> metrics = parse_hami_device_metrics(hami_metrics_text)
        >>> device = metrics["GPU-69c9edee-a1d9-5458-ee0f-4d9c8f8f6faf"]
        >>> device["core_allocated_percent"]
        100.0
    """
    parsed_metrics = parse_prometheus_metrics(metrics_text)

    devices: Dict[str, Dict[str, Any]] = {}

    # Process nodeGPUOverview first to get device metadata
    for metric in parsed_metrics.get("nodeGPUOverview", []):
        labels = metric["labels"]
        device_uuid = labels.get("deviceuuid")
        if not device_uuid:
            continue

        # Initialize device entry with metadata
        devices[device_uuid] = {
            "node_name": labels.get("nodeid", "unknown"),
            "device_index": int(labels.get("deviceidx", 0)),
            "device_type": labels.get("devicetype", "unknown"),
            "device_uuid": device_uuid,
            # Memory limit from nodeGPUOverview (in MiB, convert to GB)
            "total_memory_gb": float(labels.get("devicememorylimit", 0)) / 1024.0,
            "total_cores_percent": 100.0,  # HAMI uses percentage (0-100)
            # Will be populated from other metrics
            "core_allocated_percent": 0.0,
            "memory_allocated_gb": 0.0,
            "shared_containers_count": 0,
            "hardware_mode": "time-slicing",  # HAMI uses time-slicing
            "last_metrics_update": datetime.utcnow().isoformat(),
        }

    # Process GPUDeviceCoreAllocated
    for metric in parsed_metrics.get("GPUDeviceCoreAllocated", []):
        device_uuid = metric["labels"].get("deviceuuid")
        if device_uuid and device_uuid in devices:
            devices[device_uuid]["core_allocated_percent"] = metric["value"]

    # Process GPUDeviceMemoryAllocated (in bytes, convert to GB)
    for metric in parsed_metrics.get("GPUDeviceMemoryAllocated", []):
        device_uuid = metric["labels"].get("deviceuuid")
        if device_uuid and device_uuid in devices:
            memory_bytes = metric["value"]
            devices[device_uuid]["memory_allocated_gb"] = memory_bytes / (1024**3)

    # Process GPUDeviceSharedNum
    for metric in parsed_metrics.get("GPUDeviceSharedNum", []):
        device_uuid = metric["labels"].get("deviceuuid")
        if device_uuid and device_uuid in devices:
            devices[device_uuid]["shared_containers_count"] = int(metric["value"])

    # Calculate utilization percentages
    for _device_uuid, device_data in devices.items():
        # Core utilization (HAMI core_allocated is already a percentage)
        device_data["core_utilization_percent"] = device_data["core_allocated_percent"]

        # Memory utilization percentage
        if device_data["total_memory_gb"] > 0:
            memory_util = (device_data["memory_allocated_gb"] / device_data["total_memory_gb"]) * 100.0
            device_data["memory_utilization_percent"] = min(100.0, memory_util)
        else:
            device_data["memory_utilization_percent"] = 0.0

    logger.info(f"Parsed HAMI metrics for {len(devices)} GPU devices")
    return devices


def create_per_device_gpus_from_hami(
    base_device: Dict[str, Any], hami_metrics: Dict[str, Dict[str, Any]], node_name: str
) -> List[Dict[str, Any]]:
    """Create individual GPU device objects from HAMI metrics.

    This function replaces the aggregated GPU object (count=N) with N individual
    GPU objects, each enriched with its own HAMI metrics.

    Args:
        base_device: Base device dict from hardware detection (aggregated)
        hami_metrics: Parsed HAMI metrics keyed by device UUID
        node_name: Name of the node this device belongs to

    Returns:
        List of individual GPU device dicts, one per physical GPU with HAMI data

    Example:
        >>> base = {"type": "cuda", "name": "NVIDIA A100", "count": 2}
        >>> devices = create_per_device_gpus_from_hami(base, hami_data, "worker-1")
        >>> len(devices)
        2
        >>> devices[0]["device_uuid"]
        "GPU-8febcc2c..."
        >>> devices[1]["device_uuid"]
        "GPU-a1b2c3d4..."
    """
    per_device_gpus = []

    # Find all HAMI devices on this node
    node_hami_devices = [(uuid, data) for uuid, data in hami_metrics.items() if data["node_name"] == node_name]

    if not node_hami_devices:
        logger.debug(f"No HAMI metrics found for node {node_name}, returning single aggregated device")
        # No HAMI data - return original aggregated device
        return [base_device]

    logger.info(f"Creating {len(node_hami_devices)} individual GPU objects from HAMI data on node {node_name}")

    # Create one device object per HAMI device
    for device_uuid, hami_data in sorted(node_hami_devices, key=lambda x: x[1]["device_index"]):
        # Create a copy of the base device for this individual GPU
        individual_gpu = base_device.copy()

        # Override count to 1 (this is now a single physical GPU)
        individual_gpu["count"] = 1
        individual_gpu["total_count"] = 1
        individual_gpu["available_count"] = 1  # Will be calculated based on utilization

        # Add HAMI-specific fields
        individual_gpu["device_index"] = hami_data.get("device_index", 0)
        individual_gpu["device_uuid"] = hami_data.get("device_uuid", "")
        individual_gpu["core_utilization_percent"] = hami_data.get("core_utilization_percent", 0.0)
        individual_gpu["memory_utilization_percent"] = hami_data.get("memory_utilization_percent", 0.0)
        individual_gpu["memory_allocated_gb"] = hami_data.get("memory_allocated_gb", 0.0)
        individual_gpu["cores_allocated_percent"] = hami_data.get("core_allocated_percent", 0.0)
        individual_gpu["shared_containers_count"] = hami_data.get("shared_containers_count", 0)
        individual_gpu["hardware_mode"] = hami_data.get("hardware_mode", "time-slicing")
        individual_gpu["last_metrics_update"] = hami_data.get("last_metrics_update", "")

        # Update total memory from HAMI if available
        if "total_memory_gb" in hami_data and hami_data["total_memory_gb"] > 0:
            individual_gpu["memory_gb"] = hami_data["total_memory_gb"]
            individual_gpu["mem_per_GPU_in_GB"] = hami_data["total_memory_gb"]

        logger.debug(
            f"Created GPU device {device_uuid} (index {hami_data['device_index']}) "
            f"with {individual_gpu['core_utilization_percent']:.1f}% core util"
        )

        per_device_gpus.append(individual_gpu)

    return per_device_gpus
