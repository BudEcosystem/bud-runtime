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


"""Implements Dapr Workflows for long running tasks."""

import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import NotificationContent, NotificationRequest, WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from .schemas import PromptSchemaRequest, PromptSchemaResponse
from .services import PromptConfigurationService


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)

# Set this to None since retry policy is not used in the workflow
retry_policy = None


class PromptSchemaWorkflow:
    """Workflow for prompt schema."""

    def __init__(self) -> None:
        """Initialize the PromptSchemaWorkflow class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def validate_schema(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Validate the schema."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return PromptConfigurationService.validate_schema(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_activity
    @staticmethod
    def generate_validation_codes(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Generate the validation codes."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return PromptConfigurationService.generate_validation_codes(
            **kwargs, notification_request=notification_request
        )

    @dapr_workflow.register_activity
    @staticmethod
    def store_prompt_configuration(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Store the prompt configuration."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return PromptConfigurationService.store_prompt_configuration(
            **kwargs, notification_request=notification_request
        )

    @dapr_workflow.register_workflow
    @staticmethod
    def run_prompt_schema(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the prompt schema workflow."""
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_name = "perform_prompt_schema"
        workflow_id = ctx.instance_id
        request = PromptSchemaRequest(**payload)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")

        _ = yield ctx.call_activity(
            PromptSchemaWorkflow.validate_schema,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "request": request,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        validation_codes = yield ctx.call_activity(
            PromptSchemaWorkflow.generate_validation_codes,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "request": request,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        _ = yield ctx.call_activity(
            PromptSchemaWorkflow.store_prompt_configuration,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "request": request,
                "validation_codes": validation_codes,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        response = PromptSchemaResponse(workflow_id=workflow_id)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Prompt Schema Results",
            message="The prompt schema results are ready",
            result=response.model_dump(mode="json"),
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response.model_dump(mode="json")

    def __call__(self, request: PromptSchemaRequest, workflow_id: Optional[str] = None):
        """Schedule the prompt schema workflow."""
        selected_workflow_id = str(workflow_id or uuid.uuid4())

        response = dapr_workflow.schedule_workflow(
            workflow_name="run_prompt_schema",
            workflow_input=request.model_dump(),
            workflow_id=selected_workflow_id,
            workflow_steps=[
                WorkflowStep(
                    id="validation",
                    title="Validating the schema",
                    description="Ensure the schema is valid",
                ),
                WorkflowStep(
                    id="code_generation",
                    title="Generating the validation codes",
                    description="Generate the validation codes for the schema",
                ),
                WorkflowStep(
                    id="save_prompt_configuration",
                    title="Saving the prompt configuration to the Redis",
                    description="Save the prompt configuration to the Redis",
                ),
            ],
            eta=None,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response
