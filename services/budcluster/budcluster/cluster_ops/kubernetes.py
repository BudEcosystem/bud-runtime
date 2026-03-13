import asyncio
import json
import re
import subprocess
import tempfile
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Union
from urllib.parse import urlparse
from uuid import UUID

import requests
import yaml
from budmicroframe.commons.logging import get_logger
from kubernetes import client, config

from ..commons.config import app_settings
from ..commons.exceptions import KubernetesException

# from ..commons.utils import format_uptime
from ..deployment.schemas import DeploymentStatusEnum, WorkerData
from .ansible import AnsibleExecutor
from .base import BaseClusterHandler
from .schemas import PlatformEnum


logger = get_logger(__name__)


class KubernetesHandler(BaseClusterHandler):
    """Kubernetes cluster handler.

    This class provides methods to manage and interact with a Kubernetes cluster,
    including initial setup and container status retrieval.

    Attributes:
        config (Dict): Configuration dictionary for the Kubernetes cluster.
        ansible_executor (AnsibleExecutor): Ansible executor instance for running playbooks.
    """

    def __init__(self, config: Dict, ingress_url: str = None):
        """Initialize the KubernetesHandler with the given configuration.

        Args:
            config (Dict): Configuration dictionary for the Kubernetes cluster.
        """
        self.platform = PlatformEnum.KUBERNETES
        self.config = config
        self._load_kube_config()

        self.ingress_url = ingress_url

        self.ansible_executor = AnsibleExecutor()

    def _load_kube_config(self) -> None:
        """Load kubernetes config file and create instance-specific configuration."""
        try:
            # Create a new instance-specific configuration instead of using global default
            # This prevents race conditions when multiple clusters are monitored concurrently
            self.api_configuration = client.Configuration()

            # Load the kubeconfig into the instance configuration
            config.load_kube_config_from_dict(self.config, client_configuration=self.api_configuration)

            # Disable SSL cert validation and hostname verification
            self.api_configuration.verify_ssl = app_settings.validate_certs

            # Set connection and read timeout to prevent indefinite blocking
            # This prevents hanging when clusters are unreachable
            # Format: (connect_timeout, read_timeout) in seconds
            self.api_configuration.timeout = (30, 30)  # 30 seconds for connect and read

            # Store an API client instance for this configuration
            self.api_client = client.ApiClient(self.api_configuration)

            logger.debug("Loaded instance-specific kubernetes configuration for cluster")
        except config.ConfigException as err:
            logger.error(f"Found error while loading Kubernetes config file. {err}")
            raise KubernetesException("Invalid Kubernetes config file") from err
        except Exception as err:
            logger.error(f"Found error while loading Kubernetes config file. {err}")
            raise KubernetesException("Found error while loading Kubernetes config file") from err

    def _get_container_status(self, container_name: str, node: Dict[str, Any]) -> str:
        if "containerStatuses" in node["status"]:
            for container in node["status"]["containerStatuses"]:
                if container_name in container["name"]:
                    if "waiting" in container["state"]:
                        return container["state"]["waiting"]["reason"]
                    elif "terminated" in container["state"]:
                        return container["state"]["terminated"]["reason"]
                    elif "running" in container["state"]:
                        return "Running"
        if node["status"]["phase"] in ["Failed"]:
            return node["status"]["message"]
        return "Unknown"

    # TODO: Traefik installation
    def initial_setup(self, cluster_id: UUID) -> None:
        """Execute the initial setup for the Kubernetes cluster using Ansible playbook.

        This method runs the 'SETUP_CLUSTER' playbook to deploy NFD, GPU operators,
        Aibrix components, and gather node information.

        Raises:
            Exception: If the setup fails on any node.

        Returns:
            str: The status of the setup process.
        """
        # Setup cluster with NFD, GPU operators, and Aibrix components
        result = self.ansible_executor.run_playbook(
            playbook="SETUP_CLUSTER",  # Uses comprehensive cluster setup
            extra_vars={
                "kubeconfig_content": self.config,
                "platform": self.platform,
                "prometheus_url": f"{app_settings.prometheus_url}/api/v1/write",
                "prometheus_namespace": "bud-system",
                "cluster_name": str(cluster_id),
                "namespace": "bud-system",  # Changed to bud-system for infrastructure components
                "enable_nfd": True,  # NFD is now required
            },
        )
        if result["status"] == "failed":
            try:
                failed_task = []
                for event in result["events"]:
                    if (
                        event["status"] in ["runner_on_failed", "runner_on_unreachable"]
                        and "event_data" in event
                        and "res" in event["event_data"]
                    ):
                        # Handle pod-related failures
                        if "resources" in event["event_data"]["res"]:
                            for node in event["event_data"]["res"]["resources"]:
                                if (
                                    "status" in node
                                    and "phase" in node["status"]
                                    and node["status"]["phase"] in ["Pending", "Failed", "Unknown"]
                                ):
                                    reason = self._get_container_status("node-info-collector", node)
                                    host_ip = node.get("status", {}).get("hostIP", "unknown")
                                    failed_task.append(f"{host_ip} with reason: {reason}")
                        # Handle generic task failures
                        elif "msg" in event["event_data"]["res"]:
                            failed_task.append(event["event_data"]["res"]["msg"])

                if failed_task:
                    raise Exception(f"Cluster setup failed: {'; '.join(failed_task)}")
                else:
                    raise Exception("Cluster setup failed with unknown error")
            except Exception as err:
                raise Exception("Cluster setup failed") from err
        # TODO: remove this when we have a better way to check if the cluster configuration is ready
        import time

        time.sleep(10)
        return result["status"]

    def verify_cluster_connection(self) -> bool:
        """Verify the connection to the Kubernetes cluster.

        This method attempts to list namespaces in the cluster to verify the connection.

        Returns:
            bool: True if the connection is successful, False otherwise.

        Raises:
            KubernetesException: If there is an error while verifying the connection.
        """
        try:
            v1 = client.CoreV1Api(api_client=self.api_client)
            v1.list_namespace()
            return True
        except client.ApiException as err:
            logger.error(f"Found Kubernetes API error while verifying cluster connection. {err.reason}")
            raise KubernetesException("Found error while verifying cluster connection") from err
        except Exception as err:
            logger.error(f"Found error while verifying cluster connection {err}")
            raise KubernetesException("Found error while verifying cluster connection") from err

    def _parse_configmap_node_info(self, event: Dict[str, Any]) -> Dict[str, Any]:
        node_info = []

        for result in event["event_data"]["res"]["results"]:
            # print(result)
            for item in result["resources"]:
                configmap_data = item["data"]
                node_info.append({**configmap_data})
        return node_info

    # Fetch the IP of the NFS service
    def get_nfs_service_ip(self, service_name="nfs-service", namespace="bud-system"):
        """Get the IP address of the NFS service.

        This method attempts to retrieve the IP address of the specified NFS service
        in the given namespace. It retries up to 30 times with a 2-second interval
        between attempts.

        Args:
            service_name (str): Name of the NFS service. Defaults to "nfs-service".
            namespace (str): Namespace where the NFS service is located. Defaults to "bud-system".

        Returns:
            str: The IP address of the NFS service if found, None otherwise.
        """
        try:
            v1 = client.CoreV1Api(api_client=self.api_client)
            for attempt in range(30):  # Retry up to 30 times with a 2-second interval
                try:
                    svc = v1.read_namespaced_service(service_name, namespace)
                    if svc.spec.cluster_ip and svc.spec.cluster_ip != "None":
                        logger.info(f"Found NFS service at {svc.spec.cluster_ip}")
                        return svc.spec.cluster_ip
                    if attempt == 0:
                        logger.debug(f"NFS service {service_name} exists but no cluster IP yet, waiting...")
                except client.exceptions.ApiException as e:
                    if e.status == 404:
                        logger.debug(f"NFS service {service_name} not found in namespace {namespace}")
                        return None
                    else:
                        logger.warning(f"Error checking NFS service: {e}")
                time.sleep(2)
            logger.warning(f"NFS service {service_name} found but no cluster IP after 30 attempts")
        except Exception as e:
            logger.error(f"Failed to get IP for service {service_name}: {e}")
        return None

    def _parse_hostname(self, url: str) -> str:
        # if there's no scheme, prepend one
        if not url:
            raise ValueError("URL cannot be None or empty")
        if "://" not in url:
            url = f"http://{url}"
        return urlparse(url).netloc, urlparse(url).scheme

    def _get_gpu_allocations(self, node_name: str) -> Dict[str, int]:
        """Calculate GPU allocations for a specific node.

        Returns dict with total_gpus, allocated_gpus, and available_gpus.
        """
        try:
            # Disable SSL warnings for self-signed certs
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            v1 = client.CoreV1Api(api_client=self.api_client)

            # Get node to find total GPUs
            node = v1.read_node(node_name)
            total_gpus = 0

            if node.status and node.status.capacity:
                # Check for NVIDIA GPUs
                nvidia_gpus = node.status.capacity.get("nvidia.com/gpu", "0")
                total_gpus = int(nvidia_gpus) if nvidia_gpus else 0

                # Check for AMD GPUs
                amd_gpus = node.status.capacity.get("amd.com/gpu", "0")
                if amd_gpus:
                    total_gpus += int(amd_gpus)

            # Get pods on this node
            field_selector = f"spec.nodeName={node_name}"
            pods = v1.list_pod_for_all_namespaces(field_selector=field_selector)

            allocated_gpus = 0
            for pod in pods.items:
                # Only count Running and Pending pods
                if pod.status.phase in ["Running", "Pending"]:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            # Check NVIDIA GPUs
                            nvidia_request = container.resources.requests.get("nvidia.com/gpu", "0")
                            allocated_gpus += int(nvidia_request) if nvidia_request else 0

                            # Check AMD GPUs
                            amd_request = container.resources.requests.get("amd.com/gpu", "0")
                            allocated_gpus += int(amd_request) if amd_request else 0

            available_gpus = max(0, total_gpus - allocated_gpus)

            logger.debug(
                f"Node {node_name}: {available_gpus}/{total_gpus} GPUs available ({allocated_gpus} allocated)"
            )

            return {"total_gpus": total_gpus, "allocated_gpus": allocated_gpus, "available_gpus": available_gpus}

        except Exception as e:
            logger.warning(f"Failed to get GPU allocations for {node_name}: {e}")
            return None

    def get_node_info(self) -> List[Dict[str, Any]]:
        """Get the node information from the Kubernetes cluster using NFD labels.

        Returns:
            List[Dict[str, Any]]: A list containing node information from the Kubernetes cluster.

        Raises:
            KubernetesException: If there is an error while extracting node info.
        """
        result = self.ansible_executor.run_playbook(
            playbook="GET_NODE_INFO", extra_vars={"kubeconfig_content": self.config}
        )

        node_data = []
        if result["status"] == "successful":
            try:
                # Extract node information from NFD labels
                # First check for the output fact task
                node_info_output = None
                for event in result["events"]:
                    if event["task"] == "Set output fact for node information" and event["status"] == "runner_on_ok":
                        node_info_output = event["event_data"]["res"]["ansible_facts"].get("node_info_output", [])
                        break

                # If no output fact task, collect from individual processing tasks
                if node_info_output is None:
                    node_info_output = []
                    for event in result["events"]:
                        if (
                            event["task"] == "Process each node and extract NFD information"
                            and event["status"] == "runner_on_ok"
                            and "ansible_facts" in event["event_data"]["res"]
                        ):
                            node_info = event["event_data"]["res"]["ansible_facts"].get("node_information", [])
                            if node_info and isinstance(node_info, list) and len(node_info) > 0:
                                # Get the last item since it's accumulated
                                node_info_output = node_info

                if node_info_output:
                    # Process each node's information
                    from .device_extractor import DeviceExtractor

                    extractor = DeviceExtractor()

                    for node in node_info_output:
                        # Extract device information from node info (which includes NFD labels)
                        devices = extractor.extract_from_node_info(node)

                        # Get real GPU allocations for this node
                        node_name = node.get("node_name")
                        if node_name and devices.get("gpus"):
                            gpu_allocations = self._get_gpu_allocations(node_name)
                            if gpu_allocations:
                                # Update GPU devices with real available counts
                                for gpu in devices["gpus"]:
                                    # The total count from device extractor
                                    total_count = gpu.get("count", 1)
                                    # Use real available count from Kubernetes
                                    gpu["available_count"] = gpu_allocations["available_gpus"]
                                    gpu["total_count"] = total_count
                                    logger.debug(
                                        f"Updated GPU on {node_name}: total={total_count}, available={gpu_allocations['available_gpus']}"
                                    )

                        # Format node data for compatibility with existing structure
                        # Determine node status based on both Ready condition and schedulability
                        schedulability = node.get("schedulability", {})

                        # Convert string booleans to actual booleans (Ansible returns strings)
                        ready_value = schedulability.get("ready", False)
                        is_ready = ready_value if isinstance(ready_value, bool) else str(ready_value).lower() == "true"

                        schedulable_value = schedulability.get("schedulable", True)
                        is_schedulable = (
                            schedulable_value
                            if isinstance(schedulable_value, bool)
                            else str(schedulable_value).lower() == "true"
                        )

                        # Node is truly available only if it's both Ready and schedulable
                        node_available = is_ready and is_schedulable

                        logger.debug(
                            f"Node {node.get('node_name')}: ready={is_ready}, schedulable={is_schedulable}, available={node_available}"
                        )

                        # Extract internal IP from node addresses
                        internal_ip = None
                        addresses = node.get("addresses", [])
                        if addresses:
                            for addr in addresses:
                                if addr.get("type") == "InternalIP":
                                    internal_ip = addr.get("address")
                                    break

                        node_formatted = {
                            "node_name": node.get("node_name"),
                            "node_id": node.get("node_id"),
                            "internal_ip": internal_ip,
                            "node_status": node_available,  # Use boolean for consistency
                            "derived_status": "Ready" if node_available else "NotReady",
                            "devices": json.dumps(devices),
                            "cpu_info": node.get("cpu_info", {}),
                            "memory_info": node.get("memory_info", {}),
                            "gpu_info": node.get("gpu_info", {}),
                            "kernel_info": node.get("kernel_info", {}),
                            "capacity": node.get("capacity", {}),
                            "allocatable": node.get("allocatable", {}),
                            "labels": node.get("labels", {}),
                            "schedulability": schedulability,  # Include full schedulability info
                        }
                        node_data.append(node_formatted)

            except Exception as err:
                logger.error(f"Error while extracting node info from NFD labels: {err}")
                raise KubernetesException("Failed to extract node information from NFD labels") from err
        return node_data

    def _get_nodes_status(self, result: Dict[str, Any]) -> Dict[str, str]:
        """To creates a map of node name to node status."""
        node_status_map = {}
        try:
            for event in result["events"]:
                if event["task"] == "Get list of nodes" and event["status"] == "runner_on_ok":
                    for node in event["event_data"]["res"]["resources"]:
                        node_name = node["metadata"]["name"]
                        node_status_map[node_name] = self._derive_node_status(node)
        except Exception as err:
            logger.error(f"Error fetching node status: {err}")
            raise KubernetesException("Error fetching node status") from err

        return node_status_map

    def _derive_node_status(self, node: Dict[str, Any]) -> str:
        """To derive the final status of a node considering readiness, taints, and pressure conditions."""
        conditions = {cond["type"]: cond["status"] for cond in node.get("status", {}).get("conditions", [])}

        # Check if the node is Ready
        is_ready = conditions.get("Ready") == "True"

        # Check for unschedulable taint
        taints = node.get("spec", {}).get("taints", [])
        is_unschedulable = any(taint["key"] == "node.kubernetes.io/unschedulable" for taint in taints)

        # Check for resource pressure conditions
        has_pressure = (
            conditions.get("MemoryPressure") == "True"
            or conditions.get("DiskPressure") == "True"
            or conditions.get("PIDPressure") == "True"
        )

        # Determine the final node status
        if not is_ready:
            return "NotReady"
        if is_unschedulable:
            return "Unschedulable"
        if has_pressure:
            return "UnderPressure"
        return "Ready"

    def get_node_status(self, node_name: str) -> str:
        """Get the status of a specific node from the Kubernetes cluster.

        Args:
            node_name (str): Name of the node to get status for.

        Returns:
            str: Status of the node. Possible values:
                - 'Ready': Node is healthy and ready to accept pods
                - 'NotReady': Node is not ready to accept pods
                - 'SchedulingDisabled': Node is ready but marked as unschedulable

        Raises:
            KubernetesException: If there is an error while fetching node status
                                or if the node is not found.
            ValueError: If node_name is not provided.
        """
        if not node_name:
            raise ValueError("node_name must be provided")

        result = self.ansible_executor.run_playbook(
            playbook="GET_NODE_STATUS", extra_vars={"kubeconfig_content": self.config, "node_name": node_name}
        )

        if result["status"] != "successful":
            logger.error(f"Failed to fetch status for node {node_name}")
            raise KubernetesException(f"Failed to fetch status for node {node_name}")

        try:
            for event in result["events"]:
                if event["task"] == "Display Node Status" and event["status"] == "runner_on_ok":
                    return event["event_data"]["res"]["node_status"]
        except Exception as err:
            logger.error(f"Found error while parsing node status. {err}")
            raise KubernetesException("Found error while parsing node status") from err

        raise KubernetesException(f"Could not determine status for node {node_name}")

    def transfer_model(self, values: dict) -> None:
        """Transfer the model to the Kubernetes cluster."""
        # Set NFS server IP if volume type is NFS
        if values.get("volume_type") == "nfs":
            nfs_server = self.get_nfs_service_ip()
            if nfs_server:
                values["nfs_server"] = nfs_server
                logger.info(f"Using NFS server: {nfs_server}")
            else:
                # If NFS service is not available, fallback to local volume
                logger.warning("NFS service not found, falling back to local volume type")
                values["volume_type"] = "local"
                values["nfs_server"] = ""  # Set empty string to avoid undefined variable
        else:
            # For non-NFS volume types, ensure nfs_server is defined but empty
            values["nfs_server"] = ""

        result = self.ansible_executor.run_playbook(
            playbook="MODEL_TRANSFER", extra_vars={"kubeconfig_content": self.config, **values}
        )
        logger.debug(result["status"])
        return result["status"]

    def get_model_transfer_status(self, values: dict) -> str:
        """Get the model transfer status."""
        result = self.ansible_executor.run_playbook(
            playbook="GET_MODEL_TRANSFER_STATUS", extra_vars={"kubeconfig_content": self.config, **values}
        )
        logger.debug(f"get_model_transfer_status {values}")

        pod_info = None
        pod_status = None
        configmap_data = None
        if result["status"] == "successful":
            for event in result["events"]:
                if (
                    event["task"] == "Get Pod status"
                    and event["status"] == "runner_on_ok"
                    and event["event_data"]["res"]["resources"]
                ):
                    pod_info = event["event_data"]["res"]["resources"][0]
                    pod_status = pod_info["status"]["phase"]
                if (
                    event["task"] == "Get ConfigMap data"
                    and event["status"] == "runner_on_ok"
                    and event["event_data"]["res"]["resources"]
                ):
                    configmap_data = event["event_data"]["res"]["resources"][0]["data"]

        transfer_status = {"status": "inprogress"}

        # Check ConfigMap completion FIRST - handles case where pod completed and was garbage collected
        # but the transfer was successful (ConfigMap persists after pod deletion)
        if configmap_data and configmap_data.get("status") == "completed":
            transfer_status["status"] = configmap_data["status"]
            transfer_status["total_files"] = configmap_data.get("total_files")
            transfer_status["completed_files"] = configmap_data.get("completed_files")
            transfer_status["total_size"] = configmap_data.get("total_size")
            transfer_status["completed_size"] = configmap_data.get("completed_size")
            transfer_status["eta"] = configmap_data.get("eta")
            return transfer_status

        # Check if pod exists and its status (only after confirming transfer isn't already complete)
        if not pod_status:
            transfer_status["status"] = "failed"
            transfer_status["reason"] = "Pod not found"
            return transfer_status

        if pod_status == "Failed":
            transfer_status["status"] = "failed"
            transfer_status["reason"] = "Pod failed"
            return transfer_status

        # Check for container-level failures
        if pod_info and "status" in pod_info:
            container_statuses = pod_info["status"].get("containerStatuses", [])
            for container in container_statuses:
                if "state" in container:
                    if "waiting" in container["state"]:
                        waiting_reason = container["state"]["waiting"].get("reason", "")
                        if waiting_reason in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"]:
                            transfer_status["status"] = "failed"
                            transfer_status["reason"] = f"Container error: {waiting_reason}"
                            return transfer_status
                    elif "terminated" in container["state"]:
                        exit_code = container["state"]["terminated"].get("exitCode", 0)
                        if exit_code != 0:
                            transfer_status["status"] = "failed"
                            transfer_status["reason"] = f"Container terminated with exit code {exit_code}"
                            return transfer_status

        # Check pod age for timeout
        if pod_info and "metadata" in pod_info:
            import datetime

            creation_timestamp = pod_info["metadata"].get("creationTimestamp")
            if creation_timestamp:
                # Parse ISO format timestamp
                try:
                    from dateutil import parser

                    pod_created = parser.parse(creation_timestamp)
                    now = datetime.datetime.now(datetime.timezone.utc)
                    pod_age_minutes = (now - pod_created).total_seconds() / 60

                    # If pod is older than 5 minutes and no ConfigMap, check logs and consider it failed
                    if not configmap_data and pod_age_minutes > 5:
                        transfer_status["status"] = "failed"
                        transfer_status["reason"] = f"ConfigMap not created after {int(pod_age_minutes)} minutes"

                        # Try to get pod logs for more details
                        log_result = self.get_pod_logs_for_errors(values.get("namespace"), "model-transfer-pod")
                        if log_result["status"] == "success" and log_result.get("error_indicators"):
                            # Include top 3 errors found in logs
                            transfer_status["error_details"] = log_result["error_indicators"][:3]

                        return transfer_status
                except Exception as e:
                    logger.warning(f"Failed to parse pod creation timestamp: {e}")

        # If ConfigMap doesn't exist yet, return initializing status
        if not configmap_data:
            transfer_status["status"] = "initializing"
            return transfer_status

        transfer_status["status"] = configmap_data["status"]
        transfer_status["total_files"] = configmap_data["total_files"]
        transfer_status["completed_files"] = configmap_data["completed_files"]
        transfer_status["total_size"] = configmap_data["total_size"]
        transfer_status["completed_size"] = configmap_data["completed_size"]
        transfer_status["eta"] = configmap_data["eta"]

        return transfer_status

    def deploy_runtime(self, values: dict, playbook: str, delete_on_failure: bool = True) -> None:
        """Deploy the runtime on the Kubernetes cluster."""
        values["platform"] = self.platform
        values["nfs_server"] = self.get_nfs_service_ip()
        values["ingress_host"], _ = self._parse_hostname(values["ingress_host"])
        result = self.ansible_executor.run_playbook(
            playbook=playbook, extra_vars={"kubeconfig_content": self.config, **values}
        )
        logger.info(f"Deploy runtime playbook result: {result}")
        if result["status"] != "successful" and delete_on_failure:
            self.delete_namespace(values["namespace"])
            raise KubernetesException("Failed to deploy runtime")
        return result["status"], self.get_ingress_url(values["namespace"])

    def update_autoscale_config(self, values: dict) -> tuple[str, str]:
        """Update autoscale configuration for an existing deployment using Helm upgrade.

        This method updates the BudAIScaler configuration by running a Helm upgrade
        that only modifies autoscale-related values while preserving other settings.

        Args:
            values: Dict containing:
                - namespace: Kubernetes namespace of the deployment
                - release_name: Helm release name
                - budaiscaler: BudAIScaler configuration dict

        Returns:
            tuple: (status, message) indicating success or failure

        Raises:
            KubernetesException: If the Helm upgrade fails
        """
        namespace = values.get("namespace")
        release_name = values.get("release_name")
        budaiscaler = values.get("budaiscaler", {})

        logger.info(f"Updating autoscale config for release '{release_name}' in namespace '{namespace}'")

        # Prepare values for the Ansible playbook
        extra_vars = {
            "kubeconfig_content": self.config,
            "namespace": namespace,
            "release_name": release_name,
            "budaiscaler": budaiscaler,
            "platform": self.platform,
        }

        result = self.ansible_executor.run_playbook(
            playbook="UPDATE_AUTOSCALE",
            extra_vars=extra_vars,
        )

        logger.info(f"Update autoscale playbook result: {result}")

        if result["status"] == "successful":
            autoscale_enabled = budaiscaler.get("enabled", False)
            message = f"Autoscale {'enabled' if autoscale_enabled else 'disabled'} successfully"
            return "successful", message
        else:
            raise KubernetesException(
                f"Failed to update autoscale configuration: {result.get('message', 'Unknown error')}"
            )

    def get_pod_logs_for_errors(
        self, namespace: str, pod_name: str = "model-transfer-pod", tail_lines: int = 50
    ) -> dict:
        """Get logs from a pod and check for error patterns."""
        try:
            v1 = client.CoreV1Api(api_client=self.api_client)

            # Get pod logs
            try:
                logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=tail_lines)
                return {"status": "success", "logs": logs, "error_indicators": self._check_log_errors(logs)}
            except Exception as e:
                logger.error(f"Failed to get pod logs: {e}")
                return {"status": "failed", "error": str(e)}
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            return {"status": "failed", "error": str(e)}

    def _check_log_errors(self, logs: str) -> list:
        """Check logs for common error patterns."""
        error_patterns = [
            "Permission denied",
            "Access denied",
            "Mount failed",
            "No such file or directory",
            "Connection refused",
            "Authentication failed",
            "Out of memory",
            "Disk full",
            "ConfigMap creation failed",
            "Failed to create",
            "Error:",
            "FATAL:",
            "panic:",
        ]

        found_errors = []
        for line in logs.split("\n"):
            for pattern in error_patterns:
                if pattern.lower() in line.lower():
                    found_errors.append({"pattern": pattern, "line": line.strip()})
                    break

        return found_errors

    def delete_namespace(self, namespace: str) -> None:
        """Delete the runtime on the Kubernetes cluster."""
        result = self.ansible_executor.run_playbook(
            playbook="DELETE_NAMESPACE", extra_vars={"kubeconfig_content": self.config, "namespace": namespace}
        )
        return result["status"]

    def create_httproute(self, values: dict) -> tuple[str, str | None]:
        """Create HTTPRoute and ReferenceGrant for a use case deployment.

        Args:
            values: Dict with deployment_id, namespace, service_name, access_config.

        Returns:
            Tuple of (status, gateway_endpoint or None).
        """
        access_config = values.get("access_config", {})
        ui_config = access_config.get("ui", {})
        api_config = access_config.get("api", {})

        extra_vars = {
            "kubeconfig_content": self.config,
            "usecase_deployment_id": values["deployment_id"],
            "namespace": values["namespace"],
            "helm_service_name": values["service_name"],
            "access_ui_enabled": ui_config.get("enabled", False),
            "access_ui_port": ui_config.get("port", 80),
            "access_ui_path": ui_config.get("path", "/"),
            "access_api_enabled": api_config.get("enabled", False),
            "access_api_port": api_config.get("port", 8080),
            "access_api_base_path": api_config.get("base_path", "/"),
            "access_ui_service_suffix": ui_config.get("service_suffix", ""),
            "access_api_service_suffix": api_config.get("service_suffix", ""),
        }

        result = self.ansible_executor.run_playbook(
            playbook="CREATE_HTTPROUTE",
            extra_vars=extra_vars,
        )
        logger.info(f"Create HTTPRoute playbook result: {result['status']}")

        gateway_endpoint = None
        for event in result.get("events", []):
            if event.get("task") == "Extract gateway endpoint" and event.get("status") == "runner_on_ok":
                gateway_endpoint = (
                    event.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get("gateway_endpoint")
                )

        # Fallback to the cluster's ingress_url when the Gateway service wasn't discovered
        if not gateway_endpoint and self.ingress_url:
            gateway_endpoint = self.ingress_url.rstrip("/")
            logger.info(f"Gateway endpoint not discovered, using cluster ingress_url: {gateway_endpoint}")

        return result["status"], gateway_endpoint

    def delete_httproute(self, deployment_id: str, namespace: str) -> str:
        """Delete HTTPRoute and ReferenceGrant for a use case deployment.

        Args:
            deployment_id: The deployment ID used to name the HTTPRoute.
            namespace: The namespace containing the ReferenceGrant.

        Returns:
            Status string from the playbook execution.
        """
        extra_vars = {
            "kubeconfig_content": self.config,
            "usecase_deployment_id": deployment_id,
            "namespace": namespace,
        }

        result = self.ansible_executor.run_playbook(
            playbook="DELETE_HTTPROUTE",
            extra_vars=extra_vars,
        )
        logger.info(f"Delete HTTPRoute playbook result: {result['status']}")
        return result["status"]

    def deploy_helm_chart(
        self,
        release_name: str,
        chart_ref: str,
        namespace: str = "default",
        values: dict | None = None,
        chart_version: str | None = None,
        wait: bool = True,
        timeout: str = "600s",
        create_namespace: bool = True,
        delete_on_failure: bool = True,
        git_repo: str = "",
        git_ref: str = "main",
        chart_subpath: str = ".",
    ) -> tuple[str, dict]:
        """Deploy a Helm chart to this cluster via Ansible playbook.

        Args:
            release_name: Helm release name.
            chart_ref: Chart reference (OCI, HTTPS, or local path).
            namespace: Kubernetes namespace.
            values: Helm values to override defaults.
            chart_version: Specific chart version.
            wait: Wait for readiness.
            timeout: Helm timeout.
            create_namespace: Create namespace if missing.
            delete_on_failure: Clean up namespace on failure.
            git_repo: Git repo URL containing the chart.
            git_ref: Git branch/tag/commit.
            chart_subpath: Path to chart within git repo.

        Returns:
            Tuple of (status, result_info dict).

        Raises:
            KubernetesException: If deployment fails and delete_on_failure is True.
        """
        extra_vars = {
            "kubeconfig_content": self.config,
            "helm_release_name": release_name,
            "helm_chart_ref": chart_ref,
            "namespace": namespace,
            "values": values or {},
            "helm_wait": wait,
            "helm_timeout": timeout,
            "create_namespace": create_namespace,
        }
        if chart_version:
            extra_vars["helm_chart_version"] = chart_version
        if git_repo:
            extra_vars["helm_git_repo"] = git_repo
            extra_vars["helm_git_ref"] = git_ref
            extra_vars["helm_chart_subpath"] = chart_subpath

        result = self.ansible_executor.run_playbook(
            playbook="DEPLOY_HELM_CHART",
            extra_vars=extra_vars,
        )
        logger.info(f"Deploy Helm chart playbook result: {result['status']}")

        if result["status"] != "successful":
            if delete_on_failure:
                self.delete_namespace(namespace)
                raise KubernetesException(f"Failed to deploy Helm chart '{release_name}' in namespace '{namespace}'")
            return result["status"], {"release_name": release_name, "namespace": namespace, "services": []}

        # Extract service info from the Ansible result
        services = []
        for event in result.get("events", []):
            if event.get("task") == "Gather deployed Service resources" and event.get("status") == "runner_on_ok":
                resources = event.get("event_data", {}).get("res", {}).get("resources", [])
                for svc in resources:
                    svc_meta = svc.get("metadata", {})
                    svc_spec = svc.get("spec", {})
                    services.append(
                        {
                            "name": svc_meta.get("name"),
                            "namespace": svc_meta.get("namespace"),
                            "cluster_ip": svc_spec.get("clusterIP"),
                            "type": svc_spec.get("type"),
                            "ports": svc_spec.get("ports", []),
                        }
                    )

        result_info = {
            "release_name": release_name,
            "namespace": namespace,
            "services": services,
        }
        return result["status"], result_info

    def delete_cluster(self) -> None:
        """Delete the cluster on the Kubernetes cluster."""
        result = self.ansible_executor.run_playbook(
            playbook="DELETE_CLUSTER", extra_vars={"kubeconfig_content": self.config}
        )
        return result["status"]

    def get_ingress_url(self, namespace: str) -> str:
        """Get the ingress url for the namespace."""
        ingress_host, scheme = self._parse_hostname(self.ingress_url)
        return f"{scheme}://{ingress_host}"

    def verify_ingress_health(self, namespace: str) -> bool:
        """Verify the ingress health by checking if the model is available in the models list."""
        ingress_url = self.get_ingress_url(namespace)
        models_url = f"{ingress_url}/v1/models/"

        try:
            response = requests.get(models_url, timeout=30)
            logger.debug(f"Ingress health check response: {response.content}")
            if response.status_code == 200:
                models_data = response.json()
                # Check if namespace (model name) exists in the models list
                model_ids = [model.get("id") for model in models_data.get("data", [])]
                if namespace in model_ids:
                    logger.debug(f"Model {namespace} found in available models")
                    return True
                else:
                    logger.info(f"Model {namespace} not found in available models: {model_ids}")
                    return False
            else:
                logger.info(
                    f"Ingress health check failed for namespace {namespace} with status code {response.status_code}"
                )
                return False
        except requests.RequestException as err:
            logger.error(f"Error during ingress health check for namespace {namespace}: {err}")
            return False
        except (KeyError, ValueError) as err:
            logger.error(f"Error parsing models response for namespace {namespace}: {err}")
            return False

    def identify_supported_endpoints(self, namespace: str) -> Dict[str, bool]:
        """Identify which endpoints are supported by checking if they return 200 status.

        Args:
            namespace (str): The namespace/model name to check

        Returns:
            Dict[str, bool]: A dictionary mapping endpoint paths to their availability status
        """
        ingress_url = self.get_ingress_url(namespace)
        headers = {}

        # Define endpoints to check
        # Note: These endpoints do NOT use trailing slashes (unlike /v1/models/ which requires it)
        endpoints_to_check = [
            "/v1/embeddings",
            "/v1/chat/completions",
            "/v1/classify",
            # "/v1/models",
            # "/v1/completions",
            # "/health",
            # "/health/readiness"
        ]

        supported_endpoints = {}

        for endpoint in endpoints_to_check:
            try:
                url = f"{ingress_url}{endpoint}"

                # For endpoints that require POST, prepare minimal valid payload
                if endpoint in ["/v1/embeddings", "/v1/chat/completions", "/v1/completions", "/v1/classify"]:
                    if endpoint == "/v1/embeddings":
                        payload = {"model": namespace, "input": "test"}
                    elif endpoint == "/v1/chat/completions":
                        payload = {
                            "model": namespace,
                            "messages": [{"role": "user", "content": "who are you?"}],
                            "max_tokens": 1,
                        }
                    elif endpoint == "/v1/classify":
                        payload = {"model": namespace, "input": ["test"], "raw_scores": False}
                    else:  # /v1/completions
                        payload = {"model": namespace, "prompt": "test", "max_tokens": 1}

                    headers["Content-Type"] = "application/json"
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                else:
                    # GET endpoints
                    response = requests.get(url, headers=headers, timeout=10)

                # Check if endpoint is supported (200 OK or other success codes)
                is_success = response.status_code in [200, 201, 202, 204]
                supported_endpoints[endpoint] = is_success

                if is_success:
                    logger.debug(f"Endpoint {endpoint} returned status code {response.status_code}")
                else:
                    # Log non-success responses at INFO level for debugging deployment failures
                    response_text = response.text[:500] if response.text else ""
                    logger.info(
                        f"Endpoint {endpoint} returned non-success status {response.status_code}: {response_text}"
                    )

            except requests.RequestException as err:
                logger.debug(f"Endpoint {endpoint} failed with error: {err}")
                supported_endpoints[endpoint] = False

        logger.info(f"Supported endpoints for namespace {namespace}: {supported_endpoints}")
        return supported_endpoints

    def _format_deployment_data(
        self,
        deployment_data: Dict[str, Any],
        replica_set_data: Dict[str, Any],
        pod_data: Dict[str, Any],
        events: Dict[str, Any],
    ) -> Dict[str, Any]:
        for pod in pod_data["resources"]:
            pod["event"] = []
            for event in events["resources"]:
                if pod["metadata"]["name"] == event["involvedObject"]["name"]:
                    pod["event"].append(event)

        deployment_info = []
        worker_data_list = []
        for deployment in deployment_data["resources"]:
            deploy_info = {**deployment}
            deploy_info["pod"] = []
            for replica_set in replica_set_data["resources"]:
                replica_set_info = {}
                for owner in replica_set["metadata"]["ownerReferences"]:
                    if deployment["metadata"]["uid"] == owner["uid"]:
                        replica_set_info = {**replica_set}
                if not replica_set_info["metadata"]:
                    continue
                for pod in pod_data["resources"]:
                    if "ownerReferences" not in pod["metadata"]:
                        continue
                    if replica_set_info["metadata"]["uid"] == pod["metadata"]["ownerReferences"][0]["uid"]:
                        pod["pod_phase"] = pod.get("status", {}).get("phase", "Unknown")
                        # Build a list describing each container's state and reason
                        containers_info = []
                        last_restart_datetime = None
                        for cs in pod.get("status", {}).get("containerStatuses", []):
                            name = cs["name"]
                            state_dict = cs.get("state", {})
                            restart_time = cs.get("lastState", {}).get("terminated", {}).get("finishedAt")
                            if restart_time:
                                restart_dt = datetime.fromisoformat(restart_time)
                                if not last_restart_datetime or restart_dt > last_restart_datetime:
                                    last_restart_datetime = restart_dt

                            # Determine if container is waiting, running, or terminated
                            if "waiting" in state_dict:
                                container_state = "Waiting"
                                reason = state_dict["waiting"].get("reason", "Unknown")
                            elif "running" in state_dict:
                                container_state = "Running"
                                reason = "Running"
                            elif "terminated" in state_dict:
                                container_state = "Terminated"
                                reason = state_dict["terminated"].get("reason", "Unknown")
                            else:
                                container_state = "Unknown"
                                reason = "Unknown"

                            containers_info.append({"name": name, "state": container_state, "reason": reason})
                        pod["containers"] = containers_info
                        reason = None
                        if pod["pod_phase"] in ["Running", "Succeeded", "Failed"] and containers_info:
                            reason = containers_info[0]["reason"]
                        if (
                            pod["pod_phase"] in ["Pending", "Failed", "Unknown"]
                            and not containers_info
                            and pod.get("status", {}).get("conditions", [])
                            and not reason
                        ):
                            conditions = pod["status"]["conditions"]
                            ready_condition = [condition for condition in conditions if condition["type"] == "Ready"]
                            containers_ready_condition = [
                                condition for condition in conditions if condition["type"] == "ContainersReady"
                            ]
                            pod_scheduled_condition = [
                                condition for condition in conditions if condition["type"] == "PodScheduled"
                            ]
                            initialized_condition = [
                                condition for condition in conditions if condition["type"] == "Initialized"
                            ]
                            if ready_condition and ready_condition[0]["status"] == "False":
                                reason = f"{ready_condition[0]['reason']} : {ready_condition[0]['message']}"
                            elif containers_ready_condition and containers_ready_condition[0]["status"] == "False":
                                reason = f"{containers_ready_condition[0]['reason']} : {containers_ready_condition[0]['message']}"
                            elif pod_scheduled_condition and pod_scheduled_condition[0]["status"] == "False":
                                reason = (
                                    f"{pod_scheduled_condition[0]['reason']} : {pod_scheduled_condition[0]['message']}"
                                )
                            elif initialized_condition and initialized_condition[0]["status"] == "False":
                                reason = (
                                    f"{initialized_condition[0]['reason']} : {initialized_condition[0]['message']}"
                                )

                        if pod["pod_phase"] == "Running":
                            start_time = datetime.fromisoformat(pod["metadata"]["creationTimestamp"])
                            current_time = datetime.now(timezone.utc)
                            # uptime = format_uptime(current_time - start_time)
                            uptime = str(int((current_time - start_time).total_seconds()))

                            container_name = pod["spec"]["containers"][0]["name"]
                            hardware = "cpu"
                            if container_name == "cuda-container":
                                hardware = "gpu"
                            elif container_name == "hpu-container":
                                hardware = "hpu"

                            # TODO: remove default values for device_name and concurrency once all existing deployments are deleted
                            worker_data = WorkerData(
                                name=pod["metadata"]["name"],
                                status=pod["pod_phase"],
                                node_name=pod["spec"]["nodeName"],
                                device_name=pod["metadata"]["labels"].get(
                                    "device_name", "Intel(R) Xeon(R) Platinum 8480+"
                                ),
                                utilization=None,
                                hardware=hardware,
                                uptime=uptime,
                                created_datetime=start_time,
                                last_restart_datetime=last_restart_datetime or start_time,
                                node_ip=pod["status"]["hostIP"],
                                cores=int(
                                    pod["spec"]["containers"][0].get("resources", {}).get("requests", {}).get("cpu", 0)
                                ),
                                memory=pod["spec"]["containers"][0]
                                .get("resources", {})
                                .get("requests", {})
                                .get("memory", "0"),
                                deployment_name=deploy_info["metadata"]["name"],
                                concurrency=int(pod["metadata"]["labels"].get("concurrency") or 100),
                                reason=reason,
                            )
                            worker_data_list.append(worker_data.model_dump(mode="json", exclude_none=True))
                        deploy_info["pod"].append(pod)
            deployment_info.append(deploy_info)
        return deployment_info, worker_data_list

    def _process_deployment_status(self, deployment_data: Dict[str, Any]) -> str:
        replicas = {
            "total": 0,
            "available": 0,
            "failed": 0,
            "pending": 0,
            "status": DeploymentStatusEnum.PENDING,
            "reason": "",
        }
        for deployment in deployment_data:
            replicas["total"] += deployment["status"].get("replicas", 0)
            if "unavailableReplicas" in deployment["status"]:
                replicas["pending"] += deployment["status"]["unavailableReplicas"]

        if replicas["pending"] == 0:
            replicas["status"] = DeploymentStatusEnum.READY
            return replicas

        for deployment in deployment_data:
            for pod in deployment["pod"]:
                # 1) If the Pod's phase is "Failed", it's definitely in a failed state
                if pod["pod_phase"] == "Failed":
                    replicas["failed"] += 1
                    continue

                # 2) If the Pod is "Pending" or "Running" but container is in "waiting" with a reason
                #    like "ContainerCreating", it's waiting stage because container is not ready yet.
                if pod["pod_phase"] in ["Pending", "Running"]:
                    failed_event = False
                    for event in pod["event"]:
                        if event["reason"] in ["FailedMount", "FailedScheduling"]:
                            replicas["reason"] = event["message"]
                            replicas["failed"] += 1
                            failed_event = True
                            break
                    if failed_event:
                        continue
                    for c in pod["containers"]:
                        if c["state"] not in ["Waiting", "Running"]:
                            replicas["failed"] += 1
                else:
                    replicas["failed"] += 1

        if replicas["failed"] > 0:
            replicas["status"] = DeploymentStatusEnum.FAILED
        elif replicas["pending"] > 0:
            replicas["status"] = DeploymentStatusEnum.PENDING

        return replicas

    def get_deployment_status(self, values: dict, ingress_health: bool = True, check_pods: bool = True) -> str:
        """Get the status of a deployment on the Kubernetes cluster."""
        logger.info(
            f"get_deployment_status called for {values.get('namespace', 'unknown')}: "
            f"ingress_health={ingress_health}, check_pods={check_pods}"
        )
        if not self.ingress_url:
            raise KubernetesException("Ingress URL is not set")

        # Optimization: Skip pod checks if check_pods is False
        if not check_pods:
            if not ingress_health:
                # If both are False, we can't determine status
                logger.warning("Both check_pods and ingress_health are False, returning unknown status")
                return {
                    "status": DeploymentStatusEnum.UNKNOWN,
                    "replicas": {},
                    "ingress_health": False,
                    "worker_data_list": None,
                }

            # Only check ingress health
            ingress_healthy = self.verify_ingress_health(values["namespace"])
            status = DeploymentStatusEnum.READY if ingress_healthy else DeploymentStatusEnum.FAILED
            logger.info(
                f"Optimized status check for {values['namespace']}: {status} (ingress_healthy={ingress_healthy})"
            )

            return {
                "status": status,
                "replicas": {},
                "ingress_health": ingress_healthy,
                "worker_data_list": None,  # Return None to indicate no worker data update
            }

        while True:
            result = self.ansible_executor.run_playbook(
                playbook="GET_DEPLOYMENT_STATUS", extra_vars={"kubeconfig_content": self.config, **values}
            )
            if result["status"] != "successful":
                raise KubernetesException("Failed to get deployment status")

            for event in result["events"]:
                if event["task"] == "Gather list of Deployments" and event["status"] == "runner_on_ok":
                    deployment_data = event["event_data"]["res"]
                if event["task"] == "Gather list of ReplicaSets" and event["status"] == "runner_on_ok":
                    replica_set_data = event["event_data"]["res"]
                if event["task"] == "Gather list of Pods" and event["status"] == "runner_on_ok":
                    pod_data = event["event_data"]["res"]
                if event["task"] == "Gather events for Pods" and event["status"] == "runner_on_ok":
                    pod_events = event["event_data"]["res"]

            deployment_info, worker_data_list = self._format_deployment_data(
                deployment_data, replica_set_data, pod_data, pod_events
            )
            pod_status = self._process_deployment_status(deployment_info)
            if pod_status["status"] == DeploymentStatusEnum.FAILED:
                return {
                    "status": pod_status["status"],
                    "replicas": pod_status,
                    "ingress_health": False,
                    "worker_data_list": worker_data_list,
                }
            elif pod_status["status"] == DeploymentStatusEnum.PENDING:
                time.sleep(20)
                continue
            else:
                break

        # Phase 2: Bounded ingress/endpoint validation
        # if not worker_data_list:
        #     pod_status["status"] = DeploymentStatusEnum.FAILED
        #     return {
        #         "status": DeploymentStatusEnum.FAILED,
        #         "replicas": pod_status,
        #         "ingress_health": False,
        #         "worker_data_list": worker_data_list,
        #         "supported_endpoints": {},
        #     }

        # Only perform ingress/endpoint validation if explicitly requested
        if not ingress_health:
            return {
                "status": pod_status["status"],
                "replicas": pod_status,
                "ingress_health": True,
                "worker_data_list": worker_data_list,
                "supported_endpoints": {},
            }

        # Bounded retry for ingress and endpoint validation
        max_retries = app_settings.max_endpoint_retry_attempts
        retry_interval = app_settings.endpoint_retry_interval
        retry_count = 0

        logger.info(
            f"Starting endpoint validation retry loop for {values['namespace']}: "
            f"max_retries={max_retries}, interval={retry_interval}s, total_timeout={max_retries * retry_interval}s"
        )

        while retry_count < max_retries:
            logger.info(f"Attempt {retry_count + 1}/{max_retries} for {values['namespace']}")

            # Check ingress health (/v1/models endpoint)
            ingress_healthy = self.verify_ingress_health(values["namespace"])
            logger.debug(f"Ingress health check result: {ingress_healthy}")

            if ingress_healthy:
                # Check endpoint functionality (/v1/embeddings, /v1/chat/completions)
                endpoints_status = self.identify_supported_endpoints(values["namespace"])
                functional_endpoints = [ep for ep, supported in endpoints_status.items() if supported]
                logger.debug(f"Endpoint status: {endpoints_status}, functional: {functional_endpoints}")

                if functional_endpoints:
                    # SUCCESS: Both ingress and endpoints are ready
                    logger.info(
                        f"✓ Deployment ready for {values['namespace']} after {retry_count + 1} attempts "
                        f"with endpoints: {functional_endpoints}"
                    )
                    return {
                        "status": pod_status["status"],
                        "replicas": pod_status,
                        "ingress_health": True,
                        "worker_data_list": worker_data_list,
                        "supported_endpoints": endpoints_status,
                    }
                else:
                    logger.info(f"Endpoints not ready for {values['namespace']} (ingress OK)")
            else:
                logger.info(f"Ingress not ready for {values['namespace']}")

            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Waiting {retry_interval}s before next attempt...")
                time.sleep(retry_interval)

        # TIMEOUT: Max retries exceeded - determine final status based on original logic
        logger.error(
            f"Endpoints/ingress failed to become ready after {max_retries} attempts for {values['namespace']}"
        )

        # Check final ingress health state for status determination
        final_ingress_healthy = False
        try:
            final_ingress_healthy = self.verify_ingress_health(values["namespace"])
        except Exception as e:
            logger.warning(f"Final ingress health check failed: {e}")

        # Apply original status logic: ingress health can be checked only if workers are available
        if not final_ingress_healthy and worker_data_list:
            final_status = DeploymentStatusEnum.INGRESS_FAILED
        elif not worker_data_list:
            final_status = DeploymentStatusEnum.FAILED
        else:
            # New case: ingress is healthy but endpoints failed (timeout)
            final_status = DeploymentStatusEnum.ENDPOINTS_FAILED

        return {
            "status": final_status,
            "replicas": pod_status,
            "ingress_health": final_ingress_healthy,
            "worker_data_list": worker_data_list,
            "supported_endpoints": endpoints_status if "endpoints_status" in locals() else {},
        }

    def apply_security_context(self, namespace: str) -> None:
        """Apply security context to the runtime containers."""
        return "successful"

    def delete_pod(self, namespace: str, deployment_name: str, pod_name: str) -> None:
        """Delete a pod."""
        result = self.ansible_executor.run_playbook(
            playbook="DELETE_POD",
            extra_vars={
                "kubeconfig_content": self.config,
                "pod_name": pod_name,
                "namespace": namespace,
                "deployment_name": deployment_name,
            },
        )
        return result["status"]

    def get_pod_status(self, namespace: str, pod_name: str) -> str:
        """Get the status of a pod."""
        result = self.ansible_executor.run_playbook(
            playbook="GET_POD_STATUS",
            extra_vars={
                "kubeconfig_content": self.config,
                "namespace": namespace,
                "pod_name": pod_name,
            },
        )
        print(result)
        if result["status"] != "successful":
            fail_reason = None
            for event in result["events"]:
                if event["status"] == "runner_on_failed":
                    fail_reason = event["event_data"]["res"]["msg"]
                    break
            if fail_reason:
                raise KubernetesException(fail_reason)
            else:
                raise KubernetesException("Failed to get pod status")
        for event in result["events"]:
            if event["task"] == "Get Pod Info" and event["status"] == "runner_on_ok":
                pod_data = event["event_data"]["res"]
                break
        pod = pod_data["resources"][0]
        pod["pod_phase"] = pod.get("status", {}).get("phase", "Unknown")
        containers_info = []
        last_restart_datetime = None
        for cs in pod.get("status", {}).get("containerStatuses", []):
            name = cs["name"]
            state_dict = cs.get("state", {})
            restart_time = cs.get("lastState", {}).get("terminated", {}).get("finishedAt")
            if restart_time:
                restart_dt = datetime.fromisoformat(restart_time)
                if not last_restart_datetime or restart_dt > last_restart_datetime:
                    last_restart_datetime = restart_dt

            # Determine if container is waiting, running, or terminated
            if "waiting" in state_dict:
                container_state = "Waiting"
                reason = state_dict["waiting"].get("reason", "Unknown")
            elif "running" in state_dict:
                container_state = "Running"
                reason = "Running"
            elif "terminated" in state_dict:
                container_state = "Terminated"
                reason = state_dict["terminated"].get("reason", "Unknown")
            else:
                container_state = "Unknown"
                reason = "Unknown"

            containers_info.append({"name": name, "state": container_state, "reason": reason})
        pod["containers"] = containers_info
        reason = None
        if pod["pod_phase"] in ["Running", "Succeeded", "Failed"] and containers_info:
            reason = containers_info[0]["reason"]
        if (
            pod["pod_phase"] in ["Pending", "Failed", "Unknown"]
            and not containers_info
            and pod.get("status", {}).get("conditions", [])
            and not reason
        ):
            conditions = pod["status"]["conditions"]
            ready_condition = [condition for condition in conditions if condition["type"] == "Ready"]
            containers_ready_condition = [
                condition for condition in conditions if condition["type"] == "ContainersReady"
            ]
            pod_scheduled_condition = [condition for condition in conditions if condition["type"] == "PodScheduled"]
            initialized_condition = [condition for condition in conditions if condition["type"] == "Initialized"]
            if ready_condition and ready_condition[0]["status"] == "False":
                reason = f"{ready_condition[0]['reason']} : {ready_condition[0]['message']}"
            elif containers_ready_condition and containers_ready_condition[0]["status"] == "False":
                reason = f"{containers_ready_condition[0]['reason']} : {containers_ready_condition[0]['message']}"
            elif pod_scheduled_condition and pod_scheduled_condition[0]["status"] == "False":
                reason = f"{pod_scheduled_condition[0]['reason']} : {pod_scheduled_condition[0]['message']}"
            elif initialized_condition and initialized_condition[0]["status"] == "False":
                reason = f"{initialized_condition[0]['reason']} : {initialized_condition[0]['message']}"
        start_time = datetime.fromisoformat(pod["metadata"]["creationTimestamp"])
        current_time = datetime.now(timezone.utc)
        # uptime = format_uptime(current_time - start_time)
        uptime = str(int((current_time - start_time).total_seconds()))

        container_name = pod["spec"]["containers"][0]["name"]
        hardware = "cpu"
        if container_name == "cuda-container":
            hardware = "gpu"
        elif container_name == "hpu-container":
            hardware = "hpu"

        # TODO: remove default values for device_name and concurrency once all existing deployments are deleted
        worker_data = WorkerData(
            name=pod["metadata"]["name"],
            status=pod["pod_phase"],
            node_name=pod["spec"]["nodeName"],
            device_name=pod["metadata"]["labels"].get("device_name", "Intel(R) Xeon(R) Platinum 8480+"),
            utilization=None,
            hardware=hardware,
            uptime=uptime,
            created_datetime=start_time,
            last_restart_datetime=last_restart_datetime or start_time,
            node_ip=pod["status"]["hostIP"],
            cores=int(pod["spec"]["containers"][0].get("resources", {}).get("requests", {}).get("cpu", 0)),
            memory=pod["spec"]["containers"][0].get("resources", {}).get("requests", {}).get("memory", 0),
            deployment_name="bud-runtime-container",
            concurrency=pod["metadata"]["labels"].get("concurrency", 100),
            reason=reason,
        )
        worker_data_dict = worker_data.model_dump(mode="json", exclude_none=True)
        return worker_data_dict

    @staticmethod
    def _parse_log_line(line: str) -> Dict[str, Any]:
        """Parse a log line with timestamp into a structured dictionary.

        Args:
            line: Log line with timestamp prefix

        Returns:
            Dictionary with timestamp and message
        """
        # Common timestamp pattern in K8s logs: 2023-10-01T12:34:56.789012345Z
        timestamp_pattern = r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)"
        match = re.match(timestamp_pattern, line)

        if match:
            timestamp = match.group(1)
            message = line[len(timestamp) :].strip()
            # Convert to ISO format datetime string
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                timestamp_iso = dt.isoformat()
            except ValueError:
                timestamp_iso = timestamp

            return {"timestamp": timestamp_iso, "message": message}
        else:
            # If no timestamp found, return the whole line as message
            return {"timestamp": None, "message": line.strip()}

    def get_pod_logs(
        self, namespace: str, pod_name: str, tail_lines: int = 50, as_json: bool = True
    ) -> Union[str, List[Dict[str, Any]], None]:
        """Get the logs of a pod.

        Args:
            namespace (str): The namespace of the pod.
            pod_name (str): The name of the pod.

        Returns:
            str: The logs of the pod.
        """
        try:
            v1 = client.CoreV1Api(api_client=self.api_client)

            logger.debug(f"::WORKER::Fetching logs for pod {pod_name} in namespace {namespace}")

            params = {"name": pod_name, "namespace": namespace, "timestamps": True, "tail_lines": tail_lines}

            logger.debug(f"::WORKER::Params: {params}")

            logs = v1.read_namespaced_pod_log(**params)

            logger.debug(f"::WORKER::Logs: {logs}")

            if as_json:
                # Split log into lines and parse each line
                log_lines = logs.split("\n")
                log_entries = [self._parse_log_line(line) for line in log_lines if line.strip()]
                return log_entries
            else:
                return logs
        except client.ApiException as err:
            logger.error(f"Kubernetes API error while fetching node events: {err.reason}")
            raise KubernetesException("Failed to fetch node events") from err
        except Exception as err:
            logger.error(f"Error while fetching node events: {err}")
            raise KubernetesException("Failed to fetch node events") from err

    def get_node_wise_events_count(self) -> Dict[str, int]:
        """Get node-wise events count.

        Returns:
            Dict[str, int]: A dictionary where:
                - key (str): Node name
                - value (int): Total count of events for that node

        Raises:
            KubernetesException: If there is an error while fetching node events.
        """
        try:
            v1 = client.CoreV1Api(api_client=self.api_client)

            # Get all nodes
            nodes = v1.list_node()
            event_counts = defaultdict(int)  # Changed to simple int counter

            # Process each node
            for node in nodes.items:
                node_name = node.metadata.name

                # Get events specific to this node using field selector
                field_selector = f"involvedObject.kind=Node,involvedObject.name={node_name}"
                events = v1.list_event_for_all_namespaces(field_selector=field_selector)

                # If no events for node, default to 0
                if not events.items:
                    event_counts[node_name] = 0
                else:
                    # Simply sum up all events for this node
                    for event in events.items:
                        event_counts[node_name] += event.count or 1

            return dict(event_counts)  # Convert defaultdict to regular dict before returning

        except client.ApiException as err:
            logger.error(f"Kubernetes API error while fetching node events: {err.reason}")
            raise KubernetesException("Failed to fetch node events") from err
        except Exception as err:
            logger.error(f"Error while fetching node events: {err}")
            raise KubernetesException("Failed to fetch node events") from err

    # Get Node Wise Events with pagination and total event count
    def get_node_wise_events(self, node_hostname: str) -> Dict[str, Any]:
        """Get node-wise events with pagination and total event count.

        Args:
            node_hostname (str): The name of the node to retrieve events for.
            page (int): The page number to retrieve.
            size (int): The number of events per page.

        Returns:
            Dict[str, Any]: A dictionary containing the events, total event count, and pagination details.
        """
        try:
            # Initialize the API client
            v1 = client.CoreV1Api(api_client=self.api_client)

            # Get events for the specific node
            field_selector = f"involvedObject.kind=Node,involvedObject.name={node_hostname}"
            events = v1.list_event_for_all_namespaces(field_selector=field_selector)

            logger.info(f"Events: {events}")

            # Process events
            node_events = []
            for event in events.items:
                event_data = {
                    "type": str(event.type),
                    "reason": str(event.reason),
                    "message": str(event.message),
                    "count": int(event.count if event.count is not None else 1),
                    "first_timestamp": event.first_timestamp.isoformat() if event.first_timestamp else None,
                    "last_timestamp": event.last_timestamp.isoformat() if event.last_timestamp else None,
                    "source": {
                        "component": str(event.source.component) if event.source.component else "",
                        "host": str(event.source.host) if event.source.host else "",
                    },
                }
                node_events.append(event_data)

            # Calculate pagination details
            return {
                "events": node_events,
            }

        except client.ApiException as err:
            logger.error(f"Kubernetes API error while fetching node events: {err.reason}")
            raise KubernetesException("Failed to fetch node events") from err
        except Exception as err:
            logger.error(f"Error while fetching node events: {err}")
            raise KubernetesException("Failed to fetch node events") from err

    def deploy_quantization_job(self, values: dict):
        """Deploy quantization job."""
        values["nfs_server"] = self.get_nfs_service_ip()
        print(values)
        result = self.ansible_executor.run_playbook(
            playbook="DEPLOY_QUANTIZATION_JOB", extra_vars={"kubeconfig_content": self.config, **values}
        )
        logger.info(result["status"])
        if result["status"] != "successful":
            self.delete_namespace(values["namespace"])
            raise KubernetesException("Failed to deploy runtime")
        return result["status"]

    def get_job_status(self, job_data):
        """Determine the status of a Kubernetes job based on its data.

        Args:
            job_data (dict): A dictionary containing the job status information.

        Returns:
            str: The status of the job, which can be one of the following:
                 "Terminating", "Running", "Completed", "Failed", or "Unknown".
        """
        if job_data.get("terminating", 0) > 0:
            return "Terminating"
        if job_data.get("active", 0) > 0:
            return "Running"
        if job_data.get("succeeded", 0) > 0:
            return "Completed"
        if job_data.get("failed", 0) > 0:
            return "Failed"
        if "succeeded" in job_data.get("uncountedTerminatedPods", {}):
            return "Completed"
        if "failed" in job_data.get("uncountedTerminatedPods", {}):
            return "Failed"
        return "Unknown"

    def get_quantization_status(self, values: dict):
        """Get the status of a quantization job."""
        print(values)
        result = self.ansible_executor.run_playbook(
            playbook="GET_QUANTIZATION_STATUS", extra_vars={"kubeconfig_content": self.config, **values}
        )
        print(result)
        quantization_data = None
        job_status = None

        for event in result["events"]:
            if event["task"] == "Extract Job status" and event["status"] == "runner_on_ok":
                job_data = event["event_data"]["res"]["ansible_facts"]["job_data"]
                job_status = self.get_job_status(job_data)
            if event["task"] == "Extract quantization data" and event["status"] == "runner_on_ok":
                quantization_data = event["event_data"]["res"]["ansible_facts"]["quantization_data"]

        return job_status, quantization_data

    def _format_adapter_error_message(self, raw_message: str) -> str:
        """Format adapter error messages to be more user-friendly.

        Args:
            raw_message: Raw error message from the CRD

        Returns:
            Formatted error message
        """
        # Known error message mappings for user-friendly display
        known_errors = {
            "vLLM does not yet support DoRA": "DoRA is not yet supported",
        }
        return next((msg for key, msg in known_errors.items() if key in raw_message), raw_message)

    def get_adapter_status(self, adapter_name: str, namespace: str) -> tuple[bool, str | None]:
        """Get the status of an adapter by checking the ModelAdapter CRD status.

        Args:
            adapter_name: Name of the adapter (ModelAdapter CRD name)
            namespace: Kubernetes namespace where the adapter is deployed

        Returns:
            tuple: (success: bool, error_message: str | None)
                - success: True if adapter is ready, False otherwise
                - error_message: Error message if failed, None if successful
        """
        try:
            custom_api = client.CustomObjectsApi(api_client=self.api_client)
            adapter = custom_api.get_namespaced_custom_object(
                group="model.aibrix.ai",
                version="v1alpha1",
                namespace=namespace,
                plural="modeladapters",
                name=adapter_name,
            )

            status = adapter.get("status", {})
            phase = status.get("phase", "Unknown")

            logger.info(f"Adapter {adapter_name} in namespace {namespace} has phase: {phase}")

            if phase == "Failed":
                # Extract error message from conditions
                conditions = status.get("conditions", [])
                error_message = "Adapter loading failed"
                for condition in conditions:
                    if condition.get("type") == "Ready" and condition.get("status") == "False":
                        raw_message = condition.get("message", error_message)
                        error_message = self._format_adapter_error_message(raw_message)
                        break
                logger.error(f"Adapter {adapter_name} failed: {error_message}")
                return False, error_message

            if phase in ("Running", "Ready"):
                logger.info(f"Adapter {adapter_name} is ready")
                return True, None

            # Pending or unknown state - treat as not ready
            logger.warning(f"Adapter {adapter_name} is in {phase} state")
            return False, f"Adapter is in {phase} state"

        except client.exceptions.ApiException as e:
            if e.status == 404:
                error_message = f"ModelAdapter CRD '{adapter_name}' not found in namespace '{namespace}'"
            else:
                error_message = f"Failed to get ModelAdapter status: {e.reason}"
            logger.error(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"Unexpected error checking adapter status: {str(e)}"
            logger.error(error_message)
            return False, error_message

    def delete_adapter(self, adapter_name: str, namespace: str) -> tuple[bool, str | None]:
        """Delete a ModelAdapter CRD from the cluster.

        This is used for cleanup when an adapter deployment fails.

        Args:
            adapter_name: Name of the adapter (ModelAdapter CRD name)
            namespace: Kubernetes namespace where the adapter is deployed

        Returns:
            tuple: (success: bool, error_message: str | None)
                - success: True if adapter was deleted, False otherwise
                - error_message: Error message if failed, None if successful
        """
        try:
            custom_api = client.CustomObjectsApi(api_client=self.api_client)
            custom_api.delete_namespaced_custom_object(
                group="model.aibrix.ai",
                version="v1alpha1",
                namespace=namespace,
                plural="modeladapters",
                name=adapter_name,
            )
            logger.info(f"Successfully deleted adapter {adapter_name} from namespace {namespace}")
            return True, None

        except client.exceptions.ApiException as e:
            if e.status == 404:
                # Already deleted or doesn't exist - consider this success
                logger.info(f"Adapter {adapter_name} not found in namespace {namespace} (already deleted)")
                return True, None
            error_message = f"Failed to delete adapter {adapter_name}: {e.reason}"
            logger.error(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"Unexpected error deleting adapter {adapter_name}: {str(e)}"
            logger.error(error_message)
            return False, error_message

    def get_storage_classes(self) -> List[Dict[str, Any]]:
        """Get all storage classes available in the Kubernetes cluster.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing storage class information.
                Each dictionary includes:
                - name: Storage class name
                - provisioner: Storage class provisioner
                - parameters: Storage class parameters
                - reclaim_policy: Volume reclaim policy
                - volume_binding_mode: Volume binding mode
                - default: Whether this is the default storage class
                - recommended_access_mode: Recommended access mode based on provisioner

        Raises:
            KubernetesException: If there is an error while fetching storage classes.
        """
        try:
            # Mapping of storage provisioners to their optimal access modes
            PROVISIONER_ACCESS_MODES = {
                # ReadWriteMany capable (shared storage)
                "file.csi.azure.com": "ReadWriteMany",  # Azure Files CSI
                "kubernetes.io/azure-file": "ReadWriteMany",  # Azure Files (legacy)
                "nfs.csi.k8s.io": "ReadWriteMany",  # NFS CSI
                "efs.csi.aws.com": "ReadWriteMany",  # AWS EFS
                "csi.tigera.io/nfs": "ReadWriteMany",  # Tigera NFS
                # ReadWriteOnce only (block storage)
                "disk.csi.azure.com": "ReadWriteOnce",  # Azure Disk CSI
                "kubernetes.io/azure-disk": "ReadWriteOnce",  # Azure Disk (legacy)
                "ebs.csi.aws.com": "ReadWriteOnce",  # AWS EBS CSI
                "kubernetes.io/aws-ebs": "ReadWriteOnce",  # AWS EBS (legacy)
                "pd.csi.storage.gke.io": "ReadWriteOnce",  # Google Persistent Disk
                "kubernetes.io/gce-pd": "ReadWriteOnce",  # GCE PD (legacy)
                "csi.vsphere.vmware.com": "ReadWriteOnce",  # vSphere CSI
                "kubernetes.io/vsphere-volume": "ReadWriteOnce",  # vSphere (legacy)
                "local-path": "ReadWriteOnce",  # Local path provisioner
                "rancher.io/local-path": "ReadWriteOnce",  # Rancher local path
                # Default fallback
                "default": "ReadWriteOnce",
            }

            storage_v1 = client.StorageV1Api(api_client=self.api_client)
            storage_classes = storage_v1.list_storage_class()

            storage_class_list = []
            for sc in storage_classes.items:
                # Check if this is the default storage class
                is_default = False
                if sc.metadata.annotations:
                    # Check for default annotation
                    is_default = (
                        sc.metadata.annotations.get("storageclass.kubernetes.io/is-default-class") == "true"
                        or sc.metadata.annotations.get("storageclass.beta.kubernetes.io/is-default-class") == "true"
                    )

                # Determine recommended access mode based on provisioner
                provisioner = sc.provisioner
                recommended_access_mode = PROVISIONER_ACCESS_MODES.get(provisioner, "ReadWriteOnce")

                storage_class_info = {
                    "name": sc.metadata.name,
                    "provisioner": sc.provisioner,
                    "parameters": sc.parameters or {},
                    "reclaim_policy": sc.reclaim_policy,
                    "volume_binding_mode": sc.volume_binding_mode,
                    "default": is_default,
                    "recommended_access_mode": recommended_access_mode,
                }
                storage_class_list.append(storage_class_info)

            logger.debug(f"Found {len(storage_class_list)} storage classes")
            return storage_class_list

        except client.ApiException as err:
            logger.error(f"Kubernetes API error while fetching storage classes: {err.reason}")
            raise KubernetesException("Failed to fetch storage classes") from err
        except Exception as err:
            logger.error(f"Error while fetching storage classes: {err}")
            raise KubernetesException("Failed to fetch storage classes") from err

    @asynccontextmanager
    async def create_port_forward(
        self, service_name: str, namespace: str, target_port: int, label: str = ""
    ) -> AsyncGenerator[int, None]:
        """Create a port-forward to a Kubernetes service.

        This method establishes a kubectl port-forward tunnel from localhost to a
        service running in the target cluster. It writes the kubeconfig to a temporary
        file, finds an available local port, and manages the port-forward process lifecycle.

        Args:
            service_name: Name of the Kubernetes service to forward to
            namespace: Kubernetes namespace where the service is located
            target_port: Target port on the service
            label: Optional label for logging (e.g., "Prometheus", "HAMI")

        Yields:
            Local port number where the service is accessible

        Raises:
            KubernetesException: If port-forward fails to start

        Example:
            async with handler.create_port_forward("prometheus", "monitoring", 9090, "Prometheus") as local_port:
                url = f"http://localhost:{local_port}/api/v1/query"
                # Use the port...
        """
        # Write kubeconfig to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            if isinstance(self.config, dict):
                yaml.dump(self.config, f)
            else:
                f.write(self.config)
            kubeconfig_path = f.name

        port_forward_process = None
        local_port = None

        try:
            # Find an available local port
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                local_port = s.getsockname()[1]

            # Execute port-forward subprocess
            port_forward_process = await self._execute_port_forward_subprocess(
                kubeconfig_path, service_name, namespace, local_port, target_port, label
            )

            yield local_port

        finally:
            # Clean up port-forward process
            self._cleanup_port_forward_subprocess(port_forward_process, label)

            # Clean up temporary kubeconfig file
            import os
            from contextlib import suppress

            with suppress(Exception):
                os.unlink(kubeconfig_path)

    async def _execute_port_forward_subprocess(
        self,
        kubeconfig_path: str,
        service_name: str,
        namespace: str,
        local_port: int,
        target_port: int,
        label: str = "",
    ) -> subprocess.Popen:
        """Execute kubectl port-forward command and return the process.

        Args:
            kubeconfig_path: Path to temporary kubeconfig file
            service_name: Name of the Kubernetes service
            namespace: Kubernetes namespace
            local_port: Local port to forward to
            target_port: Target port on the service
            label: Optional label for logging

        Returns:
            subprocess.Popen: The port-forward process

        Raises:
            KubernetesException: If port-forward fails to start
        """
        cmd = [
            "kubectl",
            f"--kubeconfig={kubeconfig_path}",
        ]

        # Add insecure flag if SSL verification is disabled
        if not app_settings.validate_certs:
            cmd.append("--insecure-skip-tls-verify")

        cmd.extend(
            [
                "port-forward",
                f"service/{service_name}",
                f"{local_port}:{target_port}",
                "-n",
                namespace,
            ]
        )

        log_prefix = f"{label} " if label else ""
        logger.info(f"Creating {log_prefix}port-forward from localhost:{local_port} to {service_name}:{target_port}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait for port-forward to be ready
        # Wait up to 10 seconds for the port to be open
        import socket
        import time

        start_time = time.time()
        port_ready = False

        while time.time() - start_time < 10.0:
            if process.poll() is not None:
                break

            try:
                # Try to connect to the local port
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5)
                    # Use localhost to match the bind address logic probably used elsewhere or default
                    result = sock.connect_ex(("127.0.0.1", local_port))

                if result == 0:
                    port_ready = True
                    # Give it a tiny bit more time for the application to be ready to accept data
                    await asyncio.sleep(0.1)
                    break
            except Exception as e:
                logger.debug(f"An error occurred while polling port {local_port}: {e}")

            await asyncio.sleep(0.5)

        # Check if process is still running or if we timed out
        if not port_ready and process.poll() is None:
            # If timed out but process still running, kill it
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except Exception:
                process.kill()

            raise KubernetesException(f"{log_prefix}port-forward timed out waiting for port {local_port} to be open")

        # Check if process is still running
        if process.poll() is not None:
            stderr = process.stderr.read().decode() if process.stderr else ""
            raise KubernetesException(f"{log_prefix}port-forward failed to start: {stderr}")

        return process

    def _cleanup_port_forward_subprocess(self, process: subprocess.Popen, label: str = "") -> None:
        """Clean up the port-forward subprocess.

        Args:
            process: The subprocess.Popen instance to clean up
            label: Optional label for logging
        """
        if process:
            log_prefix = f"{label} " if label else ""
            logger.info(f"Cleaning up {log_prefix}port-forward")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
