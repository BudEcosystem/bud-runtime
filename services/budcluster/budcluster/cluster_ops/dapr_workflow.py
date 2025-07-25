import asyncio
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from dapr.conf import settings as dapr_settings
from dapr.ext.workflow import (
    DaprWorkflowClient,
    WorkflowRuntime,
)
from dapr.ext.workflow import (
    WorkflowStatus as DaprWorkflowStatus,
)
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import func

from budmicroframe.commons import logging, singleton
from budmicroframe.commons.config import get_app_settings, get_secrets_settings
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStep,
)
from budmicroframe.shared.dapr_service import DaprService
from budmicroframe.shared.dapr_workflow import WorkflowRunsSchema, WorkflowStepsSchema
from budmicroframe.shared.psql_service import CRUDMixin


logger = logging.get_logger(__name__)


class WorkflowNotFoundException(Exception):
    """Exception raised when a workflow is not found."""

    pass


class WorkflowAlreadyExistsException(Exception):
    """Exception raised when a workflow already exists."""

    pass


# class WorkflowRunsSchema(PSQLBase):
#     __tablename__ = "workflow_runs"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     workflow_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
#     workflow_name = Column(String(128), nullable=False)
#     status = Column(String(20), nullable=True)
#     input = Column(JSONB, nullable=False)
#     output = Column(JSONB, nullable=True)
#     error = Column(String(255), nullable=True)
#     notification_status = Column(JSONB, nullable=True)
#     num_retries = Column(Integer, nullable=False, default=0)
#     max_retries = Column(Integer, nullable=False, default=-1)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     modified_at = Column(DateTime(timezone=True), onupdate=func.now())

#     steps = relationship("WorkflowStepsSchema", back_populates="workflow_run")

#     def __repr__(self):
#         return f"<WorkflowRunsSchema(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"


# class WorkflowStepsSchema(PSQLBase):
#     __tablename__ = "workflow_steps"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.workflow_id"), nullable=False)
#     step_id = Column(String(128), nullable=False)
#     status = Column(String(20), nullable=True)
#     notification_status = Column(JSONB, nullable=True)
#     num_retries = Column(Integer, nullable=False, default=0)
#     max_retries = Column(Integer, nullable=False, default=-1)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     modified_at = Column(DateTime(timezone=True), onupdate=func.now())

#     workflow_run = relationship("WorkflowRunsSchema", back_populates="steps")

#     def __repr__(self):
#         return f"<WorkflowStepsSchema(id={self.id}, workflow_id={self.workflow_id}, step_id={self.step_id}, status={self.status})>"


class WorkflowRunsCRUD(CRUDMixin[WorkflowRunsSchema, None, None]):
    __model__ = WorkflowRunsSchema

    def __init__(self):
        super().__init__(model=self.__model__)


class WorkflowStepsCRUD(CRUDMixin[WorkflowStepsSchema, None, None]):
    __model__ = WorkflowStepsSchema

    def __init__(self):
        super().__init__(model=self.__model__)


