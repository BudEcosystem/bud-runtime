"""Actions API routes.

Provides REST endpoints for discovering and validating pipeline actions.
The frontend uses these endpoints to dynamically load available actions
in the pipeline editor.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from budpipeline.actions.base import ActionMeta, action_registry

from .schemas import (
    ActionCategoryResponse,
    ActionExampleResponse,
    ActionListResponse,
    ActionMetaResponse,
    ConditionalVisibilityResponse,
    OutputDefinitionResponse,
    ParamDefinitionResponse,
    RetryPolicyResponse,
    SelectOptionResponse,
    ValidateRequest,
    ValidateResponse,
    ValidationRulesResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter()

# Category icons mapping
CATEGORY_ICONS = {
    "Control Flow": "git-branch",
    "Model": "cpu",
    "Cluster": "server",
    "Deployment": "rocket",
    "Integration": "plug",
    "Simulation": "beaker",
}


def _serialize_param(param) -> ParamDefinitionResponse:
    """Serialize a ParamDefinition to response model."""
    options = None
    if param.options:
        options = [
            SelectOptionResponse(
                value=opt.value if hasattr(opt, "value") else opt.get("value", ""),
                label=opt.label if hasattr(opt, "label") else opt.get("label", ""),
            )
            for opt in param.options
        ]

    validation = None
    if param.validation:
        v = param.validation
        validation = ValidationRulesResponse(
            min=v.min if hasattr(v, "min") else v.get("min"),
            max=v.max if hasattr(v, "max") else v.get("max"),
            minLength=v.min_length if hasattr(v, "min_length") else v.get("minLength"),
            maxLength=v.max_length if hasattr(v, "max_length") else v.get("maxLength"),
            pattern=v.pattern if hasattr(v, "pattern") else v.get("pattern"),
            patternMessage=(
                v.pattern_message if hasattr(v, "pattern_message") else v.get("patternMessage")
            ),
        )

    visible_when = None
    if param.show_when:
        vw = param.show_when
        visible_when = ConditionalVisibilityResponse(
            param=vw.param if hasattr(vw, "param") else vw.get("param", ""),
            equals=vw.equals if hasattr(vw, "equals") else vw.get("equals"),
            notEquals=(vw.not_equals if hasattr(vw, "not_equals") else vw.get("notEquals")),
        )

    return ParamDefinitionResponse(
        name=param.name,
        label=param.label,
        type=param.type.value if hasattr(param.type, "value") else str(param.type),
        description=param.description,
        required=param.required,
        default=param.default,
        placeholder=param.placeholder,
        options=options,
        validation=validation,
        visibleWhen=visible_when,
    )


def _serialize_output(output) -> OutputDefinitionResponse:
    """Serialize an OutputDefinition to response model."""
    return OutputDefinitionResponse(
        name=output.name,
        type=output.type,
        description=output.description,
    )


def _serialize_meta(meta: ActionMeta) -> ActionMetaResponse:
    """Serialize ActionMeta to response model."""
    retry_policy = None
    if meta.retry_policy:
        rp = meta.retry_policy
        retry_policy = RetryPolicyResponse(
            maxAttempts=rp.max_attempts,
            backoffMultiplier=rp.backoff_multiplier,
            initialIntervalSeconds=rp.initial_interval_seconds,
        )

    examples = []
    if meta.examples:
        examples = [
            ActionExampleResponse(
                title=ex.title,
                params=ex.params,
                description=ex.description,
            )
            for ex in meta.examples
        ]

    return ActionMetaResponse(
        type=meta.type,
        version=meta.version,
        name=meta.name,
        description=meta.description,
        category=meta.category,
        icon=meta.icon,
        color=meta.color,
        params=[_serialize_param(p) for p in meta.params],
        outputs=[_serialize_output(o) for o in meta.outputs],
        executionMode=meta.execution_mode.value,
        timeoutSeconds=meta.timeout_seconds,
        retryPolicy=retry_policy,
        idempotent=meta.idempotent,
        requiredServices=list(meta.required_services),
        requiredPermissions=list(meta.required_permissions),
        examples=examples,
        docsUrl=meta.docs_url,
    )


def _get_category_icon(category: str) -> str:
    """Get icon for a category."""
    return CATEGORY_ICONS.get(category, "box")


def _is_param_visible(show_when, params: dict) -> bool:
    """Check if a param's show_when condition is met given current params."""
    target_value = params.get(show_when.param)
    if show_when.equals is not None:
        return target_value == show_when.equals
    if show_when.not_equals is not None:
        return target_value != show_when.not_equals
    return True


