"""Model Benchmark Action.

Runs performance benchmarks on a model via budapp benchmark workflow.
Uses event-driven completion - returns immediately after starting workflow
and receives completion event via on_event().
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    SelectOption,
    StepStatus,
    ValidationRules,
    register_action,
)
from budpipeline.commons.config import settings
from budpipeline.commons.constants import CALLBACK_TOPIC

logger = structlog.get_logger(__name__)


def _resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


async def _fetch_cluster_info(
    context: ActionContext,
    cluster_id: str,
    user_id: str | None = None,
) -> tuple[str | None, str | None, list[dict[str, Any]], str | None]:
    """Fetch cluster information including bud_cluster_id and nodes.

    The cluster_id param may be either a budapp UUID (cluster.id) or a
    budcluster UUID (cluster.cluster_id). The pipeline editor stores the
    budcluster UUID for CLUSTER_REF params. This function tries the budapp
    lookup first, then falls back to treating the value as a bud_cluster_id.

    Args:
        context: Action context for service invocation
        cluster_id: The cluster ID (budapp id or budcluster cluster_id)
        user_id: User ID for authorization

    Returns:
        Tuple of (budapp_cluster_id, bud_cluster_id, nodes_list, error_message)
        error_message is None on success, contains details on failure
    """
    try:
        # Step 1: Fetch cluster details from budapp to get bud_cluster_id
        # The cluster_id might be either the budapp UUID or the budcluster UUID.
        # Try budapp lookup first (GET /clusters/{id}).
        budapp_cluster_id = None
        bud_cluster_id = None

        try:
            cluster_response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"clusters/{cluster_id}",
                http_method="GET",
                params={"user_id": user_id} if user_id else None,
                timeout_seconds=30,
            )
            cluster_data = cluster_response.get("cluster", cluster_response)
            budapp_cluster_id = cluster_data.get("id") or cluster_id
            bud_cluster_id = cluster_data.get("cluster_id")
        except Exception:
            # Lookup by budapp id failed - the cluster_id might be a budcluster UUID.
            # Try listing clusters to find the one matching this cluster_id field.
            logger.info(
                "cluster_lookup_by_id_failed_trying_as_bud_cluster_id",
                cluster_id=cluster_id,
            )
            try:
                params = {"limit": 100}
                if user_id:
                    params["user_id"] = user_id
                clusters_response = await context.invoke_service(
                    app_id=settings.budapp_app_id,
                    method_path="clusters/clusters",
                    http_method="GET",
                    params=params,
                    timeout_seconds=30,
                )
                # Search through clusters to find one with matching cluster_id
                clusters_list = clusters_response.get("clusters", [])
                for c in clusters_list:
                    if c.get("cluster_id") == cluster_id:
                        budapp_cluster_id = c.get("id")
                        bud_cluster_id = cluster_id
                        logger.info(
                            "cluster_found_by_bud_cluster_id",
                            input_cluster_id=cluster_id,
                            budapp_cluster_id=budapp_cluster_id,
                            bud_cluster_id=bud_cluster_id,
                        )
                        break
                if not bud_cluster_id:
                    return (
                        None,
                        None,
                        [],
                        f"Cluster not found: no cluster with id or cluster_id "
                        f"matching '{cluster_id}'",
                    )
            except Exception as e2:
                return (
                    None,
                    None,
                    [],
                    f"Failed to fetch cluster info for cluster {cluster_id}: {e2}",
                )

        if not bud_cluster_id:
            logger.warning(
                "cluster_info_no_bud_cluster_id",
                cluster_id=cluster_id,
            )
            return None, None, [], f"Cluster {cluster_id} has no associated bud_cluster_id"

        logger.info(
            "cluster_info_fetched",
            cluster_id=cluster_id,
            budapp_cluster_id=budapp_cluster_id,
            bud_cluster_id=bud_cluster_id,
        )

        # Step 2: Fetch cluster nodes from budcluster using bud_cluster_id
        nodes_response = await context.invoke_service(
            app_id=settings.budcluster_app_id,
            method_path=f"cluster/{bud_cluster_id}/nodes",
            http_method="GET",
            timeout_seconds=30,
        )

        # Extract nodes from response
        nodes_data = nodes_response.get("param", nodes_response)
        raw_nodes = nodes_data.get("nodes", [])

        # Transform nodes to the format expected by benchmark
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

        logger.info(
            "cluster_nodes_fetched",
            cluster_id=cluster_id,
            node_count=len(nodes_list),
        )
        return str(budapp_cluster_id), str(bud_cluster_id), nodes_list, None

    except Exception as e:
        logger.error(
            "cluster_info_fetch_failed",
            cluster_id=cluster_id,
            error=str(e),
        )
        return None, None, [], f"Failed to fetch cluster info for cluster {cluster_id}: {e}"


async def _get_node_configurations(
    context: ActionContext,
    model_id: str,
    cluster_id: str,
    hostnames: list[str],
    hardware_mode: str = "dedicated",
    input_tokens: int = 1024,
    output_tokens: int = 512,
    concurrency: int = 1,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Fetch available node configurations from budsim via budapp proxy."""
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
        "node_configurations_fetching",
        model_id=model_id,
        cluster_id=cluster_id,
        hostname_count=len(hostnames),
    )

    response = await context.invoke_service(
        app_id=settings.budapp_app_id,
        method_path="benchmark/node-configurations",
        http_method="POST",
        data=payload,
        params={"user_id": user_id} if user_id else None,
        timeout_seconds=60,
    )

    if isinstance(response, dict) and response.get("code") and response.get("code") >= 400:
        error_msg = response.get("message", "Unknown error")
        raise Exception(f"Failed to get node configurations: {error_msg}")

    logger.info(
        "node_configurations_fetched",
        response_keys=list(response.keys()),
    )
    return response


