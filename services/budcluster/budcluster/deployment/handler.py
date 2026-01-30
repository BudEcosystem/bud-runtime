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
CPU_MEMORY_MULTIPLIER = 2  # Accounts for runtime overhead, activation memory, safety margin
CPU_KV_CACHE_MULTIPLIER = 2  # Accounts for KV cache overhead on CPU (vLLM CPU backend inefficiency)
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

    def _process_budaiscaler_config(
        self,
        budaiscaler: dict,
        default_metric: str,
        engine_type: str,
    ) -> dict:
        """Process and validate BudAIScaler configuration.

        Args:
            budaiscaler: Raw BudAIScaler configuration dict
            default_metric: Default metric for the engine type
            engine_type: The inference engine type (vllm, latentbud, sglang)

        Returns:
            Processed configuration dict ready for Helm values
        """
        # Start with core configuration
        config = {
            "enabled": budaiscaler.get("enabled", True),
            "minReplicas": budaiscaler.get("minReplicas", 1),
            "maxReplicas": budaiscaler.get("maxReplicas", 10),
            "scalingStrategy": budaiscaler.get("scalingStrategy", "BudScaler"),
        }

        # Process metrics sources - add default if none provided
        metrics_sources = budaiscaler.get("metricsSources", [])
        if not metrics_sources:
            # Use default engine metric when no sources specified
            metrics_sources = [
                {
                    "type": "pod",
                    "protocolType": "http",
                    "port": "9090",
                    "path": "/metrics",
                    "targetMetric": default_metric,
                    "targetValue": "0.8",
                }
            ]
        config["metricsSources"] = metrics_sources

        # GPU configuration
        gpu_config = budaiscaler.get("gpuConfig", {})
        config["gpuConfig"] = {
            "enabled": gpu_config.get("enabled", False),
            "memoryThreshold": gpu_config.get("memoryThreshold", 80),
            "computeThreshold": gpu_config.get("computeThreshold", 80),
            "topologyAware": gpu_config.get("topologyAware", False),
            "preferredGPUType": gpu_config.get("preferredGPUType", ""),
            "vGPUSupport": gpu_config.get("vGPUSupport", False),
        }

        # Cost configuration
        cost_config = budaiscaler.get("costConfig", {})
        config["costConfig"] = {
            "enabled": cost_config.get("enabled", False),
            "cloudProvider": cost_config.get("cloudProvider", ""),
            "hourlyBudgetLimit": cost_config.get("hourlyBudgetLimit", 0),
            "dailyBudgetLimit": cost_config.get("dailyBudgetLimit", 0),
            "spotInstancePreference": cost_config.get("spotInstancePreference", "none"),
        }

        # Prediction configuration
        prediction_config = budaiscaler.get("predictionConfig", {})
        config["predictionConfig"] = {
            "enabled": prediction_config.get("enabled", False),
            "lookAheadMinutes": prediction_config.get("lookAheadMinutes", 15),
            "historyDays": prediction_config.get("historyDays", 7),
            "minConfidence": prediction_config.get("minConfidence", 0.7),
            "predictionMetrics": prediction_config.get("predictionMetrics", []),
        }

        # Schedule hints
        config["scheduleHints"] = budaiscaler.get("scheduleHints", [])

        # Multi-cluster configuration
        multi_cluster = budaiscaler.get("multiCluster", {})
        config["multiCluster"] = {
            "enabled": multi_cluster.get("enabled", False),
            "federationMode": multi_cluster.get("federationMode", "active-passive"),
            "clusterWeights": multi_cluster.get("clusterWeights", {}),
            "failoverThresholds": multi_cluster.get(
                "failoverThresholds",
                {"healthCheckFailures": 3, "latencyMs": 5000},
            ),
        }

        # Behavior configuration
        behavior = budaiscaler.get("behavior", {})
        scale_up = behavior.get("scaleUp", {})
        scale_down = behavior.get("scaleDown", {})

        config["behavior"] = {
            "scaleUp": {
                "stabilizationWindowSeconds": scale_up.get("stabilizationWindowSeconds", 0),
                "policies": scale_up.get(
                    "policies",
                    [
                        {"type": "Percent", "value": 100, "periodSeconds": 15},
                        {"type": "Pods", "value": 4, "periodSeconds": 15},
                    ],
                ),
                "selectPolicy": scale_up.get("selectPolicy", "Max"),
            },
            "scaleDown": {
                "stabilizationWindowSeconds": scale_down.get("stabilizationWindowSeconds", 300),
                "policies": scale_down.get(
                    "policies",
                    [{"type": "Percent", "value": 100, "periodSeconds": 15}],
                ),
                "selectPolicy": scale_down.get("selectPolicy", "Min"),
            },
        }

        # Auto-configure scale-to-zero when minReplicas is 0
        # This enables the BudAIScaler to scale down to zero replicas
        if config["minReplicas"] == 0:
            # Use 'or {}' to handle case where scaleToZeroConfig is explicitly None
            scale_to_zero_config = budaiscaler.get("scaleToZeroConfig") or {}
            config["scaleToZeroConfig"] = {
                "enabled": scale_to_zero_config.get("enabled", True),
                "activationScale": scale_to_zero_config.get("activationScale", 1),
                "gracePeriod": scale_to_zero_config.get("gracePeriod", "30s"),
            }
            logger.info(
                f"Scale-to-zero enabled: minReplicas=0, activationScale={config['scaleToZeroConfig']['activationScale']}"
            )

        return config

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
        budaiscaler: dict = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        tool_calling_parser_type: Optional[str] = None,
        reasoning_parser_type: Optional[str] = None,
        enable_tool_calling: Optional[bool] = None,
        enable_reasoning: Optional[bool] = None,
        chat_template: Optional[str] = None,
        default_storage_class: Optional[str] = None,
        default_access_mode: Optional[str] = None,
        model_max_context_length: Optional[int] = None,
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
            budaiscaler (dict, optional): BudAIScaler configuration with full autoscaling features. Defaults to None.
            input_tokens (Optional[int], optional): Average input/context tokens. Defaults to None.
            output_tokens (Optional[int], optional): Average output/sequence tokens. Defaults to None.
            tool_calling_parser_type (Optional[str], optional): Parser type for tool calling. Defaults to None.
            reasoning_parser_type (Optional[str], optional): Parser type for reasoning. Defaults to None.
            enable_tool_calling (Optional[bool], optional): Enable tool calling feature. Defaults to None.
            enable_reasoning (Optional[bool], optional): Enable reasoning feature. Defaults to None.
            default_storage_class (Optional[str], optional): Default storage class for PVCs. Defaults to None.
            model_max_context_length (Optional[int], optional): Model's max context length to cap max_model_len. Defaults to None.

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

        # Determine engine type from first node for autoscaling metric selection
        # All nodes in a deployment should use the same engine type
        first_node_engine = node_list[0].get("engine_type", "vllm") if node_list else "vllm"
        default_metric = get_default_autoscale_metric(first_node_engine)

        # Process BudAIScaler configuration
        if budaiscaler and budaiscaler.get("enabled", False):
            # Validate user-provided metrics against engine capabilities
            for metric_source in budaiscaler.get("metricsSources", []):
                user_metric = metric_source.get("targetMetric")
                if user_metric:
                    validate_autoscale_metric(first_node_engine, user_metric)
                    logger.info(f"Validated BudAIScaler metric '{user_metric}' for engine '{first_node_engine}'")

            values["budaiscaler"] = self._process_budaiscaler_config(budaiscaler, default_metric, first_node_engine)
            logger.info(f"Using BudAIScaler with strategy: {budaiscaler.get('scalingStrategy', 'BudScaler')}")
        else:
            # No autoscaling configured
            values["budaiscaler"] = {"enabled": False}

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
                    # Formula: memory_allocation = (weights * multiplier) + (kv_cache * kv_multiplier) + buffer
                    # CPU deployments need extra overhead for both weights and KV cache
                    raw_memory_gb = (weight_memory_gb * CPU_MEMORY_MULTIPLIER) + (
                        kv_cache_memory_gb * CPU_KV_CACHE_MULTIPLIER
                    )
                    allocation_memory_gb = raw_memory_gb + buffer_gb
                    # Ensure a minimum allocation for CPU nodes
                    allocation_memory_gb = max(allocation_memory_gb, CPU_MIN_MEMORY_GB)
                    logger.info(
                        f"CPU Node {node.get('name')}: Calculated memory using formula "
                        f"({weight_memory_gb:.2f} * {CPU_MEMORY_MULTIPLIER} + {kv_cache_memory_gb:.2f} * {CPU_KV_CACHE_MULTIPLIER}) + {buffer_gb} = {allocation_memory_gb:.2f} GB"
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
                "model_max_context_length": model_max_context_length,
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
        platform: Optional[ClusterPlatformEnum] = None,
        ingress_health: bool = True,
    ):
        """Get the status of a deployment by namespace."""
        return asyncio.run(
            get_deployment_status(self.config, ingress_url, {"namespace": namespace}, platform, ingress_health)
        )

    async def get_deployment_status_async(
        self,
        namespace: str,
        ingress_url: str,
        platform: Optional[ClusterPlatformEnum] = None,
        ingress_health: bool = True,
        check_pods: bool = True,
    ):
        """Get the status of a deployment by namespace asynchronously."""
        return await get_deployment_status(
            self.config, ingress_url, {"namespace": namespace}, platform, ingress_health, check_pods
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

    def identify_supported_endpoints(self, namespace: str, ingress_url: str = None):
        """Identify which endpoints are supported by checking if they return 200 status."""
        try:
            return asyncio.run(identify_supported_endpoints(self.config, namespace, ingress_url))
        except Exception as e:
            raise Exception(f"Failed to identify supported endpoints: {str(e)}") from e

    async def update_autoscale(
        self,
        namespace: str,
        release_name: str,
        budaiscaler: dict,
        engine_type: str = "vllm",
        platform: Optional[ClusterPlatformEnum] = None,
    ) -> tuple[str, str]:
        """Update autoscale configuration for an existing deployment using Helm upgrade.

        This method updates only the BudAIScaler configuration without affecting other
        deployment settings. It uses Helm upgrade with the existing release values.

        Args:
            namespace: Kubernetes namespace of the deployment
            release_name: Helm release name of the deployment
            budaiscaler: BudAIScaler configuration dict
            engine_type: The inference engine type (vllm, latentbud, sglang)
            platform: Optional cluster platform type

        Returns:
            tuple: (status, message) indicating success or failure

        Raises:
            ValueError: If autoscale configuration is invalid
            Exception: If the Helm upgrade fails
        """
        from ..cluster_ops import update_autoscale_config

        # Get default metric for engine type
        default_metric = get_default_autoscale_metric(engine_type)

        # Validate user-provided metrics against engine capabilities
        if budaiscaler.get("enabled", False):
            for metric_source in budaiscaler.get("metricsSources", []):
                user_metric = metric_source.get("targetMetric")
                if user_metric:
                    validate_autoscale_metric(engine_type, user_metric)
                    logger.info(f"Validated autoscale metric '{user_metric}' for engine '{engine_type}'")

        # Process BudAIScaler configuration
        processed_config = self._process_budaiscaler_config(budaiscaler, default_metric, engine_type)

        # Build minimal Helm values for autoscale update
        values = {
            "namespace": namespace,
            "release_name": release_name,
            "budaiscaler": processed_config,
        }

        logger.info(f"Updating autoscale configuration for release '{release_name}' in namespace '{namespace}'")
        logger.debug(f"Autoscale values: {values}")

        try:
            status, message = await update_autoscale_config(self.config, values, platform)
            return status, message
        except Exception as e:
            logger.exception(f"Failed to update autoscale configuration: {e}")
            raise Exception(f"Autoscale update failed: {str(e)}") from e


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
