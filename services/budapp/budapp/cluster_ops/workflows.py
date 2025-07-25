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

"""This file contains the workflows for the cluster operations."""

import uuid
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

import dapr.ext.workflow as wf
from budmicroframe.commons.schemas import WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from ..commons import logging
from .scheduler import RecommendedClusterScheduler


logger = logging.get_logger(__name__)


dapr_workflow = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class ClusterRecommendedSchedulerWorkflows:
    """Workflows for the recommended cluster schedule."""

    def __init__(self) -> None:
        """Initialize the ClusterRecommendedSchedulerWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def perform_cluster_recommended_scheduler(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Perform the recommended cluster schedule workflow."""
        model_id = kwargs.get("model_id")
        model_id = UUID(model_id) if model_id else None
        try:
            RecommendedClusterScheduler().execute_cluster_recommendation(model_id=model_id)
            logger.info("Cluster recommended scheduler workflow activity completed")
        except Exception as e:
            logger.exception("Failed to perform cluster recommended scheduler workflow activity %s", e)

    @dapr_workflow.register_workflow
    @staticmethod
    def run_recommended_cluster_schedule(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the recommended cluster schedule workflow."""
        logger.info("Recommended cluster schedule workflow started")
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_name = "recommended_cluster_schedule_workflow"
        workflow_id = ctx.instance_id

        model_id = payload.get("model_id")

        _ = yield ctx.call_activity(
            ClusterRecommendedSchedulerWorkflows.perform_cluster_recommended_scheduler,
            input={"model_id": model_id},
            retry_policy=retry_policy,
        )
        logger.info("Recommended cluster schedule workflow completed")
        logger.info("Workflow %s with id %s completed", workflow_name, workflow_id)

    def __call__(self, model_id: Optional[UUID] = None, workflow_id: Optional[str] = None):
        """Call the leaderboard cron workflow."""
        model_id = str(model_id) if model_id else None
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_recommended_cluster_schedule",
            workflow_input={"model_id": model_id},
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="recommended_cluster_schedule",
                    title="Recommended cluster schedule",
                    description="Recommended cluster schedule",
                )
            ],
        )

        return response
