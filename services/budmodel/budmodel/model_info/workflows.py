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

import asyncio
import math
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import NotificationContent, NotificationRequest, WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from ..commons.exceptions import LicenseExtractionException
from .schemas import (
    LicenseFAQRequest,
    LicenseFAQResponse,
    ModelExtractionETAObserverRequest,
    ModelExtractionRequest,
    ModelExtractionResponse,
    ModelInfo,
    ModelscanETAObserverRequest,
    ModelSecurityScanRequest,
    ModelSecurityScanResponse,
)
from .services import (
    LicenseFAQService,
    ModelExtractionETAObserver,
    ModelExtractionService,
    ModelSecurityScanService,
    SecurityScanETAObserver,
)


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)

# Workflow timeout constant (24 hours)
WORKFLOW_TIMEOUT_SECONDS = 24 * 60 * 60


@dapr_workflow.register_activity
def terminate_workflow_activity(ctx: wf.WorkflowActivityContext, workflow_id: str) -> None:
    """Terminate a Dapr workflow by ID.

    This activity is used to safely terminate workflows without blocking the workflow runtime.

    Args:
        ctx: Workflow activity context
        workflow_id: ID of the workflow to terminate
    """
    try:
        asyncio.run(DaprWorkflow().terminate_workflow(workflow_id=workflow_id))
        logger.info("Successfully terminated workflow %s", workflow_id)
    except Exception as e:
        logger.exception("Error terminating workflow %s: %s", workflow_id, e)
        raise


