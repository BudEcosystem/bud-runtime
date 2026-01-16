import json
import os
import tempfile
from typing import Dict, List, Optional

import aiohttp
from agents import RunContextWrapper, function_tool
from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.dapr_service import DaprServiceCrypto

from ..agent.schemas import SessionContext
from ..commons.config import app_settings


logger = get_logger(__name__)


@function_tool
async def list_clusters(
    run_ctx: RunContextWrapper[SessionContext],  # <- wrapper, not raw ctx
) -> List[str]:
    """Return names of all clusters the user can choose from."""
    result: List[str] = await run_ctx.context.registry.list_clusters()
    return result


@function_tool
def set_active_cluster(
    run_ctx: RunContextWrapper[SessionContext],
    name: str,
) -> str:
    """Set the active cluster which will be used for kubectl commands."""
    ctx = run_ctx.context
    cluster_id = ctx.registry.get_cluster_id(name)
    if not cluster_id:
        raise ValueError(f"Cluster '{name}' does not exist.")
    ctx.active_cluster = cluster_id
    return f"Cluster '{name}' selected."


class ClusterRegistry:
    def __init__(self) -> None:
        """Initialize the ClusterRegistry.

        Creates an empty list to store cluster information. This list will be populated
        with cluster data when list_clusters() is called, containing dictionaries with
        cluster details such as name and cluster_id.
        """
        self.clusters: List[Dict[str, str]] = []

    def get_cluster_id(self, cluster_name: str) -> Optional[str]:
        """Get the cluster ID for a given cluster name.

        Args:
            cluster_name: The name of the cluster to look up.

        Returns:
            The cluster ID if found, None otherwise.
        """
        for cluster in self.clusters:
            if cluster_name in cluster["name"]:
                return cluster["cluster_id"]
        return None

    async def list_clusters(self) -> List[str]:
        """Retrieve a list of all available clusters.

        This method fetches cluster information from the backend service,
        updates the internal clusters list, and returns the names of all
        available clusters.

        Returns:
            List[str]: A list of cluster names that the user can select from.
        """
        self.clusters = await self._perform_get_clusters_request()
        logger.debug(f"Clusters: {self.clusters}")
        return [c["name"] for c in self.clusters]

    async def _perform_get_clusters_request(self) -> List[Dict[str, str]]:
        get_clusters_endpoint = f"{app_settings.dapr_base_url}v1.0/invoke/{app_settings.bud_app_id}/method/clusters"
        params = {}
        system_user_id = os.getenv("SYSTEM_USER_ID")
        if system_user_id:
            params["user_id"] = system_user_id
        headers = {}
        dapr_token = os.getenv("APP_API_TOKEN")
        if dapr_token:
            headers["dapr-api-token"] = dapr_token

        try:
            logger.debug(f"Performing get clusters request. endpoint: {get_clusters_endpoint}")
            async with (
                aiohttp.ClientSession() as session,
                session.get(get_clusters_endpoint, params=params or None, headers=headers or None) as response,
            ):
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    logger.error(f"Failed to get clusters: {response.status} {response_data}")
                    return []

                logger.debug("Successfully updated endpoint status")
                clusters: List[Dict[str, str]] = response_data["clusters"]
                return clusters
        except Exception as e:
            logger.exception(f"Failed to send update endpoint status request: {e}")
            return []

    async def get_cluster_config(self, cluster_id: str) -> str:
        """Retrieve and prepare the Kubernetes configuration for a specific cluster.

        This method fetches the cluster configuration from the backend service,
        decrypts it using the DaprServiceCrypto, and saves it to a temporary file.
        If the configuration file already exists, it returns the path without
        fetching it again.

        Args:
            cluster_id: The unique identifier of the cluster.

        Returns:
            str: The path to the kubeconfig file that can be used with kubectl.
        """
        # Create the expected file path first
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"cluster_config_{cluster_id}.json")

        # Check if the file already exists
        if os.path.exists(file_path):
            logger.debug(f"Using existing cluster configuration from {file_path}")
            return file_path

        # If not, fetch and save the configuration
        cluster_details = await self._perform_get_cluster_config_request(cluster_id)

        with DaprServiceCrypto() as dapr_service:
            configuration_decrypted = dapr_service.decrypt_data(cluster_details["configuration"])

        # Save the configuration to the file
        config_data = json.loads(configuration_decrypted)

        # Add insecure-skip-tls-verify to all clusters to fix TLS certificate issues
        # Also remove conflicting certificate fields to avoid kubectl errors
        if "clusters" in config_data and isinstance(config_data["clusters"], list):
            for cluster in config_data["clusters"]:
                if "cluster" in cluster and isinstance(cluster["cluster"], dict):
                    cluster["cluster"]["insecure-skip-tls-verify"] = True
                    # Remove conflicting certificate fields when using insecure mode
                    cluster["cluster"].pop("certificate-authority", None)
                    cluster["cluster"].pop("certificate-authority-data", None)
                    cluster["cluster"].pop("tls-server-name", None)
                    logger.debug(
                        f"Added insecure-skip-tls-verify and removed cert fields for cluster: {cluster.get('name', 'unknown')}"
                    )

        with open(file_path, "w") as f:
            json.dump(config_data, f, indent=2)

        logger.debug(f"Saved cluster configuration to {file_path}")
        return file_path

    async def _perform_get_cluster_config_request(self, cluster_id: str) -> Dict[str, str]:
        get_clusters_endpoint = f"{app_settings.dapr_base_url}v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster/{cluster_id}/get-config"

        try:
            logger.debug(f"Performing get clusters request. endpoint: {get_clusters_endpoint}")
            async with aiohttp.ClientSession() as session, session.get(get_clusters_endpoint) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    logger.error(f"Failed to get clusters: {response.status} {response_data}")
                    raise ValueError(f"Failed to get clusters: {response.status} {response_data}")

                logger.debug("Successfully updated endpoint status")
                # Explicitly cast the return value to Dict[str, str] to satisfy mypy
                cluster_details: Dict[str, str] = response_data["param"]["cluster_details"]
                return cluster_details
        except Exception as e:
            logger.exception(f"Failed to send update endpoint status request: {e}")
            raise ValueError(f"Failed to get clusters: {e}") from e
