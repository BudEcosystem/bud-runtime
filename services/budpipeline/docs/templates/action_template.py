"""
Action Template - Copy this file to create a new action.

Replace all {{PLACEHOLDER}} values with your action-specific details.
Remove comments marked with "TEMPLATE:" after customization.

File location: budpipeline/actions/{{CATEGORY}}/{{ACTION_NAME}}.py
"""

# =============================================================================
# Imports
# =============================================================================

from budpipeline.actions.base import (
    # Metadata classes
    ActionMeta,
    ParamDefinition,
    ParamType,
    OutputDefinition,
    ExecutionMode,
    SelectOption,          # TEMPLATE: Only if using SELECT/MULTISELECT params
    ValidationRules,       # TEMPLATE: Only if using validation rules
    ConditionalVisibility, # TEMPLATE: Only if using conditional visibility
    RetryPolicy,           # TEMPLATE: Only if using custom retry policy
    ActionExample,         # TEMPLATE: Only if providing examples
    # Context and result classes
    BaseActionExecutor,
    ActionContext,
    ActionResult,
    # TEMPLATE: Uncomment if event-driven action
    # EventContext,
    # EventResult,
    # EventAction,
)
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Metadata Definition
# =============================================================================

META = ActionMeta(
    # ----- Required Fields -----
    type="{{action_type}}",             # Unique identifier (lowercase, underscores)
    version="1.0.0",                    # Semantic version
    name="{{Action Name}}",             # Human-readable display name
    description="{{Description of what this action does}}",
    category="{{Category}}",            # e.g., "Control Flow", "Model", "Cluster", etc.

    # ----- Optional Display Fields -----
    icon="{{icon}}",                    # Emoji or icon identifier (e.g., "⚙️")
    color="#1890ff",                    # Hex color for UI theming

    # ----- Parameters -----
    params=[
        ParamDefinition(
            name="{{param_name}}",
            label="{{Param Label}}",
            type=ParamType.STRING,      # STRING, NUMBER, BOOLEAN, SELECT, etc.
            required=True,
            description="{{Description of this parameter}}",
            placeholder="{{Placeholder text}}",  # TEMPLATE: Optional
            default="{{default_value}}",         # TEMPLATE: Optional
            # TEMPLATE: Uncomment for SELECT/MULTISELECT params:
            # options=[
            #     SelectOption(value="option1", label="Option 1"),
            #     SelectOption(value="option2", label="Option 2"),
            # ],
            # TEMPLATE: Uncomment for validation rules:
            # validation=ValidationRules(
            #     min=0,
            #     max=100,
            #     min_length=1,
            #     max_length=255,
            #     pattern=r"^[a-z]+$",
            #     pattern_message="Must be lowercase letters only",
            # ),
            # TEMPLATE: Uncomment for conditional visibility:
            # visible_when=ConditionalVisibility(
            #     param="other_param",
            #     equals=True,  # or not_equals="value"
            # ),
        ),
        # TEMPLATE: Add more parameters as needed
    ],

    # ----- Outputs -----
    outputs=[
        OutputDefinition(
            name="{{output_name}}",
            type="{{type}}",            # e.g., "string", "number", "boolean", "object"
            description="{{Description of this output}}",
        ),
        # TEMPLATE: Add more outputs as needed
    ],

    # ----- Execution Configuration -----
    execution_mode=ExecutionMode.SYNC,  # SYNC or EVENT_DRIVEN
    timeout_seconds=60,                 # TEMPLATE: Optional, default timeout
    # TEMPLATE: Uncomment for custom retry policy:
    # retry_policy=RetryPolicy(
    #     max_attempts=3,
    #     backoff_multiplier=2.0,
    #     initial_interval_seconds=1,
    # ),

    # ----- Behavior Flags -----
    idempotent=True,                    # True if safe to retry
    required_services=[],               # e.g., ["budcluster", "budmodel"]
    required_permissions=["pipeline:execute"],  # Required permissions

    # ----- Documentation -----
    # TEMPLATE: Uncomment to add usage examples:
    # examples=[
    #     ActionExample(
    #         title="Basic Usage",
    #         params={"param_name": "example_value"},
    #         description="Simple example showing basic usage",
    #     ),
    # ],
    # docs_url="https://docs.example.com/actions/{{action_type}}",
)