class WorkflowCRUD:
    def __init__(self):
        self.workflow_runs_crud = WorkflowRunsCRUD()
        self.workflow_steps_crud = WorkflowStepsCRUD()

    def add_new_workflow_run(
        self,
        workflow_id: str,
        workflow_name: str,
        status: WorkflowStatus,
        input_data: Dict[str, Any],
        workflow_steps: Optional[List[WorkflowStep]] = None,
    ) -> None:
        try:
            workflow_run = WorkflowRunsSchema(
                workflow_id=workflow_id, workflow_name=workflow_name, status=status.value, input=input_data
            )
            self.workflow_runs_crud.insert(workflow_run)

            if workflow_steps:
                steps_to_insert = [
                    {"workflow_id": workflow_id, "step_id": step.id, "status": status.value} for step in workflow_steps
                ]
                self.workflow_steps_crud.bulk_insert(steps_to_insert)

            logger.debug("New workflow run %s added", workflow_id)
        except Exception as e:
            logger.error("Failed to add new workflow run %s: %s", workflow_id, str(e))

    def update_workflow_progress(self, workflow_id: str, notification: NotificationRequest) -> None:
        workflow_or_step_status = notification.payload.content.status.value
        notification_hash = notification.get_hash()
        skip_notification = False
        failure_statuses = (
            WorkflowStatus.FAILED.value,
            WorkflowStatus.TERMINATED.value,
            WorkflowStatus.SUSPENDED.value,
        )

        def update_notification_status(obj: Union[WorkflowStepsSchema, WorkflowRunsSchema]) -> None:
            obj.notification_status = obj.notification_status or {}
            notification_status_values = list(obj.notification_status.values())
            was_completed = WorkflowStatus.COMPLETED.value in notification_status_values
            was_failed = any(status in notification_status_values for status in failure_statuses)

            if (
                workflow_or_step_status == WorkflowStatus.STARTED.value
                and WorkflowStatus.STARTED.value in notification_status_values
            ):
                obj.num_retries += 1

            if notification_hash not in obj.notification_status:
                obj.notification_status[notification_hash] = workflow_or_step_status
            elif was_completed and workflow_or_step_status in failure_statuses:
                obj.notification_status = {
                    k: v for k, v in obj.notification_status.items() if v != WorkflowStatus.COMPLETED.value
                }
                was_completed = False
            elif was_failed and workflow_or_step_status == WorkflowStatus.COMPLETED.value:
                obj.notification_status = {
                    k: v for k, v in obj.notification_status.items() if v not in failure_statuses
                }

            return was_completed

        run = self.workflow_runs_crud.fetch_one(conditions={"workflow_id": workflow_id})
        if not run:
            logger.warning("Workflow run not found for %s", workflow_id)
            return False

        step = self.workflow_steps_crud.fetch_one(
            conditions={"workflow_id": workflow_id, "step_id": notification.payload.event}
        )
        logger.debug(f"::Cloud Workflow:: Step {step}")
        logger.debug(f"::Cloud Workflow:: Step {step.id} {step.status} {step.notification_status}")

        try:
            if step:
                logger.debug("Workflow step found for %s:%s, %s:%s, %s", workflow_id, step.step_id, notification_hash, step.status, step.notification_status)
                skip_notification = update_notification_status(step)
                step.status = workflow_or_step_status
                self.workflow_steps_crud.update(data=step, conditions={"id": step.id})
            else:
                logger.debug("Workflow run found for %s, %s:%s, %s", workflow_id, notification_hash, run.status, run.notification_status)
                skip_notification = update_notification_status(run)
                if notification.payload.event == "results":
                    run.output = notification.payload.content.result
        except Exception as e:
            logger.exception("Failed to update workflow progress for %s: %s", workflow_id, str(e))
            raise e

        run.status = workflow_or_step_status
        self.workflow_runs_crud.update(data=run, conditions={"id": run.id})

        return skip_notification


