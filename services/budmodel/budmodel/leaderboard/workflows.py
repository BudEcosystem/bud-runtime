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

"""This file contains the workflows for the leaderboard extraction.

The leaderboard extraction uses a combination of Dapr cron bindings and workflows:
1. Dapr cron binding triggers the /extraction-cron endpoint every 7 days
2. The endpoint triggers this workflow asynchronously (non-blocking)
3. The workflow orchestrates the extraction activities in the background

This pattern ensures:
- No blocking of the FastAPI server during long-running extraction
- Proper async execution managed by Dapr workflows
- Retry logic and fault tolerance
- Consistent with budprompt and budapp patterns
"""

import asyncio
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.schemas import WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from .services import LeaderboardService


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class LeaderboardExtractionWorkflow:
    """Workflow for leaderboard extraction from all sources."""

    def __init__(self) -> None:
        """Initialize the LeaderboardExtractionWorkflow class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def extract_leaderboard_data(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Extract leaderboard data from all sources.

        This activity performs the actual long-running extraction work.
        It runs asynchronously in the background without blocking the HTTP server.

        Args:
            ctx: Workflow activity context from Dapr.
            kwargs: Additional keyword arguments (currently unused).

        Raises:
            Exception: If extraction fails, will be retried based on retry_policy.
        """
        try:
            asyncio.run(LeaderboardService().upsert_leaderboard_from_all_sources())
            logger.info("Leaderboard extraction workflow activity completed")
        except Exception as e:
            logger.exception("Failed to extract leaderboard data: %s", e)
            raise

    @dapr_workflow.register_workflow
    @staticmethod
    def run_leaderboard_extraction(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the leaderboard extraction workflow.

        This workflow orchestrates the extraction process by calling the
        extract_leaderboard_data activity with retry logic.

        Args:
            ctx: Workflow context from Dapr.
            payload: Workflow input payload (currently unused).

        Returns:
            dict: Status information about the completed workflow.
        """
        logger.info("Leaderboard extraction workflow started")
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_id = ctx.instance_id

        _ = yield ctx.call_activity(
            LeaderboardExtractionWorkflow.extract_leaderboard_data,
            input={},
            retry_policy=retry_policy,
        )

        logger.info("Leaderboard extraction workflow completed for workflow_id: %s", workflow_id)
        return {"status": "completed", "workflow_id": workflow_id}

    def __call__(self, workflow_id: Optional[str] = None):
        """Schedule the leaderboard extraction workflow.

        This method schedules a new workflow instance to run asynchronously.
        It returns immediately without waiting for the workflow to complete.

        Args:
            workflow_id: Optional workflow ID. If not provided, a UUID will be generated.

        Returns:
            Workflow response from Dapr scheduler.
        """
        selected_workflow_id = str(workflow_id or uuid.uuid4())

        response = dapr_workflow.schedule_workflow(
            workflow_name="run_leaderboard_extraction",
            workflow_input={},
            workflow_id=selected_workflow_id,
            workflow_steps=[
                WorkflowStep(
                    id="extract_leaderboard",
                    title="Extract leaderboard data",
                    description="Extract and update leaderboard data from all sources",
                )
            ],
        )

        return response
