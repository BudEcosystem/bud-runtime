"""Configuration for metrics collection from clusters.

This module defines the standard Prometheus queries that are collected from each cluster.
Queries can be customized per cluster type or overridden via environment variables.
"""

import os
from typing import Dict, List


# Standard queries collected from all clusters
# These cover node, pod, container, and GPU metrics
STANDARD_QUERIES: List[str] = [
    # Node metrics
    "node_cpu_seconds_total",
    "node_memory_MemAvailable_bytes",
    "node_memory_MemTotal_bytes",
    "node_filesystem_avail_bytes",
    "node_filesystem_size_bytes",
    "node_load1",
    "node_load5",
    "node_load15",
    # Pod and container metrics
    "kube_pod_container_resource_requests",
    "kube_pod_container_resource_limits",
    "kube_pod_container_status_restarts_total",
    "kube_pod_status_phase",
    "container_cpu_usage_seconds_total",
    "container_memory_usage_bytes",
    "container_memory_working_set_bytes",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
    # Cluster metrics
    "kube_node_status_condition",
    "kube_node_status_allocatable",
    "kube_node_status_capacity",
    "kube_namespace_status_phase",
    "kube_deployment_status_replicas",
    "kube_deployment_status_replicas_available",
    "kube_deployment_status_replicas_unavailable",
    # GPU metrics (if available - will be ignored if cluster doesn't have GPUs)
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_MEM_COPY_UTIL",
    "DCGM_FI_DEV_FB_FREE",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_GPU_TEMP",
    "DCGM_FI_DEV_POWER_USAGE",
]

# Cluster type-specific queries
# Additional queries to collect based on cluster type/platform
CLUSTER_TYPE_QUERIES: Dict[str, List[str]] = {
    "eks": STANDARD_QUERIES
    + [
        # AWS-specific metrics (if needed in future)
        # "aws_cloudwatch_metric_name",
    ],
    "aks": STANDARD_QUERIES
    + [
        # Azure-specific metrics (if needed in future)
        # "azure_monitor_metric_name",
    ],
    "openshift": STANDARD_QUERIES
    + [
        # OpenShift-specific metrics (if needed in future)
        # "openshift_specific_metric",
    ],
    # Default fallback for unknown cluster types
    "default": STANDARD_QUERIES,
}


def get_queries_for_cluster_type(cluster_type: str) -> List[str]:
    """Get the list of Prometheus queries for a given cluster type.

    Args:
        cluster_type: Type of cluster (eks, aks, openshift, etc.)

    Returns:
        List of Prometheus query metric names to collect

    Example:
        >>> queries = get_queries_for_cluster_type("eks")
        >>> len(queries) > 0
        True
    """
    # Normalize cluster type to lowercase for case-insensitive matching
    cluster_type_lower = cluster_type.lower() if cluster_type else "default"

    # Return cluster-specific queries or default
    return CLUSTER_TYPE_QUERIES.get(cluster_type_lower, STANDARD_QUERIES)


# Additional query categories for fine-grained control
# Can be used to enable/disable specific metric categories

QUERY_CATEGORIES: Dict[str, List[str]] = {
    "node_resource": [
        "node_cpu_seconds_total",
        "node_memory_MemAvailable_bytes",
        "node_memory_MemTotal_bytes",
        "node_filesystem_avail_bytes",
        "node_filesystem_size_bytes",
    ],
    "node_load": [
        "node_load1",
        "node_load5",
        "node_load15",
    ],
    "pod_resource": [
        "kube_pod_container_resource_requests",
        "kube_pod_container_resource_limits",
        "kube_pod_container_status_restarts_total",
        "kube_pod_status_phase",
    ],
    "container_usage": [
        "container_cpu_usage_seconds_total",
        "container_memory_usage_bytes",
        "container_memory_working_set_bytes",
    ],
    "network": [
        "container_network_receive_bytes_total",
        "container_network_transmit_bytes_total",
    ],
    "cluster_status": [
        "kube_node_status_condition",
        "kube_node_status_allocatable",
        "kube_node_status_capacity",
        "kube_namespace_status_phase",
        "kube_deployment_status_replicas",
        "kube_deployment_status_replicas_available",
        "kube_deployment_status_replicas_unavailable",
    ],
    "gpu": [
        "DCGM_FI_DEV_GPU_UTIL",
        "DCGM_FI_DEV_MEM_COPY_UTIL",
        "DCGM_FI_DEV_FB_FREE",
        "DCGM_FI_DEV_FB_USED",
        "DCGM_FI_DEV_GPU_TEMP",
        "DCGM_FI_DEV_POWER_USAGE",
    ],
    "hami_gpu": [
        # HAMI device-level allocation metrics
        "GPUDeviceCoreAllocated",
        "GPUDeviceMemoryAllocated",
        "GPUDeviceSharedNum",
        "GPUDeviceCoreLimit",
        "GPUDeviceMemoryLimit",
        # HAMI vGPU pod-level allocation metrics
        "vGPUCoreAllocated",
        "vGPUMemoryAllocated",
        # HAMI device overview metrics
        "nodeGPUOverview",
        "nodeGPUMemoryPercentage",
    ],
}


def get_queries_by_categories(categories: List[str]) -> List[str]:
    """Get queries filtered by specific categories.

    Args:
        categories: List of category names to include

    Returns:
        Combined list of unique queries from all specified categories

    Example:
        >>> queries = get_queries_by_categories(["node_resource", "pod_resource"])
        >>> "node_cpu_seconds_total" in queries
        True
        >>> "DCGM_FI_DEV_GPU_UTIL" in queries
        False
    """
    queries = []
    for category in categories:
        if category in QUERY_CATEGORIES:
            queries.extend(QUERY_CATEGORIES[category])

    # Return unique queries preserving order
    seen = set()
    unique_queries = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append(query)

    return unique_queries


def is_hami_metrics_enabled() -> bool:
    """Check if HAMI GPU metrics collection is enabled.

    Returns:
        True if HAMI metrics are enabled, False otherwise

    Example:
        >>> is_hami_metrics_enabled()  # Returns based on env var
        True
    """
    return os.getenv("ENABLE_HAMI_METRICS", "true").lower() == "true"


def get_hami_scheduler_port() -> int:
    """Get the HAMI scheduler service port for metrics scraping.

    Returns:
        Port number for HAMI scheduler metrics endpoint (default: 31993)

    Example:
        >>> get_hami_scheduler_port()
        31993
    """
    try:
        return int(os.getenv("HAMI_SCHEDULER_PORT", "31993"))
    except ValueError:
        return 31993


def get_queries_with_hami(base_queries: List[str]) -> List[str]:
    """Get queries with HAMI metrics added if enabled.

    Args:
        base_queries: Base list of queries to extend

    Returns:
        Base queries with HAMI queries added if enabled

    Example:
        >>> queries = get_queries_with_hami(STANDARD_QUERIES)
        >>> if is_hami_metrics_enabled():
        ...     assert "GPUDeviceCoreAllocated" in queries
    """
    if is_hami_metrics_enabled():
        return base_queries + QUERY_CATEGORIES["hami_gpu"]
    return base_queries