# =============================================================================
# Executor Implementation
# =============================================================================

class Executor(BaseActionExecutor):
    """Executor for {{Action Name}}."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """
        Execute the action.

        Args:
            context: Action context containing:
                - context.step_id: Current step ID
                - context.execution_id: Pipeline execution ID
                - context.params: Action parameters
                - context.workflow_params: Global workflow parameters
                - context.step_outputs: Outputs from previous steps
                - context.timeout_seconds: Configured timeout
                - context.retry_count: Current retry attempt
                - context.metadata: Additional metadata

        Returns:
            ActionResult with success status and outputs

        TEMPLATE: Implement your action logic here.
        """
        # Extract parameters
        param_value = context.params.get("{{param_name}}", "{{default}}")

        logger.info(
            "Executing {{action_type}}",
            step_id=context.step_id,
            param_value=param_value,
        )

        try:
            # TEMPLATE: Replace with your action logic
            result = param_value  # Placeholder

            return ActionResult(
                success=True,
                outputs={
                    "{{output_name}}": result,
                },
            )

        except Exception as e:
            logger.error(
                "{{Action Name}} failed",
                error=str(e),
                step_id=context.step_id,
            )
            return ActionResult(
                success=False,
                error=str(e),
                outputs={},
            )

    def validate_params(self, params: dict) -> list[str]:
        """
        Optional: Custom parameter validation beyond schema validation.

        Args:
            params: Parameters to validate

        Returns:
            List of error messages (empty if valid)

        TEMPLATE: Add custom validation logic or remove if not needed.
        """
        errors = []

        # Example: Custom validation
        # if params.get("end_date") < params.get("start_date"):
        #     errors.append("end_date must be after start_date")

        return errors

    async def cleanup(self, context: ActionContext) -> None:
        """
        Optional: Clean up resources after execution.

        TEMPLATE: Implement cleanup logic or remove if not needed.
        """
        pass

    # =========================================================================
    # TEMPLATE: Uncomment for event-driven actions
    # =========================================================================
    #
    # async def on_event(self, context: EventContext) -> EventResult:
    #     """
    #     Handle incoming event for event-driven action.
    #
    #     Args:
    #         context: Event context containing:
    #             - context.step_execution_id: Step execution ID
    #             - context.execution_id: Pipeline execution ID
    #             - context.external_workflow_id: External workflow ID
    #             - context.event_type: Type of event
    #             - context.event_data: Event payload
    #             - context.step_outputs: Current step outputs
    #
    #     Returns:
    #         EventResult with action to take
    #     """
    #     event_type = context.event_data.get("event")
    #     status = context.event_data.get("status", "").upper()
    #
    #     logger.info(
    #         "Received event for {{action_type}}",
    #         event_type=event_type,
    #         status=status,
    #         step_execution_id=context.step_execution_id,
    #     )
    #
    #     # Handle completion
    #     if event_type == "workflow_completed" or status == "COMPLETED":
    #         return EventResult(
    #             action=EventAction.COMPLETE,
    #             status="completed",
    #             outputs={
    #                 "result": context.event_data.get("result"),
    #             },
    #         )
    #
    #     # Handle failure
    #     if status == "FAILED":
    #         return EventResult(
    #             action=EventAction.COMPLETE,
    #             status="failed",
    #             error=context.event_data.get("error", "Unknown error"),
    #         )
    #
    #     # Ignore other events (keep waiting)
    #     return EventResult(action=EventAction.IGNORE)


# =============================================================================
# Action Class Export
# =============================================================================

class {{ActionClass}}Action:
    """
    {{Action Name}} action.

    {{Longer description of what this action does and when to use it.}}

    Example usage in pipeline:
        {
            "name": "my_step",
            "action": "{{action_type}}",
            "params": {
                "{{param_name}}": "value"
            }
        }
    """
    meta = META
    executor_class = Executor


# =============================================================================
# TEMPLATE: Entry Point Registration
# =============================================================================
#
# Add to pyproject.toml:
#
# [project.entry-points."budpipeline.actions"]
# {{action_type}} = "budpipeline.actions.{{category}}.{{module_name}}:{{ActionClass}}Action"
#
# Then reinstall the package:
#   pip install -e .
#
# =============================================================================
