#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Dapr workflows for notification management."""

import asyncio
from datetime import datetime

from dapr.ext.workflow import DaprWorkflowClient, DaprWorkflowContext, WorkflowRuntime

from notify.commons import logging
from notify.commons.config import app_settings

from .ttl_service import NotificationCleanupService


logger = logging.get_logger(__name__)


def cleanup_expired_notifications_activity(ctx: DaprWorkflowContext, input: dict) -> dict:
    """Activity for cleaning up expired notifications.

    Args:
        ctx (DaprWorkflowContext): The workflow context.
        input (dict): Input parameters including environment.

    Returns:
        dict: Cleanup statistics.
    """
    environment = input.get("environment", "prod")
    logger.info(f"Running notification cleanup activity for environment: {environment}")

    cleanup_service = NotificationCleanupService()
    # Run the async cleanup in a synchronous context
    stats = asyncio.run(cleanup_service.cleanup_expired_notifications(environment=environment))

    logger.info(f"Cleanup activity completed. Stats: {stats}")
    return stats


def notification_cleanup_workflow(ctx: DaprWorkflowContext, input: dict) -> dict:
    """Workflow for periodic notification cleanup.

    This workflow runs the cleanup activity and schedules the next execution.

    Args:
        ctx (DaprWorkflowContext): The workflow context.
        input (dict): Input parameters including environment.

    Returns:
        dict: Workflow execution summary.
    """
    environment = input.get("environment", "prod")
    logger.info(f"Starting notification cleanup workflow for environment: {environment}")

    # Run cleanup activity
    stats = yield ctx.call_activity(cleanup_expired_notifications_activity, input=input)

    logger.info(f"Cleanup workflow completed with stats: {stats}")
    return {
        "completed_at": datetime.utcnow().isoformat(),
        "environment": environment,
        "stats": stats,
    }


async def start_cleanup_workflow(environment: str = "prod") -> str:
    """Start the notification cleanup workflow.

    Args:
        environment (str): The Novu environment to clean up (dev or prod).

    Returns:
        str: The workflow instance ID.
    """
    with DaprWorkflowClient() as client:
        instance_id = f"notification-cleanup-{environment}-{datetime.utcnow().timestamp()}"
        client.schedule_new_workflow(
            workflow=notification_cleanup_workflow,
            input={"environment": environment},
            instance_id=instance_id,
        )
        logger.info(f"Started cleanup workflow with instance ID: {instance_id}")
        return instance_id


def register_workflows(runtime: WorkflowRuntime) -> None:
    """Register notification workflows with Dapr workflow runtime.

    Args:
        runtime (WorkflowRuntime): The Dapr workflow runtime instance.
    """
    runtime.register_workflow(notification_cleanup_workflow)
    runtime.register_activity(cleanup_expired_notifications_activity)
    logger.info("Registered notification workflows and activities")
