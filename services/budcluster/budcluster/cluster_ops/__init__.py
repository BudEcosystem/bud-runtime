"""budcluster.cluster_ops package."""

import json
from typing import Any, Dict, Optional
from uuid import UUID

from budmicroframe.commons.logging import get_logger

from ..commons.constants import ClusterPlatformEnum
from ..commons.hami_parser import create_per_device_gpus_from_hami, parse_hami_device_metrics
from ..commons.metrics_config import is_hami_metrics_enabled
from ..metrics_collector.prometheus_client import PrometheusClient
from .base import BaseClusterHandler
from .kubernetes import KubernetesHandler
from .openshift import OpenshiftHandler
from .utils import determine_cluster_platform, get_cluster_hostname, get_cluster_server_url


logger = get_logger(__name__)


_CLUSTER_HANDLERS = {
    "kubernetes": KubernetesHandler,
    "openshift": OpenshiftHandler,
}


async def get_cluster_handler(
    config: Dict, ingress_url: Optional[str] = None, platform: Optional[ClusterPlatformEnum] = None
) -> BaseClusterHandler:
    """Get cluster handler."""
    if platform:
        cluster_platform = platform
    else:
        cluster_platform = await determine_cluster_platform(config)
    return _CLUSTER_HANDLERS[cluster_platform.value](config, ingress_url)


