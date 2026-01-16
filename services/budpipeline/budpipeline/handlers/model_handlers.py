"""Model-related workflow handlers.

Provides handlers for model operations via Dapr service invocation to budapp.
Uses budapp's workflow-based APIs and waits for completion events.
"""

import asyncio
import logging
from typing import Any

import httpx

from budpipeline.commons.config import settings
from budpipeline.handlers.base import BaseHandler, HandlerContext, HandlerResult
from budpipeline.handlers.cluster_handlers import invoke_dapr_service
from budpipeline.handlers.completion_tracker import completion_tracker
from budpipeline.handlers.registry import register_handler

logger = logging.getLogger(__name__)

# Topic that budpipeline subscribes to for completion events
CALLBACK_TOPIC = "budpipelineEvents"


def _resolve_initiator_user_id(context: HandlerContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


@register_handler("model_add")
class ModelAddHandler(BaseHandler):
    """Handler for adding a model to the repository.

    Invokes the budapp local-model-workflow to add a new model from HuggingFace.
    Waits for the workflow to complete before returning.
    """

    action_type = "model_add"
    name = "Add Model"
    description = "Add a new model to the model repository"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return []  # All params optional for flexibility

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "model_source": "huggingface",
            "huggingface_id": "",
            "model_name": "",
            "description": "",
            "author": "",
            "modality": ["text"],
            "project_id": None,
            "max_wait_seconds": 1800,  # 30 minutes default
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return ["success", "model_id", "model_name", "workflow_id", "status", "message"]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        errors = []
        source = params.get("model_source", "huggingface")

        if source == "huggingface":
            if not params.get("huggingface_id"):
                errors.append("huggingface_id is required for huggingface source")

        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute model add action via budapp workflow."""
        model_source = context.params.get("model_source", "huggingface")
        huggingface_id = context.params.get("huggingface_id", "")
        model_name = context.params.get(
            "model_name", huggingface_id.split("/")[-1] if huggingface_id else ""
        )
        description = context.params.get("description", "")
        author = context.params.get("author", "")
        modality = context.params.get("modality", ["text"])
        project_id = context.params.get("project_id")
        max_wait_seconds = context.params.get("max_wait_seconds", 1800)

        logger.info(
            f"[{context.step_id}] Adding model from {model_source}: {huggingface_id or model_name}"
        )

        try:
            # Step 1: Call budapp endpoint to start the local-model-workflow
            # Uses dual-auth (JWT or Dapr token) and optional user_id for auditing
            # Pass callback_topic to signal budapp to notify us on completion
            initiator_user_id = _resolve_initiator_user_id(context)
            method_path = "models/local-model-workflow"
            params = {"user_id": initiator_user_id} if initiator_user_id else None

            response = await invoke_dapr_service(
                app_id=settings.budapp_app_id,
                method_path=method_path,
                method="POST",
                params=params,
                data={
                    "workflow_total_steps": 1,
                    "step_number": 1,
                    "trigger_workflow": True,
                    "provider_type": "hugging_face",
                    "name": model_name,
                    "uri": huggingface_id,
                    "description": description,
                    "author": author,
                    "modality": modality,
                    "project_id": project_id,
                    "callback_topic": CALLBACK_TOPIC,  # Signal budapp to notify us
                },
                timeout=60,
            )

            # Extract workflow_id from response
            workflow_id = response.get("data", {}).get("workflow_id") or response.get("workflow_id")

            if not workflow_id:
                error_msg = "No workflow_id returned from budapp"
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "model_id": None,
                        "model_name": model_name,
                        "workflow_id": None,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            logger.info(
                f"[{context.step_id}] Model workflow started: {workflow_id}, "
                f"waiting for completion..."
            )

            # Step 2: Wait for completion event from budapp
            try:
                result = await completion_tracker.wait_for_completion(
                    workflow_id=str(workflow_id),
                    timeout=max_wait_seconds,
                )

                if result.status == "COMPLETED":
                    model_id = result.result.get("model_id")
                    result_name = result.result.get("model_name", model_name)

                    logger.info(f"[{context.step_id}] Model added successfully: {model_id}")

                    return HandlerResult(
                        success=True,
                        outputs={
                            "success": True,
                            "model_id": model_id,
                            "model_name": result_name,
                            "workflow_id": str(workflow_id),
                            "status": "completed",
                            "message": f"Model '{result_name}' added successfully",
                        },
                    )
                else:
                    error_msg = result.reason or "Model workflow failed"
                    logger.error(f"[{context.step_id}] Model workflow failed: {error_msg}")
                    return HandlerResult(
                        success=False,
                        outputs={
                            "success": False,
                            "model_id": None,
                            "model_name": model_name,
                            "workflow_id": str(workflow_id),
                            "status": "failed",
                            "message": error_msg,
                        },
                        error=error_msg,
                    )

            except asyncio.TimeoutError:
                error_msg = (
                    f"Workflow timed out after {max_wait_seconds}s. workflow_id: {workflow_id}"
                )
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "model_id": None,
                        "model_name": model_name,
                        "workflow_id": str(workflow_id),
                        "status": "timeout",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to start model workflow: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": None,
                    "model_name": model_name,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to add model: {str(e)}"
            logger.exception(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": None,
                    "model_name": model_name,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )


async def _fetch_cluster_info(
    cluster_id: str,
    user_id: str | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Fetch cluster information including bud_cluster_id and nodes.

    Args:
        cluster_id: The cluster ID (budapp cluster id)

    Returns:
        Tuple of (bud_cluster_id, nodes_list)
        bud_cluster_id: The cluster's internal UUID from budcluster
        nodes_list: List of node dictionaries with hostname and hardware info
    """
    try:
        # Step 1: Fetch cluster details from budapp to get bud_cluster_id
        # Uses dual-auth (JWT or Dapr token) with optional user_id
        cluster_response = await invoke_dapr_service(
            app_id=settings.budapp_app_id,
            method_path=f"clusters/{cluster_id}",
            method="GET",
            params={"user_id": user_id} if user_id else None,
            timeout=30,
        )

        # Extract bud_cluster_id from cluster response
        cluster_data = cluster_response.get("cluster", cluster_response)
        bud_cluster_id = cluster_data.get("cluster_id")

        if not bud_cluster_id:
            logger.warning(f"Could not get bud_cluster_id for cluster {cluster_id}")
            return None, []

        logger.info(f"Got bud_cluster_id: {bud_cluster_id} for cluster {cluster_id}")

        # Step 2: Fetch cluster nodes from budcluster using bud_cluster_id
        nodes_response = await invoke_dapr_service(
            app_id=settings.budcluster_app_id,
            method_path=f"cluster/{bud_cluster_id}/nodes",
            method="GET",
            timeout=30,
        )

        # Extract nodes from response
        nodes_data = nodes_response.get("param", nodes_response)
        raw_nodes = nodes_data.get("nodes", [])

        # Transform nodes to the format expected by benchmark
        # Benchmark expects nodes with at least 'hostname' key
        nodes_list = []
        for node in raw_nodes:
            node_dict = {
                "hostname": node.get("name", ""),
                "type": node.get("type", ""),
                "total_workers": node.get("total_workers", 0),
                "available_workers": node.get("available_workers", 0),
                "hardware_info": node.get("hardware_info", []),
            }
            if node_dict["hostname"]:
                nodes_list.append(node_dict)

        logger.info(f"Got {len(nodes_list)} nodes for cluster {cluster_id}")
        return str(bud_cluster_id), nodes_list

    except Exception as e:
        logger.error(f"Failed to fetch cluster info for {cluster_id}: {e}")
        return None, []


async def _get_node_configurations(
    model_id: str,
    cluster_id: str,
    hostnames: list[str],
    hardware_mode: str = "dedicated",
    input_tokens: int = 1024,
    output_tokens: int = 512,
    concurrency: int = 1,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Fetch available node configurations from budsim via budapp proxy.

    This function calls budapp's node-configurations endpoint
    which proxies to budsim to get available device types and TP/PP options
    for the selected nodes.

    Args:
        model_id: The model UUID (budapp model id)
        cluster_id: The cluster UUID (budapp cluster id)
        hostnames: List of hostnames to evaluate
        hardware_mode: Hardware allocation mode ('dedicated' or 'shared')
        input_tokens: Expected input tokens for sizing
        output_tokens: Expected output tokens for sizing
        concurrency: Expected concurrent requests

    Returns:
        Dict containing device_configurations with available options
    """
    payload = {
        "model_id": model_id,
        "cluster_id": cluster_id,
        "hostnames": hostnames,
        "hardware_mode": hardware_mode,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "concurrency": concurrency,
    }

    logger.info(
        f"Fetching node configurations for model={model_id}, "
        f"cluster={cluster_id}, hostnames={hostnames}"
    )

    response = await invoke_dapr_service(
        app_id=settings.budapp_app_id,
        method_path="benchmark/node-configurations",
        method="POST",
        data=payload,
        params={"user_id": user_id} if user_id else None,
        timeout=60,
    )

    # Check for error response
    if isinstance(response, dict):
        if response.get("code") and response.get("code") >= 400:
            error_msg = response.get("message", "Unknown error")
            raise Exception(f"Failed to get node configurations: {error_msg}")

    logger.info(f"Got node configurations response: {list(response.keys())}")
    return response


def _select_device_config(
    device_configurations: list[dict[str, Any]],
    selected_device_type: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Select the best device configuration based on priority or explicit selection.

    Args:
        device_configurations: List of available device configurations
        selected_device_type: Explicitly requested device type (optional)

    Returns:
        Tuple of (selected_config, error_message)
        If successful, error_message is None
        If failed, selected_config is None
    """
    if not device_configurations:
        return None, "No valid device configurations found for selected nodes"

    if selected_device_type:
        # Find matching device type
        for config in device_configurations:
            if config.get("device_type") == selected_device_type:
                return config, None
        available = [c.get("device_type") for c in device_configurations]
        return None, f"Device type '{selected_device_type}' not available. Available: {available}"

    # Auto-select based on priority: GPU > HPU > high-memory CPU > CPU
    priority_order = ["cuda", "hpu", "cpu_high", "cpu"]
    for ptype in priority_order:
        for config in device_configurations:
            if config.get("device_type") == ptype:
                return config, None

    # Fallback to first available
    return device_configurations[0], None


def _select_tp_pp_config(
    tp_pp_options: list[dict[str, Any]],
    tp_size: int | None = None,
    pp_size: int | None = None,
    replicas: int | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Select TP/PP configuration based on explicit params or first valid option.

    Args:
        tp_pp_options: List of available TP/PP options
        tp_size: Explicitly requested tensor parallelism size
        pp_size: Explicitly requested pipeline parallelism size
        replicas: Explicitly requested number of replicas

    Returns:
        Tuple of (config_dict, error_message)
        config_dict has keys: tp_size, pp_size, replicas
        If failed, config_dict is None
    """
    if not tp_pp_options:
        return None, "No valid TP/PP configurations available"

    if tp_size is not None and pp_size is not None:
        # Validate the combination exists
        for opt in tp_pp_options:
            if opt.get("tp_size") == tp_size and opt.get("pp_size") == pp_size:
                return {
                    "tp_size": tp_size,
                    "pp_size": pp_size,
                    "replicas": replicas or opt.get("max_replicas", 1),
                }, None
        valid_options = [(o.get("tp_size"), o.get("pp_size")) for o in tp_pp_options]
        return None, f"TP={tp_size}, PP={pp_size} not valid. Options: {valid_options}"

    # Auto-select first option
    first_option = tp_pp_options[0]
    return {
        "tp_size": first_option.get("tp_size", 1),
        "pp_size": first_option.get("pp_size", 1),
        "replicas": replicas or first_option.get("max_replicas", 1),
    }, None


def _extract_device_config_from_nodes(
    nodes: list[dict[str, Any]],
    selected_device_type: str | None = None,
) -> tuple[str, int, int, int]:
    """Extract device configuration directly from nodes' hardware_info.

    This is a fallback when budsim's node-configurations endpoint fails.
    It extracts available device types from the hardware_info field.

    Args:
        nodes: List of node dictionaries with hardware_info
        selected_device_type: Explicitly requested device type (optional)

    Returns:
        Tuple of (device_type, tp_size, pp_size, replicas)

    Raises:
        ValueError: If no devices found
    """
    # Collect available device types from nodes
    device_types_found: dict[str, int] = {}  # device_type -> available_count

    for node in nodes:
        hardware_info = node.get("hardware_info", [])
        for hw in hardware_info:
            device_type = hw.get("type", "").lower()
            available_count = hw.get("available_count", 0)
            if device_type and available_count > 0:
                if device_type not in device_types_found:
                    device_types_found[device_type] = 0
                device_types_found[device_type] += available_count

    if not device_types_found:
        raise ValueError("No devices found in nodes' hardware_info")

    # Select device type
    if selected_device_type:
        if selected_device_type.lower() not in device_types_found:
            available = list(device_types_found.keys())
            raise ValueError(
                f"Device type '{selected_device_type}' not found. Available: {available}"
            )
        device_type = selected_device_type.lower()
    else:
        # Auto-select based on priority: GPU > HPU > high-memory CPU > CPU
        priority_order = ["cuda", "hpu", "cpu_high", "cpu"]
        device_type = None
        for ptype in priority_order:
            if ptype in device_types_found:
                device_type = ptype
                break
        if device_type is None:
            # Fallback to first available
            device_type = list(device_types_found.keys())[0]

    # For fallback, use simple defaults:
    # TP=1, PP=1, replicas=1 (safe defaults for any device)
    tp_size = 1
    pp_size = 1
    replicas = 1

    logger.info(
        f"[fallback] Extracted device config from nodes: "
        f"device_type={device_type}, available_count={device_types_found.get(device_type, 0)}"
    )

    return device_type, tp_size, pp_size, replicas


@register_handler("model_benchmark")
class ModelBenchmarkHandler(BaseHandler):
    """Handler for running benchmarks on a model.

    Triggers benchmark execution via budapp benchmark workflow.
    Waits for the workflow to complete before returning.
    """

    action_type = "model_benchmark"
    name = "Model Benchmark"
    description = "Run benchmarks on a model"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return ["model_id", "cluster_id"]

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "benchmark_name": "auto-benchmark",
            "concurrent_requests": 1,
            "max_input_tokens": 1024,
            "max_output_tokens": 512,
            "prompt": None,
            "prompt_tokens": None,
            "max_wait_seconds": 1200,  # 20 minutes default (benchmarks can take time)
            # Hardware configuration (auto-detected if not specified)
            "hardware_mode": "dedicated",
            "selected_device_type": None,  # Auto-select based on priority
            "tp_size": None,  # Auto-select from available options
            "pp_size": None,  # Auto-select from available options
            "replicas": None,  # Auto-calculate based on max_replicas
            "num_prompts": 10,
            "run_as_simulation": False,
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return [
            "success",
            "benchmark_id",
            "workflow_id",
            "status",
            "results",
            "message",
        ]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        errors = []
        if not params.get("model_id"):
            errors.append("model_id is required for benchmarking")
        if not params.get("cluster_id"):
            errors.append("cluster_id is required for benchmarking")
        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute model benchmark action via budapp workflow."""
        model_id = context.params.get("model_id", "")
        cluster_id = context.params.get("cluster_id", "")
        benchmark_name = context.params.get("benchmark_name", "auto-benchmark")
        concurrent_requests = context.params.get("concurrent_requests", 1)
        max_input_tokens = context.params.get("max_input_tokens", 1024)
        max_output_tokens = context.params.get("max_output_tokens", 512)
        prompt = context.params.get("prompt")
        prompt_tokens = context.params.get("prompt_tokens")
        max_wait_seconds = context.params.get("max_wait_seconds", 600)
        initiator_user_id = _resolve_initiator_user_id(context)

        logger.info(
            f"[{context.step_id}] Running benchmark on model {model_id} in cluster {cluster_id}"
        )

        try:
            # Step 0: Fetch cluster information (bud_cluster_id and nodes)
            bud_cluster_id, nodes = await _fetch_cluster_info(cluster_id, user_id=initiator_user_id)

            if not bud_cluster_id:
                error_msg = f"Could not fetch cluster info for cluster {cluster_id}"
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": None,
                        "status": "failed",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            if not nodes:
                error_msg = f"No nodes found for cluster {cluster_id}"
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": None,
                        "status": "failed",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            logger.info(
                f"[{context.step_id}] Fetched cluster info: bud_cluster_id={bud_cluster_id}, "
                f"nodes_count={len(nodes)}"
            )

            # Step 1: Get node configurations from budsim via budapp
            # Extract hostnames from nodes
            hostnames = [
                node.get("hostname") or node.get("name")
                for node in nodes
                if node.get("hostname") or node.get("name")
            ]

            if not hostnames:
                error_msg = f"No valid hostnames found in cluster nodes for {cluster_id}"
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": None,
                        "status": "failed",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            # Get hardware configuration parameters
            hardware_mode = context.params.get("hardware_mode", "dedicated")

            # Fetch available device configurations from budsim
            try:
                config_response = await _get_node_configurations(
                    model_id=model_id,
                    cluster_id=cluster_id,
                    hostnames=hostnames,
                    hardware_mode=hardware_mode,
                    input_tokens=max_input_tokens,
                    output_tokens=max_output_tokens,
                    concurrency=concurrent_requests,
                    user_id=initiator_user_id,
                )

                device_configurations = config_response.get("device_configurations", [])

                # Select device configuration
                selected_device_type_param = context.params.get("selected_device_type")
                selected_config, error = _select_device_config(
                    device_configurations, selected_device_type_param
                )

                if error:
                    logger.error(f"[{context.step_id}] {error}")
                    return HandlerResult(
                        success=False,
                        outputs={
                            "success": False,
                            "benchmark_id": None,
                            "workflow_id": None,
                            "status": "failed",
                            "results": {},
                            "message": error,
                        },
                        error=error,
                    )

                device_type = selected_config.get("device_type")
                tp_pp_options = selected_config.get("tp_pp_options", [])

                # Select TP/PP configuration
                tp_pp_config, error = _select_tp_pp_config(
                    tp_pp_options,
                    tp_size=context.params.get("tp_size"),
                    pp_size=context.params.get("pp_size"),
                    replicas=context.params.get("replicas"),
                )

                if error:
                    logger.error(f"[{context.step_id}] {error}")
                    return HandlerResult(
                        success=False,
                        outputs={
                            "success": False,
                            "benchmark_id": None,
                            "workflow_id": None,
                            "status": "failed",
                            "results": {},
                            "message": error,
                        },
                        error=error,
                    )

                tp_size = tp_pp_config["tp_size"]
                pp_size = tp_pp_config["pp_size"]
                replicas = tp_pp_config["replicas"]

                logger.info(
                    f"[{context.step_id}] Selected configuration: device_type={device_type}, "
                    f"tp_size={tp_size}, pp_size={pp_size}, replicas={replicas}"
                )

            except Exception as e:
                # Fallback: Extract device config directly from nodes' hardware_info
                logger.warning(
                    f"[{context.step_id}] Node-configurations endpoint failed: {e}. "
                    f"Falling back to direct hardware_info extraction."
                )
                try:
                    selected_device_type_param = context.params.get("selected_device_type")
                    device_type, tp_size, pp_size, replicas = _extract_device_config_from_nodes(
                        nodes, selected_device_type_param
                    )
                    logger.info(
                        f"[{context.step_id}] Fallback configuration: device_type={device_type}, "
                        f"tp_size={tp_size}, pp_size={pp_size}, replicas={replicas}"
                    )
                except ValueError as fallback_error:
                    error_msg = f"Failed to discover node configurations: {str(e)}. Fallback also failed: {fallback_error}"
                    logger.error(f"[{context.step_id}] {error_msg}")
                    return HandlerResult(
                        success=False,
                        outputs={
                            "success": False,
                            "benchmark_id": None,
                            "workflow_id": None,
                            "status": "failed",
                            "results": {},
                            "message": error_msg,
                        },
                        error=error_msg,
                    )

            # Step 2: Call budapp to start the benchmark workflow
            request_data = {
                "workflow_total_steps": 1,
                "step_number": 1,
                "trigger_workflow": True,
                "model_id": model_id,
                "cluster_id": cluster_id,
                "bud_cluster_id": bud_cluster_id,  # Include bud_cluster_id
                "nodes": nodes,  # Include nodes
                "name": benchmark_name,
                "tags": [],  # Required field
                "description": f"Automated benchmark from workflow step {context.step_id}",  # Required field
                "eval_with": "configuration",  # Required field - use token-based config
                "concurrent_requests": concurrent_requests,
                "max_input_tokens": max_input_tokens,
                "max_output_tokens": max_output_tokens,
                # Hardware configuration (discovered from node-configurations)
                "hardware_mode": hardware_mode,
                "selected_device_type": device_type,
                "tp_size": tp_size,
                "pp_size": pp_size,
                "replicas": replicas,
                "num_prompts": context.params.get("num_prompts", 10),
                "user_confirmation": True,  # Auto-confirm for workflow automation
                "run_as_simulation": context.params.get("run_as_simulation", False),
                "callback_topic": CALLBACK_TOPIC,  # Signal budapp to notify us
            }

            # Add optional fields
            if prompt:
                request_data["prompt"] = prompt
            if prompt_tokens:
                request_data["prompt_tokens"] = prompt_tokens

            # Use the dual-auth endpoint with optional user_id for auditing
            method_path = "benchmark/run-workflow"
            params = {"user_id": initiator_user_id} if initiator_user_id else None

            response = await invoke_dapr_service(
                app_id=settings.budapp_app_id,
                method_path=method_path,
                method="POST",
                data=request_data,
                params=params,
                timeout=60,
            )

            # Extract workflow_id from response
            workflow_id = response.get("data", {}).get("workflow_id") or response.get("workflow_id")

            if not workflow_id:
                error_msg = "No workflow_id returned from budapp"
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": None,
                        "status": "failed",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            logger.info(
                f"[{context.step_id}] Benchmark workflow started: {workflow_id}, "
                f"waiting for completion..."
            )

            # Step 2: Wait for completion event from budapp
            try:
                result = await completion_tracker.wait_for_completion(
                    workflow_id=str(workflow_id),
                    timeout=max_wait_seconds,
                )

                if result.status == "COMPLETED":
                    benchmark_id = result.result.get("benchmark_id")
                    benchmark_name_result = result.result.get("benchmark_name", benchmark_name)

                    logger.info(f"[{context.step_id}] Benchmark completed: {benchmark_id}")

                    return HandlerResult(
                        success=True,
                        outputs={
                            "success": True,
                            "benchmark_id": benchmark_id,
                            "workflow_id": str(workflow_id),
                            "status": "completed",
                            "results": result.result,
                            "message": f"Benchmark '{benchmark_name_result}' completed "
                            f"for model {model_id}",
                        },
                    )
                else:
                    error_msg = result.reason or "Benchmark workflow failed"
                    logger.error(f"[{context.step_id}] Benchmark workflow failed: {error_msg}")
                    return HandlerResult(
                        success=False,
                        outputs={
                            "success": False,
                            "benchmark_id": None,
                            "workflow_id": str(workflow_id),
                            "status": "failed",
                            "results": {},
                            "message": error_msg,
                        },
                        error=error_msg,
                    )

            except asyncio.TimeoutError:
                error_msg = (
                    f"Benchmark timed out after {max_wait_seconds}s. workflow_id: {workflow_id}"
                )
                logger.error(f"[{context.step_id}] {error_msg}")
                return HandlerResult(
                    success=False,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": str(workflow_id),
                        "status": "timeout",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to start benchmark workflow: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "benchmark_id": None,
                    "workflow_id": None,
                    "status": "failed",
                    "results": {},
                    "message": error_msg,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Benchmark failed: {str(e)}"
            logger.exception(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "benchmark_id": None,
                    "workflow_id": None,
                    "status": "failed",
                    "results": {},
                    "message": error_msg,
                },
                error=error_msg,
            )


@register_handler("model_delete")
class ModelDeleteHandler(BaseHandler):
    """Handler for deleting a model from the repository.

    Invokes the budapp service to delete a model.
    This is a synchronous operation that doesn't require waiting.
    """

    action_type = "model_delete"
    name = "Delete Model"
    description = "Delete a model from the repository"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return ["model_id"]

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "force": False,
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return ["success", "model_id", "message"]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        errors = []
        if not params.get("model_id"):
            errors.append("model_id is required for deletion")
        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute model delete action."""
        model_id = context.params.get("model_id", "")
        force = context.params.get("force", False)
        initiator_user_id = _resolve_initiator_user_id(context)

        logger.info(f"[{context.step_id}] Deleting model {model_id} (force={force})")

        try:
            # Call budapp to delete the model
            # Model delete is a direct sync operation, no workflow needed
            params = {"force": str(force).lower()}
            if initiator_user_id:
                params["user_id"] = initiator_user_id
            response = await invoke_dapr_service(
                app_id=settings.budapp_app_id,
                method_path=f"models/{model_id}",
                method="DELETE",
                params=params,
                timeout=30,
            )

            logger.info(f"[{context.step_id}] Model deleted successfully: {model_id}")

            return HandlerResult(
                success=True,
                outputs={
                    "success": True,
                    "model_id": model_id,
                    "message": f"Model {model_id} deleted successfully",
                },
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to delete model: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": model_id,
                    "message": error_msg,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to delete model: {str(e)}"
            logger.exception(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": model_id,
                    "message": error_msg,
                },
                error=error_msg,
            )
