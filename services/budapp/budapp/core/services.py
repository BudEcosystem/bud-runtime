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


"""Implements core services and business logic that power the microservices, including key functionality and integrations."""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from budapp.cluster_ops.services import ClusterService
from budapp.commons import logging
from budapp.commons.constants import (
    PAYLOAD_TO_WORKFLOW_STEP_EVENT,
    BudServeWorkflowStepEventName,
    NotificationCategory,
    PayloadType,
)
from budapp.commons.db_utils import SessionMixin
from budapp.model_ops.quantization_services import QuantizationService
from budapp.workflow_ops.crud import (
    WorkflowDataManager,
    WorkflowStepDataManager,
)
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.models import WorkflowStep as WorkflowStepModel

from ..benchmark_ops.services import BenchmarkService
from ..endpoint_ops.services import EndpointService
from ..model_ops.services import LocalModelWorkflowService, ModelService
from ..prompt_ops.services import PromptWorkflowService
from ..shared.notification_service import BudNotifyService, NotificationBuilder
from .crud import IconDataManager, ModelTemplateDataManager
from .models import Icon as IconModel
from .models import ModelTemplate as ModelTemplateModel
from .schemas import (
    NotificationPayload,
    NotificationResponse,
    NotificationResult,
)


logger = logging.get_logger(__name__)


# Notification related business logic


