"""Run Simulation Action.

Runs a BudSim performance simulation as a standalone pipeline step.
Uses async workflow mode with Dapr pub/sub events for completion notification.

Unlike deployment_create (which runs simulation synchronously with debug=True),
this action runs simulation asynchronously and waits for completion events,
enabling longer simulations and result chaining to downstream steps.
"""

from __future__ import annotations

from typing import Any

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ConditionalVisibility,
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
from budpipeline.actions.shared.model_resolver import (
    get_model_info,
    resolve_initiator_user_id,
    resolve_pretrained_model_uri,
)
from budpipeline.commons.config import settings
from budpipeline.commons.constants import CALLBACK_TOPIC

logger = structlog.get_logger(__name__)

DEFAULT_MAX_WAIT_SECONDS = 1800  # 30 minutes


class SimulationRunExecutor(BaseActionExecutor):
    """Executor for running BudSim performance simulations."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute simulation run action.

        Resolves the model URI, builds the simulation request, and calls
        budsim in async mode (source_topic set to callback topic, debug=False).
        Returns awaiting_event=True to wait for completion via pub/sub.
        """
        # Model resolution from model_id
        model_id = context.params.get("model_id")

        # SLO targets
        input_tokens = context.params.get("input_tokens", 4096)
        output_tokens = context.params.get("output_tokens", 512)
        concurrency = context.params.get("concurrency", 1)
        target_ttft = context.params.get("target_ttft")
        target_throughput_per_user = context.params.get("target_throughput_per_user")
        target_e2e_latency = context.params.get("target_e2e_latency")

        # Optional params
        cluster_id = context.params.get("cluster_id")
        simulation_method = context.params.get("simulation_method")
        hardware_mode = context.params.get("hardware_mode", "dedicated")
        model_endpoints = context.params.get("model_endpoints")
        model_max_context_length = context.params.get("model_max_context_length")
        is_quantization = context.params.get("is_quantization", False)
        quantization_method = context.params.get("quantization_method")
        quantization_type = context.params.get("quantization_type")
        max_wait_seconds = context.params.get("max_wait_seconds", DEFAULT_MAX_WAIT_SECONDS)

        logger.info(
            "simulation_run_starting",
            step_id=context.step_id,
            model_id=model_id,
        )

        try:
            # Resolve model info from budapp
            pretrained_model_uri = None
            model_uri = None

            if model_id:
                user_id = resolve_initiator_user_id(context)
                model_info = await get_model_info(context, model_id, user_id)

                if model_info:
                    pretrained_model_uri = resolve_pretrained_model_uri(model_info)
                    model_uri = model_info.get("huggingface_url")
                    logger.info(
                        "simulation_run_resolved_model",
                        model_id=model_id,
                        pretrained_model_uri=pretrained_model_uri,
                        model_uri=model_uri,
                    )

            if not pretrained_model_uri:
                return ActionResult(
                    success=False,
                    outputs={
                        "success": False,
                        "workflow_id": None,
                        "status": "failed",
                        "recommendations": None,
                        "top_recommendation": None,
                        "cluster_id": None,
                        "metrics": None,
                        "message": "Could not resolve model URI from model_id. "
                        "Ensure the model exists in budapp.",
                    },
                    error="Could not resolve model URI from model_id",
                )

            # Build simulation request
            simulation_request: dict[str, Any] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "concurrency": concurrency,
                "is_proprietary_model": False,
                "hardware_mode": hardware_mode,
                "debug": False,  # Async mode: wait for events
                "source_topic": CALLBACK_TOPIC,  # Route events back to budpipeline
                "pretrained_model_uri": pretrained_model_uri,
            }

            if model_uri:
                simulation_request["model_uri"] = model_uri

            # SLO targets
            if target_ttft is not None:
                simulation_request["target_ttft"] = target_ttft
            if target_throughput_per_user is not None:
                simulation_request["target_throughput_per_user"] = target_throughput_per_user
            if target_e2e_latency is not None:
                simulation_request["target_e2e_latency"] = target_e2e_latency

            # Optional params
            if cluster_id:
                simulation_request["cluster_id"] = cluster_id
            if simulation_method:
                simulation_request["simulation_method"] = simulation_method
            if model_endpoints:
                simulation_request["model_endpoints"] = model_endpoints
            if model_max_context_length is not None:
                simulation_request["model_max_context_length"] = model_max_context_length

            # Quantization
            if is_quantization:
                simulation_request["is_quantization"] = True
                if quantization_method:
                    simulation_request["quantization_method"] = quantization_method
                if quantization_type:
                    simulation_request["quantization_type"] = quantization_type

            logger.info(
                "simulation_run_calling_budsim",
                step_id=context.step_id,
                request_keys=list(simulation_request.keys()),
            )

            # Call budsim
            response = await context.invoke_service(
                app_id=settings.budsim_app_id,
                method_path="simulator/run",
                http_method="POST",
                data=simulation_request,
                timeout_seconds=120,
            )

            # Extract workflow_id from response (WorkflowMetadataResponse)
            workflow_id = response.get("workflow_id")

            if not workflow_id:
                return ActionResult(
                    success=False,
                    outputs={
                        "success": False,
                        "workflow_id": None,
                        "status": "failed",
                        "recommendations": None,
                        "top_recommendation": None,
                        "cluster_id": None,
                        "metrics": None,
                        "message": "BudSim did not return a workflow_id",
                    },
                    error="BudSim did not return a workflow_id",
                )

            logger.info(
                "simulation_run_awaiting",
                step_id=context.step_id,
                workflow_id=workflow_id,
            )

            return ActionResult(
                success=True,
                awaiting_event=True,
                external_workflow_id=str(workflow_id),
                timeout_seconds=max_wait_seconds,
                outputs={
                    "success": True,
                    "workflow_id": str(workflow_id),
                    "status": "running",
                    "recommendations": None,
                    "top_recommendation": None,
                    "cluster_id": None,
                    "metrics": None,
                    "message": "Simulation started, waiting for results...",
                },
            )

        except Exception as e:
            error_msg = f"Failed to start simulation: {e!s}"
            logger.exception("simulation_run_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "workflow_id": None,
                    "status": "failed",
                    "recommendations": None,
                    "top_recommendation": None,
                    "cluster_id": None,
                    "metrics": None,
                    "message": error_msg,
                },
                error=error_msg,
            )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion event from budsim workflow.

        BudSim publishes activity events to the budpipelineEvents topic.
        Events have type=<activity_name> (e.g., "get_cluster_recommendations"),
        with payload.event and payload.content.status indicating progress.

        The event router matches events to waiting steps via payload.workflow_id.
        """
        event_type = context.event_data.get("type", "")
        payload = context.event_data.get("payload") or {}
        event_name = payload.get("event", "")
        content = payload.get("content") or {}
        status_str = content.get("status", "")

        logger.info(
            "simulation_run_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
            status=status_str,
        )

        # Skip metadata events (no actionable payload)
        if event_type == "workflow_metadata":
            return EventResult(action=EventAction.IGNORE)

        # Completion event: event_name="results" with status COMPLETED
        if event_name == "results" and status_str in ("completed", "COMPLETED"):
            result = content.get("result") or {}
            recommendations = result.get("recommendations", [])
            return self._build_completion_result(context, recommendations)

        # Failure event: any event with FAILED status
        if status_str in ("failed", "FAILED"):
            error_msg = (
                content.get("message", "") or content.get("error", "") or "Simulation failed"
            )
            logger.error(
                "simulation_run_failed",
                step_execution_id=context.step_execution_id,
                error=error_msg,
            )
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs=self._failed_outputs(context, error_msg),
                error=error_msg,
            )

        # Progress events: update progress based on activity phase
        progress_map = {
            "validation": 10.0,
            "hardware_selection": 25.0,
            "engine_configuration": 50.0,
            "performance_estimation": 75.0,
            "ranking": 90.0,
        }
        if event_name in progress_map and status_str in ("STARTED", "COMPLETED"):
            progress = progress_map[event_name]
            # Bump progress slightly higher on COMPLETED vs STARTED
            if status_str == "COMPLETED":
                progress = min(progress + 5.0, 95.0)
            return EventResult(
                action=EventAction.UPDATE_PROGRESS,
                progress=progress,
            )

        # Unknown event - ignore
        logger.debug(
            "simulation_run_event_ignored",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
        )
        return EventResult(action=EventAction.IGNORE)

    def _build_completion_result(
        self, context: EventContext, recommendations: list[dict[str, Any]]
    ) -> EventResult:
        """Build a completion EventResult from simulation recommendations."""
        if not recommendations:
            error_msg = "Simulation completed but returned no recommendations"
            logger.warning(
                "simulation_run_no_recommendations",
                step_execution_id=context.step_execution_id,
            )
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs=self._failed_outputs(context, error_msg),
                error=error_msg,
            )

        top_rec = recommendations[0]
        metrics = {
            "ttft": top_rec.get("ttft"),
            "throughput_per_user": top_rec.get("throughput_per_user"),
            "e2e_latency": top_rec.get("e2e_latency"),
            "error_rate": top_rec.get("error_rate"),
            "cost_per_million_tokens": top_rec.get("cost_per_million_tokens"),
        }

        logger.info(
            "simulation_run_completed",
            step_execution_id=context.step_execution_id,
            num_recommendations=len(recommendations),
            top_cluster_id=top_rec.get("cluster_id"),
        )

        return EventResult(
            action=EventAction.COMPLETE,
            status=StepStatus.COMPLETED,
            outputs={
                "success": True,
                "workflow_id": context.external_workflow_id,
                "status": "completed",
                "recommendations": recommendations,
                "top_recommendation": top_rec,
                "cluster_id": top_rec.get("cluster_id"),
                "metrics": metrics,
                "tool_calling_parser_type": top_rec.get("tool_calling_parser_type"),
                "reasoning_parser_type": top_rec.get("reasoning_parser_type"),
                "chat_template": top_rec.get("chat_template"),
                "supports_lora": top_rec.get("supports_lora"),
                "supports_pipeline_parallelism": top_rec.get("supports_pipeline_parallelism"),
                "message": f"Simulation completed with {len(recommendations)} recommendation(s)",
            },
        )

    def _failed_outputs(self, context: EventContext, message: str) -> dict[str, Any]:
        """Build standard failure outputs."""
        return {
            "success": False,
            "workflow_id": context.external_workflow_id,
            "status": "failed",
            "recommendations": None,
            "top_recommendation": None,
            "cluster_id": None,
            "metrics": None,
            "message": message,
        }

    def validate_params(self, params: dict) -> list[str]:
        """Validate simulation parameters."""
        errors = []

        if not params.get("model_id"):
            errors.append("model_id is required")

        # SLO targets are required
        missing_slo = []
        if params.get("target_ttft") is None:
            missing_slo.append("target_ttft")
        if params.get("target_throughput_per_user") is None:
            missing_slo.append("target_throughput_per_user")
        if params.get("target_e2e_latency") is None:
            missing_slo.append("target_e2e_latency")
        if missing_slo:
            errors.append(f"SLO targets required: missing {', '.join(missing_slo)}")

        # Validate enum values
        simulation_method = params.get("simulation_method")
        if simulation_method and simulation_method not in ("regressor", "heuristic"):
            errors.append("simulation_method must be 'regressor' or 'heuristic'")

        hardware_mode = params.get("hardware_mode")
        if hardware_mode and hardware_mode not in ("dedicated", "shared"):
            errors.append("hardware_mode must be 'dedicated' or 'shared'")

        # Validate quantization consistency
        is_quantization = params.get("is_quantization", False)
        quantization_method = params.get("quantization_method")
        quantization_type = params.get("quantization_type")
        if not is_quantization and (quantization_method or quantization_type):
            errors.append("quantization_method/quantization_type require is_quantization=true")

        return errors


META = ActionMeta(
    type="simulation_run",
    version="1.0.0",
    name="Run Simulation",
    description=(
        "Run a BudSim performance simulation to find optimal deployment configurations. "
        "Returns hardware recommendations, estimated metrics (TTFT, throughput, latency), "
        "and engine parser configs. Results can be chained to deployment steps."
    ),
    category="Simulation",
    icon="beaker",
    color="#8B5CF6",  # Purple
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=DEFAULT_MAX_WAIT_SECONDS,
    idempotent=True,
    required_services=["budsim"],
    params=[
        ParamDefinition(
            name="model_id",
            label="Model",
            type=ParamType.MODEL_REF,
            description="Model to simulate",
            required=True,
        ),
        ParamDefinition(
            name="input_tokens",
            label="Input Tokens",
            type=ParamType.NUMBER,
            description="Average input token count per request",
            required=True,
            default=4096,
            validation=ValidationRules(min=1, max=200000),
        ),
        ParamDefinition(
            name="output_tokens",
            label="Output Tokens",
            type=ParamType.NUMBER,
            description="Average output token count per request",
            required=True,
            default=512,
            validation=ValidationRules(min=1, max=50000),
        ),
        ParamDefinition(
            name="concurrency",
            label="Concurrency",
            type=ParamType.NUMBER,
            description="Number of concurrent requests",
            required=True,
            default=1,
            validation=ValidationRules(min=1, max=1000),
        ),
        ParamDefinition(
            name="target_ttft",
            label="Target TTFT (ms)",
            type=ParamType.NUMBER,
            description="Target time to first token in milliseconds",
            required=True,
            validation=ValidationRules(min=1, max=60000),
        ),
        ParamDefinition(
            name="target_throughput_per_user",
            label="Target Throughput (tokens/sec)",
            type=ParamType.NUMBER,
            description="Target output tokens per second per user",
            required=True,
            validation=ValidationRules(min=1, max=1000),
        ),
        ParamDefinition(
            name="target_e2e_latency",
            label="Target E2E Latency (sec)",
            type=ParamType.NUMBER,
            description="Target end-to-end latency in seconds",
            required=True,
            validation=ValidationRules(min=1, max=600),
        ),
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="Specific cluster to simulate on (omit to evaluate all clusters)",
            required=False,
        ),
        ParamDefinition(
            name="simulation_method",
            label="Simulation Method",
            type=ParamType.SELECT,
            description="Optimization method: regressor (ML-based) or heuristic (memory-based)",
            required=False,
            options=[
                SelectOption(label="Regressor (ML-based)", value="regressor"),
                SelectOption(label="Heuristic (Memory-based)", value="heuristic"),
            ],
        ),
        ParamDefinition(
            name="hardware_mode",
            label="Hardware Mode",
            type=ParamType.SELECT,
            description="GPU allocation mode",
            required=False,
            default="dedicated",
            options=[
                SelectOption(label="Dedicated GPU", value="dedicated"),
                SelectOption(label="Shared GPU (Time-slicing)", value="shared"),
            ],
        ),
        ParamDefinition(
            name="model_endpoints",
            label="Model Endpoints",
            type=ParamType.STRING,
            description="Endpoint types: 'EMBEDDING', 'LLM', or 'EMBEDDING,LLM'",
            required=False,
            placeholder="LLM",
        ),
        ParamDefinition(
            name="model_max_context_length",
            label="Max Context Length",
            type=ParamType.NUMBER,
            description="Override maximum context length for the model",
            required=False,
            validation=ValidationRules(min=1, max=1000000),
        ),
        ParamDefinition(
            name="is_quantization",
            label="Enable Quantization",
            type=ParamType.BOOLEAN,
            description="Enable quantized model simulation",
            required=False,
            default=False,
        ),
        ParamDefinition(
            name="quantization_method",
            label="Quantization Method",
            type=ParamType.STRING,
            description="Quantization method (e.g., 'awq', 'gptq')",
            required=False,
            placeholder="awq",
            show_when=ConditionalVisibility(param="is_quantization", equals=True),
        ),
        ParamDefinition(
            name="quantization_type",
            label="Quantization Type",
            type=ParamType.STRING,
            description="Quantization precision (e.g., 'int4', 'int8')",
            required=False,
            placeholder="int4",
            show_when=ConditionalVisibility(param="is_quantization", equals=True),
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time (sec)",
            type=ParamType.NUMBER,
            description="Maximum time to wait for simulation completion",
            required=False,
            default=DEFAULT_MAX_WAIT_SECONDS,
            validation=ValidationRules(min=60, max=7200),
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether simulation completed successfully",
        ),
        OutputDefinition(
            name="workflow_id",
            type="string",
            description="BudSim workflow ID for tracking",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Simulation status: running, completed, or failed",
        ),
        OutputDefinition(
            name="recommendations",
            type="json",
            description="Full array of deployment recommendations",
        ),
        OutputDefinition(
            name="top_recommendation",
            type="json",
            description="Best recommendation object",
        ),
        OutputDefinition(
            name="cluster_id",
            type="string",
            description="Cluster ID from the top recommendation",
        ),
        OutputDefinition(
            name="metrics",
            type="json",
            description="Estimated metrics: ttft, throughput_per_user, e2e_latency, error_rate, cost_per_million_tokens",
        ),
        OutputDefinition(
            name="tool_calling_parser_type",
            type="string",
            description="Tool calling parser configuration from top recommendation",
        ),
        OutputDefinition(
            name="reasoning_parser_type",
            type="string",
            description="Reasoning parser configuration from top recommendation",
        ),
        OutputDefinition(
            name="chat_template",
            type="string",
            description="Chat template from top recommendation",
        ),
        OutputDefinition(
            name="supports_lora",
            type="boolean",
            description="Whether LoRA adapters are supported",
        ),
        OutputDefinition(
            name="supports_pipeline_parallelism",
            type="boolean",
            description="Whether pipeline parallelism is supported",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class SimulationRunAction:
    """Action for running standalone BudSim performance simulations."""

    meta = META
    executor_class = SimulationRunExecutor
