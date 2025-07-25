from typing import Any, Dict, Optional
from urllib.parse import urlparse

from budmicroframe.commons.logging import get_logger

from ..commons.constants import ClusterPlatformEnum
from .ansible import AnsibleExecutor


logger = get_logger(__name__)


async def determine_cluster_platform(config: Dict[str, Any]) -> ClusterPlatformEnum:
    """Determine the cluster platform based on the config."""
    # openshift_namespaces = [
    #     "openshift-image-registry",
    #     "openshift-machine-api",
    #     "openshift-marketplace",
    # ]
    # cluster_namespaces = [
    #     context["context"].get("namespace")
    #     for context in config.get("contexts", [])
    #     if "namespace" in context["context"]
    # ]

    # if any(namespace in cluster_namespaces for namespace in openshift_namespaces):
    #     return ClusterPlatformEnum.OPENSHIFT  # noqa: E712
    # return ClusterPlatformEnum.KUBERNETES  # noqa: E712
    # TODO: save the results in DB and reuse for next time
    ansible_executor = AnsibleExecutor()
    result = ansible_executor.run_playbook(playbook="IDENTIFY_PLATFORM", extra_vars={"kubeconfig_content": config})
    if result["status"] == "successful":
        for event in result["events"]:
            if event["task"] == "Set platform type" and event["status"] == "runner_on_ok":
                platform = event["event_data"]["res"]["ansible_facts"]["platform_type"]
        return ClusterPlatformEnum.OPENSHIFT if platform == "openshift" else ClusterPlatformEnum.KUBERNETES
    else:
        raise Exception(f"Failed to determine cluster platform: {result}")


async def get_cluster_hostname(config: Dict[str, Any], platform: ClusterPlatformEnum) -> Optional[str]:
    """Get the cluster hostname from the config."""
    try:
        server_url = config["clusters"][0]["cluster"]["server"]
        parsed_url = urlparse(server_url)
        hostname = parsed_url.hostname
        logger.debug(f"Extracted hostname from config: {hostname}")

        if platform == ClusterPlatformEnum.OPENSHIFT:
            if hostname and hostname.startswith("api."):
                return hostname.replace("api.", "apps.", 1)
            else:
                return None

        return hostname
    except (KeyError, IndexError, Exception) as e:
        logger.error(f"Failed to parse cluster hostname: {e}")
        return None


async def get_cluster_server_url(config: Dict[str, Any]) -> Optional[str]:
    """Get the cluster server url from the config."""
    try:
        server_url = config["clusters"][0]["cluster"]["server"]
        logger.debug(f"Extracted server url from config: {server_url}")
        parsed_url = urlparse(server_url)
        return parsed_url.geturl()
    except (KeyError, IndexError, Exception) as e:
        logger.error(f"Failed to parse cluster server url: {e}")
        return None
