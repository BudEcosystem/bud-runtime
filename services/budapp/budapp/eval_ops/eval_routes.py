import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse
from budapp.eval_ops.schemas import (
    ConfigureRunsRequest,
    ConfigureRunsResponse,
    CreateEvalTagResponse,
    CreateExperimentRequest,
    CreateExperimentResponse,
    DatasetFilter,
    DeleteExperimentResponse,
    DeleteRunResponse,
    EvalTagCreate,
    EvalTagListResponse,
    EvalTagSearchResponse,
    EvaluationWorkflowResponse,
    EvaluationWorkflowStepRequest,
    ExperimentEvaluationsResponse,
    ExperimentModelListItem,
    ExperimentWorkflowStepRequest,
    GetDatasetResponse,
    GetExperimentResponse,
    GetRunResponse,
    ListDatasetsResponse,
    ListEvaluationsResponse,
    ListExperimentModelsResponse,
    ListExperimentsResponse,
    ListRunsResponse,
    ListTraitsResponse,
    RunHistoryResponse,
    UpdateExperimentRequest,
    UpdateExperimentResponse,
    UpdateRunRequest,
    UpdateRunResponse,
)
from budapp.eval_ops.services import (
    EvalTagService,
    EvaluationWorkflowService,
    ExperimentService,
    ExperimentWorkflowService,
)
from budapp.user_ops.models import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse


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

    Creates an experiment with basic information only. Use POST /{experiment_id}/runs
    to configure the model-dataset evaluation runs afterward.

    - **request**: Payload containing `name`, `description`, `project_id`, and optional `tags`.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user creating the experiment.

    Returns a `CreateExperimentResponse` with the created experiment.
    """
    try:
        experiment = ExperimentService(session).create_experiment(request, current_user.id)
    except ClientException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
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
    project_id: Annotated[Optional[uuid.UUID], Query(description="Filter by project ID")] = None,
    id: Annotated[Optional[uuid.UUID], Query(description="Filter by experiment ID")] = None,
    search: Annotated[
        Optional[str], Query(min_length=1, max_length=100, description="Search experiments by name (case-insensitive)")
    ] = None,
    status: Annotated[
        Optional[str],
        Query(description="Filter by status: running, completed, failed, pending, cancelled, no_runs"),
    ] = None,
    model_id: Annotated[Optional[uuid.UUID], Query(description="Filter by model ID")] = None,
    created_after: Annotated[
        Optional[datetime], Query(description="Filter experiments created after this date (ISO 8601)")
    ] = None,
    created_before: Annotated[
        Optional[datetime], Query(description="Filter experiments created before this date (ISO 8601)")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
):
    """List all experiments for the current user with pagination and advanced filtering.

    - **session**: Database session dependency.
    - **current_user**: The authenticated user whose experiments are listed.
    - **search**: Optional search query to filter by experiment name (case-insensitive substring match).
    - **project_id**: Optional filter by project ID.
    - **id**: Optional filter by experiment ID.
    - **status**: Optional filter by computed status (running/completed/failed/pending/cancelled/no_runs).
    - **model_id**: Optional filter by model ID used in experiment runs.
    - **created_after**: Optional filter for experiments created after this date (ISO 8601 format).
    - **created_before**: Optional filter for experiments created before this date (ISO 8601 format).
    - **page**: Page number (default: 1).
    - **limit**: Items per page (default: 10, max: 100).

    Returns a `ListExperimentsResponse` containing a paginated list of experiments.
    """
    try:
        offset = (page - 1) * limit
        experiments, total_count = ExperimentService(session).list_experiments(
            user_id=current_user.id,
            project_id=project_id,
            experiment_id=id,
            search_query=search,
            status=status,
            model_id=model_id,
            created_after=created_after,
            created_before=created_before,
            offset=offset,
            limit=limit,
        )
    except Exception as e:
        logger.debug(f"Failed to list experiments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list experiments") from e

    return ListExperimentsResponse(
        code=status.HTTP_200_OK,
        object="experiment.list",
        message="Successfully listed experiments",
        experiments=experiments,
        page=page,
        limit=limit,
        total_record=total_count,
    )


@router.get(
    "/models",
    response_model=ListExperimentModelsResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}},
)
def list_experiment_models(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    project_id: Annotated[Optional[uuid.UUID], Query(description="Filter by project ID")] = None,
):
    """List all unique models used across user's experiments.

    This endpoint returns all unique models that have been used in the current user's
    experiments, along with the count of experiments using each model. This is useful
    for populating filter dropdowns in the frontend.

    - **session**: Database session dependency.
    - **current_user**: The authenticated user whose experiments are queried.
    - **project_id**: Optional filter by project ID to limit models to specific project.

    Returns a `ListExperimentModelsResponse` containing:
    - List of models with their IDs, names, deployment names, and experiment counts
    - Total count of unique models
    """
    try:
        models, total_count = ExperimentService(session).list_experiment_models(
            user_id=current_user.id,
            project_id=project_id,
        )

        # Convert dict results to Pydantic models
        model_items = [ExperimentModelListItem(**model) for model in models]

        return ListExperimentModelsResponse(
            code=status.HTTP_200_OK,
            object="experiment.models.list",
            message="Successfully listed experiment models",
            models=model_items,
            total_count=total_count,
        )
    except Exception as e:
        logger.debug(f"Failed to list experiment models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list experiment models") from e


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
    modalities: Annotated[
        Optional[str],
        Query(description="Filter by modalities (comma-separated)"),
    ] = None,
    language: Annotated[
        Optional[str],
        Query(description="Filter by languages (comma-separated)"),
    ] = None,
    domains: Annotated[Optional[str], Query(description="Filter by domains (comma-separated)")] = None,
    trait_ids: Annotated[
        Optional[str],
        Query(description="Filter by trait UUIDs (comma-separated)"),
    ] = None,
    has_gen_eval_type: Annotated[
        bool,
        Query(description="Filter datasets with 'gen' key in eval_types. Set to false to show all datasets."),
    ] = True,
):
    """List datasets with optional filtering and pagination.

    By default, only datasets with 'gen' evaluation type are returned. Set `has_gen_eval_type=false` to see all datasets.
    """
    try:
        offset = (page - 1) * limit

        # Parse comma-separated filters
        trait_id_list = None
        if trait_ids:
            # Convert comma-separated UUIDs to list of UUID objects
            trait_id_list = []
            for tid in trait_ids.split(","):
                try:
                    trait_id_list.append(uuid.UUID(tid.strip()))
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid UUID format for trait_id: {tid}",
                    )

        filters = DatasetFilter(
            name=name,
            modalities=modalities.split(",") if modalities else None,
            language=language.split(",") if language else None,
            domains=domains.split(",") if domains else None,
            trait_ids=trait_id_list,
            has_gen_eval_type=has_gen_eval_type,
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


# ------------------------ Tag Management Routes ------------------------


@router.get(
    "/tags",
    response_model=EvalTagListResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse}},
)
def list_tags(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
):
    """List all evaluation tags with pagination.

    Tags are global and shared across all users. This endpoint returns
    all tags ordered alphabetically.

    - **session**: Database session dependency.
    - **current_user**: The authenticated user.
    - **page**: Page number (default: 1).
    - **limit**: Items per page (default: 50, max: 100).

    Returns an `EvalTagListResponse` containing a paginated list of tags.
    """
    try:
        offset = (page - 1) * limit
        tags, total = EvalTagService(session).list_tags(offset, limit)

        return EvalTagListResponse(
            code=status.HTTP_200_OK,
            object="eval_tag.list",
            message="Successfully listed tags",
            tags=tags,
            total_record=total,
            page=page,
            limit=limit,
        )
    except Exception as e:
        logger.debug(f"Failed to list tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list tags") from e


@router.get(
    "/tags/search",
    response_model=EvalTagSearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def search_tags(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    q: Annotated[str, Query(min_length=1, description="Search query")],
    limit: Annotated[int, Query(ge=1, le=50, description="Maximum results")] = 10,
):
    """Search tags by name with character-by-character autocomplete.

    Performs case-insensitive prefix matching on tag names. This is designed
    for autocomplete functionality where the search query is updated as the
    user types.

    - **session**: Database session dependency.
    - **current_user**: The authenticated user.
    - **q**: Search query string (minimum 1 character).
    - **limit**: Maximum number of results (default: 10, max: 50).

    Returns an `EvalTagSearchResponse` with matching tags and total count.
    """
    try:
        tags, total = EvalTagService(session).search_tags(q, limit)

        return EvalTagSearchResponse(
            code=status.HTTP_200_OK,
            object="eval_tag.search",
            message="Successfully searched tags",
            tags=tags,
            total=total,
        )
    except Exception as e:
        logger.debug(f"Failed to search tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search tags") from e


@router.post(
    "/tags",
    response_model=CreateEvalTagResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def create_tag(
    request: EvalTagCreate,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new evaluation tag or return existing tag if name already exists.

    Tag names are case-insensitive and must be unique. If a tag with the same
    name (case-insensitive) already exists, the existing tag is returned instead
    of creating a duplicate.

    - **request**: Tag creation request with name and optional description.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user creating the tag.

    Returns a `CreateEvalTagResponse` with the created or existing tag.

    **Validation rules:**
    - Name: 1-20 characters, alphanumeric, hyphens, and underscores only
    - Description: Optional, max 255 characters
    """
    try:
        tag = EvalTagService(session).create_tag(request.name, request.description)
        session.commit()

        return CreateEvalTagResponse(
            code=status.HTTP_201_CREATED,
            object="eval_tag.create",
            message="Successfully created tag",
            tag=tag,
        )
    except ValueError as e:
        logger.debug(f"Tag validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.debug(f"Failed to create tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create tag") from e


@router.get(
    "/{experiment_id}",
    response_model=GetExperimentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def get_experiment(
    experiment_id: Annotated[uuid.UUID, Path(..., description="ID of experiment to retrieve")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get an experiment by ID.

    - **experiment_id**: UUID of the experiment to retrieve.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user requesting the experiment.

    Returns a `GetExperimentResponse` with the requested experiment.
    """
    try:
        experiment = ExperimentService(session).get_experiment(experiment_id, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to get experiment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get experiment") from e

    return GetExperimentResponse(
        code=status.HTTP_200_OK,
        object="experiment.get",
        message="Successfully retrieved experiment",
        experiment=experiment,
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
    experiment_id: Annotated[uuid.UUID, Path(..., description="ID of experiment to update")],
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
    response_model=RetrieveWorkflowDataResponse,
    response_model_exclude_none=True,
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

    **Step 2: Endpoint Selection**
    - Required: endpoint_ids (list of endpoint UUIDs)

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
    response_model=RetrieveWorkflowDataResponse,
    response_model_exclude_none=True,
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
    response_model=ListEvaluationsResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def list_runs(
    experiment_id: Annotated[uuid.UUID, Path(..., description="Experiment ID")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List completed evaluations for an experiment.

    - **experiment_id**: UUID of the experiment.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user.

    Returns a `ListEvaluationsResponse` containing a list of completed evaluations with model, traits, and scores.
    """
    try:
        evaluations = ExperimentService(session).list_runs(experiment_id, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list evaluations") from e

    return ListEvaluationsResponse(
        code=status.HTTP_200_OK,
        object="evaluation.list",
        message="Successfully listed completed evaluations",
        evaluations=evaluations,
    )


@router.get(
    "/{experiment_id}/runs/history",
    response_model=RunHistoryResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def get_runs_history(
    experiment_id: Annotated[uuid.UUID, Path(..., description="Experiment ID")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 50,
    sort_field: Annotated[str, Query(description="Field to sort by")] = "started_at",
    sort_direction: Annotated[str, Query(description="Sort direction (asc/desc)")] = "desc",
):
    """Get run history for an experiment with pagination.

    - **experiment_id**: UUID of the experiment.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user.
    - **page**: Page number (default: 1).
    - **page_size**: Page size (default: 50, max: 100).
    - **sort_field**: Field to sort by (default: "started_at").
    - **sort_direction**: Sort direction (default: "desc").

    Returns a `RunHistoryResponse` with paginated run history.
    """
    try:
        runs_history = ExperimentService(session).get_runs_history(
            experiment_id,
            current_user.id,
            page=page,
            page_size=page_size,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get run history") from e

    return RunHistoryResponse(
        code=status.HTTP_200_OK,
        object="runs.history",
        message="Successfully retrieved run history",
        runs_history=runs_history,
    )


@router.post(
    "/{experiment_id}/runs",
    response_model=ConfigureRunsResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def configure_runs(
    experiment_id: Annotated[uuid.UUID, Path(..., description="Experiment ID")],
    request: ConfigureRunsRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Configure runs for an experiment by creating model-dataset combinations.

    - **experiment_id**: UUID of the experiment to configure runs for.
    - **request**: Payload containing endpoint_ids, dataset_ids, and optional evaluation_config.
    - **session**: Database session dependency.
    - **current_user**: The authenticated user.

    Returns a `ConfigureRunsResponse` with the created runs.
    """
    try:
        runs = ExperimentService(session).configure_runs(experiment_id, request, current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to configure runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to configure runs") from e

    return ConfigureRunsResponse(
        code=status.HTTP_201_CREATED,
        object="experiment.runs.configure",
        message="Successfully configured runs",
        runs=runs,
        total_runs=len(runs),
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


# ------------------------ Evaluation Workflow Routes ------------------------


@router.post(
    "/{experiment_id}/evaluations/workflow",
    response_model=RetrieveWorkflowDataResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def evaluation_workflow_step(
    experiment_id: Annotated[
        uuid.UUID,
        Path(..., description="ID of experiment to create evaluation for"),
    ],
    request: EvaluationWorkflowStepRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Process a step in the evaluation creation workflow.

    This endpoint handles a 5-step workflow for creating evaluation runs within an experiment:

    **Step 1: Basic Information**
    - Provide `name` and optional `description` in `stage_data`
    - `workflow_id` should be null for first step
    - `workflow_total_steps` should be 5

    **Step 2: Endpoint Selection**
    - Provide `endpoint_id` in `stage_data` (select one endpoint from experiment's existing runs)
    - `workflow_id` from step 1 response required

    **Step 3: Trait Selection**
    - Provide `trait_ids` array in `stage_data` (minimum 1)
    - `workflow_id` from previous step required

    **Step 4: Dataset Selection**
    - Provide `dataset_ids` array in `stage_data` (minimum 1 per trait)
    - Only datasets linked to selected traits are valid
    - `workflow_id` from previous step required

    **Step 5: Final Confirmation**
    - Review summary and set `trigger_workflow=true` to create the runs
    - `workflow_id` from previous step required

    - **experiment_id**: UUID of the experiment to create evaluation runs for
    - **request**: Workflow step request with step data
    - **session**: Database session dependency
    - **current_user**: The authenticated user creating the evaluation

    Returns an `EvaluationWorkflowResponse` with workflow status and next step data.
    """
    try:
        response = await EvaluationWorkflowService(session).process_evaluation_workflow_step(
            experiment_id, request, current_user.id
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to process evaluation workflow step: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process evaluation workflow step") from e

    return response


@router.get(
    "/{experiment_id}/evaluations/workflow/{workflow_id}",
    response_model=RetrieveWorkflowDataResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def get_evaluation_workflow_data(
    experiment_id: Annotated[uuid.UUID, Path(..., description="ID of experiment")],
    workflow_id: Annotated[
        uuid.UUID,
        Path(..., description="ID of evaluation workflow to retrieve"),
    ],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get complete evaluation workflow data for review.

    Retrieves all accumulated data from an evaluation workflow, useful for reviewing
    selections before final submission or resuming an incomplete workflow.

    - **experiment_id**: UUID of the experiment
    - **workflow_id**: UUID of the evaluation workflow to retrieve
    - **session**: Database session dependency
    - **current_user**: The authenticated user

    Returns an `EvaluationWorkflowResponse` with complete workflow data.
    """
    try:
        response = await EvaluationWorkflowService(session).get_evaluation_workflow_data(
            experiment_id, workflow_id, current_user.id
        )
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to get evaluation workflow data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get evaluation workflow data") from e


@router.get(
    "/{experiment_id}/evaluations",
    response_model=ExperimentEvaluationsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def get_experiment_evaluations(
    experiment_id: Annotated[
        uuid.UUID,
        Path(..., description="ID of experiment to get evaluations for"),
    ],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get all evaluations for an experiment with models, traits, datasets, and scores from BudEval.

    This endpoint retrieves comprehensive evaluation data for an experiment including:
    - All runs with their current status
    - Model details for each run
    - Traits with their associated datasets (datasets nested under traits)
    - Real-time evaluation scores from BudEval service (fetched in parallel)

    The scores are fetched asynchronously from the BudEval service, so running evaluations
    may not have scores available yet.

    - **experiment_id**: UUID of the experiment to retrieve evaluations for
    - **session**: Database session dependency
    - **current_user**: The authenticated user requesting the evaluations

    Returns an `ExperimentEvaluationsResponse` with experiment details and all evaluations.
    """
    try:
        result = await ExperimentService(session).get_experiment_evaluations(experiment_id, current_user.id)

        return ExperimentEvaluationsResponse(
            code=status.HTTP_200_OK,
            object="experiment.evaluations",
            message="Successfully retrieved experiment evaluations",
            experiment=result["experiment"],
            evaluations=result["evaluations"],
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(f"Failed to get experiment evaluations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get experiment evaluations") from e