def _select_device_config(
    device_configurations: list[dict[str, Any]],
    selected_device_type: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Select the best device configuration based on priority or explicit selection."""
    if not device_configurations:
        return None, "No valid device configurations found for selected nodes"

    if selected_device_type:
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

    return device_configurations[0], None


def _select_tp_pp_config(
    tp_pp_options: list[dict[str, Any]],
    tp_size: int | None = None,
    pp_size: int | None = None,
    replicas: int | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Select TP/PP configuration based on explicit params or first valid option."""
    if not tp_pp_options:
        return None, "No valid TP/PP configurations available"

    if tp_size is not None and pp_size is not None:
        for opt in tp_pp_options:
            if opt.get("tp_size") == tp_size and opt.get("pp_size") == pp_size:
                return {
                    "tp_size": tp_size,
                    "pp_size": pp_size,
                    "replicas": replicas or opt.get("max_replicas", 1),
                }, None
        valid_options = [(o.get("tp_size"), o.get("pp_size")) for o in tp_pp_options]
        return None, f"TP={tp_size}, PP={pp_size} not valid. Options: {valid_options}"

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
    """Extract device configuration directly from nodes' hardware_info (fallback)."""
    device_types_found: dict[str, int] = {}

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

    if selected_device_type:
        if selected_device_type.lower() not in device_types_found:
            available = list(device_types_found.keys())
            raise ValueError(
                f"Device type '{selected_device_type}' not found. Available: {available}"
            )
        device_type = selected_device_type.lower()
    else:
        priority_order = ["cuda", "hpu", "cpu_high", "cpu"]
        device_type = None
        for ptype in priority_order:
            if ptype in device_types_found:
                device_type = ptype
                break
        if device_type is None:
            device_type = list(device_types_found.keys())[0]

    tp_size = 1
    pp_size = 1
    replicas = 1

    logger.info(
        "device_config_fallback_extracted",
        device_type=device_type,
        available_count=device_types_found.get(device_type, 0),
    )

    return device_type, tp_size, pp_size, replicas


class ModelBenchmarkExecutor(BaseActionExecutor):
    """Executor for running benchmarks on a model."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Start model benchmark workflow and return immediately.

        The workflow completion will be signaled via on_event() when
        budcluster publishes the completion event.
        """
        model_id = context.params.get("model_id", "")
        cluster_id = context.params.get("cluster_id", "")
        benchmark_name = context.params.get("benchmark_name", "auto-benchmark")
        concurrent_requests = context.params.get("concurrent_requests", 1)
        max_input_tokens = context.params.get("max_input_tokens", 1024)
        max_output_tokens = context.params.get("max_output_tokens", 512)
        prompt = context.params.get("prompt")
        prompt_tokens = context.params.get("prompt_tokens")
        max_wait_seconds = context.params.get("max_wait_seconds", 1200)
        initiator_user_id = _resolve_initiator_user_id(context)

        logger.info(
            "model_benchmark_starting",
            step_id=context.step_id,
            model_id=model_id,
            cluster_id=cluster_id,
        )

        try:
            # Step 0: Fetch cluster information (bud_cluster_id and nodes)
            budapp_cluster_id, bud_cluster_id, nodes, fetch_error = await _fetch_cluster_info(
                context, cluster_id, user_id=initiator_user_id
            )

            if not bud_cluster_id:
                error_msg = fetch_error or f"Could not fetch cluster info for cluster {cluster_id}"
                logger.error(
                    "model_benchmark_no_cluster_info",
                    step_id=context.step_id,
                    cluster_id=cluster_id,
                    error=error_msg,
                )
                return ActionResult(
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
                logger.error(
                    "model_benchmark_no_nodes",
                    step_id=context.step_id,
                    cluster_id=cluster_id,
                )
                return ActionResult(
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

            # Step 1: Get node configurations
            hostnames = [
                node.get("hostname") or node.get("name")
                for node in nodes
                if node.get("hostname") or node.get("name")
            ]

            if not hostnames:
                error_msg = f"No valid hostnames found in cluster nodes for {cluster_id}"
                logger.error(
                    "model_benchmark_no_hostnames",
                    step_id=context.step_id,
                    cluster_id=cluster_id,
                )
                return ActionResult(
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

            hardware_mode = context.params.get("hardware_mode", "dedicated")

            # Fetch available device configurations from budsim
            # Use budapp_cluster_id since node-configurations endpoint expects budapp UUID
            try:
                config_response = await _get_node_configurations(
                    context=context,
                    model_id=model_id,
                    cluster_id=budapp_cluster_id or cluster_id,
                    hostnames=hostnames,
                    hardware_mode=hardware_mode,
                    input_tokens=max_input_tokens,
                    output_tokens=max_output_tokens,
                    concurrency=concurrent_requests,
                    user_id=initiator_user_id,
                )

                device_configurations = config_response.get("device_configurations", [])

                selected_device_type_param = context.params.get("selected_device_type")
                selected_config, error = _select_device_config(
                    device_configurations, selected_device_type_param
                )

                if error:
                    logger.error(
                        "model_benchmark_device_selection_failed",
                        step_id=context.step_id,
                        error=error,
                    )
                    return ActionResult(
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

                tp_pp_config, error = _select_tp_pp_config(
                    tp_pp_options,
                    tp_size=context.params.get("tp_size"),
                    pp_size=context.params.get("pp_size"),
                    replicas=context.params.get("replicas"),
                )

                if error:
                    logger.error(
                        "model_benchmark_tp_pp_selection_failed",
                        step_id=context.step_id,
                        error=error,
                    )
                    return ActionResult(
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
                    "model_benchmark_config_selected",
                    step_id=context.step_id,
                    device_type=device_type,
                    tp_size=tp_size,
                    pp_size=pp_size,
                    replicas=replicas,
                )

            except Exception as e:
                # Fallback: Extract device config directly from nodes
                logger.warning(
                    "model_benchmark_config_fallback",
                    step_id=context.step_id,
                    error=str(e),
                )
                try:
                    selected_device_type_param = context.params.get("selected_device_type")
                    device_type, tp_size, pp_size, replicas = _extract_device_config_from_nodes(
                        nodes, selected_device_type_param
                    )
                except ValueError as fallback_error:
                    error_msg = (
                        f"Failed to discover node configurations: {e!s}. "
                        f"Fallback also failed: {fallback_error}"
                    )
                    logger.error(
                        "model_benchmark_config_fallback_failed",
                        step_id=context.step_id,
                        error=error_msg,
                    )
                    return ActionResult(
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
            # Use budapp_cluster_id for cluster_id (budapp run-workflow expects budapp UUID)
            request_data = {
                "workflow_total_steps": 1,
                "step_number": 1,
                "trigger_workflow": True,
                "model_id": model_id,
                "cluster_id": budapp_cluster_id or cluster_id,
                "bud_cluster_id": bud_cluster_id,
                "nodes": nodes,
                "name": benchmark_name,
                "tags": [],
                "description": f"Automated benchmark from workflow step {context.step_id}",
                "eval_with": "configuration",
                "concurrent_requests": concurrent_requests,
                "max_input_tokens": max_input_tokens,
                "max_output_tokens": max_output_tokens,
                "hardware_mode": hardware_mode,
                "selected_device_type": device_type,
                "tp_size": tp_size,
                "pp_size": pp_size,
                "replicas": replicas,
                "num_prompts": context.params.get("num_prompts", 10),
                "user_confirmation": True,
                "callback_topic": CALLBACK_TOPIC,
            }

            if prompt:
                request_data["prompt"] = prompt
            if prompt_tokens:
                request_data["prompt_tokens"] = prompt_tokens

            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path="benchmark/run-workflow",
                http_method="POST",
                data=request_data,
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                timeout_seconds=60,
            )

            # Extract workflow_id from response
            data = response.get("data", {}) if "data" in response else response

            # Get the budapp internal workflow ID - this is used for event correlation
            budapp_workflow_id = data.get("workflow_id")

            # Extract the Dapr workflow ID from budserve_cluster_events (for debugging only)
            workflow_steps = data.get("workflow_steps", {})
            budserve_events = (
                workflow_steps.get("budserve_cluster_events", {}) if workflow_steps else {}
            )
            dapr_workflow_id = budserve_events.get("workflow_id") if budserve_events else None

            # Use budapp internal workflow ID for event correlation
            workflow_id = budapp_workflow_id
            logger.info(
                "model_benchmark_workflow_started",
                step_id=context.step_id,
                workflow_id=workflow_id,
                dapr_workflow_id=dapr_workflow_id,
            )

            if not workflow_id:
                error_msg = "No workflow_id returned from budapp"
                logger.error(
                    "model_benchmark_no_workflow_id",
                    step_id=context.step_id,
                )
                return ActionResult(
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

            # Return immediately with awaiting_event=True
            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "benchmark_id": None,  # Will be set when event arrives
                    "workflow_id": str(workflow_id),
                    "status": "running",
                    "results": {},
                    "message": f"Benchmark workflow started: {workflow_id}",
                },
                awaiting_event=True,
                external_workflow_id=str(workflow_id),
                timeout_seconds=max_wait_seconds,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to start benchmark workflow: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error(
                "model_benchmark_http_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
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
            error_msg = f"Benchmark failed: {e!s}"
            logger.exception(
                "model_benchmark_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
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

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion event from benchmark workflow.

        Called when an event arrives matching this step's external_workflow_id.
        Handles events from both budapp (workflow_completed) and budcluster
        (performance_benchmark:results).
        """
        event_type = context.event_data.get("type", "")
        payload = context.event_data.get("payload", {})
        event_name = payload.get("event", "")
        content = payload.get("content", {})
        status_str = content.get("status", "")

        logger.info(
            "model_benchmark_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
            status=status_str,
        )

        # Handle workflow_completed event (from budapp workaround or future direct)
        if event_type == "workflow_completed":
            result_data = context.event_data.get("result", {})
            status = context.event_data.get("status", "UNKNOWN")

            if status == "COMPLETED":
                benchmark_id = result_data.get("benchmark_id")
                benchmark_name = result_data.get("benchmark_name", "")

                logger.info(
                    "model_benchmark_completed",
                    step_execution_id=context.step_execution_id,
                    benchmark_id=benchmark_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "benchmark_id": benchmark_id,
                        "workflow_id": context.external_workflow_id,
                        "status": "completed",
                        "results": result_data,
                        "message": f"Benchmark '{benchmark_name}' completed successfully",
                    },
                )
            else:
                error_msg = context.event_data.get("reason", "Benchmark workflow failed")
                logger.error(
                    "model_benchmark_workflow_failed",
                    step_execution_id=context.step_execution_id,
                    error=error_msg,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": context.external_workflow_id,
                        "status": "failed",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Handle performance_benchmark:results event (direct from budcluster)
        # Also handle notification:results which is the actual event type sent by budcluster
        if (
            event_type == "performance_benchmark" or event_type == "notification"
        ) and event_name == "results":
            if status_str in ("COMPLETED", "completed"):
                result = content.get("result", {})
                benchmark_id = result.get("benchmark_id")
                benchmark_name = result.get("benchmark_name", "")

                logger.info(
                    "model_benchmark_completed_direct",
                    step_execution_id=context.step_execution_id,
                    benchmark_id=benchmark_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "benchmark_id": benchmark_id,
                        "workflow_id": context.external_workflow_id,
                        "status": "completed",
                        "results": result,
                        "message": f"Benchmark '{benchmark_name}' completed successfully",
                    },
                )
            elif status_str in ("FAILED", "failed"):
                error_msg = content.get("message", "Benchmark failed")
                logger.error(
                    "model_benchmark_failed_direct",
                    step_execution_id=context.step_execution_id,
                    error=error_msg,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "benchmark_id": None,
                        "workflow_id": context.external_workflow_id,
                        "status": "failed",
                        "results": {},
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Handle failure events from intermediate steps
        if (
            event_type == "performance_benchmark" or event_type == "notification"
        ) and status_str in ("FAILED", "failed"):
            error_msg = content.get("message", f"Benchmark step '{event_name}' failed")
            title = content.get("title", "Benchmark failed")
            logger.error(
                "model_benchmark_step_failed",
                step_execution_id=context.step_execution_id,
                event_name=event_name,
                title=title,
                error=error_msg,
            )

            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={
                    "success": False,
                    "benchmark_id": None,
                    "workflow_id": context.external_workflow_id,
                    "status": "failed",
                    "results": {},
                    "message": f"{title}: {error_msg}",
                    "failed_step": event_name,
                },
                error=f"{title}: {error_msg}",
            )

        # Event not relevant to completion
        logger.debug(
            "model_benchmark_event_ignored",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
        )
        return EventResult(action=EventAction.IGNORE)

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []
        if not params.get("model_id"):
            errors.append("model_id is required for benchmarking")
        if not params.get("cluster_id"):
            errors.append("cluster_id is required for benchmarking")
        benchmark_name = params.get("benchmark_name", "")
        if benchmark_name and len(benchmark_name) > 50:
            errors.append(
                f"benchmark_name must be at most 50 characters (got {len(benchmark_name)}). "
                "This limit ensures the Kubernetes namespace stays within the 63-character limit."
            )
        return errors


META = ActionMeta(
    type="model_benchmark",
    version="1.0.0",
    name="Model Benchmark",
    description="Run performance benchmarks on a model",
    category="Model Operations",
    icon="chart-bar",
    color="#3B82F6",  # Blue
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=1200,  # 20 minutes
    idempotent=True,
    required_services=["budapp", "budcluster"],
    params=[
        ParamDefinition(
            name="model_id",
            label="Model",
            type=ParamType.MODEL_REF,
            description="The model to benchmark",
            required=True,
        ),
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="The cluster to run the benchmark on",
            required=True,
        ),
        ParamDefinition(
            name="benchmark_name",
            label="Benchmark Name",
            type=ParamType.STRING,
            description="Name for this benchmark run (max 50 characters due to Kubernetes namespace limits)",
            default="auto-benchmark",
            validation=ValidationRules(max_length=50),
        ),
        ParamDefinition(
            name="concurrent_requests",
            label="Concurrent Requests",
            type=ParamType.NUMBER,
            description="Number of concurrent requests to run",
            default=1,
            validation=ValidationRules(min=1, max=100),
        ),
        ParamDefinition(
            name="max_input_tokens",
            label="Max Input Tokens",
            type=ParamType.NUMBER,
            description="Maximum input tokens for benchmark prompts",
            default=1024,
            validation=ValidationRules(min=1, max=128000),
        ),
        ParamDefinition(
            name="max_output_tokens",
            label="Max Output Tokens",
            type=ParamType.NUMBER,
            description="Maximum output tokens for benchmark responses",
            default=512,
            validation=ValidationRules(min=1, max=32000),
        ),
        ParamDefinition(
            name="num_prompts",
            label="Number of Prompts",
            type=ParamType.NUMBER,
            description="Number of prompts to run in the benchmark",
            default=10,
            validation=ValidationRules(min=1, max=1000),
        ),
        ParamDefinition(
            name="hardware_mode",
            label="Hardware Mode",
            type=ParamType.SELECT,
            description="Hardware allocation mode",
            default="dedicated",
            options=[
                SelectOption(value="dedicated", label="Dedicated"),
                SelectOption(value="shared", label="Shared"),
            ],
        ),
        ParamDefinition(
            name="selected_device_type",
            label="Device Type",
            type=ParamType.SELECT,
            description="Override automatic device selection",
            required=False,
            options=[
                SelectOption(value="cuda", label="NVIDIA GPU (CUDA)"),
                SelectOption(value="hpu", label="Habana Gaudi (HPU)"),
                SelectOption(value="cpu", label="CPU"),
            ],
        ),
        ParamDefinition(
            name="tp_size",
            label="Tensor Parallelism Size",
            type=ParamType.NUMBER,
            description="Tensor parallelism size (auto-selected if not specified)",
            required=False,
            validation=ValidationRules(min=1, max=16),
        ),
        ParamDefinition(
            name="pp_size",
            label="Pipeline Parallelism Size",
            type=ParamType.NUMBER,
            description="Pipeline parallelism size (auto-selected if not specified)",
            required=False,
            validation=ValidationRules(min=1, max=16),
        ),
        ParamDefinition(
            name="replicas",
            label="Replicas",
            type=ParamType.NUMBER,
            description="Number of model replicas",
            required=False,
            validation=ValidationRules(min=1, max=32),
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time",
            type=ParamType.NUMBER,
            description="Maximum time to wait for benchmark completion (seconds)",
            default=1200,
            validation=ValidationRules(min=60, max=7200),
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether the benchmark completed successfully",
        ),
        OutputDefinition(
            name="benchmark_id",
            type="string",
            description="The unique identifier of the benchmark run",
        ),
        OutputDefinition(
            name="workflow_id",
            type="string",
            description="The workflow ID for tracking the operation",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Current status of the benchmark",
        ),
        OutputDefinition(
            name="results",
            type="object",
            description="Benchmark results including throughput, latency, etc.",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error description",
        ),
    ],
)


@register_action(META)
class ModelBenchmarkAction:
    """Action for running benchmarks on a model."""

    meta = META
    executor_class = ModelBenchmarkExecutor
