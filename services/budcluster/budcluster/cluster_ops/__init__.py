"""budcluster.cluster_ops package."""

from typing import Any, Dict, Optional
from uuid import UUID

from ..commons.constants import ClusterPlatformEnum
from .base import BaseClusterHandler
from .kubernetes import KubernetesHandler
from .openshift import OpenshiftHandler
from .utils import determine_cluster_platform, get_cluster_hostname, get_cluster_server_url


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
    """Get the node information from the Kubernetes cluster."""
    cluster_handler = await get_cluster_handler(config, platform=platform)
    return cluster_handler.get_node_info()


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
