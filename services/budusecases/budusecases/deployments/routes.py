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

"""REST API routes for Deployment module."""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .crud import DeploymentDataManager
from .enums import DeploymentStatus
from .exceptions import (
    AccessConfigValidationError,
    DeploymentNotFoundError,
    IncompatibleComponentError,
    InvalidDeploymentStateError,
    MissingRequiredComponentError,
    TemplateNotFoundError,
)
from .schemas import (
    DeploymentCreateSchema,
    DeploymentListResponseSchema,
    DeploymentProgressResponseSchema,
    DeploymentResponseSchema,
    DeploymentStartResponseSchema,
    DeploymentStopResponseSchema,
)
from .services import DeploymentOrchestrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deployments", tags=["deployments"])


def get_session() -> Session:
    """Get database session. Override in app setup."""
    # This should be replaced with actual dependency injection
    raise NotImplementedError("Session dependency not configured")


def get_current_user_id() -> UUID:
    """Get current user ID. Override in app setup."""
    # This should be replaced with actual auth dependency
    raise NotImplementedError("Auth dependency not configured")


def get_current_project_id() -> UUID | None:
    """Get current project ID. Override in app setup."""
    # This should be replaced with actual dependency injection
    raise NotImplementedError("Project ID dependency not configured")


def _resolve_access_urls(deployment) -> dict[str, str] | None:
    """Build user-facing access URLs when a deployment is running."""
    if not deployment.gateway_url or not deployment.access_config:
        return None
    urls = {}
    access = deployment.access_config
    if isinstance(access.get("ui"), dict) and access["ui"].get("enabled"):
        urls["ui"] = f"/budusecases/usecases/{deployment.id}/ui/"
    if isinstance(access.get("api"), dict) and access["api"].get("enabled"):
        urls["api"] = f"{deployment.gateway_url}/usecases/{deployment.id}/api"
    return urls if urls else None