async def verify_cluster_connection(config: Dict, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Verify the connection to the cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.verify_cluster_connection()


async def initial_setup(config: Dict, cluster_id: UUID, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Execute initial setup."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.initial_setup(cluster_id)


async def get_node_info(config: Dict, platform: Optional[ClusterPlatformEnum] = None) -> Dict[str, Any]:
    """Get the node information from the Kubernetes cluster.

    This function collects node information including hardware details.

    By default, uses the Python-based implementation for better performance
    and lower memory usage.

    If HAMI GPU time-slicing is enabled, it also enriches device objects
    with real-time GPU utilization and allocation metrics.

    Args:
        config: Kubernetes configuration
        platform: Optional cluster platform type

    Returns:
        List of node information dictionaries with enriched device data
    """
    from ..node_info_collector import get_node_info_python

    logger.info("Using Python-based node info collection")
    node_data = await get_node_info_python(config, platform)

    # Enrich with HAMI metrics if enabled
    if is_hami_metrics_enabled():
        try:
            logger.info("HAMI metrics enabled - enriching device data with GPU utilization")

            # Create Prometheus client and scrape HAMI metrics
            prom_client = PrometheusClient(kubeconfig=config)
            hami_metrics_text = await prom_client.get_hami_metrics()

            if hami_metrics_text:
                # Parse HAMI metrics
                hami_device_metrics = parse_hami_device_metrics(hami_metrics_text)
                logger.info(f"Parsed HAMI metrics for {len(hami_device_metrics)} GPU devices")

                # Enrich each node's devices with HAMI data
                for node in node_data:
                    node_name = node.get("node_name")
                    if not node_name:
                        continue

                    # Parse devices JSON string
                    devices_str = node.get("devices", "{}")
                    devices = json.loads(devices_str) if isinstance(devices_str, str) else devices_str

                    # Replace aggregated GPU objects with per-device GPUs enriched with HAMI metrics
                    if devices.get("gpus"):
                        per_device_gpus = []
                        for gpu_device in devices["gpus"]:
                            # Create individual GPU objects from HAMI data
                            individual_gpus = create_per_device_gpus_from_hami(
                                gpu_device, hami_device_metrics, node_name
                            )
                            per_device_gpus.extend(individual_gpus)

                        # Replace aggregated GPU list with per-device GPU list
                        devices["gpus"] = per_device_gpus

                        # Save enriched devices back
                        node["devices"] = json.dumps(devices)
                        logger.info(
                            f"Created {len(per_device_gpus)} individual GPU device objects on node {node_name}"
                        )
            else:
                logger.info("HAMI metrics scraping returned no data - cluster may not have HAMI installed")

        except Exception as e:
            # Log error but don't fail the entire operation
            logger.warning(f"Failed to enrich devices with HAMI metrics: {e}")
            logger.warning("Continuing with standard device data without HAMI enrichment")

    return node_data


async def get_node_status(
    config: Dict, node_name: str, platform: Optional[ClusterPlatformEnum] = None
) -> Dict[str, Any]:
    """Get the status of a specific node from the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_node_status(node_name)


async def transfer_model(config: Dict, values: Dict, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Transfer the model to the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.transfer_model(values)


async def get_model_transfer_status(
    config: Dict, values: Dict, platform: Optional[ClusterPlatformEnum] = None
) -> None:
    """Get the model transfer status."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_model_transfer_status(values)


async def deploy_runtime(
    config: Dict,
    values: Dict,
    playbook: str = "DEPLOY_RUNTIME",
    platform: Optional[ClusterPlatformEnum] = None,
    delete_on_failure: bool = True,
) -> None:
    """Deploy the runtime on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, ingress_url=values["ingress_host"], platform=platform)
    return cluster_handler.deploy_runtime(values, playbook, delete_on_failure=delete_on_failure)


async def get_deployment_status(
    config: Dict,
    ingress_url: str,
    values: Dict,
    cloud_model: bool = False,
    platform: Optional[ClusterPlatformEnum] = None,
    ingress_health: bool = True,
) -> str:
    """Get the status of a deployment on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, ingress_url, platform=platform)
    return cluster_handler.get_deployment_status(values, cloud_model, ingress_health)


async def delete_namespace(config: Dict, namespace: str, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Delete the namespace on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    cluster_handler.delete_namespace(namespace)


async def delete_cluster(config: Dict, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Delete the cluster on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.delete_cluster()


async def apply_security_context(config: Dict, namespace: str, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Apply security context to the runtime containers."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.apply_security_context(namespace)


async def delete_pod(
    config: Dict, namespace: str, deployment_name: str, pod_name: str, platform: Optional[ClusterPlatformEnum] = None
) -> None:
    """Delete the pod on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.delete_pod(namespace, deployment_name, pod_name)


async def get_pod_status(
    config: Dict, namespace: str, pod_name: str, platform: Optional[ClusterPlatformEnum] = None
) -> str:
    """Get the status of a pod on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_pod_status(namespace, pod_name)


async def get_pod_logs(
    config: Dict, namespace: str, pod_name: str, platform: Optional[ClusterPlatformEnum] = None
) -> str:
    """Get the logs of a pod on the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_pod_logs(namespace, pod_name)


async def get_node_wise_events_count(config: Dict, platform: Optional[ClusterPlatformEnum] = None) -> Dict[str, int]:
    """Get the count of events for each node in the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_node_wise_events_count()


async def get_node_wise_events(
    config: Dict, node_hostname: str, platform: Optional[ClusterPlatformEnum] = None
) -> Dict[str, Any]:
    """Get node-wise events with pagination and total event count for the cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_node_wise_events(node_hostname)


async def deploy_quantization_job(config: Dict, values: Dict, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Deploy quantization job."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.deploy_quantization_job(values)


async def get_quantization_status(config: Dict, values: Dict, platform: Optional[ClusterPlatformEnum] = None) -> None:
    """Get the status of a quantization job."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_quantization_status(values)


async def get_adapter_status(config: Dict, adapter_name: str, ingress_url: str) -> None:
    """Get the status of a adapter."""
    cluster_handler = await get_cluster_handler(
        config, ingress_url=ingress_url, platform=ClusterPlatformEnum.KUBERNETES
    )
    return cluster_handler.get_adapter_status(adapter_name)


async def identify_supported_endpoints(
    config: Dict,
    namespace: str,
    cloud_model: bool = False,
    ingress_url: Optional[str] = None,
    platform: Optional[ClusterPlatformEnum] = None,
) -> Dict[str, bool]:
    """Identify which endpoints are supported by checking if they return 200 status."""
    cluster_handler = await get_cluster_handler(config, ingress_url=ingress_url, platform=platform)
    return cluster_handler.identify_supported_endpoints(namespace, cloud_model)


__all__ = [
    "determine_cluster_platform",
    "get_cluster_hostname",
    "get_cluster_handler",
    "initial_setup",
    "get_node_info",
    "get_node_status",
    "verify_cluster_connection",
    "deploy_runtime",
    "get_deployment_status",
    "delete_namespace",
    "get_cluster_server_url",
    "delete_pod",
    "get_pod_status",
    "get_node_wise_events_count",
    "get_node_wise_events",
    "deploy_quantization_job",
    "get_quantization_status",
    "get_adapter_status",
    "identify_supported_endpoints",
]
