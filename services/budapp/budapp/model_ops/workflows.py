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

"""This file contains the workflows for the model operations."""

import asyncio
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

import dapr.ext.workflow as wf
from budmicroframe.commons.schemas import WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from ..commons import logging
from .scheduler import CloudModelSyncScheduler


logger = logging.get_logger(__name__)


dapr_workflow = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class CloudModelSyncWorkflows:
    """Workflows for the cloud model sync."""

    def __init__(self) -> None:
        """Initialize the CloudModelSyncWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def perform_cloud_model_sync(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Perform the cloud model sync workflow."""
        try:
            asyncio.run(CloudModelSyncScheduler().sync_data())
            logger.info("Cloud model sync workflow activity completed")
        except Exception as e:
            logger.exception("Failed to perform cloud model sync workflow activity %s", e)

    @dapr_workflow.register_workflow
    @staticmethod
    def run_cloud_model_sync(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the cloud model sync workflow."""
        logger.info("Cloud model sync workflow started")
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_name = "cloud_model_sync_workflow"
        workflow_id = ctx.instance_id

        _ = yield ctx.call_activity(
            CloudModelSyncWorkflows.perform_cloud_model_sync,
            input={},
            retry_policy=retry_policy,
        )
        logger.info("Cloud model sync workflow completed")
        logger.info("Workflow %s with id %s completed", workflow_name, workflow_id)

        # Schedule the next run after 7 days
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(days=7))
        ctx.continue_as_new(payload)

    def __call__(self, workflow_id: Optional[str] = None):
        """Call the leaderboard cron workflow."""
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_cloud_model_sync",
            workflow_input={},
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="cloud_model_sync",
                    title="Cloud model sync",
                    description="Cloud model sync",
                )
            ],
        )

        return response