def _deployment_to_response(deployment) -> DeploymentResponseSchema:
    """Convert deployment model to response schema."""
    return DeploymentResponseSchema(
        id=str(deployment.id),
        name=deployment.name,
        template_id=str(deployment.template_id) if deployment.template_id else None,
        template_name=deployment.template.name if deployment.template else None,
        cluster_id=str(deployment.cluster_id),
        project_id=str(deployment.project_id) if deployment.project_id else None,
        status=deployment.status.value if hasattr(deployment.status, "value") else deployment.status,
        parameters=deployment.parameters,
        error_message=deployment.error_message,
        pipeline_execution_id=deployment.pipeline_execution_id,
        access_config=deployment.access_config,
        gateway_url=deployment.gateway_url,
        access_urls=_resolve_access_urls(deployment),
        components=[
            {
                "id": str(c.id),
                "component_name": c.component_name,
                "component_type": c.component_type,
                "selected_component": c.selected_component,
                "job_id": str(c.job_id) if c.job_id else None,
                "status": c.status.value if hasattr(c.status, "value") else c.status,
                "endpoint_url": c.endpoint_url,
                "error_message": c.error_message,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in deployment.component_deployments
        ],
        created_at=deployment.created_at.isoformat(),
        updated_at=deployment.updated_at.isoformat(),
        started_at=deployment.started_at.isoformat() if deployment.started_at else None,
        completed_at=deployment.completed_at.isoformat() if deployment.completed_at else None,
    )


@router.post(
    "",
    response_model=DeploymentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    request: DeploymentCreateSchema,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    project_id: UUID | None = Depends(get_current_project_id),
) -> DeploymentResponseSchema:
    """Create a new deployment.

    Args:
        request: Deployment creation request.
        session: Database session.
        user_id: Current user ID.
        project_id: Current project ID (from header).

    Returns:
        Created deployment.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        deployment = await service.create_deployment(
            request=request,
            user_id=user_id,
            project_id=project_id,
        )
        return _deployment_to_response(deployment)

    except TemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except MissingRequiredComponentError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except IncompatibleComponentError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except AccessConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("", response_model=DeploymentListResponseSchema)
async def list_deployments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    cluster_id: str | None = Query(None, description="Filter by cluster ID"),
    template_name: str | None = Query(None, description="Filter by template name"),
    project_id: str | None = Query(None, description="Filter by project ID"),
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> DeploymentListResponseSchema:
    """List deployments with optional filters.

    Args:
        page: Page number.
        page_size: Items per page.
        status_filter: Optional status filter.
        cluster_id: Optional cluster ID filter.
        template_name: Optional template name filter.
        session: Database session.
        user_id: Current user ID.

    Returns:
        Paginated list of deployments.
    """
    manager = DeploymentDataManager(session=session)

    # Parse filters
    status_enum = None
    if status_filter:
        try:
            status_enum = DeploymentStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            ) from None

    cluster_uuid = None
    if cluster_id:
        try:
            cluster_uuid = UUID(cluster_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cluster_id: {cluster_id}",
            ) from None

    project_uuid = None
    if project_id:
        try:
            project_uuid = UUID(project_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid project_id: {project_id}",
            ) from None

    deployments = manager.list_deployments(
        page=page,
        page_size=page_size,
        user_id=user_id,
        cluster_id=cluster_uuid,
        status=status_enum,
        project_id=project_uuid,
    )

    total = manager.count_deployments(
        user_id=user_id,
        cluster_id=cluster_uuid,
        status=status_enum,
        project_id=project_uuid,
    )

    return DeploymentListResponseSchema(
        items=[_deployment_to_response(d) for d in deployments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{deployment_id}", response_model=DeploymentResponseSchema)
async def get_deployment(
    deployment_id: UUID,
    session: Session = Depends(get_session),
) -> DeploymentResponseSchema:
    """Get a deployment by ID.

    Args:
        deployment_id: Deployment UUID.
        session: Database session.

    Returns:
        Deployment details.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        deployment = await service.get_deployment_details(deployment_id)
        return _deployment_to_response(deployment)

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{deployment_id}/progress", response_model=DeploymentProgressResponseSchema)
async def get_deployment_progress(
    deployment_id: UUID,
    session: Session = Depends(get_session),
) -> DeploymentProgressResponseSchema:
    """Get real-time deployment progress.

    Returns step-level progress from BudPipeline for pipeline-orchestrated
    deployments, or synthesized progress from local statuses for legacy
    deployments.

    Args:
        deployment_id: Deployment UUID.
        session: Database session.

    Returns:
        Deployment progress with step details and aggregated metrics.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        progress = await service.get_deployment_progress(deployment_id)
        return DeploymentProgressResponseSchema(**progress)

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{deployment_id}/start", response_model=DeploymentStartResponseSchema)
async def start_deployment(
    deployment_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> DeploymentStartResponseSchema:
    """Start a deployment.

    Validates the deployment, builds the pipeline DAG, and updates the status
    to DEPLOYING immediately.  The actual pipeline submission to BudPipeline
    is deferred to a background task so this endpoint returns fast.

    Args:
        deployment_id: Deployment UUID.
        request: FastAPI request (for reading notification headers).
        background_tasks: FastAPI background tasks.
        session: Database session.

    Returns:
        Start response with new status.
    """
    service = DeploymentOrchestrationService(session=session)
    notification_workflow_id = request.headers.get("X-Notification-Workflow-ID")
    logger.info(
        "start_deployment route: deployment_id=%s, notification_workflow_id=%s",
        deployment_id,
        notification_workflow_id,
    )

    try:
        deployment = await service.start_deployment(
            deployment_id,
            notification_workflow_id=notification_workflow_id,
        )

        # Schedule pipeline submission as a background task (fire-and-forget).
        # The DAG was built by the service and stored on the service instance.
        dag = getattr(service, "_pending_dag", None)
        if dag is not None:
            background_tasks.add_task(
                DeploymentOrchestrationService.run_pipeline_in_background,
                deployment_id=deployment.id,
                user_id=deployment.user_id,
                dag=dag,
                notification_workflow_id=notification_workflow_id,
            )

        return DeploymentStartResponseSchema(
            id=str(deployment.id),
            status=deployment.status.value if hasattr(deployment.status, "value") else deployment.status,
            message="Deployment started",
            pipeline_execution_id=deployment.pipeline_execution_id,
        )

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidDeploymentStateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post("/{deployment_id}/stop", response_model=DeploymentStopResponseSchema)
async def stop_deployment(
    deployment_id: UUID,
    session: Session = Depends(get_session),
) -> DeploymentStopResponseSchema:
    """Stop a running deployment.

    Args:
        deployment_id: Deployment UUID.
        session: Database session.

    Returns:
        Stop response with new status.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        deployment = await service.stop_deployment(deployment_id)
        return DeploymentStopResponseSchema(
            id=str(deployment.id),
            status=deployment.status.value if hasattr(deployment.status, "value") else deployment.status,
            message="Deployment stopped",
        )

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidDeploymentStateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> None:
    """Delete a deployment.

    Deletes DB records immediately and schedules cluster resource
    cleanup (namespace deletion) as a background task.

    Args:
        deployment_id: Deployment UUID.
        background_tasks: FastAPI background tasks.
        session: Database session.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        cleanup_context = await service.delete_deployment(deployment_id)
        background_tasks.add_task(
            DeploymentOrchestrationService.cleanup_deployment_resources,
            cleanup_context,
        )

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidDeploymentStateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post("/{deployment_id}/sync", response_model=DeploymentResponseSchema)
async def sync_deployment_status(
    deployment_id: UUID,
    session: Session = Depends(get_session),
) -> DeploymentResponseSchema:
    """Sync deployment status from BudCluster.

    Args:
        deployment_id: Deployment UUID.
        session: Database session.

    Returns:
        Updated deployment details.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        deployment = await service.sync_deployment_status(deployment_id)
        return _deployment_to_response(deployment)

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{deployment_id}/retry-gateway", response_model=DeploymentResponseSchema)
async def retry_gateway_route(
    deployment_id: UUID,
    session: Session = Depends(get_session),
) -> DeploymentResponseSchema:
    """Retry HTTPRoute creation for a deployment missing a gateway URL.

    Useful when a deployment completed but gateway route creation failed.
    Works for RUNNING or FAILED deployments with access config enabled.

    Args:
        deployment_id: Deployment UUID.
        session: Database session.

    Returns:
        Updated deployment details.
    """
    service = DeploymentOrchestrationService(session=session)

    try:
        deployment = await service.retry_gateway_route(deployment_id)
        return _deployment_to_response(deployment)

    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidDeploymentStateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
