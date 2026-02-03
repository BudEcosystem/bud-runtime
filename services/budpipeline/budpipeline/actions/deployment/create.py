"""Create Deployment Action.

Deploys a model to a cluster, creating an inference endpoint.
Supports both cloud models (sync) and local models (async/event-driven).

Smart Mode: For local model deployments with SLO targets, automatically
runs budsim simulation to determine optimal parser configs before deployment.
"""

from __future__ import annotations

from typing import Any

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


async def _get_model_info(
    context: ActionContext, model_id: str, user_id: str | None
) -> dict[str, Any]:
    """Get model info from budapp to determine provider type and local path."""
    try:
        response = await context.invoke_service(
            app_id=settings.budapp_app_id,
            method_path=f"models/{model_id}",
            http_method="GET",
            params={"user_id": user_id} if user_id else None,
            timeout_seconds=30,
        )
        # Response structure: {"object": "model.get", "model": {...}, ...}
        # Extract the nested model data
        return response.get("model", response.get("data", response))
    except Exception as e:
        logger.warning(
            "deployment_create_get_model_failed",
            model_id=model_id,
            error=str(e),
        )
        return {}


async def _run_simulation(
    context: ActionContext,
    model_info: dict[str, Any],
    deploy_config: dict[str, Any],
    cluster_id: str | None,
    hardware_mode: str,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Run budsim simulation to get parser configs and simulator_id.

    Uses debug=True for synchronous execution.
    Returns tuple of (top_recommendation, simulator_id, error_message) from simulation results.
    The simulator_id is used by budcluster to fetch deployment configurations.
    If simulation fails, error_message contains the failure reason.
    """
    # Check if this is a local model
    provider_type = model_info.get("provider_type", "")
    if provider_type == "CLOUD_MODEL":
        logger.info("deployment_create_skip_simulation_cloud_model")
        return None, None, None

    # Get the local model path (needed for simulation)
    # Try multiple fields in order of preference
    local_path = (
        model_info.get("local_path") or model_info.get("uri") or model_info.get("huggingface_url")
    )

    # Log available model info fields for debugging
    logger.info(
        "deployment_create_model_info_fields",
        provider_type=provider_type,
        local_path=model_info.get("local_path"),
        uri=model_info.get("uri"),
        huggingface_url=model_info.get("huggingface_url"),
        resolved_path=local_path,
        model_info_keys=list(model_info.keys()),
    )

    if not local_path:
        logger.warning(
            "deployment_create_skip_simulation_no_local_path",
            available_fields=list(model_info.keys()),
        )
        return None, None, None

    # Get SLO targets from deploy_config
    ttft = deploy_config.get("ttft")
    per_session_tokens_per_sec = deploy_config.get("per_session_tokens_per_sec")
    e2e_latency = deploy_config.get("e2e_latency")

    has_slo_targets = all([ttft, per_session_tokens_per_sec, e2e_latency])

    # For dedicated hardware mode, SLO targets are required
    # For shared hardware mode, SLO targets are optional (use defaults)
    if hardware_mode == "dedicated" and not has_slo_targets:
        logger.warning("deployment_create_skip_simulation_missing_slo_targets")
        return None, None, None

    # Build simulation request
    # Extract target values (use min for ttft/e2e_latency, max for throughput)
    # For shared mode without SLO targets, use 0 (budsim handles this)
    target_ttft = 0
    target_throughput = 0
    target_e2e = 0

    if ttft:
        target_ttft = ttft[0] if isinstance(ttft, list) else ttft
    if per_session_tokens_per_sec:
        target_throughput = (
            per_session_tokens_per_sec[1]
            if isinstance(per_session_tokens_per_sec, list)
            else per_session_tokens_per_sec
        )
    if e2e_latency:
        target_e2e = e2e_latency[0] if isinstance(e2e_latency, list) else e2e_latency

    simulation_request = {
        "pretrained_model_uri": local_path,
        "input_tokens": deploy_config.get("avg_context_length", 4096),
        "output_tokens": deploy_config.get("avg_sequence_length", 512),
        "concurrency": deploy_config.get("concurrent_requests", 1),
        "target_ttft": target_ttft,
        "target_throughput_per_user": target_throughput,
        "target_e2e_latency": target_e2e,
        "is_proprietary_model": False,
        "hardware_mode": hardware_mode,
        "debug": True,  # KEY: This makes simulation synchronous
    }

    # Add cluster_id if provided
    if cluster_id:
        simulation_request["cluster_id"] = cluster_id

    logger.info(
        "deployment_create_running_simulation",
        local_path=local_path,
        cluster_id=cluster_id,
        hardware_mode=hardware_mode,
    )

    try:
        response = await context.invoke_service(
            app_id=settings.budsim_app_id,
            method_path="simulator/run",
            http_method="POST",
            data=simulation_request,
            timeout_seconds=120,  # Simulation can take time
        )

        # Extract simulator_id (workflow_id) from response - this is needed by budcluster
        simulator_id = response.get("workflow_id")

        # Extract recommendations from response
        recommendations = response.get("recommendations", [])
        if not recommendations:
            logger.warning("deployment_create_simulation_no_recommendations")
            # Check if there's an error message in the response
            error_msg = (
                response.get("message") or "No deployment recommendations found from simulation"
            )
            return None, simulator_id, error_msg

        # Return the top recommendation and simulator_id
        top_rec = recommendations[0]
        logger.info(
            "deployment_create_simulation_complete",
            simulator_id=simulator_id,
            cluster_id=top_rec.get("cluster_id"),
            tool_calling_parser_type=top_rec.get("tool_calling_parser_type"),
            reasoning_parser_type=top_rec.get("reasoning_parser_type"),
            supports_lora=top_rec.get("supports_lora"),
        )
        return top_rec, simulator_id, None

    except Exception as e:
        error_msg = str(e)
        logger.warning(
            "deployment_create_simulation_failed",
            error=error_msg,
        )
        return None, None, error_msg


def _needs_simulation(params: dict) -> bool:
    """Check if simulation is needed based on params.

    Simulation is needed when:
    1. It's a local model deployment (cluster_id provided, no credential_id)
    2. For dedicated hardware: SLO targets are provided
       For shared hardware: SLO targets are optional
    3. Parser configs are NOT already provided
    """
    cluster_id = params.get("cluster_id")
    credential_id = params.get("credential_id")
    hardware_mode = params.get("hardware_mode", "dedicated")

    # Cloud model - no simulation needed
    if credential_id and not cluster_id:
        return False

    # No cluster_id - can't run simulation
    if not cluster_id:
        return False

    # Check if SLO targets are provided
    has_slo_targets = all(
        [
            params.get("ttft"),
            params.get("per_session_tokens_per_sec"),
            params.get("e2e_latency"),
        ]
    )

    # For dedicated hardware mode, SLO targets are required
    # For shared hardware mode, SLO targets are optional
    if hardware_mode == "dedicated" and not has_slo_targets:
        return False

    # Check if parser configs are already provided (skip simulation if so)
    parser_configs_provided = any(
        [
            params.get("tool_calling_parser_type"),
            params.get("reasoning_parser_type"),
            params.get("chat_template"),
        ]
    )

    return not parser_configs_provided


class DeploymentCreateExecutor(BaseActionExecutor):
    """Executor for creating deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute deployment create action.

        Cloud models are deployed synchronously (endpoint created directly).
        Local models are deployed asynchronously via budcluster.

        Smart Mode: For local model deployments with SLO targets but without
        parser configs, automatically runs budsim simulation to determine
        optimal engine configuration before deployment.
        """
        # Required params
        model_id = context.params.get("model_id", "")
        project_id = context.params.get("project_id", "")
        endpoint_name = context.params.get("endpoint_name", "")

        # Optional basic params
        cluster_id = context.params.get("cluster_id")  # Required for local models
        credential_id = context.params.get("credential_id")  # Required for cloud models

        # Deployment configuration
        concurrent_requests = context.params.get("concurrent_requests", 1)
        avg_sequence_length = context.params.get("avg_sequence_length", 512)
        avg_context_length = context.params.get("avg_context_length", 4096)

        # Performance targets for local model simulation (SLO targets)
        ttft = context.params.get("ttft")  # [min, max] in ms
        per_session_tokens_per_sec = context.params.get("per_session_tokens_per_sec")  # [min, max]
        e2e_latency = context.params.get("e2e_latency")  # [min, max] in seconds

        # Hardware mode (dedicated GPU vs shared/time-slicing)
        hardware_mode = context.params.get("hardware_mode", "dedicated")

        # Parser metadata (usually comes from simulation results)
        tool_calling_parser_type = context.params.get("tool_calling_parser_type")
        reasoning_parser_type = context.params.get("reasoning_parser_type")
        chat_template = context.params.get("chat_template")

        # Engine capability flags (usually from simulation results)
        supports_lora = context.params.get("supports_lora")
        supports_pipeline_parallelism = context.params.get("supports_pipeline_parallelism")

        # BudAIScaler specification for autoscaling
        budaiscaler_specification = context.params.get("budaiscaler_specification")

        # Check if we need to run simulation to get parser configs
        needs_sim = _needs_simulation(context.params)

        logger.info(
            "deployment_create_starting",
            step_id=context.step_id,
            model_id=model_id,
            project_id=project_id,
            endpoint_name=endpoint_name,
            cluster_id=cluster_id,
            hardware_mode=hardware_mode,
            has_slo_targets=bool(ttft and per_session_tokens_per_sec and e2e_latency),
            needs_simulation=needs_sim,
        )

        try:
            initiator_user_id = _resolve_initiator_user_id(context)

            # Build deploy_config
            deploy_config: dict = {
                "concurrent_requests": concurrent_requests,
                "avg_sequence_length": avg_sequence_length,
                "avg_context_length": avg_context_length,
            }
            # Add performance targets for local model simulation
            if ttft:
                deploy_config["ttft"] = ttft
            if per_session_tokens_per_sec:
                deploy_config["per_session_tokens_per_sec"] = per_session_tokens_per_sec
            if e2e_latency:
                deploy_config["e2e_latency"] = e2e_latency

            # Smart Mode: Run simulation to get parser configs and simulator_id if needed
            simulator_id = None  # Will be passed to budapp to skip redundant simulation
            if needs_sim:
                logger.info(
                    "deployment_create_smart_mode",
                    step_id=context.step_id,
                    message="Running simulation to determine optimal engine configuration",
                )

                # Get model info first (need local_path for simulation)
                model_info = await _get_model_info(context, model_id, initiator_user_id)

                if model_info:
                    # Run simulation - returns (recommendation, simulator_id, error_message)
                    sim_result, simulator_id, sim_error = await _run_simulation(
                        context=context,
                        model_info=model_info,
                        deploy_config=deploy_config,
                        cluster_id=cluster_id,
                        hardware_mode=hardware_mode,
                    )

                    # If simulation failed with an error, fail the step
                    # This is critical for dedicated hardware mode where simulation must succeed
                    if sim_error and not sim_result:
                        error_msg = f"Simulation failed: {sim_error}"
                        logger.error(
                            "deployment_create_simulation_failed_step",
                            step_id=context.step_id,
                            hardware_mode=hardware_mode,
                            error=sim_error,
                        )
                        return ActionResult(
                            success=False,
                            outputs={
                                "success": False,
                                "endpoint_id": None,
                                "endpoint_url": None,
                                "endpoint_name": endpoint_name,
                                "workflow_id": None,
                                "status": "failed",
                                "message": error_msg,
                            },
                            error=error_msg,
                        )

                    # Extract parser configs from simulation result
                    if sim_result:
                        # Only override if not already set
                        if not tool_calling_parser_type:
                            tool_calling_parser_type = sim_result.get("tool_calling_parser_type")
                        if not reasoning_parser_type:
                            reasoning_parser_type = sim_result.get("reasoning_parser_type")
                        if not chat_template:
                            chat_template = sim_result.get("chat_template")
                        if supports_lora is None:
                            supports_lora = sim_result.get("supports_lora")
                        if supports_pipeline_parallelism is None:
                            supports_pipeline_parallelism = sim_result.get(
                                "supports_pipeline_parallelism"
                            )

                        logger.info(
                            "deployment_create_extracted_parser_configs",
                            step_id=context.step_id,
                            simulator_id=simulator_id,
                            tool_calling_parser_type=tool_calling_parser_type,
                            reasoning_parser_type=reasoning_parser_type,
                            chat_template=chat_template[:50] if chat_template else None,
                            supports_lora=supports_lora,
                            supports_pipeline_parallelism=supports_pipeline_parallelism,
                        )

            # Build request payload
            request_data: dict = {
                "workflow_total_steps": 1,
                "step_number": 1,
                "trigger_workflow": True,
                "model_id": model_id,
                "project_id": project_id,
                "endpoint_name": endpoint_name,
                "deploy_config": deploy_config,
                "callback_topic": CALLBACK_TOPIC,
            }

            # Add optional fields
            if cluster_id:
                request_data["cluster_id"] = cluster_id
            if credential_id:
                request_data["credential_id"] = credential_id

            # Hardware mode
            if hardware_mode:
                request_data["hardware_mode"] = hardware_mode

            # Auto-enable capabilities based on parser types from simulation
            # If simulation returned parser types, enable the corresponding capabilities
            if tool_calling_parser_type:
                request_data["enable_tool_calling"] = True
            if reasoning_parser_type:
                request_data["enable_reasoning"] = True

            # Parser metadata (from simulation)
            if tool_calling_parser_type:
                request_data["tool_calling_parser_type"] = tool_calling_parser_type
            if reasoning_parser_type:
                request_data["reasoning_parser_type"] = reasoning_parser_type
            if chat_template:
                request_data["chat_template"] = chat_template

            # Engine capability flags
            if supports_lora is not None:
                request_data["supports_lora"] = supports_lora
            if supports_pipeline_parallelism is not None:
                request_data["supports_pipeline_parallelism"] = supports_pipeline_parallelism

            # BudAIScaler specification
            if budaiscaler_specification:
                request_data["budaiscaler_specification"] = budaiscaler_specification

            # Simulator ID from budpipeline's simulation (avoids redundant simulation in budapp)
            if simulator_id:
                request_data["simulator_id"] = simulator_id

            # Call budapp deploy endpoint
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path="models/deploy-workflow",
                http_method="POST",
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                data=request_data,
                timeout_seconds=120,
            )

            # Extract workflow info from response
            workflow_data = response.get("data", {})
            workflow_id = workflow_data.get("workflow_id") or response.get("workflow_id")
            workflow_status = workflow_data.get("status") or response.get("status")

            # Check progress for endpoint info (cloud models complete immediately)
            progress = workflow_data.get("progress", {})
            endpoint_id = progress.get("endpoint_id")
            endpoint_url = progress.get("endpoint_url")

            # Cloud models: workflow is COMPLETED immediately
            if workflow_status in ("completed", "COMPLETED"):
                logger.info(
                    "deployment_create_completed",
                    step_id=context.step_id,
                    endpoint_id=endpoint_id,
                    endpoint_url=endpoint_url,
                )
                return ActionResult(
                    success=True,
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "endpoint_url": endpoint_url,
                        "endpoint_name": endpoint_name,
                        "workflow_id": str(workflow_id) if workflow_id else None,
                        "status": "completed",
                        "message": f"Endpoint '{endpoint_name}' deployed successfully",
                    },
                )

            # Local models: workflow is still running, wait for events
            logger.info(
                "deployment_create_awaiting",
                step_id=context.step_id,
                workflow_id=workflow_id,
                workflow_status=workflow_status,
            )
            return ActionResult(
                success=True,
                awaiting_event=True,
                external_workflow_id=str(workflow_id) if workflow_id else None,
                timeout_seconds=600,  # 10 minutes for deployment
                outputs={
                    "success": True,
                    "endpoint_id": None,
                    "endpoint_url": None,
                    "endpoint_name": endpoint_name,
                    "workflow_id": str(workflow_id) if workflow_id else None,
                    "status": "deploying",
                    "message": "Model deployment in progress...",
                },
            )

        except Exception as e:
            error_msg = f"Failed to deploy model: {e!s}"
            logger.exception("deployment_create_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "endpoint_id": None,
                    "endpoint_url": None,
                    "endpoint_name": endpoint_name,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion event from deployment workflow.

        Called when an event arrives matching this step's external_workflow_id.
        Handles events from budapp/budcluster deployment workflows.
        """
        event_type = context.event_data.get("type", "")
        event_name = context.event_data.get("payload", {}).get("event", "")
        payload = context.event_data.get("payload", {})
        content = payload.get("content", {})
        status_str = content.get("status", "")

        logger.info(
            "deployment_create_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
            status=status_str,
        )

        # Handle workflow_completed events from budapp
        if event_type == "workflow_completed":
            result_data = context.event_data.get("result", {})
            status = context.event_data.get("status", "UNKNOWN")

            if status == "COMPLETED":
                endpoint_id = result_data.get("endpoint_id")
                endpoint_url = result_data.get("endpoint_url")
                endpoint_name = context.step_outputs.get("endpoint_name", "")

                logger.info(
                    "deployment_create_completed",
                    step_execution_id=context.step_execution_id,
                    endpoint_id=endpoint_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "endpoint_url": endpoint_url,
                        "endpoint_name": endpoint_name,
                        "workflow_id": context.external_workflow_id,
                        "status": "completed",
                        "message": f"Endpoint '{endpoint_name}' deployed successfully",
                    },
                )
            else:
                error_msg = context.event_data.get("reason", "Deployment workflow failed")
                logger.error(
                    "deployment_create_workflow_failed",
                    step_execution_id=context.step_execution_id,
                    error=error_msg,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "endpoint_id": None,
                        "endpoint_url": None,
                        "endpoint_name": context.step_outputs.get("endpoint_name", ""),
                        "workflow_id": context.external_workflow_id,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Handle notification events from budapp/budcluster
        if event_type == "notification":
            payload_type = payload.get("type", "")
            # Check for deployment completion events
            is_completion_event = event_name in ("results", "deploy_model", "deployment_status")
            # Any FAILED event from deployment workflow should complete the step as failed
            is_failure_event = status_str == "FAILED" and payload_type in (
                "deploy_model",
                "perform_deployment",
            )

            if payload_type in ("deploy_model", "perform_deployment") and (
                is_completion_event or is_failure_event
            ):
                if status_str == "COMPLETED":
                    result = content.get("result", {})
                    endpoint_id = result.get("endpoint_id")
                    endpoint_url = result.get("endpoint_url")
                    endpoint_name = context.step_outputs.get("endpoint_name", "")

                    logger.info(
                        "deployment_create_completed_via_notification",
                        step_execution_id=context.step_execution_id,
                        endpoint_id=endpoint_id,
                        event_name=event_name,
                    )

                    return EventResult(
                        action=EventAction.COMPLETE,
                        status=StepStatus.COMPLETED,
                        outputs={
                            "success": True,
                            "endpoint_id": endpoint_id,
                            "endpoint_url": endpoint_url,
                            "endpoint_name": endpoint_name,
                            "workflow_id": context.external_workflow_id,
                            "status": "completed",
                            "message": f"Endpoint '{endpoint_name}' deployed successfully",
                        },
                    )
                elif status_str == "FAILED":
                    error_msg = (
                        content.get("message", "")
                        or content.get("error", "")
                        or "Deployment failed"
                    )
                    logger.error(
                        "deployment_create_failed_via_notification",
                        step_execution_id=context.step_execution_id,
                        error=error_msg,
                        event_name=event_name,
                    )

                    return EventResult(
                        action=EventAction.COMPLETE,
                        status=StepStatus.FAILED,
                        outputs={
                            "success": False,
                            "endpoint_id": None,
                            "endpoint_url": None,
                            "endpoint_name": context.step_outputs.get("endpoint_name", ""),
                            "workflow_id": context.external_workflow_id,
                            "status": "failed",
                            "message": error_msg,
                        },
                        error=error_msg,
                    )

        # Event not relevant to completion
        logger.debug(
            "deployment_create_event_ignored",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
        )
        return EventResult(action=EventAction.IGNORE)

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters.

        Smart validation that:
        - Requires model_id, project_id, endpoint_name for all deployments
        - For local models (when cluster_id is provided), SLO targets are recommended
        - For cloud models (when credential_id is provided without cluster_id), credential is required
        """
        errors = []

        if not params.get("model_id"):
            errors.append("model_id is required")

        if not params.get("project_id"):
            errors.append("project_id is required")

        if not params.get("endpoint_name"):
            errors.append("endpoint_name is required")

        # Smart validation for local vs cloud models
        cluster_id = params.get("cluster_id")
        credential_id = params.get("credential_id")
        hardware_mode = params.get("hardware_mode", "dedicated")

        # Validate that at least one of cluster_id or credential_id is provided
        if not cluster_id and not credential_id:
            errors.append(
                "Either cluster_id (for local models) or credential_id (for cloud models) is required"
            )

        # If cluster_id is provided (local model deployment), validate SLO targets
        if cluster_id:
            ttft = params.get("ttft")
            per_session_tokens_per_sec = params.get("per_session_tokens_per_sec")
            e2e_latency = params.get("e2e_latency")
            has_slo_targets = all([ttft, per_session_tokens_per_sec, e2e_latency])

            # For dedicated hardware mode, SLO targets are MANDATORY
            if hardware_mode == "dedicated" and not has_slo_targets:
                missing = []
                if not ttft:
                    missing.append("ttft")
                if not per_session_tokens_per_sec:
                    missing.append("per_session_tokens_per_sec")
                if not e2e_latency:
                    missing.append("e2e_latency")
                errors.append(
                    f"SLO targets are required for dedicated hardware mode: missing {', '.join(missing)}"
                )

        # Validate JSON array format for SLO targets
        for slo_param in ["ttft", "per_session_tokens_per_sec", "e2e_latency"]:
            value = params.get(slo_param)
            if value is not None:
                if not isinstance(value, list) or len(value) != 2:
                    errors.append(f"{slo_param} must be a [min, max] array")
                elif not all(isinstance(v, int | float) for v in value):
                    errors.append(f"{slo_param} values must be numbers")
                elif value[0] > value[1]:
                    errors.append(f"{slo_param} min value cannot be greater than max value")

        # Validate hardware_mode
        hardware_mode = params.get("hardware_mode")
        if hardware_mode and hardware_mode not in ("dedicated", "shared"):
            errors.append("hardware_mode must be 'dedicated' or 'shared'")

        # Validate budaiscaler_specification structure if provided
        budaiscaler_spec = params.get("budaiscaler_specification")
        if budaiscaler_spec:
            if not isinstance(budaiscaler_spec, dict):
                errors.append("budaiscaler_specification must be an object")
            else:
                # Validate key fields if present
                if "minReplicas" in budaiscaler_spec:
                    min_rep = budaiscaler_spec["minReplicas"]
                    if not isinstance(min_rep, int) or min_rep < 0:
                        errors.append(
                            "budaiscaler_specification.minReplicas must be a non-negative integer"
                        )
                if "maxReplicas" in budaiscaler_spec:
                    max_rep = budaiscaler_spec["maxReplicas"]
                    if not isinstance(max_rep, int) or max_rep < 1:
                        errors.append(
                            "budaiscaler_specification.maxReplicas must be a positive integer"
                        )

        return errors


META = ActionMeta(
    type="deployment_create",
    version="1.6.0",
    name="Deploy Model",
    description="Deploy a model to create an inference endpoint. Supports cloud models (OpenAI, Anthropic) and local models (HuggingFace). Smart Mode: For local models with SLO targets, automatically runs simulation to determine optimal parser configs (tool calling, reasoning, chat template) before deployment.",
    category="Deployment",
    icon="rocket",
    color="#10B981",  # Emerald
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=600,
    idempotent=False,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="model_id",
            label="Model",
            type=ParamType.MODEL_REF,
            description="The model to deploy",
            required=True,
        ),
        ParamDefinition(
            name="project_id",
            label="Project",
            type=ParamType.PROJECT_REF,
            description="The project to deploy the endpoint in",
            required=True,
        ),
        ParamDefinition(
            name="endpoint_name",
            label="Endpoint Name",
            type=ParamType.STRING,
            description="Unique name for the deployment endpoint (lowercase, hyphens allowed)",
            required=True,
            placeholder="my-model-endpoint",
        ),
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="Target cluster for deployment (required for local models, optional for cloud models)",
            required=False,
        ),
        ParamDefinition(
            name="credential_id",
            label="API Credential",
            type=ParamType.CREDENTIAL_REF,
            description="API credential for cloud model provider (required for cloud models like OpenAI, Anthropic)",
            required=False,
        ),
        ParamDefinition(
            name="hardware_mode",
            label="Hardware Mode",
            type=ParamType.SELECT,
            description="GPU allocation mode: 'dedicated' for full GPU access, 'shared' for GPU time-slicing",
            required=False,
            default="dedicated",
            options=[
                SelectOption(label="Dedicated GPU", value="dedicated"),
                SelectOption(label="Shared GPU (Time-slicing)", value="shared"),
            ],
        ),
        ParamDefinition(
            name="concurrent_requests",
            label="Concurrent Requests",
            type=ParamType.NUMBER,
            description="Number of concurrent requests the endpoint should handle",
            default=1,
            required=True,
            validation=ValidationRules(min=1, max=1000),
        ),
        ParamDefinition(
            name="avg_sequence_length",
            label="Avg Sequence Length",
            type=ParamType.NUMBER,
            description="Average output sequence length (tokens)",
            default=512,
            required=True,
            validation=ValidationRules(min=1, max=10000),
        ),
        ParamDefinition(
            name="avg_context_length",
            label="Avg Context Length",
            type=ParamType.NUMBER,
            description="Average input context length (tokens)",
            default=4096,
            required=True,
            validation=ValidationRules(min=1, max=200000),
        ),
        ParamDefinition(
            name="ttft",
            label="Target TTFT (ms)",
            type=ParamType.RANGE,
            description="Time to first token range [min, max] in milliseconds. Required for local model simulation.",
            required=False,
            default=[50, 200],
            validation=ValidationRules(min=10, max=10000),
        ),
        ParamDefinition(
            name="per_session_tokens_per_sec",
            label="Tokens/Sec Target",
            type=ParamType.RANGE,
            description="Tokens per second range [min, max]. Required for local model simulation.",
            required=False,
            default=[10, 50],
            validation=ValidationRules(min=1, max=500),
        ),
        ParamDefinition(
            name="e2e_latency",
            label="E2E Latency (sec)",
            type=ParamType.RANGE,
            description="End-to-end latency range [min, max] in seconds. Required for local model simulation.",
            required=False,
            default=[10, 60],
            validation=ValidationRules(min=1, max=600),
        ),
        ParamDefinition(
            name="budaiscaler_specification",
            label="Autoscaling Configuration",
            type=ParamType.JSON,
            description="BudAIScaler specification for autoscaling. Includes minReplicas, maxReplicas, scalingStrategy, metricsSources, gpuConfig, costConfig, predictionConfig.",
            required=False,
            placeholder='{"enabled": true, "minReplicas": 1, "maxReplicas": 5}',
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether deployment was successful",
        ),
        OutputDefinition(
            name="endpoint_id",
            type="string",
            description="Unique identifier of the created endpoint",
        ),
        OutputDefinition(
            name="endpoint_url",
            type="string",
            description="URL of the deployment endpoint",
        ),
        OutputDefinition(
            name="endpoint_name",
            type="string",
            description="Name of the deployment endpoint",
        ),
        OutputDefinition(
            name="workflow_id",
            type="string",
            description="Workflow ID for tracking the deployment",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Current status of the deployment",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class DeploymentCreateAction:
    """Action for deploying models to create inference endpoints."""

    meta = META
    executor_class = DeploymentCreateExecutor
