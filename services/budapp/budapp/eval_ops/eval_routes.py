import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.schemas import ErrorResponse
from budapp.eval_ops.schemas import (
    CreateExperimentRequest,
    CreateExperimentResponse,
    DatasetFilter,
    DeleteExperimentResponse,
    DeleteRunResponse,
    ExperimentWorkflowResponse,
    ExperimentWorkflowStepRequest,
    GetDatasetResponse,
    GetRunResponse,
    ListDatasetsResponse,
    ListExperimentsResponse,
    ListRunsResponse,
    ListTraitsResponse,
    UpdateExperimentRequest,
    UpdateExperimentResponse,
    UpdateRunRequest,
    UpdateRunResponse,
)
from budapp.eval_ops.services import ExperimentService, ExperimentWorkflowService
from budapp.user_ops.models import User


router = APIRouter(prefix="/experiments", tags=["experiments"])

logger = logging.get_logger(__name__)


@router.post(
    "/",
    response_model=CreateExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def create_experiment(
    request: CreateExperimentRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new experiment.

    - **request**: Payload containing `name`, `description`, and `project_id`.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user creating the experiment.

    Returns a `CreateExperimentResponse` with the created experiment.
    """
    try:
        experiment = ExperimentService(session).create_experiment(request, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to create experiment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create experiment") from e

    return CreateExperimentResponse(
        code=status.HTTP_201_CREATED,
        object="experiment.create",
        message="Successfully created experiment",
        experiment=experiment,
    )


@router.get(
    "/",
    response_model=ListExperimentsResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}},
)
def list_experiments(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List all experiments for the current user.

    - **session**: Database session dependency.
    - **current_user**: The authenticated user whose experiments are listed.

    Returns a `ListExperimentsResponse` containing a list of experiments.
    """
    try:
        experiments = ExperimentService(session).list_experiments(current_user.id)
    except Exception as e:
        logger.debug(f"Failed to list experiments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list experiments") from e

    return ListExperimentsResponse(
        code=status.HTTP_200_OK,
        object="experiment.list",
        message="Successfully listed experiments",
        experiments=experiments,
    )


@router.patch(
    "/{experiment_id}",
    response_model=UpdateExperimentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def update_experiment(
    request: UpdateExperimentRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update an existing experiment.

    - **experiment_id**: UUID of the experiment to update.
    - **request**: Payload with optional `name` and/or `description` fields.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user performing the update.

    Returns an `UpdateExperimentResponse` with the updated experiment.
    """
    try:
        experiment = ExperimentService(session).update_experiment(experiment_id, request, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update experiment") from e

    return UpdateExperimentResponse(
        code=status.HTTP_200_OK,
        object="experiment.update",
        message="Successfully updated experiment",
        experiment=experiment,
    )


@router.delete(
    "/{experiment_id}",
    response_model=DeleteExperimentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def delete_experiment(
    experiment_id: Annotated[uuid.UUID, Path(..., description="ID of experiment to delete")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Soft-delete an existing experiment by marking its status as 'deleted'.

    - **experiment_id**: UUID of the experiment to delete.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user performing the deletion.

    Returns a `DeleteExperimentResponse` confirming the deletion.
    """
    try:
        ExperimentService(session).delete_experiment(experiment_id, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete experiment") from e

    return DeleteExperimentResponse(
        code=status.HTTP_200_OK,
        object="experiment.delete",
        message="Successfully deleted experiment",
    )


@router.post(
    "/workflow",
    response_model=ExperimentWorkflowResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def experiment_workflow_step(
    request: ExperimentWorkflowStepRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Process a step in the experiment creation workflow.

    This endpoint handles the multi-stage experiment creation process:

    **Step 1: Basic Information**
    - Required: name, project_id
    - Optional: description

    **Step 2: Model Selection**
    - Required: model_ids (list of model UUIDs)

    **Step 3: Traits Selection**
    - Required: trait_ids (list of trait UUIDs)
    - Optional: dataset_ids (specific datasets)

    **Step 4: Performance Point**
    - Required: performance_point (integer between 0-100)

    **Step 5: Finalization**
    - Optional: run_name, run_description, evaluation_config
    - Set trigger_workflow=true to create the experiment

    - **request**: Workflow step request with stage_data
    - **session**: Database session dependency
    - **current_user**: The authenticated user

    Returns an `ExperimentWorkflowResponse` with workflow status and next step guidance.
    """
    try:
        workflow_service = ExperimentWorkflowService(session)
        response = await workflow_service.process_experiment_workflow_step(request, current_user.id)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to process experiment workflow step: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process workflow step") from e


@router.get(
    "/workflow/{workflow_id}",
    response_model=ExperimentWorkflowResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def review_experiment_workflow(
    workflow_id: Annotated[uuid.UUID, Path(..., description="Workflow ID to review")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Review experiment workflow data.

    This endpoint allows you to review all data collected during the experiment creation workflow.
    It returns the complete workflow state including:

    - Current step and total steps
    - All accumulated data from completed steps
    - Workflow status and completion state
    - Next step information (if not complete)

    Useful for:
    - Reviewing data before final submission
    - Checking workflow progress
    - Auditing completed workflows
    - Debugging workflow issues

    - **workflow_id**: UUID of the workflow to review
    - **session**: Database session dependency
    - **current_user**: The authenticated user

    Returns an `ExperimentWorkflowResponse` with complete workflow data.
    """
    try:
        workflow_service = ExperimentWorkflowService(session)
        response = await workflow_service.get_experiment_workflow_data(workflow_id, current_user.id)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to review experiment workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to review workflow") from e


@router.get(
    "/{experiment_id}/runs",
    response_model=ListRunsResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def list_runs(
    experiment_id: Annotated[uuid.UUID, Path(..., description="Experiment ID")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List runs for an experiment.

    - **experiment_id**: UUID of the experiment.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user.

    Returns a `ListRunsResponse` containing a list of runs.
    """
    try:
        runs = ExperimentService(session).list_runs(experiment_id, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list runs") from e

    return ListRunsResponse(
        code=status.HTTP_200_OK,
        object="run.list",
        message="Successfully listed runs",
        runs=runs,
    )


@router.get(
    "/runs/{run_id}",
    response_model=GetRunResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def get_run(
    run_id: Annotated[uuid.UUID, Path(..., description="Run ID")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get detailed run information with evaluations.

    - **run_id**: UUID of the run.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user.

    Returns a `GetRunResponse` with the run and its evaluations.
    """
    try:
        run = ExperimentService(session).get_run_with_results(run_id, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get run") from e

    return GetRunResponse(
        code=status.HTTP_200_OK,
        object="run.get",
        message="Successfully retrieved run",
        run=run,
    )


@router.patch(
    "/runs/{run_id}",
    response_model=UpdateRunResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def update_run(
    run_id: Annotated[uuid.UUID, Path(..., description="Run ID")],
    request: Annotated[UpdateRunRequest, Depends()],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update a run.

    - **run_id**: UUID of the run to update.
    - **request**: Payload with optional fields to update.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user performing the update.

    Returns an `UpdateRunResponse` with the updated run.
    """
    try:
        run = ExperimentService(session).update_run(run_id, request, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update run") from e

    return UpdateRunResponse(
        code=status.HTTP_200_OK,
        object="run.update",
        message="Successfully updated run",
        run=run,
    )


@router.delete(
    "/runs/{run_id}",
    response_model=DeleteRunResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def delete_run(
    run_id: Annotated[uuid.UUID, Path(..., description="Run ID")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Delete a run.

    - **run_id**: UUID of the run to delete.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user performing the deletion.

    Returns a `DeleteRunResponse` confirming the deletion.
    """
    try:
        ExperimentService(session).delete_run(run_id, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete run") from e

    return DeleteRunResponse(
        code=status.HTTP_200_OK,
        object="run.delete",
        message="Successfully deleted run",
    )


@router.get(
    "/traits",
    response_model=ListTraitsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def list_traits(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, description="Results per page")] = 10,
    name: Annotated[Optional[str], Query(description="Filter by trait name")] = None,
    unique_id: Annotated[Optional[str], Query(description="Filter by trait UUID")] = None,
):
    """List experiment traits with optional filtering and pagination."""
    try:
        offset = (page - 1) * limit
        traits, total_count = ExperimentService(session).list_traits(
            offset=offset, limit=limit, name=name, unique_id=unique_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list traits") from e

    return ListTraitsResponse(
        code=status.HTTP_200_OK,
        object="trait.list",
        message="Successfully listed traits",
        traits=traits,
        total_record=total_count,
        page=page,
        limit=limit,
    )


@router.get(
    "/datasets",
    response_model=ListDatasetsResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}},
)
def list_datasets(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, description="Results per page")] = 10,
    name: Annotated[Optional[str], Query(description="Filter by dataset name")] = None,
    modalities: Annotated[Optional[str], Query(description="Filter by modalities (comma-separated)")] = None,
    language: Annotated[Optional[str], Query(description="Filter by languages (comma-separated)")] = None,
    domains: Annotated[Optional[str], Query(description="Filter by domains (comma-separated)")] = None,
):
    """List datasets with optional filtering and pagination."""
    try:
        offset = (page - 1) * limit

        # Parse comma-separated filters
        filters = DatasetFilter(
            name=name,
            modalities=modalities.split(",") if modalities else None,
            language=language.split(",") if language else None,
            domains=domains.split(",") if domains else None,
        )

        datasets, total_count = ExperimentService(session).list_datasets(offset=offset, limit=limit, filters=filters)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list datasets") from e

    return ListDatasetsResponse(
        code=status.HTTP_200_OK,
        object="dataset.list",
        message="Successfully listed datasets",
        datasets=datasets,
        total_record=total_count,
        page=page,
        limit=limit,
    )


@router.get(
    "/datasets/{dataset_id}",
    response_model=GetDatasetResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def get_dataset_by_id(
    dataset_id: Annotated[uuid.UUID, Path(..., description="ID of dataset to retrieve")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get a dataset by ID with associated traits."""
    try:
        dataset = ExperimentService(session).get_dataset_by_id(dataset_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get dataset") from e

    return GetDatasetResponse(
        code=status.HTTP_200_OK,
        object="dataset.get",
        message="Successfully retrieved dataset",
        dataset=dataset,
    )
