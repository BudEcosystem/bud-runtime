import asyncio
import copy
import json
import math
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
from .engine_processors import get_default_autoscale_metric, get_engine_processor, validate_autoscale_metric
from .schemas import GetDeploymentConfigRequest, WorkerInfo


logger = get_logger(__name__)

# CPU deployment memory and resource constants
CPU_MEMORY_MULTIPLIER = 1.7  # Accounts for runtime overhead, activation memory, safety margin
CPU_MIN_MEMORY_GB = 10  # Minimum memory allocation for CPU nodes
SHARED_MODE_CORE_RATIO = 0.1  # CPU request ratio for shared mode (10% of limit)


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
        # Clean the endpoint name by replacing non-alphanumeric characters with hyphens
        cleaned_name = re.sub(r"[^a-zA-Z0-9-]", "-", endpoint_name).lower()
        # Remove consecutive hyphens
        cleaned_name = re.sub(r"-+", "-", cleaned_name).strip("-")
        # Kubernetes namespace limit is 63 characters
        # Format: bud-{cleaned_name}-{unique_id}
        # Reserved: "bud-" (4) + "-" (1) + unique_id (8) = 13 characters
        # Max cleaned_name length: 63 - 13 = 50 characters
        max_name_length = 50
        cleaned_name = cleaned_name[:max_name_length].rstrip("-")
        if not cleaned_name:
            cleaned_name = "benchmark"
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
        """Get maximum memory size from node list for PVC sizing fallback.

        This method calculates the maximum memory across all nodes as a fallback
        for PVC sizing when actual storage size is not available. For shared
        deployments, all replicas share the same PVC, so we use the maximum
        memory requirement.

        Args:
            node_list: List of node configurations

        Returns:
            Maximum memory size in GB across all nodes
        """
        max_memory_bytes = 0
        nodes_with_memory = 0

        for node in node_list:
            node_memory = 0
            if "memory" in node:
                # New node group format: memory directly on node
                node_memory = node["memory"]
                logger.debug(f"Node {node.get('name', 'unknown')}: {node_memory} bytes")
            elif "devices" in node and node["devices"]:
                # Legacy format: memory in devices array
                for device in node["devices"]:
                    if "memory" in device:
                        node_memory = device["memory"]
                        logger.warning(
                            f"Node {node.get('name', 'unknown')} using legacy devices format - "
                            "consider migrating to node groups"
                        )
                        break

            if node_memory > 0:
                nodes_with_memory += 1
                max_memory_bytes = max(max_memory_bytes, node_memory)

        if max_memory_bytes == 0:
            logger.warning(f"No memory size found in node list, using default of {CPU_MIN_MEMORY_GB}GB")
            max_memory_bytes = CPU_MIN_MEMORY_GB * (1024**3)  # Default for models
        else:
            logger.info(
                f"Calculated maximum memory from {nodes_with_memory} nodes: {max_memory_bytes / (1024**3):.2f} GB"
            )

        return max_memory_bytes / (1024**3)

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
        default_storage_class: Optional[str] = None,
        default_access_mode: Optional[str] = None,
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
            default_storage_class (Optional[str], optional): Default storage class for PVCs. Defaults to None.

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
            "skipMasterNodeForCpu": app_settings.skip_master_node_for_cpu,
        }

        # Add storage class configuration if provided, otherwise fall back to default
        if default_storage_class:
            values["storageClass"] = default_storage_class
            logger.info(f"Using custom storage class: {default_storage_class}")
        else:
            # Check if there's an app setting default, otherwise let Helm chart handle it
            if hasattr(app_settings, "default_storage_class") and app_settings.default_storage_class:
                values["storageClass"] = app_settings.default_storage_class
                logger.info(f"Using app default storage class: {app_settings.default_storage_class}")
            else:
                logger.info("No storage class specified, using Helm chart default")

        access_mode = default_access_mode or "ReadWriteOnce"

        if default_access_mode:
            logger.info(f"Using provided access mode: {default_access_mode}")
        else:
            # Determine access mode based on storage class capabilities
            try:
                from ..cluster_ops.kubernetes import KubernetesHandler

                k8s_handler = KubernetesHandler(self.config)
                storage_classes = k8s_handler.get_storage_classes()

                # Find the storage class we're using
                target_storage_class = values.get("storageClass")
                if target_storage_class and target_storage_class != "default":
                    for sc in storage_classes:
                        if sc["name"] == target_storage_class:
                            access_mode = sc["recommended_access_mode"]
                            logger.info(f"Using access mode {access_mode} for storage class {target_storage_class}")
                            break
                else:
                    # Use default storage class
                    for sc in storage_classes:
                        if sc["default"]:
                            access_mode = sc["recommended_access_mode"]
                            logger.info(f"Using access mode {access_mode} for default storage class {sc['name']}")
                            break
            except Exception as e:
                logger.warning(f"Could not determine optimal access mode, using {access_mode}: {e}")

        values["accessMode"] = access_mode

        if not podscaler:
            podscaler = {}

        # Determine engine type from first node for autoscaling metric selection
        # All nodes in a deployment should use the same engine type
        first_node_engine = node_list[0].get("engine_type", "vllm") if node_list else "vllm"
        default_metric = get_default_autoscale_metric(first_node_engine)

        # Validate user-provided autoscale metric against engine capabilities
        user_metric = podscaler.get("scalingMetric") if podscaler else None
        if user_metric:
            validate_autoscale_metric(first_node_engine, user_metric)
            logger.info(f"Validated autoscale metric '{user_metric}' for engine '{first_node_engine}'")

        values["podscaler"] = {
            "enabled": bool(podscaler and podscaler.get("enabled", False)) if podscaler else False,
            "minReplicas": podscaler.get("minReplicas", 1),
            "maxReplicas": podscaler.get("maxReplicas", 2),
            "upFluctuationTolerance": podscaler.get("scaleUpTolerance", 1.5),
            "downFluctuationTolerance": podscaler.get("scaleDownTolerance", 0.5),
            "window": podscaler.get("window", 30),
            "targetMetric": podscaler.get("scalingMetric", default_metric),
            "targetValue": podscaler.get("scalingValue", 0.5),
            "type": podscaler.get("scalingType", "metrics"),
        }

        full_node_list = copy.deepcopy(node_list)

        for _idx, node in enumerate(node_list):
            # Determine engine type for this node (default to vllm for backward compatibility)
            engine_type = node.get("engine_type", "vllm")
            logger.info(f"Processing node {_idx} with engine type: {engine_type}")

            # Get the appropriate engine processor
            try:
                engine_processor = get_engine_processor(engine_type)
            except ValueError as e:
                logger.warning(f"Unknown engine type '{engine_type}', falling back to vllm: {e}")
                engine_type = "vllm"
                engine_processor = get_engine_processor("vllm")
                node["engine_type"] = "vllm"

            # Extract concurrency from labels (where budsim actually stores it)
            node_concurrency = node.get("labels", {}).get("concurrency", "1")
            node_concurrency = int(node_concurrency)  # Convert from string to int
            node["concurrency"] = node_concurrency  # Also preserve at top level for Helm template

            # Memory is already in GB from BudSim, no conversion needed
            # Use tiered buffer: 1GB for ≤10GB, 2GB for >10GB
            buffer_gb = 1 if node["memory"] <= 10 else 2
            allocation_memory_gb = max(node["memory"] + buffer_gb, 1)  # Ensure non-zero for division safety

            # Check for CPU device type and apply specific memory formula
            device_type = node.get("type", "cpu")
            if device_type == "cpu_high":
                weight_memory_gb = node.get("weight_memory_gb", 0)
                kv_cache_memory_gb = node.get("kv_cache_memory_gb", 0) if node.get("kv_cache_memory_gb", 0) > 4 else 4

                # If we have the detailed memory components, use the new formula
                if weight_memory_gb > 0 and kv_cache_memory_gb > 0:
                    # Formula: memory_allocation = total_memory * multiplier + kv_cache_memory
                    # Here "total_memory" is interpreted as model weights
                    raw_memory_gb = (weight_memory_gb * CPU_MEMORY_MULTIPLIER) + kv_cache_memory_gb
                    allocation_memory_gb = raw_memory_gb + buffer_gb
                    # Ensure a minimum allocation for CPU nodes
                    allocation_memory_gb = max(allocation_memory_gb, CPU_MIN_MEMORY_GB)
                    logger.info(
                        f"CPU Node {node.get('name')}: Calculated memory using formula "
                        f"({weight_memory_gb:.2f} * {CPU_MEMORY_MULTIPLIER} + {kv_cache_memory_gb:.2f}) + {buffer_gb} = {allocation_memory_gb:.2f} GB"
                    )

                    # Update node memory for consistency
                    node["memory"] = allocation_memory_gb
                else:
                    logger.warning(
                        f"CPU Node {node.get('name')}: Missing detailed memory components (weight: {weight_memory_gb}, kv: {kv_cache_memory_gb}). "
                        "Using default memory allocation."
                    )

                # Set core_count for CPU resource limits in Helm template
                # Priority: cores from budsim > physical_cores > default 14
                core_count = node.get("cores") or node.get("physical_cores") or 14
                node["core_count"] = core_count - 2

                # For shared mode, set CPU request to configured ratio of limit (minimum 1 core)
                # For dedicated mode, request equals limit
                hardware_mode = node.get("hardware_mode", "dedicated")
                if hardware_mode == "shared":
                    node["core_request"] = max(1, int(node["core_count"] * SHARED_MODE_CORE_RATIO))
                    logger.info(
                        f"CPU Node {node.get('name')}: Shared mode - core_request={node['core_request']}, core_limit={node['core_count']}"
                    )
                else:
                    node["core_request"] = node["core_count"]
                    logger.info(f"CPU Node {node.get('name')}: Dedicated mode - core_count={node['core_count']}")

            # Store allocation_memory_gb for engine processor use
            node["allocation_memory_gb"] = allocation_memory_gb

            # For shared hardware mode, calculate GPU memory limit in MB
            hardware_mode = node.get("hardware_mode", "dedicated")
            if hardware_mode == "shared":
                # Convert GB to MB for nvidia.com/gpumem resource limit
                gpu_memory_mb = int(allocation_memory_gb * 1024)
                node["gpu_memory_mb"] = gpu_memory_mb
                logger.debug(
                    f"Shared mode: Setting GPU memory limit to {gpu_memory_mb}MB ({allocation_memory_gb:.2f}GB)"
                )

            # Build context for engine processor
            engine_context = {
                "namespace": namespace,
                "concurrency": node_concurrency,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "enable_tool_calling": enable_tool_calling,
                "tool_calling_parser_type": tool_calling_parser_type,
                "enable_reasoning": enable_reasoning,
                "reasoning_parser_type": reasoning_parser_type,
                "chat_template": chat_template,
                "container_port": values["container_port"],
            }

            # Use engine processor to set args and envs
            engine_processor.process_args(node, engine_context)
            engine_processor.process_envs(node, engine_context)

            # Update the full_node_list with the modified args
            full_node_list[_idx]["args"] = node["args"].copy()

            # Convert args dict to list format (--key=value format) for all engines
            if isinstance(node["args"], dict):
                node["args"] = self._prepare_args(node["args"])

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
        default_storage_class: Optional[str] = None,
        default_access_mode: Optional[str] = None,
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

        # Add storage class configuration if provided, otherwise fall back to default
        if default_storage_class:
            values["storageClass"] = default_storage_class
            logger.info(f"Using custom storage class for cloud deployment: {default_storage_class}")
        else:
            # Check if there's an app setting default, otherwise let Helm chart handle it
            if hasattr(app_settings, "default_storage_class") and app_settings.default_storage_class:
                values["storageClass"] = app_settings.default_storage_class
                logger.info(
                    f"Using app default storage class for cloud deployment: {app_settings.default_storage_class}"
                )
            else:
                logger.info("No storage class specified for cloud deployment, using Helm chart default")

        access_mode = default_access_mode or "ReadWriteOnce"

        if default_access_mode:
            logger.info(f"Using provided access mode for cloud deployment: {default_access_mode}")
        else:
            # Determine access mode based on storage class capabilities
            try:
                from ..cluster_ops.kubernetes import KubernetesHandler

                k8s_handler = KubernetesHandler(self.config)
                storage_classes = k8s_handler.get_storage_classes()

                # Find the storage class we're using
                target_storage_class = values.get("storageClass")
                if target_storage_class and target_storage_class != "default":
                    for sc in storage_classes:
                        if sc["name"] == target_storage_class:
                            access_mode = sc["recommended_access_mode"]
                            logger.info(
                                "Using access mode %s for cloud deployment storage class %s",
                                access_mode,
                                target_storage_class,
                            )
                            break
                else:
                    # Use default storage class
                    for sc in storage_classes:
                        if sc["default"]:
                            access_mode = sc["recommended_access_mode"]
                            logger.info(
                                "Using access mode %s for cloud deployment default storage class %s",
                                access_mode,
                                sc["name"],
                            )
                            break
            except Exception as e:
                logger.warning(
                    "Could not determine optimal access mode for cloud deployment, using %s: %s",
                    access_mode,
                    e,
                )

        values["accessMode"] = access_mode
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
        default_storage_class: Optional[str] = None,
        default_access_mode: Optional[str] = None,
        storage_size_gb: Optional[float] = None,
    ):
        """Transfer model to the pod.

        Args:
            model_uri: The URI of the model to transfer
            endpoint_name: Name of the endpoint
            node_list: List of nodes for deployment
            platform: Optional cluster platform
            namespace: Optional Kubernetes namespace
            default_storage_class: Optional storage class for PVC creation
            default_access_mode: Optional access mode for PVC
            storage_size_gb: Actual model storage size in GB from MinIO
        """
        model_uri = [part for part in model_uri.split("/") if part]
        model_uri = model_uri[-1]
        namespace = namespace or self._get_namespace(endpoint_name)
        access_mode = default_access_mode or "ReadWriteOnce"
        if default_access_mode:
            logger.info(f"Model transfer using provided access mode: {default_access_mode}")

        # Calculate PVC size with validation
        if storage_size_gb and storage_size_gb > 0:
            # Use actual storage size from MinIO with 20% buffer for safety
            pvc_size_gb = math.ceil(storage_size_gb * 1.2)
            logger.info(
                f"Using actual model storage size: {storage_size_gb:.2f} GB, "
                f"PVC size with 20% buffer: {pvc_size_gb} GB"
            )
        else:
            # Fallback to memory-based calculation
            raw_size = self._get_memory_size(node_list) * 1.1
            pvc_size_gb = math.ceil(raw_size)
            logger.warning(f"Model storage size not available, using fallback calculation: {pvc_size_gb} GB")

        # Additional warning if below recommended minimum
        if pvc_size_gb < 1:
            pvc_size_gb = 1
            logger.warning(
                f"PVC size ({pvc_size_gb} GB) is below recommended minimum of 1 GB. Setting the value to 1 GB"
            )

        # Determine device type and hardware mode from node_list for model transfer affinity
        # CPU deployments need nodeAffinity to avoid master nodes
        # Shared mode needs podAffinity for bin-packing
        device_type = ""
        hardware_mode = "dedicated"
        if node_list:
            for node in node_list:
                if isinstance(node, dict):
                    if node.get("type"):
                        device_type = node.get("type")
                    if node.get("hardware_mode"):
                        hardware_mode = node.get("hardware_mode")
                    break

        values = {
            "source_model_path": model_uri,
            "namespace": namespace,
            "minio_endpoint": app_settings.minio_endpoint,
            "minio_secure": app_settings.minio_secure,
            "minio_access_key": secrets_settings.minio_access_key,
            "minio_secret_key": secrets_settings.minio_secret_key,
            "minio_bucket": app_settings.minio_bucket,
            "model_size": pvc_size_gb,
            "nodes": node_list,
            "volume_type": app_settings.volume_type,
            "deviceType": device_type,
            "hardwareMode": hardware_mode,
            "skipMasterNodeForCpu": app_settings.skip_master_node_for_cpu,
        }

        # Add storage class configuration if provided
        if default_storage_class:
            values["storageClass"] = default_storage_class
            logger.info(f"Model transfer using storage class: {default_storage_class}")

            # Determine if we should use local volume type based on storage class
            # NFS volume type should only be used if NFS provisioner is available
            if values["volume_type"] == "nfs":
                # Let the transfer_model in kubernetes.py handle NFS detection
                logger.info("Volume type is NFS, will check for NFS service availability")
            else:
                # Default to local volume type for standard storage classes
                values["volume_type"] = "local"
                logger.info(f"Using local volume type with storage class: {default_storage_class}")

        if not default_access_mode:
            # Attempt to align access mode with the selected storage class recommendations
            try:
                from ..cluster_ops.kubernetes import KubernetesHandler

                k8s_handler = KubernetesHandler(self.config)
                storage_classes = k8s_handler.get_storage_classes()

                target_storage_class = values.get("storageClass")
                if target_storage_class and target_storage_class != "default":
                    for sc in storage_classes:
                        if sc["name"] == target_storage_class:
                            access_mode = sc["recommended_access_mode"]
                            logger.info(
                                "Model transfer selecting access mode %s based on storage class %s",
                                access_mode,
                                target_storage_class,
                            )
                            break
                else:
                    for sc in storage_classes:
                        if sc["default"]:
                            access_mode = sc["recommended_access_mode"]
                            logger.info(
                                "Model transfer selecting access mode %s based on default storage class %s",
                                access_mode,
                                sc["name"],
                            )
                            break
            except Exception as e:
                logger.warning(f"Model transfer falling back to {access_mode} access mode: {e}")

        values["accessMode"] = access_mode

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

    async def get_deployment_status_async(
        self,
        namespace: str,
        ingress_url: str,
        cloud_model: bool = False,
        platform: Optional[ClusterPlatformEnum] = None,
        ingress_health: bool = True,
        check_pods: bool = True,
    ):
        """Get the status of a deployment by namespace asynchronously."""
        return await get_deployment_status(
            self.config, ingress_url, {"namespace": namespace}, cloud_model, platform, ingress_health, check_pods
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

    async def get_benchmark_config(
        self,
        cluster_id: UUID,
        model_id: UUID,
        model_uri: str,
        hostnames: list[str],
        device_type: str,
        tp_size: int,
        pp_size: int,
        replicas: int,
        input_tokens: int = 1024,
        output_tokens: int = 512,
        concurrency: int = 10,
        hardware_mode: str = "dedicated",
    ):
        """Get benchmark deployment configuration from BudSim.

        This calls the /simulator/benchmark-config endpoint which generates
        full deployment configuration from user-selected parameters.

        Args:
            cluster_id: The cluster ID
            model_id: The model ID
            model_uri: The model URI/path
            hostnames: List of selected node hostnames
            device_type: Selected device type (cuda, cpu, hpu)
            tp_size: Tensor parallelism size
            pp_size: Pipeline parallelism size
            replicas: Number of replicas
            input_tokens: Expected input token count
            output_tokens: Expected output token count
            concurrency: Expected concurrent requests
            hardware_mode: Hardware mode (dedicated or shared)

        Returns:
            list: Node groups with full deployment configuration
        """
        request_data = {
            "cluster_id": str(cluster_id),
            "model_id": str(model_id),
            "model_uri": model_uri,
            "hostnames": hostnames,
            "device_type": device_type,
            "tp_size": tp_size,
            "pp_size": pp_size,
            "replicas": replicas,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "concurrency": concurrency,
            "hardware_mode": hardware_mode,
        }

        logger.info(f"Getting benchmark config from budsim: {request_data}")
        try:
            url = (
                f"http://localhost:{app_settings.dapr_http_port}/v1.0/invoke/budsim/method/simulator/benchmark-config"
            )
            async with AsyncHTTPClient() as http_client:
                response = await http_client.send_request(
                    "POST",
                    url,
                    json=request_data,
                    follow_redirects=True,
                )
                response_str = response.body.decode("utf-8")
                logger.info(f"Response from budsim benchmark-config: {response_str}")
                if response.status_code != 200:
                    raise Exception(f"Failed to get benchmark config: {response_str}")

                response_data = json.loads(response_str)
                node_groups = response_data.get("node_groups", [])

                if not node_groups:
                    raise Exception("No node groups returned from benchmark config endpoint")

                logger.info(f"Received {len(node_groups)} node groups for benchmark")
                return node_groups

        except Exception as e:
            raise Exception(f"Failed to get benchmark config: {str(e)}") from e


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
