import asyncio
import copy
import json
import re
import uuid
from typing import Any, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from budmicroframe.commons.logging import get_logger

# from ..shared.dapr_service import DaprService
from budmicroframe.shared.http_client import AsyncHTTPClient

from ..cluster_ops import (
    apply_security_context,
    delete_namespace,
    delete_pod,
    deploy_quantization_job,
    deploy_runtime,
    get_adapter_status,
    get_deployment_status,
    get_model_transfer_status,
    get_pod_logs,
    get_pod_status,
    get_quantization_status,
    identify_supported_endpoints,
    transfer_model,
)
from ..commons.config import app_settings, secrets_settings
from ..commons.constants import ClusterPlatformEnum
from ..device_mapping import ClusterDeviceValidator, DeviceMappingRegistry
from .schemas import GetDeploymentConfigRequest, WorkerInfo


logger = get_logger(__name__)


class DeploymentHandler:
    """DeploymentHandler is responsible for handling the deployment of nodes using Helm.

    This class provides methods to initialize the deployment handler with a given configuration,
    generate unique namespaces, and deploy nodes with specified configurations.

    Attributes:
        config (dict): Configuration dictionary for the deployment handler.
    """

    def __init__(self, config: dict):
        """Initialize the DeploymentHandler with the given configuration.

        Args:
            config (dict): Configuration dictionary for the deployment handler.
        """
        self.config = config

    def _get_namespace(self, endpoint_name: str):
        # Generates a unique 8-character identifier
        unique_id = uuid.uuid4().hex[:8]
        # Clean the enpoint name by replacing non-alphanumeric characters with hyphens
        cleaned_name = re.sub(r"[^a-zA-Z0-9-]", "-", endpoint_name).lower()
        # return "llama-test-f94b"
        return f"bud-{cleaned_name}-{unique_id}"

    def _get_cpu_affinity(self, tp_size: int):
        # TODO: Make this dynamic based on the number of NUMA nodes in the cluster
        cpu_affinity = []
        available_numa = [0, 1, 2, 3, 4, 5, 6, 7]

        if tp_size > len(available_numa):
            raise ValueError(
                f"Requested tensor parallel size {tp_size} is greater than the number of available NUMA nodes {len(available_numa)}"
            )

        for numa in available_numa[:tp_size]:
            cpu_affinity.append(f"{numa * 14}-{(numa + 1) * 14 - 2}")
        thread_bind = "|".join(cpu_affinity)
        return thread_bind, tp_size * 26

    def _prepare_args(self, args: dict):
        args_list = []
        for key, value in args.items():
            if value is True:
                args_list.append(f"--{key}")
            elif value is False:
                continue
            else:
                args_list.append(f"--{key}={value}")
        return args_list

    def _parse_hostname(self, url: str) -> str:
        # if there's no scheme, prepend one
        if "://" not in url:
            url = f"http://{url}"
        return urlparse(url).netloc

    def _get_memory_size(self, node_list: List[dict]) -> int:
        """Get memory size from node list, supporting both legacy and new formats.

        Args:
            node_list: List of node configurations

        Returns:
            Memory size in GB
        """
        memory_size = 0
        for node in node_list:
            if "memory" in node:
                # New node group format: memory directly on node
                memory_size = node["memory"]
                logger.info(f"Using memory from node group format: {memory_size} bytes")
                break
            elif "devices" in node and node["devices"]:
                # Legacy format: memory in devices array
                for device in node["devices"]:
                    memory_size = device["memory"]
                    logger.warning("Using memory from legacy devices format - consider migrating to node groups")
                    break
                break
            else:
                logger.warning(f"Node {node.get('name', 'unknown')} has no memory information")

        if memory_size == 0:
            logger.warning("No memory size found in node list, using default")
            memory_size = 1024**3  # 1GB default

        return memory_size / (1024**3)

    def deploy(
        self,
        node_list: List[dict],
        endpoint_name: str = None,
        hf_token: str = None,
        namespace: str = None,
        ingress_url: str = None,
        platform: Optional[ClusterPlatformEnum] = None,
        add_worker: bool = False,
        adapters: List[dict] = None,
        delete_on_failure: bool = True,
        podscaler: dict = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        tool_calling_parser_type: Optional[str] = None,
        reasoning_parser_type: Optional[str] = None,
        enable_tool_calling: Optional[bool] = None,
        enable_reasoning: Optional[bool] = None,
        chat_template: Optional[str] = None,
    ):
        """Deploy nodes using Helm.

        Args:
            node_list (List[dict]): List of nodes to be deployed, each represented as a dictionary.
            endpoint_name (str, optional): Name of the endpoint for the deployment. Defaults to None.
            hf_token (str, optional): Hugging Face token for authentication. Defaults to None.
            namespace (str, optional): Kubernetes namespace for deployment. If None, generated from endpoint_name.
            ingress_url (str, optional): URL for the ingress endpoint. Required for deployment.
            platform (ClusterPlatformEnum, optional): Platform type for the cluster deployment.
            add_worker (bool, optional): Whether to add a worker node. Defaults to False.
            adapters (List[dict], optional): List of model adapters to deploy. Defaults to None.
            delete_on_failure (bool, optional): Whether to delete resources on failure. Defaults to True.
            chat_template (str, optional): Chat template to use for the model. Defaults to None.
            podscaler (dict, optional): Pod autoscaling configuration. Defaults to None.
            input_tokens (Optional[int], optional): Average input/context tokens. Defaults to None.
            output_tokens (Optional[int], optional): Average output/sequence tokens. Defaults to None.
            tool_calling_parser_type (Optional[str], optional): Parser type for tool calling. Defaults to None.
            reasoning_parser_type (Optional[str], optional): Parser type for reasoning. Defaults to None.
            enable_tool_calling (Optional[bool], optional): Enable tool calling feature. Defaults to None.
            enable_reasoning (Optional[bool], optional): Enable reasoning feature. Defaults to None.

        Raises:
            ValueError: If the device configuration is missing required keys or if ingress_url is not provided.
            Exception: If the deployment fails.

        Returns:
            tuple: Contains (status, namespace, deployment_url, number_of_nodes, node_list).
        """
        if namespace is None:
            if endpoint_name is None:
                raise ValueError("Either namespace or endpoint_name must be provided")
            namespace = self._get_namespace(endpoint_name)

        if ingress_url is None:
            raise ValueError("ingress_url is required")

        values = {
            "hf_token": hf_token,
            "namespace": namespace,
            "nodes": [],
            "container_port": app_settings.engine_container_port,
            "ingress_host": ingress_url,
            "volume_type": app_settings.volume_type,
            "model_name": namespace,
            "adapters": adapters,
        }

        if not podscaler:
            podscaler = {}
        values["podscaler"] = {
            "enabled": bool(podscaler and podscaler.get("enabled", False)) if podscaler else False,
            "minReplicas": podscaler.get("minReplicas", 1),
            "maxReplicas": podscaler.get("maxReplicas", 2),
            "upFluctuationTolerance": podscaler.get("scaleUpTolerance", 1.5),
            "downFluctuationTolerance": podscaler.get("scaleDownTolerance", 0.5),
            "window": podscaler.get("window", 30),
            "targetMetric": podscaler.get("scalingMetric", "gpu_cache_usage_perc"),
            "targetValue": podscaler.get("scalingValue", 0.5),
            "type": podscaler.get("scalingType", "metrics"),
        }

        full_node_list = copy.deepcopy(node_list)

        max_loras = 1 if not adapters else max(1, len(adapters))

        for idx, node in enumerate(node_list):
            node["args"]["gpu-memory-utilization"] = 0.95
            node["args"]["max-loras"] = max_loras
            node["args"]["max-lora-rank"] = 256
            # node["args"]["pipeline-parallel-size"] = 2
            # node["pp_size"] = 2

            node["args"] = self._prepare_args(node["args"])
            node["args"].append(f"--served-model-name={namespace}")
            node["args"].append("--enable-lora")

            # Calculate max_model_len dynamically
            if input_tokens and output_tokens:
                max_model_len = int((input_tokens + output_tokens) * 1.1)  # Add 10% safety margin
                node["args"].append(f"--max-model-len={max_model_len}")
            else:
                node["args"].append("--max-model-len=8192")  # Default fallback

            # Add parser configuration if enabled
            if enable_tool_calling and tool_calling_parser_type:
                node["args"].append("--enable-auto-tool-choice")
                node["args"].append(f"--tool-call-parser={tool_calling_parser_type}")
                logger.info(f"Enabled tool calling with parser: {tool_calling_parser_type}")
                # Add chat template if provided
                if chat_template:
                    node["args"].append(f"--chat-template={chat_template}")
                    logger.info(f"Using chat template: {chat_template}")

            if enable_reasoning and reasoning_parser_type:
                # Add reasoning-specific args based on parser type
                node["args"].append(f"--reasoning-parser={reasoning_parser_type}")
                # Add other reasoning parser configurations as needed

            # Update the full_node_list with the modified args
            full_node_list[idx]["args"] = node["args"].copy()

            # thread_bind, core_count = self._get_cpu_affinity(device["tp_size"])
            # node["envs"]["VLLM_CPU_OMP_THREADS_BIND"] = thread_bind
            node["envs"]["VLLM_LOGGING_LEVEL"] = "INFO"
            # node["envs"]["VLLM_SKIP_WARMUP"] = "true"
            node["envs"]["VLLM_ALLOW_RUNTIME_LORA_UPDATING"] = "True"
            # node["core_count"] = core_count if device["type"] == "cpu" else 1
            node["memory"] = node["memory"] / (1024**3)
            node["name"] = self._to_k8s_label(node["name"])

            # Add device mapping for node selector
            device_name = node.get("device_name") or node.get("name", "")
            device_type = node.get("type", "cpu")
            device_model = node.get("device_model", "")

            # Get node selector labels from device mapping
            node_selector = DeviceMappingRegistry.get_node_selector_for_device(
                device_name=device_name,
                device_type=device_type,
                device_model=device_model,
                raw_name=node.get("raw_name", ""),
            )

            # Add node selector to the node configuration
            node["node_selector"] = node_selector
            logger.info(f"Generated node selector for device {device_name} ({device_type}): {node_selector}")

            values["nodes"].append(node)

        # Validate device availability before deployment
        try:
            kubeconfig_path = self.config.get("kubeconfig_path")
            if kubeconfig_path:
                validator = ClusterDeviceValidator(kubeconfig_path)

                for node in values["nodes"]:
                    device_name = node.get("device_name") or node.get("name", "")
                    device_type = node.get("type", "cpu")
                    replicas = node.get("replicas", 1)
                    tp_size = node.get("tp_size", 1)
                    pp_size = node.get("pp_size", 1)

                    # Calculate total devices needed
                    required_devices = replicas * tp_size * pp_size

                    is_available, error_msg, available_nodes = validator.validate_device_availability(
                        device_name=device_name, device_type=device_type, required_count=required_devices
                    )

                    if not is_available:
                        logger.warning(f"Device validation warning for {device_name}: {error_msg}")
                        logger.info(f"Available nodes: {available_nodes}")
                        # Continue deployment with warning for now, but log the issue
                    else:
                        logger.info(
                            f"Device validation passed for {device_name}: {len(available_nodes)} suitable nodes available"
                        )
            else:
                logger.warning("No kubeconfig path provided, skipping device availability validation")
        except Exception as e:
            logger.warning(f"Device validation failed (deployment will continue): {str(e)}")

        try:
            logger.info(f"Values for local model deployment: {values}")
            number_of_nodes = len(values["nodes"])
            status = asyncio.run(apply_security_context(self.config, values["namespace"]))
            status, deployment_url = asyncio.run(
                deploy_runtime(self.config, values, platform=platform, delete_on_failure=delete_on_failure)
            )
            return status, values["namespace"], deployment_url, number_of_nodes, full_node_list

        except Exception as e:
            raise Exception(f"Deployment failed: {str(e)}") from e

    def cloud_model_deploy(
        self,
        node_list: List[dict],
        endpoint_name: str,
        model: str,
        credential_id: UUID,
        ingress_url: str,
        platform: Optional[ClusterPlatformEnum] = None,
        namespace: str = None,
        add_worker: bool = False,
        use_tensorzero: bool = False,
        provider: str = None,
    ):
        """Deploy cloud model nodes using Helm.

        Args:
            node_list (List[dict]): List of nodes to be deployed.
            endpoint_name (str): Name of the endpoint for the deployment.
            credential_id (UUID): Unique identifier for the cloud provider credentials.
            use_tensorzero (bool): Whether to use TensorZero instead of LiteLLM.

        Returns:
            tuple: A tuple containing (deployment_status, namespace).

        Raises:
            ValueError: If the device configuration is missing required keys.
            Exception: If the deployment fails.
        """
        if use_tensorzero:
            return self.tensorzero_deploy(
                node_list=node_list,
                endpoint_name=endpoint_name,
                model=model,
                credential_id=credential_id,
                ingress_url=ingress_url,
                platform=platform,
                namespace=namespace,
                add_worker=add_worker,
                provider=provider,
            )
        values = {
            "namespace": namespace or self._get_namespace(endpoint_name),
            "nodes": [],
            "service_type": "ClusterIP",
            "pull_policy": "IfNotPresent",
            "container_port": app_settings.litellm_server_port,
            # TODO: uncomment when ingress issue is resolved
            # currently if we don't send ingress_host, default value from values.yaml will be used
            "ingress_host": ingress_url,
        }
        values["model_name"] = values["namespace"]

        # TODO: to be stored and fetched from dapr secret-store
        proprietary_credential = asyncio.run(BudserveHandler().get_credential_details(credential_id))

        values["proxy_config"] = {
            "model_list": [
                {
                    "model_name": values["namespace"],
                    "litellm_params": {
                        "model": model,
                        "drop_params": True,
                        **proprietary_credential["other_provider_creds"],
                    },
                }
            ],
            "general_settings": {"master_key": secrets_settings.litellm_master_key},
        }

        for node in node_list:
            node_values = {"name": node["name"], "devices": []}
            for device in node["devices"]:
                if not all(key in device for key in ("image", "replica", "memory", "num_cpus", "concurrency")):
                    raise ValueError(f"Device configuration is missing required keys: {device}")
                device["core_count"] = device["num_cpus"]
                device["name"] = self._to_k8s_label(device["name"])
                node_values["devices"].append(device)
            values["nodes"].append(node_values)
        try:
            logger.info(f"Values for cloud model deployment: {values}")
            number_of_nodes = len(values["nodes"])
            status, deployment_url = asyncio.run(deploy_runtime(self.config, values, "DEPLOY_CLOUD_MODEL", platform))
            return status, values["namespace"], deployment_url, number_of_nodes, node_list

        except Exception as e:
            raise Exception(f"Deployment failed: {str(e)}") from e

    def tensorzero_deploy(
        self,
        node_list: List[dict],
        endpoint_name: str,
        model: str,
        credential_id: UUID,
        ingress_url: str,
        platform: Optional[ClusterPlatformEnum] = None,
        namespace: str = None,
        add_worker: bool = False,
        provider: str = None,
    ):
        """Deploy cloud model using TensorZero gateway.

        Args:
            node_list (List[dict]): List of nodes to be deployed.
            endpoint_name (str): Name of the endpoint for the deployment.
            model (str): Model name to deploy.
            credential_id (UUID): Unique identifier for the cloud provider credentials.
            ingress_url (str): Ingress URL for the deployment.
            platform (Optional[ClusterPlatformEnum]): Platform type.
            namespace (str): Kubernetes namespace.
            add_worker (bool): Whether to add a worker.

        Returns:
            tuple: A tuple containing (deployment_status, namespace, deployment_url, number_of_nodes, node_list).

        Raises:
            ValueError: If the device configuration is missing required keys.
            Exception: If the deployment fails.
        """
        if namespace is None:
            namespace = self._get_namespace(endpoint_name)
        values = {
            "namespace": namespace,
            "modelName": namespace,
            "gateway": {
                "image": {
                    "repository": app_settings.tensorzero_image.rsplit(":", 1)[0]
                    if ":" in app_settings.tensorzero_image
                    else app_settings.tensorzero_image,
                    "tag": app_settings.tensorzero_image.rsplit(":", 1)[1]
                    if ":" in app_settings.tensorzero_image
                    else "latest",
                },
                "service": {
                    "port": 3000,  # TensorZero default port
                },
            },
            "ingress_host": ingress_url,
        }

        # Get credentials
        proprietary_credential = asyncio.run(BudserveHandler().get_credential_details(credential_id))

        # Configure TensorZero config map
        provider_type = provider or "openai"  # Default to OpenAI compatible
        api_key = proprietary_credential["other_provider_creds"].get("api_key", "")

        # Build the tensorzero.toml configuration
        toml_config = f"""[gateway]
bind_address = "0.0.0.0:3000"

[gateway.authentication]
enabled = false

[models."{namespace}"]
routing = ["{provider_type}"]

[models."{namespace}".providers.{provider_type}]
type = "{provider_type}"
model_name = "{model}"
api_key_location = "env::API_KEY"
"""

        values["configMap"] = {"data": {"tensorzero.toml": toml_config}}

        # Add credentials to Kubernetes secret
        values["credentials"] = {"api_key": api_key}

        try:
            logger.info(f"Values for TensorZero deployment: {values}")
            status, deployment_url = asyncio.run(deploy_runtime(self.config, values, "DEPLOY_TENSORZERO", platform))
            return status, values["namespace"], deployment_url, 1, node_list

        except Exception as e:
            raise Exception(f"TensorZero deployment failed: {str(e)}") from e

    # TODO: Update this to use proper PVC with shared storage
    def transfer_model(
        self,
        model_uri: str,
        endpoint_name: str,
        node_list: List[dict],
        platform: Optional[ClusterPlatformEnum] = None,
        namespace: str = None,
    ):
        """Transfer model to the pod."""
        model_uri = [part for part in model_uri.split("/") if part]
        model_uri = model_uri[-1]
        namespace = namespace or self._get_namespace(endpoint_name)
        values = {
            "source_model_path": model_uri,
            "namespace": namespace,
            "minio_endpoint": app_settings.minio_endpoint,
            "minio_secure": app_settings.minio_secure,
            "minio_access_key": secrets_settings.minio_access_key,
            "minio_secret_key": secrets_settings.minio_secret_key,
            "minio_bucket": app_settings.minio_bucket,
            "model_size": self._get_memory_size(node_list),
            "nodes": node_list,
            "volume_type": app_settings.volume_type,
        }
        try:
            return asyncio.run(transfer_model(self.config, values, platform)), namespace
        except Exception as e:
            raise Exception(f"Transfer model failed: {str(e)}") from e

    def get_model_transfer_status(self, namespace: str):
        """Get the status of a model transfer."""
        values = {"namespace": namespace}
        try:
            return asyncio.run(get_model_transfer_status(self.config, values))
        except Exception as e:
            raise Exception(f"Failed to get model transfer status: {str(e)}") from e

    def delete(self, namespace: str, platform: Optional[ClusterPlatformEnum] = None):
        """Delete a deployment by namespace."""
        try:
            asyncio.run(delete_namespace(self.config, namespace, platform))
        except Exception as e:
            raise Exception(f"Deletion failed: {str(e)}") from e

    def delete_pod(
        self, namespace: str, deployment_name: str, pod_name: str, platform: Optional[ClusterPlatformEnum] = None
    ):
        """Delete a pod by namespace and pod name."""
        try:
            return asyncio.run(delete_pod(self.config, namespace, deployment_name, pod_name, platform))
        except Exception as e:
            raise Exception(f"Deletion failed: {str(e)}") from e

    def get_deployment_status(
        self,
        namespace: str,
        ingress_url: str,
        cloud_model: bool = False,
        platform: Optional[ClusterPlatformEnum] = None,
        ingress_health: bool = True,
    ):
        """Get the status of a deployment by namespace."""
        return asyncio.run(
            get_deployment_status(
                self.config, ingress_url, {"namespace": namespace}, cloud_model, platform, ingress_health
            )
        )

    async def get_pod_status(self, namespace: str, pod_name: str, platform: Optional[ClusterPlatformEnum] = None):
        """Get the status of a pod by namespace and pod name."""
        return await get_pod_status(self.config, namespace, pod_name, platform)

    async def get_pod_logs(self, namespace: str, pod_name: str, platform: Optional[ClusterPlatformEnum] = None):
        """Get the logs of a pod by namespace and pod name."""
        return await get_pod_logs(self.config, namespace, pod_name, platform)

    def _transform_workers_info(self, workers_info: List[WorkerInfo]) -> dict:
        worker_info_dict = {}
        for worker in workers_info:
            node_name = worker.node_name
            device_name = self._to_k8s_label(worker.device_name)
            if node_name not in worker_info_dict:
                worker_info_dict[node_name] = {device_name: [worker]}
            else:
                if device_name not in worker_info_dict[node_name]:
                    worker_info_dict[node_name][device_name] = [worker]
                else:
                    worker_info_dict[node_name][device_name].append(worker)
        return worker_info_dict

    def _to_k8s_label(self, label: str):
        # Convert to lowercase
        label = label.lower()
        # Replace invalid characters with a hyphen
        label = re.sub(r"[^a-z0-9]+", "-", label)
        # Ensure it starts and ends with an alphanumeric character
        label = re.sub(r"^-+|-+$", "", label)
        return label

    def deploy_quantization(
        self,
        namespace: str,
        qunatization_config: dict = None,
        hf_token: str = None,
    ):
        """Deploy quantization job."""
        values = {
            "hf_token": hf_token,
            "namespace": namespace,
            "volume_type": app_settings.volume_type,
            "quantization_job_image": app_settings.quantization_job_image,
            "quantization_config": qunatization_config,
        }

        try:
            logger.info(f"Values for local model deployment: {values}")
            status = asyncio.run(deploy_quantization_job(self.config, values))
            return status

        except Exception as e:
            raise Exception(f"Deployment failed: {str(e)}") from e

    def get_quantization_status(self, namespace: str):
        """Get the status of a quantization job."""
        try:
            return asyncio.run(get_quantization_status(self.config, {"namespace": namespace}))
        except Exception as e:
            raise Exception(f"Failed to get quantization status: {str(e)}") from e

    def get_adapter_status(self, adapter_name: str, ingress_url: str):
        """Get the status of a adapter."""
        try:
            logger.info(f"within handler: {adapter_name}")
            return asyncio.run(get_adapter_status(self.config, adapter_name, ingress_url))
        except Exception as e:
            raise Exception(f"Failed to get adapter status: {str(e)}") from e

    def identify_supported_endpoints(self, namespace: str, cloud_model: bool = False, ingress_url: str = None):
        """Identify which endpoints are supported by checking if they return 200 status."""
        try:
            return asyncio.run(identify_supported_endpoints(self.config, namespace, cloud_model, ingress_url))
        except Exception as e:
            raise Exception(f"Failed to identify supported endpoints: {str(e)}") from e


