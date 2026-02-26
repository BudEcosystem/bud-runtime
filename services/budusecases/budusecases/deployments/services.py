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

"""Deployment Orchestration Service."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from budusecases.clients.budcluster import (
    BudClusterClient,
    JobCreateRequest,
    JobResponse,
    JobSource,
    JobStatus,
    JobType,
)
from budusecases.clients.budpipeline import BudPipelineClient
from budusecases.commons.config import app_settings
from budusecases.templates.crud import TemplateDataManager
from budusecases.templates.models import Template

from .crud import DeploymentDataManager
from .dag_builder import build_deployment_dag
from .enums import ComponentDeploymentStatus, DeploymentStatus
from .exceptions import (
    AccessConfigValidationError,
    DeploymentNotFoundError,
    IncompatibleComponentError,
    InvalidDeploymentStateError,
    MissingRequiredComponentError,
    TemplateNotFoundError,
)
from .models import ComponentDeployment, UseCaseDeployment
from .schemas import DeploymentCreateSchema

logger = logging.getLogger(__name__)


# Map component types to job types
# All ML models (LLMs, embedders, rerankers) use MODEL_DEPLOYMENT
# Template slot types (embedder, reranker) also map to MODEL_DEPLOYMENT
COMPONENT_TYPE_TO_JOB_TYPE = {
    "model": JobType.MODEL_DEPLOYMENT,
    "llm": JobType.MODEL_DEPLOYMENT,  # Template slot type
    "embedder": JobType.MODEL_DEPLOYMENT,  # Template slot type
    "reranker": JobType.MODEL_DEPLOYMENT,  # Template slot type
    "helm": JobType.HELM_DEPLOY,
}


class DeploymentOrchestrationService:
    """Service for orchestrating use case deployments."""

    def __init__(self, session: Session) -> None:
        """Initialize the orchestration service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.deployment_manager = DeploymentDataManager(session=session)
        self.template_manager = TemplateDataManager(session=session)
        self.budcluster_client = BudClusterClient()

    async def create_deployment(
        self,
        request: DeploymentCreateSchema,
        user_id: UUID,
        project_id: UUID | None = None,
    ) -> UseCaseDeployment:
        """Create a new use case deployment.

        Args:
            request: Deployment creation request.
            user_id: User creating the deployment.
            project_id: Project UUID for API access scoping.

        Returns:
            Created deployment.

        Raises:
            TemplateNotFoundError: If template doesn't exist.
            AccessConfigValidationError: If API access is enabled but project_id is missing.
            MissingRequiredComponentError: If a required component is missing.
            IncompatibleComponentError: If a component is not compatible.
        """
        # Resolve project_id: request body takes precedence, then parameter
        resolved_project_id = project_id
        if request.project_id:
            resolved_project_id = UUID(request.project_id)

        # Get template (user-scoped lookup so user can deploy from private templates)
        template = self._get_template(request.template_name, user_id=user_id)
        if template is None:
            raise TemplateNotFoundError(f"Template not found: {request.template_name}")

        # Copy access config from template (snapshot at deployment time)
        access_config = template.access if template.access else None

        # Validate: project_id is required when API access is enabled
        if access_config:
            api_config = access_config.get("api", {})
            if api_config.get("enabled") and not resolved_project_id:
                raise AccessConfigValidationError("project_id is required when API access is enabled")

        # Validate component selections
        self._validate_components(template, request.components)

        # Create deployment record
        deployment = self._create_deployment_record(
            request=request,
            template=template,
            user_id=user_id,
            project_id=resolved_project_id,
            access_config=access_config,
        )

        return deployment

    async def start_deployment(
        self,
        deployment_id: UUID,
        notification_workflow_id: str | None = None,
    ) -> UseCaseDeployment:
        """Start a deployment.

        Routes to BudPipeline orchestration or the legacy direct-job path
        depending on the ``use_pipeline_orchestration`` config flag.

        Args:
            deployment_id: Deployment UUID.
            notification_workflow_id: Optional budapp workflow ID for real-time notifications.

        Returns:
            Updated deployment.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
            InvalidDeploymentStateError: If deployment is not in pending state.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        if deployment.status != DeploymentStatus.PENDING:
            raise InvalidDeploymentStateError(f"Cannot start deployment in {deployment.status} state")

        if app_settings.use_pipeline_orchestration:
            return await self._start_deployment_via_pipeline(
                deployment, notification_workflow_id=notification_workflow_id
            )
        else:
            return await self._start_deployment_legacy(deployment)

    async def _start_deployment_via_pipeline(
        self,
        deployment: UseCaseDeployment,
        notification_workflow_id: str | None = None,
    ) -> UseCaseDeployment:
        """Start a deployment via BudPipeline orchestration.

        Builds a DAG and updates the deployment status to DEPLOYING immediately.
        The actual pipeline submission is deferred to
        :meth:`run_pipeline_in_background` which should be called as a
        ``BackgroundTasks`` callback so the HTTP response returns instantly.

        Args:
            deployment: Deployment instance in PENDING state.
            notification_workflow_id: Optional budapp workflow ID for real-time notifications.

        Returns:
            Updated deployment in DEPLOYING state (pipeline not yet submitted).

        Raises:
            TemplateNotFoundError: If the associated template is missing.
        """
        # Get the template
        template = self.template_manager.get_template(deployment.template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template not found: {deployment.template_id}")

        # Build component selections from component_deployments
        component_selections = {cd.component_name: cd.selected_component for cd in deployment.component_deployments}

        # Build template dict for DAG builder.
        template_dict: dict[str, Any] = {
            "components": [
                {
                    "name": comp.name,
                    "type": comp.component_type,
                    "chart": comp.chart,
                    "default_component": comp.default_component,
                }
                for comp in template.components
            ],
            "deployment_order": template.deployment_order or [],
            "parameters": template.parameters or {},
        }

        # Build DAG (pure computation, no I/O)
        dag = build_deployment_dag(
            deployment_id=str(deployment.id),
            deployment_name=deployment.name,
            cluster_id=str(deployment.cluster_id),
            user_id=str(deployment.user_id),
            template=template_dict,
            component_selections=component_selections,
            parameters=deployment.parameters or {},
            access_config=deployment.access_config,
            project_id=str(deployment.project_id) if deployment.project_id else None,
        )

        # Update statuses to DEPLOYING immediately (before pipeline submission)
        self.deployment_manager.update_deployment_status(
            deployment_id=deployment.id,
            status=DeploymentStatus.DEPLOYING,
        )
        for component in deployment.component_deployments:
            self.deployment_manager.update_component_deployment_status(
                component_id=component.id,
                status=ComponentDeploymentStatus.DEPLOYING,
            )

        self.session.commit()

        # Store the DAG on the service for the route to pass to background task
        self._pending_dag = dag

        return self._get_deployment(deployment.id)

    @staticmethod
    async def run_pipeline_in_background(
        deployment_id: UUID,
        user_id: UUID,
        dag: dict[str, Any],
        notification_workflow_id: str | None = None,
    ) -> None:
        """Submit the DAG to BudPipeline (runs as a background task).

        This is called via ``BackgroundTasks`` so the HTTP response has already
        been sent. On success the ``pipeline_execution_id`` is stored on the
        deployment record; on failure the deployment is marked FAILED.

        Args:
            deployment_id: Deployment UUID.
            user_id: User who started the deployment.
            dag: Pre-built pipeline DAG dict.
            notification_workflow_id: Optional budapp workflow ID.
        """
        from budmicroframe.shared.psql_service import Database

        db = Database()
        session = db.get_session()
        try:
            deployment_manager = DeploymentDataManager(session=session)

            pipeline_client = BudPipelineClient()
            callback_topics = ["budusecasesEvents"]
            if notification_workflow_id:
                callback_topics.append(app_settings.budapp_callback_topic)

            logger.info(
                "Background: submitting to BudPipeline: deployment_id=%s, "
                "notification_workflow_id=%s, callback_topics=%s",
                deployment_id,
                notification_workflow_id,
                callback_topics,
            )
            result = await pipeline_client.run_ephemeral(
                pipeline_definition=dag,
                params={
                    "deployment_id": str(deployment_id),
                    "user_id": str(user_id),
                },
                callback_topics=callback_topics,
                user_id=str(user_id),
                initiator="budusecases",
                subscriber_ids=str(user_id) if notification_workflow_id else None,
                payload_type="usecase_deployment" if notification_workflow_id else None,
                notification_workflow_id=notification_workflow_id,
            )

            execution_id = result.get("execution_id") or result.get("id")

            # Store pipeline execution ID
            deployment_manager.update_deployment_pipeline_execution(
                deployment_id=deployment_id,
                execution_id=str(execution_id),
            )
            session.commit()
            logger.info(
                "Background: pipeline submitted for deployment %s, execution_id=%s",
                deployment_id,
                execution_id,
            )

        except Exception:
            logger.exception(
                "Background: failed to submit pipeline for deployment %s",
                deployment_id,
            )
            try:
                deployment_manager = DeploymentDataManager(session=session)
                deployment_manager.update_deployment_status(
                    deployment_id=deployment_id,
                    status=DeploymentStatus.FAILED,
                )
                session.commit()
            except Exception:
                logger.exception(
                    "Background: failed to mark deployment %s as FAILED",
                    deployment_id,
                )
        finally:
            db.close_session(session)

    async def _start_deployment_legacy(self, deployment: UseCaseDeployment) -> UseCaseDeployment:
        """Start a deployment via direct BudCluster job creation (legacy path).

        Iterates over component deployments and creates a BudCluster job for
        each one individually.

        Args:
            deployment: Deployment instance in PENDING state.

        Returns:
            Updated deployment.
        """
        # Update status to deploying
        self.deployment_manager.update_deployment_status(
            deployment_id=deployment.id,
            status=DeploymentStatus.DEPLOYING,
        )

        # Start deploying each component
        for component in deployment.component_deployments:
            try:
                job = await self._deploy_component(
                    component=component,
                    cluster_id=deployment.cluster_id,
                    deployment_id=deployment.id,
                )
                self.deployment_manager.update_component_deployment_job(
                    component_id=component.id,
                    job_id=job.id,
                )
            except Exception as e:
                logger.error(f"Failed to deploy component {component.component_name}: {e}")
                self.deployment_manager.update_component_deployment_status(
                    component_id=component.id,
                    status=ComponentDeploymentStatus.FAILED,
                    error_message=str(e),
                )

        self.session.commit()
        return self._get_deployment(deployment.id)

    async def stop_deployment(self, deployment_id: UUID) -> UseCaseDeployment:
        """Stop a running deployment.

        Routes to BudPipeline cancellation or the legacy per-job cancellation
        path depending on whether the deployment has a pipeline execution ID.

        Also deletes the HTTPRoute/ReferenceGrant resources on the target cluster
        if the deployment has access modes configured.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            Updated deployment.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
            InvalidDeploymentStateError: If deployment is not in running state.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        if deployment.status not in (DeploymentStatus.RUNNING, DeploymentStatus.DEPLOYING):
            raise InvalidDeploymentStateError(f"Cannot stop deployment in {deployment.status} state")

        # Delete HTTPRoute before stopping (non-blocking)
        await self._delete_httproute_if_needed(deployment)

        if deployment.pipeline_execution_id:
            # Pipeline path: cancel the pipeline execution
            try:
                pipeline_client = BudPipelineClient()
                await pipeline_client.cancel_execution(deployment.pipeline_execution_id)
            except Exception as e:
                logger.warning(f"Failed to cancel pipeline execution {deployment.pipeline_execution_id}: {e}")
                # Continue to update local status even if cancel fails
                # (pipeline may already be completed/failed)

            # Update all non-terminal component statuses to STOPPED
            for component in deployment.component_deployments:
                if component.status not in (
                    ComponentDeploymentStatus.FAILED,
                    ComponentDeploymentStatus.STOPPED,
                ):
                    self.deployment_manager.update_component_deployment_status(
                        component_id=component.id,
                        status=ComponentDeploymentStatus.STOPPED,
                    )
        else:
            # Legacy path: cancel individual BudCluster jobs
            for component in deployment.component_deployments:
                if component.job_id:
                    try:
                        await self.budcluster_client.cancel_job(component.job_id)
                    except Exception as e:
                        logger.error(f"Failed to cancel job {component.job_id}: {e}")

        # Update deployment status
        self.deployment_manager.update_deployment_status(
            deployment_id=deployment_id,
            status=DeploymentStatus.STOPPED,
        )

        self.session.commit()
        return self._get_deployment(deployment_id)

    async def delete_deployment(self, deployment_id: UUID) -> dict:
        """Delete a deployment from the database and return cleanup context.

        Deletes DB records immediately and returns info needed for
        asynchronous cluster resource cleanup, including HTTPRoute deletion.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            Cleanup context dict with keys: cluster_id,
            pipeline_execution_id, job_ids, deployment_id, access_config,
            deployment_name.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        # Extract cleanup info before deleting DB records
        cleanup_context = {
            "cluster_id": deployment.cluster_id,
            "pipeline_execution_id": deployment.pipeline_execution_id,
            "job_ids": [c.job_id for c in deployment.component_deployments if c.job_id],
            # HTTPRoute cleanup context
            "deployment_id": str(deployment.id),
            "deployment_name": deployment.name,
            "access_config": deployment.access_config,
        }

        # Delete DB records immediately
        self.deployment_manager.delete_deployment(deployment_id)
        self.session.commit()

        return cleanup_context

    @staticmethod
    async def cleanup_deployment_resources(cleanup_context: dict) -> None:
        """Clean up cluster resources for a deleted deployment.

        Runs as a background task after the DB records are deleted.
        Cancels pipelines/jobs, deletes HTTPRoute resources, and deletes
        Kubernetes namespaces.

        Args:
            cleanup_context: Dict with cluster_id, pipeline_execution_id,
                job_ids, deployment_id, deployment_name, access_config.
        """
        cluster_id = cleanup_context["cluster_id"]
        pipeline_execution_id = cleanup_context.get("pipeline_execution_id")
        job_ids = cleanup_context.get("job_ids", [])
        deployment_id = cleanup_context.get("deployment_id")
        access_config = cleanup_context.get("access_config")

        budcluster_client = BudClusterClient()
        namespaces_to_delete: set[str] = set()

        # Delete HTTPRoute resources if access was configured
        if deployment_id and DeploymentOrchestrationService._has_any_access_mode_enabled(access_config):
            namespace = f"usecase-{deployment_id[:8]}"
            try:
                await budcluster_client.delete_httproute(
                    cluster_id=cluster_id,
                    deployment_id=deployment_id,
                    namespace=namespace,
                )
                logger.info(f"Deleted HTTPRoute for deployment {deployment_id} on cluster {cluster_id}")
            except Exception as e:
                logger.warning(f"Failed to delete HTTPRoute for deployment {deployment_id} during cleanup: {e}")

        if pipeline_execution_id:
            pipeline_client = BudPipelineClient()
            try:
                await pipeline_client.cancel_execution(pipeline_execution_id)
            except Exception as e:
                logger.warning(f"Failed to cancel pipeline execution {pipeline_execution_id}: {e}")

            try:
                progress = await pipeline_client.get_execution_progress(pipeline_execution_id)
                for step in progress.get("steps", []):
                    outputs = step.get("outputs") or {}
                    ns = outputs.get("namespace")
                    if ns and ns != "default":
                        namespaces_to_delete.add(ns)
            except Exception as e:
                logger.warning(f"Failed to get pipeline progress for cleanup: {e}")
        else:
            for job_id in job_ids:
                try:
                    job = await budcluster_client.get_job(job_id)
                    if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                        await budcluster_client.cancel_job(job_id)
                    config = job.config or {}
                    ns = config.get("namespace")
                    if ns and ns != "default":
                        namespaces_to_delete.add(ns)
                except Exception as e:
                    logger.warning(f"Failed to process job {job_id}: {e}")

        for ns in namespaces_to_delete:
            try:
                await budcluster_client.delete_namespace(
                    cluster_id=cluster_id,
                    namespace=ns,
                )
                logger.info(f"Deleted namespace {ns} on cluster {cluster_id}")
            except Exception as e:
                logger.warning(f"Failed to delete namespace {ns} on cluster {cluster_id}: {e}")

    async def sync_deployment_status(self, deployment_id: UUID) -> UseCaseDeployment:
        """Sync deployment status from BudPipeline or BudCluster jobs.

        If the deployment has a ``pipeline_execution_id`` the status is
        fetched from BudPipeline; otherwise the legacy per-job polling
        path is used.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            Updated deployment.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        if deployment.pipeline_execution_id:
            return await self._sync_deployment_status_pipeline(deployment)
        else:
            return await self._sync_deployment_status_legacy(deployment)

    async def retry_gateway_route(self, deployment_id: UUID) -> UseCaseDeployment:
        """Retry HTTPRoute creation for a deployment missing a gateway URL.

        If the deployment is in FAILED state (because gateway creation failed),
        it is first transitioned back to RUNNING before retrying. If HTTPRoute
        creation succeeds, the deployment stays RUNNING; if it fails again, the
        deployment is marked as FAILED.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            Updated deployment.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
            InvalidDeploymentStateError: If deployment is not RUNNING or FAILED.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        if deployment.status not in (DeploymentStatus.RUNNING, DeploymentStatus.FAILED):
            raise InvalidDeploymentStateError(
                f"Cannot retry gateway route for deployment in {deployment.status} state (must be running or failed)"
            )

        if not self._has_any_access_mode_enabled(deployment.access_config):
            raise InvalidDeploymentStateError("Deployment has no access modes (UI/API) enabled")

        # If deployment failed due to gateway, set back to RUNNING first
        if deployment.status == DeploymentStatus.FAILED:
            self.deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.RUNNING,
            )

        # Clear any existing gateway_url before retrying
        self.deployment_manager.update_deployment_gateway_url(
            deployment_id=deployment.id,
            gateway_url=None,
        )

        await self._create_httproute_if_needed(deployment)
        self.session.commit()

        return self._get_deployment(deployment.id)

    async def _sync_deployment_status_pipeline(self, deployment: UseCaseDeployment) -> UseCaseDeployment:
        """Sync deployment status from BudPipeline execution progress.

        When the pipeline execution completes, transitions the deployment to
        RUNNING and creates HTTPRoute resources if access modes are configured.

        Args:
            deployment: Deployment with a pipeline_execution_id.

        Returns:
            Updated deployment.
        """
        pipeline_client = BudPipelineClient()
        try:
            progress = await pipeline_client.get_execution_progress(deployment.pipeline_execution_id)
            # Update deployment status based on execution status
            exec_status = progress.get("execution", {}).get("status", "")
            if exec_status == "completed":
                self.deployment_manager.update_deployment_status(
                    deployment_id=deployment.id,
                    status=DeploymentStatus.RUNNING,
                )
                for component in deployment.component_deployments:
                    self.deployment_manager.update_component_deployment_status(
                        component_id=component.id,
                        status=ComponentDeploymentStatus.RUNNING,
                    )

                # Create HTTPRoute after all components are running
                await self._create_httproute_if_needed(deployment)

            elif exec_status == "failed":
                error_msg = progress.get("execution", {}).get("error", "Pipeline execution failed")
                self.deployment_manager.update_deployment_status(
                    deployment_id=deployment.id,
                    status=DeploymentStatus.FAILED,
                    error_message=error_msg,
                )
            elif exec_status in ("running", "pending"):
                # Still in progress -- update individual component statuses
                # from step-level detail if available
                steps = progress.get("steps", [])
                self._update_component_statuses_from_steps(deployment=deployment, steps=steps)
            self.session.commit()
        except Exception as e:
            logger.error(f"Failed to sync pipeline progress: {e}")

        return self._get_deployment(deployment.id)

    async def _sync_deployment_status_legacy(self, deployment: UseCaseDeployment) -> UseCaseDeployment:
        """Sync deployment status from BudCluster jobs (legacy path).

        When all jobs complete, transitions the deployment to RUNNING and
        creates HTTPRoute resources if access modes are configured.

        Args:
            deployment: Deployment without a pipeline_execution_id.

        Returns:
            Updated deployment.
        """
        all_completed = True
        any_failed = False

        for component in deployment.component_deployments:
            if component.job_id:
                try:
                    job = await self.budcluster_client.get_job(component.job_id)
                    new_status = self._map_job_status_to_component_status(job.status)
                    self.deployment_manager.update_component_deployment_status(
                        component_id=component.id,
                        status=new_status,
                    )

                    if job.status != JobStatus.COMPLETED:
                        all_completed = False
                    if job.status == JobStatus.FAILED:
                        any_failed = True

                except Exception as e:
                    logger.error(f"Failed to sync job {component.job_id}: {e}")
                    all_completed = False

        # Update overall deployment status
        if any_failed:
            self.deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.FAILED,
            )
        elif all_completed:
            self.deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.RUNNING,
            )

            # Create HTTPRoute after all components are running
            await self._create_httproute_if_needed(deployment)

        self.session.commit()
        return self._get_deployment(deployment.id)

    async def get_deployment_progress(self, deployment_id: UUID) -> dict[str, Any]:
        """Get real-time deployment progress from BudPipeline.

        For pipeline-orchestrated deployments, fetches step-level progress
        from BudPipeline.  For legacy deployments (no pipeline_execution_id),
        synthesizes a progress dict from local component deployment statuses.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            Progress dict matching the ``DeploymentProgressResponseSchema``.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        if deployment.pipeline_execution_id:
            pipeline_client = BudPipelineClient()
            try:
                return await pipeline_client.get_execution_progress(deployment.pipeline_execution_id)
            except Exception as e:
                logger.error(f"Failed to fetch pipeline progress: {e}")
                # Fall through to local synthesis
                return self._synthesize_progress(deployment)
        else:
            return self._synthesize_progress(deployment)

    def _synthesize_progress(self, deployment: UseCaseDeployment) -> dict[str, Any]:
        """Build a progress dict from local component deployment statuses.

        Used when BudPipeline is unreachable or for legacy deployments.

        Args:
            deployment: The deployment to synthesize progress for.

        Returns:
            Dict matching ``DeploymentProgressResponseSchema`` shape.
        """
        components = deployment.component_deployments
        total = len(components)
        completed = sum(
            1
            for c in components
            if c.status
            in (ComponentDeploymentStatus.RUNNING, ComponentDeploymentStatus.FAILED, ComponentDeploymentStatus.STOPPED)
        )
        overall = str(round((completed / total) * 100)) if total else "0"

        # Find current step (first DEPLOYING component)
        current_step: str | None = None
        for c in components:
            if c.status == ComponentDeploymentStatus.DEPLOYING:
                current_step = f"deploy_{c.component_name}"
                break

        steps = []
        for idx, c in enumerate(components):
            step_status = {
                ComponentDeploymentStatus.PENDING: "pending",
                ComponentDeploymentStatus.DEPLOYING: "running",
                ComponentDeploymentStatus.RUNNING: "completed",
                ComponentDeploymentStatus.FAILED: "failed",
                ComponentDeploymentStatus.STOPPED: "cancelled",
            }.get(c.status, "pending")

            steps.append(
                {
                    "id": str(c.id),
                    "execution_id": deployment.pipeline_execution_id or "",
                    "step_id": str(c.id),
                    "step_name": f"deploy_{c.component_name}",
                    "status": step_status,
                    "start_time": None,
                    "end_time": None,
                    "progress_percentage": "100" if step_status in ("completed", "failed", "cancelled") else "0",
                    "outputs": {"endpoint_url": c.endpoint_url} if c.endpoint_url else None,
                    "error_message": c.error_message,
                    "sequence_number": idx,
                    "awaiting_event": False,
                }
            )

        return {
            "execution": {
                "id": deployment.pipeline_execution_id or str(deployment.id),
                "status": deployment.status.value if hasattr(deployment.status, "value") else str(deployment.status),
                "progress_percentage": overall,
            },
            "steps": steps,
            "recent_events": [],
            "aggregated_progress": {
                "overall_progress": overall,
                "eta_seconds": None,
                "completed_steps": completed,
                "total_steps": total,
                "current_step": current_step,
            },
        }

    async def get_deployment_details(self, deployment_id: UUID) -> UseCaseDeployment:
        """Get full deployment details.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            Deployment with all details.

        Raises:
            DeploymentNotFoundError: If deployment doesn't exist.
        """
        deployment = self._get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"Deployment not found: {deployment_id}")

        return deployment

    def _get_template(self, name: str, user_id: UUID | None = None) -> Template | None:
        """Get a template by name, with user-scoped lookup."""
        return self.template_manager.get_template_by_name(name, user_id=user_id)

    def _get_deployment(self, deployment_id: UUID) -> UseCaseDeployment | None:
        """Get a deployment by ID."""
        return self.deployment_manager.get_deployment(deployment_id)

    def _validate_components(
        self,
        template: Template,
        selected_components: dict[str, str],
    ) -> None:
        """Validate selected components against template requirements."""
        self._validate_required_components(
            template_components=template.components,
            selected_components=selected_components,
        )

        for template_comp in template.components:
            if template_comp.name in selected_components:
                self._validate_component_compatibility(
                    template_component=template_comp,
                    selected_component_name=selected_components[template_comp.name],
                )

    def _validate_required_components(
        self,
        template_components: list[Any],
        selected_components: dict[str, str],
    ) -> None:
        """Validate that all required components are provided."""
        for comp in template_components:
            if comp.required and comp.name not in selected_components:
                raise MissingRequiredComponentError(f"Missing required component: {comp.name}")

    def _validate_component_compatibility(
        self,
        template_component: Any,
        selected_component_name: str,
    ) -> None:
        """Validate that selected component is compatible."""
        if template_component.compatible_components:
            if selected_component_name not in template_component.compatible_components:
                raise IncompatibleComponentError(
                    f"Component {selected_component_name} is not compatible with "
                    f"template slot {template_component.name}. "
                    f"Compatible: {template_component.compatible_components}"
                )

    def _create_deployment_record(
        self,
        request: DeploymentCreateSchema,
        template: Template,
        user_id: UUID,
        project_id: UUID | None = None,
        access_config: dict[str, Any] | None = None,
    ) -> UseCaseDeployment:
        """Create deployment and component records."""
        deployment = self.deployment_manager.create_deployment(
            name=request.name,
            template_id=template.id,
            cluster_id=UUID(request.cluster_id),
            user_id=user_id,
            project_id=project_id,
            parameters=request.parameters,
            metadata_=request.metadata_,
            access_config=access_config,
        )

        # Create component deployments
        for template_comp in template.components:
            component_name = request.components.get(
                template_comp.name,
                template_comp.default_component,
            )
            if component_name:
                self.deployment_manager.create_component_deployment(
                    usecase_deployment_id=deployment.id,
                    component_name=template_comp.name,
                    component_type=template_comp.component_type,
                    selected_component=component_name,
                )

        self.session.commit()
        return deployment

    async def _deploy_component(
        self,
        component: ComponentDeployment,
        cluster_id: UUID,
        deployment_id: UUID,
    ) -> JobResponse:
        """Deploy a single component via BudCluster.

        Args:
            component: Component deployment to deploy.
            cluster_id: Target cluster UUID.
            deployment_id: Parent deployment UUID.

        Returns:
            Created job response.
        """
        job_type = COMPONENT_TYPE_TO_JOB_TYPE.get(component.component_type, JobType.GENERIC)

        request = JobCreateRequest(
            name=f"deploy-{component.component_name}-{deployment_id}",
            job_type=job_type,
            source=JobSource.BUDUSECASES,
            source_id=str(deployment_id),
            cluster_id=cluster_id,
            config=component.config,
            metadata_={
                "component_name": component.component_name,
                "component_type": component.component_type,
            },
        )

        job = await self.budcluster_client.create_job(request)

        # Update component status
        self.deployment_manager.update_component_deployment_status(
            component_id=component.id,
            status=ComponentDeploymentStatus.DEPLOYING,
        )

        return job

    def _map_job_status_to_component_status(self, job_status: JobStatus) -> ComponentDeploymentStatus:
        """Map BudCluster job status to component deployment status."""
        mapping = {
            JobStatus.PENDING: ComponentDeploymentStatus.PENDING,
            JobStatus.RUNNING: ComponentDeploymentStatus.DEPLOYING,
            JobStatus.COMPLETED: ComponentDeploymentStatus.RUNNING,
            JobStatus.FAILED: ComponentDeploymentStatus.FAILED,
            JobStatus.CANCELLED: ComponentDeploymentStatus.STOPPED,
        }
        return mapping.get(job_status, ComponentDeploymentStatus.PENDING)

    def _update_component_statuses_from_steps(
        self,
        deployment: UseCaseDeployment,
        steps: list[dict[str, Any]],
    ) -> None:
        """Update individual component deployment statuses from pipeline step data.

        Maps pipeline step names (``deploy_<component_name>``) back to the
        corresponding ``ComponentDeployment`` record and updates its status.

        Args:
            deployment: The parent deployment.
            steps: List of step dicts from BudPipeline execution progress.
        """
        _STEP_STATUS_MAP: dict[str, ComponentDeploymentStatus] = {
            "pending": ComponentDeploymentStatus.PENDING,
            "running": ComponentDeploymentStatus.DEPLOYING,
            "completed": ComponentDeploymentStatus.RUNNING,
            "failed": ComponentDeploymentStatus.FAILED,
            "cancelled": ComponentDeploymentStatus.STOPPED,
        }

        # Build lookup: component_name -> ComponentDeployment
        comp_lookup = {cd.component_name: cd for cd in deployment.component_deployments}

        for step in steps:
            step_id: str = step.get("step_id", "") or step.get("name", "")
            if not step_id.startswith("deploy_"):
                continue
            comp_name = step_id[len("deploy_") :]
            component = comp_lookup.get(comp_name)
            if component is None:
                continue

            step_status = step.get("status", "")
            new_status = _STEP_STATUS_MAP.get(step_status)
            if new_status is not None:
                outputs = step.get("outputs") or {}
                endpoint_url = outputs.get("endpoint_url")
                self.deployment_manager.update_component_deployment_status(
                    component_id=component.id,
                    status=new_status,
                    endpoint_url=endpoint_url,
                    error_message=step.get("error"),
                )

    # ------------------------------------------------------------------
    # HTTPRoute Lifecycle Orchestration
    # ------------------------------------------------------------------

    @staticmethod
    def _has_any_access_mode_enabled(
        access_config: dict[str, Any] | None,
    ) -> bool:
        """Check whether the access config has at least one enabled mode.

        Args:
            access_config: The deployment's access configuration dict, or None.

        Returns:
            True if UI or API access is enabled, False otherwise.
        """
        if not isinstance(access_config, dict):
            return False
        ui = access_config.get("ui")
        api = access_config.get("api")
        ui_enabled = isinstance(ui, dict) and ui.get("enabled", False)
        api_enabled = isinstance(api, dict) and api.get("enabled", False)
        return bool(ui_enabled or api_enabled)

    def _resolve_helm_service_name(self, deployment: UseCaseDeployment) -> str | None:
        """Resolve the Kubernetes Service name for the helm component.

        The service name follows the DAG builder convention:
        ``{deployment_name}-{component_name}``.  Only the first helm-type
        component is considered since that is the application service that
        needs external routing.

        Args:
            deployment: The deployment to resolve the service name for.

        Returns:
            The service name string, or None if no helm component exists.
        """
        for cd in deployment.component_deployments:
            if cd.component_type == "helm":
                return f"{deployment.name}-{cd.component_name}"
        return None

    def _resolve_namespace(self, deployment: UseCaseDeployment) -> str:
        """Resolve the Kubernetes namespace for a deployment.

        Follows the DAG builder convention: ``usecase-{deployment_id[:8]}``.

        Args:
            deployment: The deployment.

        Returns:
            The namespace string.
        """
        return f"usecase-{str(deployment.id)[:8]}"

    async def _create_httproute_if_needed(self, deployment: UseCaseDeployment) -> None:
        """Create HTTPRoute and ReferenceGrant on the target cluster.

        Called after a deployment transitions to RUNNING. Calls budcluster via
        Dapr service invocation to create Kubernetes Gateway API resources for
        routing traffic through Envoy Gateway to the deployed use case service.

        The gateway endpoint URL returned by budcluster is stored on the
        deployment record as ``gateway_url``.

        If access modes (UI/API) are enabled and HTTPRoute creation fails, this
        method marks the deployment as FAILED because the user's app would be
        inaccessible without a gateway route.

        Args:
            deployment: The deployment that just transitioned to RUNNING.
        """
        if not self._has_any_access_mode_enabled(deployment.access_config):
            return

        service_name = self._resolve_helm_service_name(deployment)
        if not service_name:
            error_msg = (
                f"Deployment {deployment.id} has access config but no helm "
                f"component to route to; cannot create gateway route"
            )
            logger.error(error_msg)
            self.deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.FAILED,
                error_message=error_msg,
            )
            return

        namespace = self._resolve_namespace(deployment)

        try:
            response = await self.budcluster_client.create_httproute(
                cluster_id=deployment.cluster_id,
                deployment_id=str(deployment.id),
                namespace=namespace,
                service_name=service_name,
                access_config=deployment.access_config,
            )

            # Extract gateway endpoint from the response
            # budcluster returns: {"param": {"gateway_endpoint": "...", ...}, ...}
            param = response.get("param", {})
            gateway_endpoint = param.get("gateway_endpoint", "")

            if gateway_endpoint:
                self.deployment_manager.update_deployment_gateway_url(
                    deployment_id=deployment.id,
                    gateway_url=gateway_endpoint,
                )
                logger.info(f"HTTPRoute created for deployment {deployment.id}; gateway_url={gateway_endpoint}")
            else:
                error_msg = (
                    f"HTTPRoute created for deployment {deployment.id} but "
                    f"no gateway endpoint was returned by budcluster"
                )
                logger.error(error_msg)
                self.deployment_manager.update_deployment_status(
                    deployment_id=deployment.id,
                    status=DeploymentStatus.FAILED,
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = f"Failed to create gateway route for deployment {deployment.id}: {e}"
            logger.error(error_msg)
            self.deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.FAILED,
                error_message=error_msg,
            )

    async def _delete_httproute_if_needed(self, deployment: UseCaseDeployment) -> None:
        """Delete HTTPRoute and ReferenceGrant from the target cluster.

        Called when a deployment is being stopped. Calls budcluster via Dapr
        service invocation to remove the Kubernetes Gateway API resources.

        Also clears the ``gateway_url`` on the deployment record.

        This method is non-blocking: HTTPRoute deletion failures are logged as
        warnings but do not fail the stop/delete operation.

        Args:
            deployment: The deployment being stopped or deleted.
        """
        if not self._has_any_access_mode_enabled(deployment.access_config):
            return

        namespace = self._resolve_namespace(deployment)

        try:
            await self.budcluster_client.delete_httproute(
                cluster_id=deployment.cluster_id,
                deployment_id=str(deployment.id),
                namespace=namespace,
            )
            logger.info(f"HTTPRoute deleted for deployment {deployment.id} on cluster {deployment.cluster_id}")
        except Exception as e:
            logger.warning(f"Failed to delete HTTPRoute for deployment {deployment.id}: {e}")

        # Clear gateway_url regardless of whether the delete call succeeded,
        # since the deployment is being stopped/deleted
        self.deployment_manager.update_deployment_gateway_url(
            deployment_id=deployment.id,
            gateway_url=None,
        )