class ModelExtractionWorkflows:
    """Workflows for model extraction."""

    def __init__(self) -> None:
        """Initialize the ModelExtractionWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def validate_model_uri(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> None:
        """Validate the model URI."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return ModelExtractionService.validate_model_uri(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_activity
    @staticmethod
    def download_model(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> str:
        """Download the model."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return ModelExtractionService.download_model(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_activity
    @staticmethod
    def extract_model_info(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> ModelInfo:
        """Extract the model info."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return ModelExtractionService.extract_model_info(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_activity
    @staticmethod
    def save_model_to_registry(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> str:
        """Save the model to the registry."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return ModelExtractionService.save_model_to_registry(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_workflow
    @staticmethod
    def run_model_extraction(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the model extraction workflow."""
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        # Schedule the eta observer workflow
        eta_observer_request = ModelExtractionETAObserverRequest(**payload, workflow_id=ctx.instance_id)
        asyncio.run(ModelExtractionETAObserverWorkflows().__call__(eta_observer_request))

        workflow_name = "perform_model_extraction"
        workflow_id = ctx.instance_id
        request = ModelExtractionRequest(**payload)
        hf_token = request.hf_token  # TODO: add decryption logic here

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")

        _ = yield ctx.call_activity(
            ModelExtractionWorkflows.validate_model_uri,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "model_uri": request.model_uri,
                "provider_type": request.provider_type,
                "hf_token": hf_token,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        downloaded_path = yield ctx.call_activity(
            ModelExtractionWorkflows.download_model,
            input={
                "workflow_id": workflow_id,
                "model_name": request.model_name,
                "model_uri": request.model_uri,
                "provider_type": request.provider_type,
                "notification_request": notification_request_dict,
                "hf_token": hf_token,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        model_info = yield ctx.call_activity(
            ModelExtractionWorkflows.extract_model_info,
            input={
                "workflow_id": workflow_id,
                "model_path": downloaded_path,
                "model_uri": request.model_uri,
                "provider_type": request.provider_type,
                "notification_request": notification_request_dict,
                "hf_token": hf_token,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        _ = yield ctx.call_activity(
            ModelExtractionWorkflows.save_model_to_registry,
            input={
                "workflow_id": workflow_id,
                "model_path": downloaded_path,
                "notification_request": notification_request_dict,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        response = ModelExtractionResponse(workflow_id=workflow_id, model_info=model_info, local_path=downloaded_path)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Model Extraction Results",
            message="The model extraction results are ready",
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

    def __call__(self, request: ModelExtractionRequest, workflow_id: Optional[str] = None):
        """Schedule the model extraction workflow."""
        selected_workflow_id = str(workflow_id or uuid.uuid4())

        # Calculate the initial ETA
        eta = ModelExtractionService.calculate_initial_eta(
            request.provider_type, request.model_uri, selected_workflow_id, request.hf_token
        )
        # NOTE: Convert initial eta to minutes (frontend integration in minutes)
        eta = math.ceil(eta / 60)
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_model_extraction",
            workflow_input=request.model_dump(),
            workflow_id=selected_workflow_id,
            workflow_steps=[
                WorkflowStep(
                    id="validation",
                    title="Validating the model URI",
                    description="Ensure the model URI is valid",
                ),
                WorkflowStep(
                    id="model_download",
                    title="Downloading the model",
                    description="Download the model from the given URI",
                ),
                WorkflowStep(
                    id="model_extraction",
                    title="Extracting the model info",
                    description="Extract the model info from the downloaded model",
                ),
                WorkflowStep(
                    id="save_model",
                    title="Saving the model to the registry",
                    description="Save the model to the registry",
                ),
            ],
            eta=eta,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class ModelSecurityScanWorkflows:
    """Workflows for model security scan."""

    def __init__(self) -> None:
        """Initialize the ModelSecurityScanWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def perform_security_scan(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> str:
        """Perform the security scan."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return ModelSecurityScanService.perform_security_scan(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_workflow
    @staticmethod
    def run_model_security_scan(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the model security scan workflow."""
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        eta_observer_request = ModelscanETAObserverRequest(**payload, workflow_id=ctx.instance_id)
        asyncio.run(SecurityScanETAObserverWorkflows().__call__(eta_observer_request))

        workflow_name = "perform_model_security_scan"
        workflow_id = ctx.instance_id
        request = ModelSecurityScanRequest(**payload)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")

        scan_result = yield ctx.call_activity(
            ModelSecurityScanWorkflows.perform_security_scan,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "model_path": request.model_path,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        response = ModelSecurityScanResponse(workflow_id=workflow_id, scan_result=scan_result)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Model Security Scan Results",
            message="The model security scan results are ready",
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

    def __call__(self, request: ModelSecurityScanRequest, workflow_id: Optional[str] = None):
        """Schedule the model security scan workflow."""
        selected_workflow_id = str(workflow_id or uuid.uuid4())
        eta = ModelSecurityScanService.calculate_initial_eta(
            workflow_id=selected_workflow_id, model_path=request.model_path
        )

        eta = math.ceil(eta / 60)
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_model_security_scan",
            workflow_input=request.model_dump(),
            workflow_id=selected_workflow_id,
            workflow_steps=[
                WorkflowStep(
                    id="security_scan",
                    title="Performing the security scan",
                    description="Perform the security scan on the given model",
                ),
            ],
            eta=eta,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class LicenseFAQWorkflows:
    """Workflows for fetching License FAQs."""

    def __init__(self) -> None:
        """Initialize the LicenseFAQWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def fetch_license_faqs(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch the license FAQs."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        try:
            return LicenseFAQService.fetch_license_faqs(**kwargs, notification_request=notification_request)
        except (Exception, LicenseExtractionException) as e:
            logger.exception("Error fetching license FAQs: %s", e)
            return {}

    @dapr_workflow.register_workflow
    @staticmethod
    def run_license_faq_workflow(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the license FAQ fetching workflow."""
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_name = "fetch_license_faqs"
        workflow_id = ctx.instance_id
        request = LicenseFAQRequest(**payload)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")

        license_details = yield ctx.call_activity(
            LicenseFAQWorkflows.fetch_license_faqs,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "license_source": request.license_source,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
            },
            retry_policy=retry_policy,
        )

        response = LicenseFAQResponse(workflow_id=workflow_id, license_details=license_details)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="License FAQs Results",
            message="The license FAQs have been retrieved successfully",
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

    def __call__(self, request: LicenseFAQRequest, workflow_id: Optional[str] = None):
        """Schedule the license FAQ fetching workflow."""
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_license_faq_workflow",
            workflow_input=request.model_dump(),
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="fetch_license_faqs",
                    title="Fetching License FAQs",
                    description="Retrieve the FAQs from the given license source",
                ),
            ],
            eta=15 * 60,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class ModelExtractionETAObserverWorkflows:
    """Workflows for model extraction ETA observer."""

    def __init__(self) -> None:
        """Initialize the ModelExtractionETAObserverWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def perform_model_extraction_eta_observer(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> str:
        """Perform the model extraction ETA observer."""
        try:
            notification_request = NotificationRequest(**kwargs.pop("notification_request"))
            return ModelExtractionETAObserver().calculate_eta(**kwargs, notification_request=notification_request)
        except Exception as e:
            logger.exception("Error performing model extraction ETA observer: %s", e)
            raise e

    @dapr_workflow.register_workflow
    @staticmethod
    def model_extraction_eta_workflow(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the model extraction ETA observer workflow."""
        logger.debug("Is workflow replaying: %s", ctx.is_replaying)
        logger.debug("model_extraction_eta_workflow id: %s", ctx.instance_id)

        workflow_name = "model_extraction_eta_workflow"
        workflow_id = ctx.instance_id
        if isinstance(payload, str):
            request = ModelExtractionETAObserverRequest.model_validate_json(payload)
        else:
            request = ModelExtractionETAObserverRequest(**payload)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")

        _ = yield ctx.call_activity(
            ModelExtractionETAObserverWorkflows.perform_model_extraction_eta_observer,
            input={
                "workflow_id": request.workflow_id,
                "notification_request": notification_request_dict,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
                "model_uri": request.model_uri,
                "provider_type": request.provider_type,
                "hf_token": request.hf_token,
            },
            retry_policy=retry_policy,
        )

        # Get current status of the workflow
        workflow_current_status = asyncio.run(
            DaprWorkflow().get_workflow_details(workflow_id=request.workflow_id, fetch_payloads=True)
        )
        runtime_status = workflow_current_status["runtime_status"]
        logger.info("Current status of the workflow: %s", runtime_status)

        # Check for timeout (24 hours)
        current_time = ctx.current_utc_datetime.timestamp()
        if request.start_time is None:
            request.start_time = current_time

        elapsed_time = current_time - request.start_time
        if elapsed_time > WORKFLOW_TIMEOUT_SECONDS:
            logger.warning(
                "Workflow %s exceeded %d hours timeout. Terminating.", ctx.instance_id, WORKFLOW_TIMEOUT_SECONDS / 3600
            )

            # Notify user about timeout
            notification_request.payload.event = "timeout"
            notification_request.payload.content = NotificationContent(
                title="Workflow Timeout",
                message="Model extraction exceeded 24 hours and was terminated",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=request.workflow_id,
                notification=notification_request,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            # Terminate the main workflow via activity (non-blocking)
            yield ctx.call_activity(terminate_workflow_activity, input=request.workflow_id)

            return

        if runtime_status == "RUNNING":
            yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=60))
            ctx.continue_as_new(request.model_dump_json())
        else:
            logger.info(
                "Workflow is not running, skipping recursive workflow creation for model extraction eta observer"
            )
            return

    def __call__(self, request: ModelExtractionETAObserverRequest, workflow_id: Optional[str] = None):
        """Schedule the model eta observer workflow."""
        workflow_input = request.model_dump()
        response = dapr_workflow.schedule_workflow(
            workflow_name="model_extraction_eta_workflow",
            workflow_input=workflow_input,
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="model_extraction_eta_observer",
                    title="Model Extraction ETA Observer",
                    description="Observe the model extraction ETA",
                ),
            ],
            eta=86400,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class SecurityScanETAObserverWorkflows:
    """Workflows for model extraction ETA observer."""

    def __init__(self) -> None:
        """Initialize the ModelScanETAObserverWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity
    @staticmethod
    def perform_security_scan_eta_observer(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> str:
        """Perform the model scan ETA observer."""
        try:
            notification_request = NotificationRequest(**kwargs.pop("notification_request"))
            return SecurityScanETAObserver().calculate_eta(**kwargs, notification_request=notification_request)
        except Exception as e:
            logger.exception("Error performing model scan ETA observer: %s", e)
            raise e

    @dapr_workflow.register_workflow
    @staticmethod
    def model_scan_eta_workflow(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the model scan ETA observer workflow."""
        logger.debug("Is workflow replaying: %s", ctx.is_replaying)
        logger.debug("model_scan_eta_workflow id: %s", ctx.instance_id)

        workflow_name = "model_scan_eta_workflow"
        workflow_id = ctx.instance_id
        if isinstance(payload, str):
            request = ModelscanETAObserverRequest.model_validate_json(payload)
        else:
            request = ModelscanETAObserverRequest(**payload)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")

        _ = yield ctx.call_activity(
            SecurityScanETAObserverWorkflows.perform_security_scan_eta_observer,
            input={
                "workflow_id": request.workflow_id,
                "notification_request": notification_request_dict,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
                "model_path": request.model_path,
            },
            retry_policy=retry_policy,
        )

        # Get current status of the workflow
        workflow_current_status = asyncio.run(
            DaprWorkflow().get_workflow_details(workflow_id=request.workflow_id, fetch_payloads=True)
        )
        runtime_status = workflow_current_status["runtime_status"]
        logger.info("Current status of the workflow: %s", runtime_status)

        # Check for timeout (24 hours)
        current_time = ctx.current_utc_datetime.timestamp()
        if request.start_time is None:
            request.start_time = current_time

        elapsed_time = current_time - request.start_time
        if elapsed_time > WORKFLOW_TIMEOUT_SECONDS:
            logger.warning(
                "Workflow %s exceeded %d hours timeout. Terminating.", ctx.instance_id, WORKFLOW_TIMEOUT_SECONDS / 3600
            )

            # Notify user about timeout
            notification_request.payload.event = "timeout"
            notification_request.payload.content = NotificationContent(
                title="Workflow Timeout",
                message="Security scan exceeded 24 hours and was terminated",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=request.workflow_id,
                notification=notification_request,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            # Terminate the main workflow via activity (non-blocking)
            yield ctx.call_activity(terminate_workflow_activity, input=request.workflow_id)

            return

        if runtime_status == "RUNNING":
            yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=60))
            ctx.continue_as_new(request.model_dump_json())
        else:
            logger.info("Workflow is not running, skipping recursive workflow creation for model scan eta observer")
            return

    def __call__(self, request: ModelscanETAObserverRequest, workflow_id: Optional[str] = None):
        """Schedule the model eta observer workflow."""
        workflow_input = request.model_dump()
        response = dapr_workflow.schedule_workflow(
            workflow_name="model_scan_eta_workflow",
            workflow_input=workflow_input,
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="model_scan_eta_observer",
                    title="Model scan ETA Observer",
                    description="Observe the model scan ETA",
                ),
            ],
            eta=86400,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response
