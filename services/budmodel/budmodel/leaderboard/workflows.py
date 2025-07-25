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

"""This file contains the workflows for the leaderboard API."""

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


class LeaderboardCronWorkflows:
    """Workflows for the leaderboard cron."""

    def __init__(self) -> None:
        """Initialize the LeaderboardCronWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def perform_leaderboard_cron(ctx: wf.WorkflowActivityContext) -> None:
        """Perform the leaderboard cron workflow."""
        try:
            asyncio.run(LeaderboardService().upsert_leaderboard_from_all_sources())
            logger.info("Leaderboard cron workflow activity completed")
        except Exception as e:
            logger.exception("Failed to perform leaderboard cron workflow activity %s", e)

    @dapr_workflow.register_workflow
    @staticmethod
    def run_leaderboard_cron(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the leaderboard cron workflow."""
        logger.info("Leaderboard cron workflow started")
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_name = "leaderboard_cron_workflow"
        workflow_id = ctx.instance_id

        _ = yield ctx.call_activity(
            LeaderboardCronWorkflows.perform_leaderboard_cron,
        )
        logger.info("Leaderboard cron workflow completed")
        logger.info("Workflow %s with id %s completed", workflow_name, workflow_id)

        # Schedule the next run after 7 days
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(days=7))
        ctx.continue_as_new(payload)

    def __call__(self, workflow_id: Optional[str] = None):
        """Call the leaderboard cron workflow."""
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_leaderboard_cron",
            workflow_input={},
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="leaderboard_cron",
                    title="Update leaderboard from all sources",
                    description="Update leaderboard from all sources periodically",
                )
            ],
        )

        return response