class DaprWorkflow(WorkflowCRUD, metaclass=singleton.Singleton):
    def __init__(
        self,
        dapr_grpc_or_http_port: Optional[int] = None,
        dapr_api_token: Optional[str] = None,
    ) -> None:
        super().__init__()

        app_settings = get_app_settings()
        secrets_settings = get_secrets_settings()
        if app_settings is not None and secrets_settings is not None:
            self.dapr_grpc_or_http_port = dapr_grpc_or_http_port or app_settings.dapr_grpc_port
            dapr_api_token = dapr_api_token or secrets_settings.dapr_api_token
        else:
            self.dapr_grpc_or_http_port = dapr_grpc_or_http_port
            logger.warning("App/Secrets settings are not registered, some funcionalities might not work as intended.")

        dapr_settings.DAPR_API_TOKEN = dapr_api_token

        self.workflow_runtime: WorkflowRuntime = WorkflowRuntime(host="127.0.0.1", port=self.dapr_grpc_or_http_port)
        self.wf_client: Optional[DaprWorkflowClient] = None
        self.is_running = False

        self.registered_workflows = {}
        self.registered_activities = {}
        self.registered_jobs = {}

        # Start
        self.start_workflow_runtime()

    def start_workflow_runtime(self) -> None:
        if not self.is_running:
            self.workflow_runtime.start()
            self.wf_client = DaprWorkflowClient(host="127.0.0.1", port=self.dapr_grpc_or_http_port)
            self.is_running = True
        else:
            logger.warning("Workflow runtime is already running")

    def shutdown_workflow_runtime(self) -> None:
        """Shutdown the workflow runtime if it is currently running.

        This static method checks if the workflow runtime is initialized.
        If it is, it shuts down the workflow runtime and sets the global
        workflow_runtime variable to None.

        Raises:
            Exception: If there is an error during the shutdown of workflows.
        """
        if self.is_running:
            self.workflow_runtime.shutdown()
            self.wf_client = None
            self.is_running = False
        else:
            logger.warning("Workflow runtime is not running")

    def register_workflow(self, func: Callable[..., None], name: Optional[str] = None) -> Callable[..., None]:
        """Register a workflow function.

        This decorator adds the provided workflow function to the global list of registered workflows,
        allowing it to be recognized and executed by the workflow runtime.

        Args:
            func (Callable[..., None]): The workflow function to register.

        Returns:
            Callable[..., None]: The original workflow function.
        """
        name = name or func.__name__
        self.registered_workflows[name] = func
        decorated_func = self.workflow_runtime.workflow(func)
        return decorated_func

    def register_activity(self, func: Callable[..., None], name: Optional[str] = None) -> Callable[..., None]:
        """Register an activity function.

        This decorator adds the provided activity function to the global list of registered activities,
        allowing it to be recognized and executed by the workflow runtime.

        Args:
            func (Callable[..., None]): The activity function to register.

        Returns:
            Callable[..., None]: The original activity function.
        """
        name = name or func.__name__
        self.registered_activities[name] = func
        decorated_func = self.workflow_runtime.activity(func)
        return decorated_func

    def publish_notification(
        self,
        workflow_id: str,
        notification: NotificationRequest,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        is_replaying: bool = False,
    ) -> None:
        skip_notification = self.update_workflow_progress(workflow_id, notification)
        if skip_notification:
            logger.info("Skipping notification for %s:%s", notification.payload.type, notification.payload.event)
            return

        logger.info(
            "Publishing %s:%s notification for workflow %s with status %s",
            notification.payload.type,
            notification.payload.event,
            workflow_id,
            notification.payload.content.status.name,
        )

        dapr_service = DaprService()
        notification_data = notification.model_dump(mode="json")

        app_settings = get_app_settings()
        if app_settings.notify_service_name and not (
            notification.subscriber_ids is None and notification.topic_keys is None
        ):
            try:
                dapr_service.publish_to_topic(
                    data=notification_data,
                    target_name=app_settings.notify_service_name,
                    target_topic_name=app_settings.notify_service_topic,
                    event_type="notification",
                )
            except Exception as e:
                logger.exception(
                    "Failed to publish %s notification to %s: %s",
                    notification.payload.type,
                    app_settings.notify_service_name,
                    str(e),
                )

        if target_topic_name or target_name:
            try:
                dapr_service.publish_to_topic(
                    data=notification_data,
                    target_topic_name=target_topic_name,
                    target_name=target_name,
                    event_type=notification.payload.type,
                )
            except Exception as e:
                logger.exception(
                    "Failed to publish %s notification to %s: %s",
                    notification.payload.type,
                    target_name or target_topic_name,
                    str(e),
                )

    async def get_workflow_details(
        self, workflow_id: Union[str, uuid.UUID], fetch_payloads: bool = False, skip_logs: bool = False
    ) -> Dict[str, Any]:
        """Retrieve details of a specific workflow by its ID.

        This asynchronous method fetches the workflow details from the Dapr
        workflow component. It logs the workflow's runtime status, output,
        and any errors encountered during execution. If the workflow is not
        found, it raises a WorkflowNotFoundException.

        Args:
            workflow_id (str): The unique identifier of the workflow to retrieve.

        Returns:
            dict: A dictionary containing the workflow's status, output, error details,
            and custom status.

        Raises:
            WorkflowNotFoundException: If no workflow exists with the provided ID.
            DaprInternalError: If there is an error while fetching the workflow details.
        """
        workflow_id = str(workflow_id)
        try:
            wf_state = self.wf_client.get_workflow_state(instance_id=workflow_id, fetch_payloads=fetch_payloads)
            if not skip_logs:
                logger.info("Workflow %s returned %s", workflow_id, wf_state)
            if not wf_state:
                raise WorkflowNotFoundException("No such workflow exists")
            return wf_state.to_json()
        except Exception as err:
            if not skip_logs:
                logger.exception("Couldn't resolve workflow status: %s", str(err))
            if "no such instance exists" in str(err):
                raise WorkflowNotFoundException("No such workflow exists") from err
            else:
                raise err

    async def does_workflow_exist(self, workflow_id: Union[str, uuid.UUID]) -> bool:
        workflow_id = str(workflow_id)
        try:
            await self.get_workflow_details(workflow_id, fetch_payloads=False, skip_logs=True)
            return True
        except WorkflowNotFoundException:
            return False
        except Exception:
            return self.workflow_runs_crud.fetch_one(conditions={"workflow_id": workflow_id}) is not None

    async def schedule_workflow(
        self,
        workflow_name: str,
        workflow_input: Union[str, Dict[str, Any]],
        workflow_id: Optional[Union[str, uuid.UUID]] = None,
        workflow_steps: Optional[List[WorkflowStep]] = None,
        eta: Optional[int] = None,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        exists_ok: bool = False,
    ) -> None:
        workflow = self.registered_workflows.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow {workflow_name} is not registered")

        workflow_id = str(workflow_id or uuid.uuid4())
        workflow_exists = await self.does_workflow_exist(workflow_id)
        if workflow_exists and not exists_ok:
            return ErrorResponse(message="Workflow already exists", code=409)

        try:
            instance_id = self.wf_client.schedule_new_workflow(
                workflow=workflow,
                input=workflow_input,
                instance_id=workflow_id,
            )
            if not workflow_exists:
                self.add_new_workflow_run(
                    instance_id, workflow_name, WorkflowStatus.PENDING, workflow_input, workflow_steps
                )
            else:
                self.workflow_runs_crud.update(
                    data={"status": WorkflowStatus.PENDING.value},
                    conditions={"workflow_id": instance_id},
                    raise_on_error=False,
                )
        except Exception as e:
            logger.exception("Failed to schedule workflow %s: %s", workflow_name, str(e))
            if isinstance(e, AttributeError) and self.wf_client is None:
                return ErrorResponse(message="Workflow runtime not initialized", code=502)
            else:
                return ErrorResponse(message="Workflow orchestration failed", code=500)

        try:
            response = WorkflowMetadataResponse(
                workflow_id=instance_id,
                workflow_name=workflow_name,
                steps=workflow_steps or [],
                status=WorkflowStatus.PENDING,
                eta=eta,
            )
            # try:
            #     orchestrator_state = self.wf_client.wait_for_workflow_start(
            #         instance_id=instance_id, fetch_payloads=False, timeout_in_seconds=60
            #     )
            # except Exception as e:
            #     logger.exception("Waiting for workflow resulted in error: %s", e)
            orchestrator_state = None
            if orchestrator_state is not None and orchestrator_state.runtime_status == DaprWorkflowStatus.FAILED:
                wf_state = await self.get_workflow_details(instance_id, fetch_payloads=True)
                response.status = WorkflowStatus.FAILED
                response.eta = 0
                self.workflow_runs_crud.update(
                    data={"status": WorkflowStatus.FAILED.value},
                    conditions={"workflow_id": instance_id},
                    raise_on_error=False,
                )
                logger.error("Workflow %s failed with %s", instance_id, wf_state)

            if target_topic_name or target_name:
                with DaprService() as dapr_service:
                    dapr_service.publish_to_topic(
                        data=response.model_dump(mode="json"),
                        target_topic_name=target_topic_name,
                        target_name=target_name,
                        event_type="workflow_metadata",
                    )
            return response
        except WorkflowNotFoundException:
            return ErrorResponse(message="Workflow orchestration failed", code=500)

    async def stop_workflow(self, workflow_id: Union[str, uuid.UUID]) -> None:
        workflow_id = str(workflow_id)
        try:
            wf_state = await self.get_workflow_details(workflow_id, fetch_payloads=False, skip_logs=True)
            self.workflow_runs_crud.update(
                data={"status": WorkflowStatus.TERMINATED.value},
                conditions={"workflow_id": workflow_id},
                raise_on_error=False,
            )

            if wf_state["runtime_status"] not in (DaprWorkflowStatus.COMPLETED.name, DaprWorkflowStatus.FAILED.name):
                self.wf_client.terminate_workflow(workflow_id)
                timeout = 60
                orch_state = self.wf_client.wait_for_workflow_completion(workflow_id, timeout_in_seconds=timeout)
                logger.info("Workflow %s responded to termination with %s", workflow_id, orch_state)
                if orch_state is not None and orch_state.runtime_status == DaprWorkflowStatus.TERMINATED:
                    return SuccessResponse(
                        message="Workflow stopped",
                        param={"workflow_id": workflow_id, "status": orch_state.runtime_status.name},
                        code=200,
                    )
                else:
                    return SuccessResponse(
                        message=f"Workflow stopped but did not reach terminal state within {timeout}s",
                        param={"workflow_id": workflow_id, "status": orch_state.runtime_status.name},
                        code=202,
                    )

            elif wf_state["runtime_status"] == DaprWorkflowStatus.TERMINATED.name:
                return SuccessResponse(
                    message="Workflow is already terminated",
                    param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                    code=202,
                )
            else:
                logger.info(
                    "Workflow %s is not in a terminal state, cannot stop (%s)", workflow_id, wf_state["runtime_status"]
                )
                return ErrorResponse(
                    message="Workflow is not in a terminal state, cannot stop",
                    param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                    code=400,
                )
        except Exception as e:
            if isinstance(e, WorkflowNotFoundException):
                return ErrorResponse(message="No such workflow exists", code=404)
            elif isinstance(e, AttributeError) and self.wf_client is None:
                return ErrorResponse(message="Workflow runtime not initialized", code=502)
            else:
                logger.exception("Failed to stop workflow %s: %s", workflow_id, str(e))
                return ErrorResponse(message="Failed to stop workflow", code=500)

    async def pause_workflow(self, workflow_id: Union[str, uuid.UUID]) -> None:
        workflow_id = str(workflow_id)
        try:
            wf_state = await self.get_workflow_details(workflow_id, fetch_payloads=False)
            self.workflow_runs_crud.update(
                data={"status": WorkflowStatus.SUSPENDED.value},
                conditions={"workflow_id": workflow_id},
                raise_on_error=False,
            )

            if wf_state["runtime_status"] not in (
                DaprWorkflowStatus.FAILED.name,
                DaprWorkflowStatus.COMPLETED.name,
                DaprWorkflowStatus.TERMINATED.name,
            ):
                self.wf_client.pause_workflow(workflow_id)

                timeout = 10
                await asyncio.sleep(timeout)
                wf_state = await self.get_workflow_details(workflow_id, fetch_payloads=False)
                logger.info("Workflow %s responded to pause with %s", workflow_id, wf_state)

                if wf_state is not None and wf_state["runtime_status"] == DaprWorkflowStatus.SUSPENDED.name:
                    return SuccessResponse(
                        message="Workflow paused",
                        param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                        code=200,
                    )
                else:
                    return ErrorResponse(
                        message=f"Workflow did not pause within {timeout}s",
                        param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                        code=202,
                    )
            elif wf_state["runtime_status"] == DaprWorkflowStatus.SUSPENDED.name:
                return SuccessResponse(
                    message="Workflow is already paused",
                    param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                    code=202,
                )
            else:
                logger.info(
                    "Workflow %s is not in a state that can be paused (%s)", workflow_id, wf_state["runtime_status"]
                )
                return ErrorResponse(
                    message="Workflow is not in a state that can be paused",
                    param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                    code=400,
                )
        except Exception as e:
            if isinstance(e, WorkflowNotFoundException):
                return ErrorResponse(message="No such workflow exists", code=404)
            elif isinstance(e, AttributeError) and self.wf_client is None:
                return ErrorResponse(message="Workflow runtime not initialized", code=502)
            else:
                logger.exception("Failed to pause workflow %s: %s", workflow_id, str(e))
                return ErrorResponse(message="Failed to pause workflow", code=500)

    async def resume_workflow(self, workflow_id: Union[str, uuid.UUID]) -> None:
        workflow_id = str(workflow_id)
        try:
            wf_state = await self.get_workflow_details(workflow_id, fetch_payloads=False)
            self.workflow_runs_crud.update(
                data={"status": WorkflowStatus.RUNNING.value},
                conditions={"workflow_id": workflow_id},
                raise_on_error=False,
            )

            if wf_state["runtime_status"] == DaprWorkflowStatus.SUSPENDED.name:
                self.wf_client.resume_workflow(workflow_id)

                timeout = 10
                await asyncio.sleep(timeout)
                wf_state = await self.get_workflow_details(workflow_id, fetch_payloads=False)
                logger.info("Workflow %s responded to resume with %s", workflow_id, wf_state)

                if wf_state is not None and wf_state["runtime_status"] == DaprWorkflowStatus.RUNNING.name:
                    return SuccessResponse(
                        message="Workflow resumed",
                        param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                        code=200,
                    )
                else:
                    return ErrorResponse(
                        message=f"Workflow did not resume within {timeout}s",
                        param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                        code=202,
                    )
            elif wf_state["runtime_status"] == DaprWorkflowStatus.RUNNING.name:
                return SuccessResponse(
                    message="Workflow is already running",
                    param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                    code=202,
                )
            else:
                logger.info(
                    "Workflow %s is not in a state that can be resumed (%s)", workflow_id, wf_state["runtime_status"]
                )
                return ErrorResponse(
                    message="Workflow is not in a state that can be resumed",
                    param={"workflow_id": workflow_id, "status": wf_state["runtime_status"]},
                    code=400,
                )
        except Exception as e:
            if isinstance(e, WorkflowNotFoundException):
                return ErrorResponse(message="No such workflow exists", code=404)
            elif isinstance(e, AttributeError) and self.wf_client is None:
                return ErrorResponse(message="Workflow runtime not initialized", code=502)
            else:
                logger.exception("Failed to resume workflow %s: %s", workflow_id, str(e))
                return ErrorResponse(message="Failed to resume workflow", code=500)

    async def restart_workflow(self, workflow_id: Union[str, uuid.UUID]) -> None:
        workflow_id = str(workflow_id)
        workflow = self.workflow_runs_crud.fetch_one(conditions={"workflow_id": workflow_id})
        if not workflow:
            return ErrorResponse(message="No such workflow exists", code=404)
        try:
            await self.stop_workflow(workflow_id)
            # TODO: Save target topic name from previous workflow run ?
            await self.schedule_workflow(workflow.workflow_name, workflow.input, workflow_id, exists_ok=True)
            return SuccessResponse(message="Workflow restarted", param={"workflow_id": workflow_id}, code=200)
        except Exception as e:
            logger.exception("Failed to restart workflow %s: %s", workflow_id, str(e))
            if isinstance(e, AttributeError) and self.wf_client is None:
                return ErrorResponse(message="Workflow runtime not initialized", code=502)
            else:
                return ErrorResponse(message="Failed to restart workflow", code=500)