@router.get("", response_model=ActionListResponse)
async def list_actions() -> ActionListResponse:
    """List all registered actions.

    Returns all actions with their metadata, organized both as a flat list
    and grouped by category for the frontend action palette.
    """
    # Ensure actions are discovered
    action_registry.discover_actions()

    all_meta = action_registry.get_all_meta()
    by_category = action_registry.get_by_category()

    actions = [_serialize_meta(m) for m in all_meta]

    categories = [
        ActionCategoryResponse(
            name=cat_name,
            icon=_get_category_icon(cat_name),
            actions=[_serialize_meta(m) for m in cat_actions],
        )
        for cat_name, cat_actions in sorted(by_category.items())
    ]

    logger.info("actions_listed", count=len(actions), categories=len(categories))

    return ActionListResponse(
        actions=actions,
        categories=categories,
        total=len(actions),
    )


@router.get("/{action_type}", response_model=ActionMetaResponse)
async def get_action(action_type: str) -> ActionMetaResponse:
    """Get metadata for a specific action type.

    Args:
        action_type: The action type identifier (e.g., "model_add", "log")

    Returns:
        Full action metadata including params and outputs

    Raises:
        404: If action type not found
    """
    # Ensure actions are discovered
    action_registry.discover_actions()

    meta = action_registry.get_meta(action_type)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"Action '{action_type}' not found",
        )

    logger.info("action_retrieved", action_type=action_type)
    return _serialize_meta(meta)


@router.post("/validate", response_model=ValidateResponse)
async def validate_params(request: ValidateRequest) -> ValidateResponse:
    """Validate parameters for an action.

    Validates the provided parameters against the action's parameter
    definitions and any custom validation logic in the executor.

    Args:
        request: The action type and parameters to validate

    Returns:
        Validation result with any errors

    Raises:
        404: If action type not found
    """
    # Ensure actions are discovered
    action_registry.discover_actions()

    meta = action_registry.get_meta(request.action_type)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"Action '{request.action_type}' not found",
        )

    errors: list[str] = []

    # Check required parameters
    for param in meta.params:
        if param.required and param.name not in request.params:
            # Skip required check if show_when condition is not met
            if param.show_when and not _is_param_visible(param.show_when, request.params):
                continue
            errors.append(f"Missing required parameter: {param.name}")
            continue

        value = request.params.get(param.name)
        if value is None:
            continue

        # Check validation rules
        if param.validation:
            v = param.validation
            if v.min is not None and isinstance(value, int | float) and value < v.min:
                errors.append(f"{param.name}: must be >= {v.min}")
            if v.max is not None and isinstance(value, int | float) and value > v.max:
                errors.append(f"{param.name}: must be <= {v.max}")
            if v.min_length is not None and isinstance(value, str) and len(value) < v.min_length:
                errors.append(f"{param.name}: must be at least {v.min_length} chars")
            if v.max_length is not None and isinstance(value, str) and len(value) > v.max_length:
                errors.append(f"{param.name}: must be at most {v.max_length} chars")

    # Run executor's custom validation
    try:
        executor = action_registry.get_executor(request.action_type)
        executor_errors = executor.validate_params(request.params)
        errors.extend(executor_errors)
    except Exception as e:
        logger.error(
            "validation_executor_error",
            action_type=request.action_type,
            error=str(e),
        )
        errors.append(f"Validation error: {e!s}")

    logger.info(
        "action_validated",
        action_type=request.action_type,
        valid=len(errors) == 0,
        error_count=len(errors),
    )

    return ValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
    )