class NotificationService(SessionMixin):
    """Service for managing notifications."""

    async def update_recommended_cluster_events(self, payload: NotificationPayload) -> None:
        """Update the recommended cluster events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        try:
            await self._update_workflow_step_events(
                BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value,
                payload,
            )

            # Update progress in workflow
            await self._update_workflow_progress(
                BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value,
                payload,
            )
        except Exception:
            logger.error("Failed to update workflow step events")

        # Send number of recommended cluster as notification
        if payload.event == "results":
            await ClusterService(self.session).handle_recommended_cluster_events(payload)

        # FAILURE status handled for recommended cluster scheduler
        if payload.content.status == "FAILED":
            await ClusterService(self.session).handle_recommended_cluster_failure_events(payload)

    async def update_model_deployment_events(self, payload: NotificationPayload) -> None:
        """Update the model deployment events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value, payload)

        # Create endpoint when deployment is completed
        # Note: Cloud models create endpoints directly and don't use this notification path
        if payload.event == "results":
            await EndpointService(self.session).create_endpoint_from_notification_event(payload)

    async def update_cluster_creation_events(self, payload: NotificationPayload) -> None:
        """Update the cluster creation events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value, payload)

        # Create cluster in database if node info fetched successfully
        if payload.event == "results":
            await ClusterService(self.session).create_cluster_from_notification_event(payload)

    async def update_model_extraction_events(self, payload: NotificationPayload) -> None:
        """Update the model extraction events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.MODEL_EXTRACTION_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.MODEL_EXTRACTION_EVENTS.value, payload)

        # Create cluster in database if node info fetched successfully
        if payload.event == "results":
            await LocalModelWorkflowService(self.session).create_model_from_notification_event(payload)

    async def update_delete_cluster_events(self, payload: NotificationPayload) -> None:
        """Update the delete cluster events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS.value, payload)

        # Create cluster in database if node info fetched successfully
        if payload.event == "results":
            await ClusterService(self.session).delete_cluster_from_notification_event(payload)

    async def update_delete_endpoint_events(self, payload: NotificationPayload) -> None:
        """Update the delete endpoint events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS.value, payload)

        # Create cluster in database if node info fetched successfully
        if payload.event == "results":
            await EndpointService(self.session).delete_endpoint_from_notification_event(payload)

    async def update_delete_worker_events(self, payload: NotificationPayload) -> None:
        """Update the delete worker events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.DELETE_WORKER_EVENTS.value, payload)
        # Create cluster in database if node info fetched successfully
        if payload.event == "results":
            await EndpointService(self.session).delete_worker_from_notification_event(payload)

    async def update_model_security_scan_events(self, payload: NotificationPayload) -> None:
        """Update the model security scan events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(
            BudServeWorkflowStepEventName.MODEL_SECURITY_SCAN_EVENTS.value,
            payload,
        )

        # Update progress in workflow
        await self._update_workflow_progress(
            BudServeWorkflowStepEventName.MODEL_SECURITY_SCAN_EVENTS.value,
            payload,
        )

        # Create cluster in database if node info fetched successfully
        if payload.event == "results":
            await LocalModelWorkflowService(self.session).create_scan_result_from_notification_event(payload)

    async def update_license_faqs_update_events(self, payload: NotificationPayload) -> None:
        """Update the model license faqs events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.LICENSE_FAQ_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.LICENSE_FAQ_EVENTS.value, payload)

        # update faqs in database if node info fetched successfully
        if payload.event == "results":
            await ModelService(self.session).update_license_faqs_from_notification_event(payload)

    async def update_cluster_status_update_events(self, payload: NotificationPayload) -> None:
        """Update the cluster status update events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update cluster status in database
        if payload.event == "results":
            await ClusterService(self.session).update_cluster_status_from_notification_event(payload)

    async def update_endpoint_status_update_events(self, payload: NotificationPayload) -> None:
        """Update the endpoint status update events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update endpoint status in database
        if payload.event == "results":
            await EndpointService(self.session).update_endpoint_status_from_notification_event(payload)

    async def update_add_worker_to_deployment_events(self, payload: NotificationPayload) -> None:
        """Update the add worker to deployment events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value, payload)

        # Add worker to deployment
        if payload.event == "results":
            await EndpointService(self.session).add_worker_from_notification_event(payload)

    async def update_deploy_quantization_events(self, payload: NotificationPayload) -> None:
        """Update the deploy quantization events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(
            BudServeWorkflowStepEventName.QUANTIZATION_DEPLOYMENT_EVENTS.value,
            payload,
        )

        # Update progress in workflow
        await self._update_workflow_progress(
            BudServeWorkflowStepEventName.QUANTIZATION_DEPLOYMENT_EVENTS.value,
            payload,
        )

        # Add quantization to model
        if payload.event == "results":
            await QuantizationService(self.session).add_quantization_to_model_from_notification_event(payload)

    async def update_run_benchmark_events(self, payload: NotificationPayload) -> None:
        """Update the run benchmark events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value, payload)

        if payload.event == "results":
            await BenchmarkService(self.session).update_benchmark_status_from_notification_event(payload)

    async def update_evaluation_events(self, payload: NotificationPayload) -> None:
        """Update the evaluation workflow events for a workflow step.

        Mirrors other workflows: updates the step data and progress, and on completion
        persists any evaluation results metadata if provided.
        """
        logger.debug(
            "Eval notification received: type=%s event=%s workflow_id=%s",
            getattr(payload, "type", None),
            getattr(payload, "event", None),
            getattr(payload, "workflow_id", None),
        )
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.EVALUATION_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.EVALUATION_EVENTS.value, payload)

        # Hanle the failure status , even for non
        if payload.event == "monitor_eval_job_progress" and payload.content.status == "FAILED":
            logger.debug("XX Evaluation job failed XX")
            from ..eval_ops.services import EvaluationWorkflowService

            await EvaluationWorkflowService(self.session).update_eval_run_status_from_notification(payload)

        # Handle evaluation completion/failure events similar to cluster creation
        if payload.event == "results":
            from ..eval_ops.services import EvaluationWorkflowService

            await EvaluationWorkflowService(self.session).create_evaluation_from_notification_event(payload)

    async def update_adapter_deployment_events(self, payload: NotificationPayload) -> None:
        """Update the quantization deployment events for a workflow step."""
        # Update workflow step data event
        await self._update_workflow_step_events(
            BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS.value,
            payload,
        )

        # Update progress in workflow
        await self._update_workflow_progress(
            BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS.value,
            payload,
        )

        if payload.event == "results":
            await EndpointService(self.session).add_adapter_from_notification_event(payload)

    async def update_delete_adapter_events(self, payload: NotificationPayload) -> None:
        """Update the delete adapter events for a workflow step."""
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.ADAPTER_DELETE_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.ADAPTER_DELETE_EVENTS.value, payload)

        # Delete adapter from database
        if payload.event == "results":
            await EndpointService(self.session).delete_adapter_from_notification_event(payload)

    async def update_prompt_schema_events(self, payload: NotificationPayload) -> None:
        """Update the prompt schema events for a workflow step.

        Args:
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Update workflow step data event
        await self._update_workflow_step_events(BudServeWorkflowStepEventName.PROMPT_SCHEMA_EVENTS.value, payload)

        # Update progress in workflow
        await self._update_workflow_progress(BudServeWorkflowStepEventName.PROMPT_SCHEMA_EVENTS.value, payload)

        # Create prompt_id in workflow response
        if payload.event == "results":
            await PromptWorkflowService(self.session).create_prompt_schema_from_notification_event(payload)

    async def update_eta_events(self, payload: NotificationPayload) -> None:
        """Update ETA value for workflow progress and step."""
        if not payload.workflow_id:
            logger.error("No workflow_id provided in ETA payload")
            return

        try:
            eta = int(payload.content.message)
        except (TypeError, ValueError):
            logger.error(
                "Invalid ETA value received for workflow %s: %s",
                payload.workflow_id,
                payload.content.message,
            )
            return

        event_name = PAYLOAD_TO_WORKFLOW_STEP_EVENT.get(PayloadType(payload.type))
        if not event_name:
            logger.error(
                "No workflow step mapping found for payload type %s",
                payload.type,
            )
            return

        # Update workflow progress ETA
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
            WorkflowModel, {"id": payload.workflow_id}
        )
        if db_workflow and isinstance(db_workflow.progress, dict):
            progress = db_workflow.progress
            progress["eta"] = eta
            self.session.refresh(db_workflow)
            await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"progress": progress})

        # Update workflow step ETA
        db_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps_by_data(
            data_key=event_name.value, workflow_id=payload.workflow_id
        )
        if db_steps:
            # Get and validate latest step
            latest_step = db_steps[-1]

            # Update step data with ETA
            data = latest_step.data
            event_data = data.get(event_name.value, {})
            event_data["eta"] = eta
            data[event_name.value] = event_data

            # Refresh step and update data in db
            self.session.refresh(latest_step)
            await WorkflowStepDataManager(self.session).update_by_fields(latest_step, {"data": data})
        else:
            logger.error(
                "Error updating ETA for workflow %s: No workflow step found",
                payload.workflow_id,
            )

    async def _update_workflow_step_events(self, event_name: str, payload: NotificationPayload) -> None:
        """Update the workflow step events for a workflow step.

        Args:
            event_name: The name of event to update.
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Fetch workflow steps with simulator events
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps_by_data(
            data_key=event_name, workflow_id=payload.workflow_id
        )

        if not db_workflow_steps:
            logger.warning(f"No workflow steps found for workflow {payload.workflow_id}")
            return

        # Get and validate latest step
        latest_step = db_workflow_steps[-1]

        # Update the payload for the event
        updated_data = await self._update_step_data(event_name, latest_step, payload)

        if not updated_data:
            logger.warning(f"No matching event found for {payload.event}")
            return

        # Update the workflow step data
        # refresh sqlalchemy session otherwise the updated data will not be reflected in the session
        self.session.refresh(latest_step)
        db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
            latest_step, {"data": updated_data}
        )
        logger.info(f"Updated workflow step with {event_name} events: {db_workflow_step.id}")

    async def _update_step_data(
        self,
        event_name: str,
        step: WorkflowStepModel,
        payload: NotificationPayload,
    ) -> dict:
        """Update the payload for the event in the step data.

        Args:
            event_name: The name of event to update.
            step: The workflow step to update.
            payload: The payload to update the step with.

        Returns:
            The updated step data or None if the update failed.
        """
        data = step.data
        simulator_events = data.get(event_name, {})
        steps = simulator_events.get("steps", [])

        if not isinstance(steps, list):
            logger.warning("Steps data is not in expected format")
            return None

        updated = False
        for step_data in steps:
            if isinstance(step_data, dict) and step_data.get("id") == payload.event:
                step_data["payload"] = payload.model_dump(exclude_unset=True, mode="json")
                updated = True
                break

        if not updated:
            logger.warning(
                "No matching step id found for event '%s' in '%s'. Available step ids: %s",
                payload.event,
                event_name,
                [s.get("id") for s in steps if isinstance(s, dict)],
            )
        return data if updated else None

    async def _update_workflow_progress(self, event_name: str, payload: NotificationPayload) -> None:
        """Update the workflow progress for a workflow step.

        Args:
            event_name: The name of event to update.
            payload: The payload to update the step with.

        Returns:
            None
        """
        # Fetch workflow with progress
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
            WorkflowModel, {"id": payload.workflow_id}
        )

        if not isinstance(db_workflow.progress, dict):
            logger.warning(f"Workflow {payload.workflow_id} progress is not in expected format")
            return

        progress_type = db_workflow.progress.get("progress_type")
        if progress_type != event_name:
            logger.warning(f"Progress type {progress_type} does not match event name {event_name}")
            return

        updated_progress = await self._update_progress_data(db_workflow.progress, payload)
        if not updated_progress:
            logger.warning(f"No matching event found for {payload.event}")
            return

        # Update progress in workflow
        self.session.refresh(db_workflow)
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": updated_progress}
        )
        logger.info(f"Updated workflow progress: {db_workflow.id}")

    async def _update_progress_data(
        self, progress: Dict[str, Any], payload: NotificationPayload
    ) -> Optional[Dict[str, Any]]:
        """Update the progress data for a workflow.

        Args:
            payload: The payload to update the step.
            progress: The progress data to update.

        Returns:
            The updated progress data or None if the update failed.
        """
        steps = progress.get("steps", [])

        if not isinstance(steps, list):
            logger.warning("Steps data is not in expected format")
            return

        updated = False
        for step_data in steps:
            if isinstance(step_data, dict) and step_data.get("id") == payload.event:
                step_data["payload"] = payload.model_dump(exclude_unset=True, mode="json")
                updated = True
                break

        return progress if updated else None