class SimulatorHandler:
    """SimulatorHandler is responsible for interacting with the bud-simulator service."""

    async def get_cluster_simulator_config(
        self,
        cluster_id: UUID,
        simulator_id: UUID,
        concurrency: Optional[int] = None,
        feedback: Optional[list[dict[str, Any]]] = None,
    ):
        """Get the configuration of a simulator by cluster id and simulator id.

        Returns:
            tuple: (node_list, metadata) where metadata contains parser information
        """
        get_deployment_config_request = GetDeploymentConfigRequest(
            workflow_id=simulator_id,
            cluster_id=cluster_id,
            concurrency=concurrency,
            feedback=feedback,
        )
        logger.info(f"Getting simulator config for : {get_deployment_config_request}")
        try:
            url = f"http://localhost:{app_settings.dapr_http_port}/v1.0/invoke/budsim/method/simulator/configurations"
            async with AsyncHTTPClient() as http_client:
                response = await http_client.send_request(
                    "POST",
                    url,
                    json=get_deployment_config_request.model_dump(mode="json"),
                    follow_redirects=True,
                )
                response_str = response.body.decode("utf-8")
                logger.info(f"Response from budsim: {response_str}")
                if response.status_code != 200:
                    raise Exception(f"Failed to get simulator configurations: {response_str}")
                response_data = json.loads(response_str)

                # Extract parser metadata from response
                metadata = {
                    "tool_calling_parser_type": response_data.get("tool_calling_parser_type"),
                    "reasoning_parser_type": response_data.get("reasoning_parser_type"),
                    "chat_template": response_data.get("chat_template"),
                }

                # Handle both legacy nodes[] and new node_groups[] formats
                node_groups = response_data.get("node_groups", [])
                legacy_nodes = response_data.get("nodes", [])

                if node_groups:
                    # New format: return node groups directly
                    # Device mapping will be handled later in DeploymentHandler.deploy()
                    logger.info(f"Received {len(node_groups)} node groups from budsim")
                    node_list = node_groups
                else:
                    # Legacy format: use nodes directly (deprecated)
                    logger.warning("Received legacy nodes format from budsim - this is deprecated")
                    node_list = legacy_nodes

        except Exception as e:
            raise Exception(f"Failed to get simulator config: {str(e)}") from e
        return node_list, metadata


class BudserveHandler:
    """BudserveHandler is responsible for interacting with the bud-serve service."""

    async def get_credential_details(self, credential_id: UUID):
        """Get the details of a credential by credential id."""
        async with AsyncHTTPClient() as http_client:
            response = await http_client.send_request(
                "GET",
                f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_app_id}/method/proprietary/credentials/{credential_id}/details",
                follow_redirects=True,
            )
            response_str = response.body.decode("utf-8")
            if response.status_code != 200:
                raise Exception(f"Failed to get credential details: {response_str}")
            response_data = json.loads(response_str)
            if response_data["success"]:
                return response_data["result"]
            raise Exception(response_data["message"])
