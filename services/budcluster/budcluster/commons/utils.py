import asyncio
import functools
import json
from datetime import timedelta
from typing import Union

from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from budmicroframe.shared.dapr_service import DaprService
from starlette.responses import JSONResponse

from .config import app_settings


logger = get_logger(__name__)


def skip_if_running(job_name: str):
    """Skip duplicate cron invocations using an asyncio.Lock.

    If the decorated handler is already running, return HTTP 200 with a skip
    message instead of executing again. This prevents resource exhaustion when
    Dapr scheduler replays missed cron jobs after sidecar reconnection.
    """

    def decorator(func):
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not lock.locked():
                async with lock:
                    return await func(*args, **kwargs)
            else:
                logger.warning("Skipping duplicate cron invocation for '%s' — previous run still active", job_name)
                return JSONResponse(
                    content=SuccessResponse(
                        message=f"Skipped: '{job_name}' is already running",
                    ).model_dump(),
                    status_code=200,
                )

        return wrapper

    return decorator


def check_workflow_status_in_statestore(workflow_id: str) -> Union[ErrorResponse, None]:
    """Check if the workflow is already terminated in the statestore."""
    with DaprService() as dapr_service:
        workflow_status = dapr_service.get_state(store_name=app_settings.statestore_name, key=str(workflow_id))
        if workflow_status and workflow_status.data:
            workflow_status_dict = json.loads(workflow_status.data)
            if workflow_status_dict.get("status") == WorkflowStatus.TERMINATED.value:
                return ErrorResponse(message="Workflow is already terminated")
    return None


def get_workflow_data_from_statestore(workflow_id: str) -> Union[dict, None]:
    """Get the workflow data from the statestore."""
    with DaprService() as dapr_service:
        workflow_data = dapr_service.get_state(store_name=app_settings.statestore_name, key=str(workflow_id))
        if workflow_data and workflow_data.data:
            workflow_data_dict = json.loads(workflow_data.data)
            return workflow_data_dict
    return None


def update_workflow_data_in_statestore(workflow_id: str, data: dict):
    """Update the workflow data in the statestore."""
    workflow_data = get_workflow_data_from_statestore(workflow_id)
    if workflow_data:
        workflow_data.update(data)
    else:
        workflow_data = data
    with DaprService() as dapr_service:
        dapr_service.save_to_statestore(key=str(workflow_id), value=json.dumps(workflow_data), ttl=3600)
    return workflow_data


def save_workflow_status_in_statestore(workflow_id: str, status: str):
    """Save the workflow status in the statestore."""
    update_workflow_data_in_statestore(workflow_id, {"status": status})


def format_uptime(td: timedelta) -> str:
    """Format the uptime to a string."""
    # Get total seconds
    total_seconds = int(td.total_seconds())

    # Calculate hours, minutes, seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