class SubscriberHandler:
    """Service for handling subscriber events."""

    def __init__(self, session: Session):
        """Initialize the SubscriberHandler with a database session."""
        self.session = session

    async def handle_subscriber_event(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the subscriber event."""
        logger.debug(f"Received subscriber event: {payload}")

        if payload.category != NotificationCategory.INTERNAL:
            logger.warning("Skipping non-internal notification")
            return NotificationResponse(
                object="notification",
                message="Pubsub notification received",
            ).to_http_response()

        if payload.event == "eta":
            await NotificationService(self.session).update_eta_events(payload)
            return NotificationResponse(
                object="notification",
                message="Updated workflow ETA",
            ).to_http_response()

        handlers = {
            PayloadType.DEPLOYMENT_RECOMMENDATION: self._handle_deployment_recommendation,
            PayloadType.DEPLOY_MODEL: self._handle_deploy_model,
            PayloadType.REGISTER_CLUSTER: self._handle_register_cluster,
            PayloadType.PERFORM_MODEL_EXTRACTION: self._handle_perform_model_extraction,
            PayloadType.PERFORM_MODEL_SECURITY_SCAN: self._handle_perform_model_security_scan,
            PayloadType.DELETE_CLUSTER: self._handle_delete_cluster,
            PayloadType.DELETE_DEPLOYMENT: self._handle_delete_endpoint,
            PayloadType.CLUSTER_STATUS_UPDATE: self._handle_cluster_status_update,
            PayloadType.DEPLOYMENT_STATUS_UPDATE: self._handle_endpoint_status_update,
            PayloadType.DELETE_WORKER: self._handle_delete_worker,
            PayloadType.ADD_WORKER: self._handle_add_worker_to_deployment,
            PayloadType.FETCH_LICENSE_FAQS: self._handle_license_faqs_update,
            PayloadType.DEPLOY_QUANTIZATION: self._handle_deploy_quantization,
            PayloadType.RUN_BENCHMARK: self._handle_run_benchmark,
            PayloadType.ADD_ADAPTER: self._handle_deploy_adapter,
            PayloadType.DELETE_ADAPTER: self._handle_delete_adapter,
            PayloadType.EVALUATE_MODEL: self._handle_evaluate_model,
            PayloadType.PERFORM_PROMPT_SCHEMA: self._handle_perform_prompt_schema,
        }

        handler = handlers.get(payload.type)
        if not handler:
            logger.warning(f"No handler found for payload type: {payload.type}")
            return NotificationResponse(
                object="notification", message="Pubsub notification received"
            ).to_http_response()

        return await handler(payload)

    async def _handle_deployment_recommendation(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the deployment recommendation event."""
        await NotificationService(self.session).update_recommended_cluster_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated recommended cluster event in workflow step",
        ).to_http_response()

    async def _handle_deploy_model(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the deploy model event."""
        await NotificationService(self.session).update_model_deployment_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated model deployment event in workflow step",
        ).to_http_response()

    async def _handle_register_cluster(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the register cluster event."""
        await NotificationService(self.session).update_cluster_creation_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated cluster creation event in workflow step",
        ).to_http_response()

    async def _handle_perform_model_extraction(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the perform model extraction event."""
        await NotificationService(self.session).update_model_extraction_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated model extraction event in workflow step",
        ).to_http_response()

    async def _handle_perform_model_security_scan(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the perform model security scan event."""
        await NotificationService(self.session).update_model_security_scan_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated model security scan event in workflow step",
        ).to_http_response()

    async def _handle_delete_cluster(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the delete cluster event."""
        await NotificationService(self.session).update_delete_cluster_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated delete cluster event in workflow step",
        ).to_http_response()

    async def _handle_delete_endpoint(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the delete endpoint event."""
        await NotificationService(self.session).update_delete_endpoint_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated delete endpoint event in workflow step",
        ).to_http_response()

    async def _handle_cluster_status_update(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the cluster status update event."""
        await NotificationService(self.session).update_cluster_status_update_events(payload)
        return NotificationResponse(
            object="notification",
            message="Update cluster status in db",
        ).to_http_response()

    async def _handle_endpoint_status_update(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the endpoint status update event."""
        await NotificationService(self.session).update_endpoint_status_update_events(payload)
        return NotificationResponse(
            object="notification",
            message="Update endpoint status in db",
        ).to_http_response()

    async def _handle_delete_worker(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the delete worker event."""
        await NotificationService(self.session).update_delete_worker_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated delete worker event in workflow step",
        ).to_http_response()

    async def _handle_add_worker_to_deployment(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the add worker to deployment event."""
        await NotificationService(self.session).update_add_worker_to_deployment_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated add worker to deployment event in workflow step",
        ).to_http_response()

    async def _handle_license_faqs_update(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the license faq update event."""
        await NotificationService(self.session).update_license_faqs_update_events(payload)
        return NotificationResponse(
            object="notification",
            message="Update license faqs in db",
        ).to_http_response()

    async def _handle_deploy_quantization(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the deploy quantization event."""
        await NotificationService(self.session).update_deploy_quantization_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated deploy quantization event in workflow step",
        ).to_http_response()

    async def _handle_run_benchmark(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the run benchmark event."""
        await NotificationService(self.session).update_run_benchmark_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated run benchmark event in workflow step",
        ).to_http_response()

    async def _handle_deploy_adapter(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the adapter deployment event."""
        await NotificationService(self.session).update_adapter_deployment_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated run adapter event in workflow step",
        ).to_http_response()

    async def _handle_delete_adapter(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the adapter deletion event."""
        await NotificationService(self.session).update_delete_adapter_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated delete adapter event in workflow step",
        ).to_http_response()

    async def _handle_evaluate_model(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the evaluate model (budeval) events."""
        await NotificationService(self.session).update_evaluation_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated evaluation event in workflow step",
        ).to_http_response()

    async def _handle_perform_prompt_schema(self, payload: NotificationPayload) -> NotificationResponse:
        """Handle the perform prompt schema event."""
        await NotificationService(self.session).update_prompt_schema_events(payload)
        return NotificationResponse(
            object="notification",
            message="Updated prompt schema event in workflow step",
        ).to_http_response()


class IconService(SessionMixin):
    """Service for managing icons."""

    async def get_all_icons(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[IconModel], int]:
        """Get all icon icons."""
        return await IconDataManager(self.session).get_all_icons(offset, limit, filters, order_by, search)


class ModelTemplateService(SessionMixin):
    """Service for managing model templates."""

    async def get_all_templates(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ModelTemplateModel], int]:
        """Get all model templates."""
        return await ModelTemplateDataManager(self.session).get_all_model_templates(
            offset, limit, filters, order_by, search
        )
