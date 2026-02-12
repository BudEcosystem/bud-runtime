"""Shared model resolution utilities for pipeline actions.

Provides common functions for resolving user IDs and fetching model info
from budapp. Used by deployment_create and simulation_run actions.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from budpipeline.actions.base import ActionContext
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)

# UUID pattern for validating model_id to prevent path traversal
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls.

    Uses only trusted sources (workflow_params set by the system, or
    the configured system_user_id). Does NOT read from context.params
    to prevent user impersonation via action parameters.
    """
    return context.workflow_params.get("user_id") or settings.system_user_id


async def get_model_info(
    context: ActionContext, model_id: str, user_id: str | None
) -> dict[str, Any]:
    """Get model info from budapp to determine provider type and local path.

    Args:
        context: Action execution context with service invocation capability.
        model_id: The model ID to look up (must be a valid UUID).
        user_id: The user ID for authorization.

    Returns:
        Model info dict, or empty dict on failure.
    """
    if not _UUID_PATTERN.match(model_id):
        logger.warning("get_model_info_invalid_id", model_id=model_id)
        return {}

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
            "get_model_info_failed",
            model_id=model_id,
            error=str(e),
        )
        return {}


def resolve_pretrained_model_uri(model_info: dict[str, Any]) -> str | None:
    """Extract the pretrained model URI from model info.

    Tries multiple fields in order of preference:
    local_path > uri > huggingface_url.

    Args:
        model_info: Model info dict from budapp.

    Returns:
        The resolved model URI, or None if not found.
    """
    return (
        model_info.get("local_path") or model_info.get("uri") or model_info.get("huggingface_url")
    )
