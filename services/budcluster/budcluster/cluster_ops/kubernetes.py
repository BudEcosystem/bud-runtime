import base64
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Union
from urllib.parse import urlparse
from uuid import UUID

import requests
from budmicroframe.commons.logging import get_logger
from kubernetes import client, config

from ..commons.config import app_settings, secrets_settings
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
        """Load kubernetes config file."""
        try:
            config.load_kube_config_from_dict(self.config)
            # Get the default configuration
            configuration = client.Configuration.get_default_copy()
            # Disable SSL cert validation and hostname verification
            configuration.verify_ssl = app_settings.validate_certs
            # Set this configuration as the default
            client.Configuration.set_default(configuration)
        except config.ConfigException as err:
            logger.error(f"Found error while loading Kubernetes config file. {err}")
            raise KubernetesException("Invalid Kubernetes config file") from err
        except Exception as err:
            logger.error(f"Found error while loading Kubernetes config file. {err}")
            raise KubernetesException("Found error while loading Kubernetes config file") from err

    def _get_container_status(self, container_name: str, node: Dict[str, Any]) -> str:
        print(node["status"])
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

    def get_image_pull_secret(self) -> Dict[str, Any]:
        """Generate and return the image pull secret for the Kubernetes cluster."""
        return {
            "auths": {
                app_settings.registry_server: {
                    "username": app_settings.registry_username,
                    "password": app_settings.registry_password,
                    "auth": base64.b64encode(
                        f"{app_settings.registry_username}:{app_settings.registry_password}".encode()
                    ).decode(),
                }
            }
        }

    # TODO: Traefik installation
    def initial_setup(self, cluster_id: UUID) -> None:
        """Execute the initial setup for the Kubernetes cluster using Ansible playbook.

        This method runs the 'NODE_INFO_COLLECTOR' playbook to gather node information
        and apply necessary configurations.

        Raises:
            Exception: If the setup fails on any node.

        Returns:
            str: The status of the setup process.
        """
        # Deploy NFD (Node Feature Discovery) for hardware detection
        result = self.ansible_executor.run_playbook(
            playbook="DEPLOY_NFD",  # Updated to use NFD-only approach
            extra_vars={
                "kubeconfig_content": self.config,
                "image_pull_secrets": self.get_image_pull_secret(),
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
            v1 = client.CoreV1Api()
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
        v1 = client.CoreV1Api()
        for _ in range(30):  # Retry up to 30 times with a 2-second interval
            svc = v1.read_namespaced_service(service_name, namespace)
            if svc.spec.cluster_ip:
                return svc.spec.cluster_ip
            time.sleep(2)
        logger.error(f"Failed to get IP for service {service_name}")
        return None

    def _parse_hostname(self, url: str) -> str:
        # if there's no scheme, prepend one
        if not url:
            raise ValueError("URL cannot be None or empty")
        if "://" not in url:
            url = f"http://{url}"
        return urlparse(url).netloc, urlparse(url).scheme

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

                        node_formatted = {
                            "node_name": node.get("node_name"),
                            "node_id": node.get("node_id"),
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
        values["nfs_server"] = self.get_nfs_service_ip()
        values["image_pull_secrets"] = self.get_image_pull_secret()
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

        pod_status = None
        configmap_data = None
        if result["status"] == "successful":
            for event in result["events"]:
                if event["task"] == "Get Pod status" and event["status"] == "runner_on_ok":
                    pod_status = event["event_data"]["res"]["resources"][0]["status"]["phase"]
                if event["task"] == "Get ConfigMap data" and event["status"] == "runner_on_ok":
                    configmap_data = event["event_data"]["res"]["resources"][0]["data"]

        transfer_status = {"status": "inprogress"}
        if not pod_status or pod_status == "Failed" or not configmap_data:
            transfer_status["status"] = "failed"
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
        values["image_pull_secrets"] = self.get_image_pull_secret()
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

    def delete_namespace(self, namespace: str) -> None:
        """Delete the runtime on the Kubernetes cluster."""
        result = self.ansible_executor.run_playbook(
            playbook="DELETE_NAMESPACE", extra_vars={"kubeconfig_content": self.config, "namespace": namespace}
        )
        return result["status"]

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

    def verify_ingress_health(self, namespace: str, cloud_model: bool = False) -> bool:
        """Verify the ingress health by checking if the model is available in the models list."""
        ingress_url = self.get_ingress_url(namespace)
        models_url = f"{ingress_url}/v1/models"
        headers = {}
        if cloud_model:
            headers["Authorization"] = f"Bearer {secrets_settings.litellm_master_key}"

        try:
            response = requests.get(models_url, headers=headers, timeout=30)
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

    def identify_supported_endpoints(self, namespace: str, cloud_model: bool = False) -> Dict[str, bool]:
        """Identify which endpoints are supported by checking if they return 200 status.

        Args:
            namespace (str): The namespace/model name to check
            cloud_model (bool): Whether this is a cloud model requiring authentication

        Returns:
            Dict[str, bool]: A dictionary mapping endpoint paths to their availability status
        """
        ingress_url = self.get_ingress_url(namespace)
        headers = {}
        if cloud_model:
            headers["Authorization"] = f"Bearer {secrets_settings.litellm_master_key}"

        # Define endpoints to check
        endpoints_to_check = [
            "/v1/embeddings",
            "/v1/chat/completions",
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
                if endpoint in ["/v1/embeddings", "/v1/chat/completions", "/v1/completions"]:
                    if endpoint == "/v1/embeddings":
                        payload = {"model": namespace, "input": "test"}
                    elif endpoint == "/v1/chat/completions":
                        payload = {
                            "model": namespace,
                            "messages": [{"role": "user", "content": "test"}],
                            "max_tokens": 1,
                        }
                    else:  # /v1/completions
                        payload = {"model": namespace, "prompt": "test", "max_tokens": 1}

                    headers["Content-Type"] = "application/json"
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                else:
                    # GET endpoints
                    response = requests.get(url, headers=headers, timeout=10)

                # Check if endpoint is supported (200 OK or other success codes)
                supported_endpoints[endpoint] = response.status_code in [200, 201, 202, 204]
                logger.debug(f"Endpoint {endpoint} returned status code {response.status_code}")

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
                                cores=int(pod["spec"]["containers"][0]["resources"]["requests"].get("cpu", 0)),
                                memory=pod["spec"]["containers"][0]["resources"]["requests"].get("memory", "0"),
                                deployment_name=deploy_info["metadata"]["name"],
                                concurrency=pod["metadata"]["labels"].get("concurrency", 100),
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

    def get_deployment_status(self, values: dict, cloud_model: bool = False, ingress_health: bool = True) -> str:
        """Get the status of a deployment on the Kubernetes cluster."""
        if not self.ingress_url:
            raise KubernetesException("Ingress URL is not set")

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

        ingress_health = (
            self.verify_ingress_health(values["namespace"], cloud_model=cloud_model) if ingress_health else True
        )
        # ingress health can be checked only if workers are available
        if not ingress_health and worker_data_list:
            pod_status["status"] = DeploymentStatusEnum.INGRESS_FAILED
        elif not worker_data_list:
            pod_status["status"] = DeploymentStatusEnum.FAILED

        return {
            "status": pod_status["status"],
            "replicas": pod_status,
            "ingress_health": ingress_health,
            "worker_data_list": worker_data_list,
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
            cores=int(pod["spec"]["containers"][0]["resources"]["requests"].get("cpu", 0)),
            memory=pod["spec"]["containers"][0]["resources"]["requests"].get("memory", 0),
            deployment_name="litellm-container"
            if pod["metadata"]["name"].startswith("litellm-container")
            else "bud-runtime-container",
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
            v1 = client.CoreV1Api()

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
            v1 = client.CoreV1Api()

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
            v1 = client.CoreV1Api()

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
        values["image_pull_secrets"] = self.get_image_pull_secret()
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

    def get_adapter_status(self, adapter_name: str):
        """Get the status of a adapter."""
        return self.verify_ingress_health(adapter_name)
