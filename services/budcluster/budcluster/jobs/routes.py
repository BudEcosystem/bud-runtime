#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  Licensed under the Apache License, Version 2.0
#  -----------------------------------------------------------------------------

"""REST API routes for the unified job tracking system in BudCluster."""

from __future__ import annotations

from uuid import UUID

from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.psql_service import DBSession
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from .enums import JobType
from .events import publish_job_event
from .schemas import JobCreate, JobResponse
from .services import JobService
from .validators import validate_helm_config


logger = get_logger(__name__)

job_router = APIRouter(prefix="/job")


@job_router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(data: JobCreate) -> JobResponse:
    """Create a new job."""
    return await JobService.create_job(data)


@job_router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID) -> JobResponse:
    """Get a job by ID."""
    return await JobService.get_job(job_id)


@job_router.post("/{job_id}/execute", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_job(job_id: UUID, background_tasks: BackgroundTasks) -> JobResponse:
    """Trigger execution of a job.

    Currently supports HELM_DEPLOY jobs. Validates the config,
    transitions the job to RUNNING, and dispatches a background task.
    """
    job = await JobService.get_job(job_id)

    if job.job_type != JobType.HELM_DEPLOY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job type '{job.job_type}' does not support direct execution",
        )

    # Validate helm config
    config = job.config or {}
    errors = validate_helm_config(config)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Helm config: {'; '.join(errors)}",
        )

    # Transition to RUNNING
    running_job = await JobService.start_job(job_id)

    # Dispatch background execution
    background_tasks.add_task(
        _run_helm_deploy,
        job_id=job_id,
        cluster_id=job.cluster_id,
        config=config,
        source=str(job.source),
        source_id=str(job.source_id) if job.source_id else None,
    )

    return running_job


async def _run_helm_deploy(
    job_id: UUID,
    cluster_id: UUID,
    config: dict,
    source: str,
    source_id: str | None,
) -> None:
    """Background task: run Helm deploy via Ansible and publish result event."""
    try:
        # Lazy imports to avoid circular deps at module level
        from ..cluster_ops.crud import ClusterDataManager
        from ..cluster_ops.kubernetes import KubernetesHandler

        # Fetch cluster config
        with DBSession() as session:
            cluster_dm = ClusterDataManager(session)
            cluster = await cluster_dm.retrieve_cluster_by_fields({"id": cluster_id}, missing_ok=False)

        k8s_handler = KubernetesHandler(cluster.config_file_dict, cluster.ingress_url)

        # Run the Helm deploy playbook
        deploy_status, result_info = k8s_handler.deploy_helm_chart(
            release_name=config.get("release_name", "release"),
            chart_ref=config.get("chart_ref", ""),
            namespace=config.get("namespace", "default"),
            values=config.get("values", {}),
            chart_version=config.get("chart_version"),
            timeout=config.get("timeout", "600s"),
            delete_on_failure=False,
            git_repo=config.get("git_repo", ""),
            git_ref=config.get("git_ref", "main"),
            chart_subpath=config.get("chart_subpath", "."),
        )

        if deploy_status == "successful":
            await JobService.complete_job(job_id)
            publish_job_event(
                job_id=str(job_id),
                job_type=JobType.HELM_DEPLOY,
                source=source,
                source_id=source_id,
                status="COMPLETED",
                result=result_info,
            )
        else:
            error_msg = f"Helm deploy finished with status: {deploy_status}"
            await JobService.fail_job(job_id, error_msg)
            publish_job_event(
                job_id=str(job_id),
                job_type=JobType.HELM_DEPLOY,
                source=source,
                source_id=source_id,
                status="FAILED",
                error=error_msg,
            )

    except Exception as e:
        error_msg = f"Helm deploy failed: {e!s}"
        logger.exception("helm_deploy_background_error", job_id=str(job_id), error=error_msg)
        try:
            await JobService.fail_job(job_id, error_msg)
        except Exception:
            logger.exception("failed_to_update_job_status", job_id=str(job_id))
        publish_job_event(
            job_id=str(job_id),
            job_type=JobType.HELM_DEPLOY,
            source=source,
            source_id=source_id,
            status="FAILED",
            error=error_msg,
        )
