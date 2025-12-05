import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import aiohttp
from budmicroframe.commons.schemas import WorkflowMetadataResponse
from fastapi import HTTPException, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import (
    BUD_INTERNAL_WORKFLOW,
    BudServeWorkflowStepEventName,
    ProjectStatusEnum,
    WorkflowTypeEnum,
)
from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.eval_ops.models import (
    EvalTag,
    Evaluation,
    EvaluationStatusEnum,
    ExpDatasetVersion,
    ExperimentStatusEnum,
    RunStatusEnum,
)
from budapp.eval_ops.models import Evaluation as EvaluationModel
from budapp.eval_ops.models import ExpDataset as DatasetModel
from budapp.eval_ops.models import Experiment as ExperimentModel
from budapp.eval_ops.models import (
    ExpMetric as MetricModel,
)
from budapp.eval_ops.models import (
    ExpRawResult as RawResultModel,
)
from budapp.eval_ops.models import ExpTrait as TraitModel
from budapp.eval_ops.models import ExpTraitsDatasetPivot as PivotModel
from budapp.eval_ops.models import (
    Run as RunModel,
)
from budapp.eval_ops.schemas import (
    BudgetStats,
    ConfigureRunsRequest,
    CreateDatasetRequest,
    CreateExperimentRequest,
    CurrentMetric,
    DatasetFilter,
    EvaluationListItem,
    EvaluationWorkflowResponse,
    EvaluationWorkflowStepRequest,
    ExperimentStats,
    ExperimentWorkflowResponse,
    ExperimentWorkflowStepData,
    ExperimentWorkflowStepRequest,
    JudgeInfo,
    ModelSummary,
    ProcessingRate,
    ProgressActions,
    ProgressDataset,
    ProgressInfo,
    ProgressOverview,
    RuntimeStats,
    TokenStats,
    TraitBasic,
    TraitSummary,
    UpdateDatasetRequest,
    UpdateExperimentRequest,
    UpdateRunRequest,
)
from budapp.eval_ops.schemas import Evaluation as EvaluationSchema
from budapp.eval_ops.schemas import (
    ExpDataset as DatasetSchema,
)
from budapp.eval_ops.schemas import (
    Experiment as ExperimentSchema,
)
from budapp.eval_ops.schemas import (
    Run as RunSchema,
)
from budapp.eval_ops.schemas import (
    RunWithResults as RunWithResultsSchema,
)
from budapp.eval_ops.schemas import (
    Trait as TraitSchema,
)
from budapp.model_ops.models import Model as ModelTable
from budapp.workflow_ops.crud import (
    WorkflowDataManager,
    WorkflowStepDataManager,
)
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.models import WorkflowStatusEnum
from budapp.workflow_ops.models import WorkflowStep as WorkflowStepModel
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService, WorkflowStepService


logger = logging.get_logger(__name__)


class EvalTagService:
    """Service layer for EvalTag operations.

    Handles tag creation, searching, and management for experiments.
    Tags are global and shared across all users.
    """

    def __init__(self, session: Session):
        """Initialize EvalTagService with database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self.session = session

    def create_tag(self, name: str, description: Optional[str] = None) -> EvalTag:
        """Create a new tag or return existing tag (case-insensitive check).

        Args:
            name: Tag name (1-20 chars, alphanumeric + hyphens/underscores)
            description: Optional tag description

        Returns:
            EvalTag: The created or existing tag object

        Raises:
            ValueError: If tag name format is invalid
        """
        logger.info(f"[EvalTag] create_tag called with name='{name}', description='{description}'")

        # Validate and clean name
        original_name = name
        name = name.strip()
        logger.debug(f"[EvalTag] Cleaned name from '{original_name}' to '{name}'")

        if not re.match(r"^[a-zA-Z0-9\-_]+$", name):
            logger.error(f"[EvalTag] Validation failed: Invalid characters in tag name '{name}'")
            raise ValueError("Tag name can only contain letters, numbers, hyphens, and underscores")
        if len(name) > 20:
            logger.error(f"[EvalTag] Validation failed: Tag name '{name}' exceeds 20 characters (length={len(name)})")
            raise ValueError("Tag name must not exceed 20 characters")
        if len(name) < 1:
            logger.error("[EvalTag] Validation failed: Tag name is empty")
            raise ValueError("Tag name must be at least 1 character")

        logger.debug(f"[EvalTag] Validation passed for tag name '{name}'")

        # Check if tag exists (case-insensitive)
        from sqlalchemy import select

        stmt = select(EvalTag).where(func.lower(EvalTag.name) == func.lower(name))
        logger.debug(f"[EvalTag] Checking if tag '{name}' exists (case-insensitive)")

        try:
            existing = self.session.execute(stmt).scalar_one_or_none()

            if existing:
                logger.info(f"[EvalTag] Tag '{name}' already exists with id={existing.id}. Returning existing tag.")
                return existing

            logger.debug(f"[EvalTag] Tag '{name}' does not exist. Creating new tag.")
        except Exception as e:
            logger.error(
                f"[EvalTag] Error checking for existing tag '{name}': {str(e)}",
                exc_info=True,
            )
            raise

        # Create new tag
        try:
            tag = EvalTag(name=name, description=description)
            self.session.add(tag)
            self.session.flush()  # Get ID without committing
            logger.info(f"[EvalTag] Successfully created new tag '{name}' with id={tag.id}")
            return tag
        except Exception as e:
            logger.error(
                f"[EvalTag] Error creating tag '{name}': {str(e)}",
                exc_info=True,
            )
            raise

    def create_tags_from_names(self, tag_names: List[str]) -> List[EvalTag]:
        """Create or get existing tags from a list of names.

        This is useful for backward compatibility when tags are provided as strings.

        Args:
            tag_names: List of tag names to create or retrieve

        Returns:
            List[EvalTag]: List of tag objects
        """
        tags = []
        for name in tag_names:
            if name and name.strip():  # Skip empty strings
                tag = self.create_tag(name.strip())
                tags.append(tag)
        return tags

    def search_tags(self, query: str, limit: int = 10) -> Tuple[List[EvalTag], int]:
        """Search tags by name with case-insensitive prefix matching.

        This enables character-by-character autocomplete functionality.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            Tuple[List[EvalTag], int]: (List of matching tags, Total count of matches)
        """
        from sqlalchemy import select

        # Search with prefix match
        stmt = (
            select(EvalTag)
            .where(func.lower(EvalTag.name).like(func.lower(f"{query}%")))
            .order_by(EvalTag.name)
            .limit(limit)
        )
        tags = self.session.execute(stmt).scalars().all()

        # Get total count
        count_stmt = select(func.count(EvalTag.id)).where(func.lower(EvalTag.name).like(func.lower(f"{query}%")))
        total = self.session.execute(count_stmt).scalar() or 0

        return list(tags), total

    def list_tags(self, offset: int, limit: int) -> Tuple[List[EvalTag], int]:
        """List all tags with pagination, ordered alphabetically.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple[List[EvalTag], int]: (List of tags, Total count)
        """
        from sqlalchemy import select

        # Get tags with pagination
        stmt = select(EvalTag).order_by(EvalTag.name).offset(offset).limit(limit)
        tags = self.session.execute(stmt).scalars().all()

        # Get total count
        total = self.session.execute(select(func.count(EvalTag.id))).scalar() or 0

        return list(tags), total

    def get_tags_by_ids(self, tag_ids: List[uuid.UUID]) -> List[EvalTag]:
        """Fetch tags by their IDs.

        Args:
            tag_ids: List of tag UUIDs to retrieve

        Returns:
            List[EvalTag]: List of tag objects found
        """
        from sqlalchemy import select

        if not tag_ids:
            return []

        stmt = select(EvalTag).where(EvalTag.id.in_(tag_ids))
        tags = self.session.execute(stmt).scalars().all()
        return list(tags)

    def get_tag_by_id(self, tag_id: uuid.UUID) -> Optional[EvalTag]:
        """Fetch a single tag by ID.

        Args:
            tag_id: Tag UUID to retrieve

        Returns:
            Optional[EvalTag]: Tag object if found, None otherwise
        """
        from sqlalchemy import select

        stmt = select(EvalTag).where(EvalTag.id == tag_id)
        return self.session.execute(stmt).scalar_one_or_none()


class ExperimentService:
    """Service layer for Experiment operations.

    Methods:
        - create_experiment: create and persist a new Experiment with automatic run creation.
        - list_experiments: retrieve all non-deleted Experiments for a user.
        - update_experiment: apply updates to an existing Experiment.
        - delete_experiment: perform a soft delete on an Experiment.
        - list_runs: list runs for an experiment.
        - get_run_with_results: get a run with its metrics and results.
        - update_run: update a run.
        - delete_run: delete a run.
        - list_traits: list Trait entries with optional filters and pagination.
        - get_dataset_by_id: get a dataset by ID with associated traits.
        - list_datasets: list datasets with optional filters and pagination.
        - create_dataset: create a new dataset with traits.
        - update_dataset: update an existing dataset and its traits.
        - delete_dataset: delete a dataset and its trait associations.
    """

    def __init__(self, session: Session):
        """Initialize the service with a database session.

        Parameters:
            session (Session): SQLAlchemy database session.
        """
        self.session = session

    def create_experiment(self, req: CreateExperimentRequest, user_id: uuid.UUID) -> ExperimentSchema:
        """Create a new Experiment record (without runs).

        Parameters:
            req (CreateExperimentRequest): Payload containing name, description, project_id, tags.
            user_id (uuid.UUID): ID of the user creating the experiment.

        Returns:
            ExperimentSchema: Pydantic schema of the created Experiment.

        Raises:
            HTTPException(status_code=400): If experiment with same name already exists for the user.
            HTTPException(status_code=500): If database insertion fails.
        """
        # Check for duplicate experiment name for this user
        # Note: name has already been validated and trimmed by Pydantic
        existing_experiment = (
            self.session.query(ExperimentModel)
            .filter(
                ExperimentModel.name == req.name,
                ExperimentModel.created_by == user_id,
                ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
            )
            .first()
        )

        if existing_experiment:
            raise ClientException(
                message=f"An experiment with the name '{req.name}' already exists. Please choose a different name.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Handle tags - support both new tag_ids and legacy tags
        tag_service = EvalTagService(self.session)
        tag_ids = []

        # Priority 1: Use tag_ids if provided
        if req.tag_ids:
            tag_ids = req.tag_ids
        # Priority 2: Convert legacy tags (strings) to tag IDs
        elif req.tags:
            created_tags = tag_service.create_tags_from_names(req.tags)
            tag_ids = [tag.id for tag in created_tags]

        # Create experiment without project_id initially
        ev = ExperimentModel(
            name=req.name,
            description=req.description,
            # project_id=req.project_id,  # Commented out - made optional
            created_by=user_id,
            status=ExperimentStatusEnum.ACTIVE.value,
            tags=req.tags or [],  # Keep for backward compatibility
            tag_ids=tag_ids,
        )

        # Only set project_id if provided
        if req.project_id:
            ev.project_id = req.project_id
        try:
            self.session.add(ev)
            self.session.commit()
            self.session.refresh(ev)
        except Exception as e:
            self.session.rollback()
            logger.warning(f"Failed to create experiment: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create experiment",
            ) from e

        # Create experiment schema with empty models and traits (new experiment has no runs yet)
        exp_data = ExperimentSchema.model_validate(ev)
        exp_data.models = []
        exp_data.traits = []
        exp_data.status = "no_runs"  # New experiment has no runs

        # Populate tag objects if tag_ids exist
        if ev.tag_ids:
            exp_data.tag_objects = tag_service.get_tags_by_ids(ev.tag_ids)

        return exp_data

    def configure_runs(
        self,
        experiment_id: uuid.UUID,
        req: ConfigureRunsRequest,
        user_id: uuid.UUID,
    ) -> List[RunSchema]:
        """Configure runs for an experiment by creating model-dataset combinations.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment to configure runs for.
            req (ConfigureRunsRequest): Payload containing endpoint_ids, dataset_ids, evaluation_config.
            user_id (uuid.UUID): ID of the user configuring the runs.

        Returns:
            List[RunSchema]: List of created runs.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
            HTTPException(status_code=400): If dataset version not found.
            HTTPException(status_code=500): If database insertion fails.
        """
        # Verify experiment exists and user has access
        experiment = self.session.get(ExperimentModel, experiment_id)
        if not experiment or experiment.created_by != user_id or experiment.status == "deleted":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        try:
            # Get the next run_index to start from
            max_run_index = (
                self.session.query(RunModel.run_index)
                .filter(RunModel.experiment_id == experiment_id)
                .order_by(RunModel.run_index.desc())
                .first()
            )
            next_run_index = (max_run_index[0] + 1) if max_run_index else 1

            created_runs = []

            # Create runs for each model-dataset combination
            for endpoint_id in req.endpoint_ids:
                for dataset_id in req.dataset_ids:
                    # Get the latest version of the dataset
                    dataset_version = (
                        self.session.query(ExpDatasetVersion)
                        .filter(ExpDatasetVersion.dataset_id == dataset_id)
                        .order_by(ExpDatasetVersion.created_at.desc())
                        .first()
                    )

                    if not dataset_version:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"No version found for dataset {dataset_id}",
                        )

                    run = RunModel(
                        experiment_id=experiment_id,
                        run_index=next_run_index,
                        endpoint_id=endpoint_id,
                        dataset_version_id=dataset_version.id,
                        status=RunStatusEnum.RUNNING.value,
                        config=req.evaluation_config or {},
                    )
                    self.session.add(run)
                    self.session.flush()  # Get the run ID
                    created_runs.append(RunSchema.from_orm(run))
                    next_run_index += 1

            self.session.commit()
            return created_runs

        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            logger.warning(f"Failed to configure runs: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to configure runs",
            ) from e

    def list_experiments(
        self,
        user_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
        search_query: Optional[str] = None,
        status: Optional[str] = None,
        model_id: Optional[uuid.UUID] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[ExperimentSchema], int]:
        """List all non-deleted Experiments for a given user with optional filters and pagination.

        Parameters:
            user_id (uuid.UUID): ID of the user whose experiments to list.
            project_id (Optional[uuid.UUID]): Filter by project ID.
            experiment_id (Optional[uuid.UUID]): Filter by experiment ID.
            search_query (Optional[str]): Search query to filter by experiment name (case-insensitive).
            status (Optional[str]): Filter by computed status (running/completed/failed/pending/cancelled/no_runs).
            model_id (Optional[uuid.UUID]): Filter by model ID used in experiment runs.
            created_after (Optional[datetime]): Filter experiments created after this date.
            created_before (Optional[datetime]): Filter experiments created before this date.
            offset (int): Number of records to skip.
            limit (int): Maximum number of records to return.

        Returns:
            Tuple[List[ExperimentSchema], int]: List of experiments and total count.

        Raises:
            HTTPException(status_code=500): If database query fails.
        """
        try:
            q = self.session.query(ExperimentModel).filter(
                ExperimentModel.created_by == user_id,
                ExperimentModel.status != "deleted",
            )

            if project_id is not None:
                q = q.filter(ExperimentModel.project_id == project_id)

            if experiment_id is not None:
                q = q.filter(ExperimentModel.id == experiment_id)

            if search_query is not None and search_query.strip():
                search_pattern = f"%{search_query.strip()}%"
                q = q.filter(ExperimentModel.name.ilike(search_pattern))

            # Date range filters
            if created_after is not None:
                q = q.filter(ExperimentModel.created_at >= created_after)

            if created_before is not None:
                q = q.filter(ExperimentModel.created_at <= created_before)

            # Model filter: experiments that have runs with endpoints using this model
            if model_id is not None:
                model_subquery = (
                    self.session.query(RunModel.experiment_id)
                    .join(EndpointModel, RunModel.endpoint_id == EndpointModel.id)
                    .filter(
                        EndpointModel.model_id == model_id,
                        RunModel.status != RunStatusEnum.DELETED.value,
                    )
                    .distinct()
                    .subquery()
                )
                q = q.filter(ExperimentModel.id.in_(model_subquery))

            # For status filter, we need to fetch more results initially
            # Then filter by status and apply pagination
            if status is not None:
                # Get all matching experiments (without pagination initially)
                q_for_status = q.order_by(ExperimentModel.created_at.desc())
                all_evs = q_for_status.all()

                # Compute statuses for all experiments
                all_experiment_ids = [exp.id for exp in all_evs]
                statuses = self.get_experiment_statuses_batch(all_experiment_ids)

                # Filter by status
                filtered_evs = [exp for exp in all_evs if statuses.get(exp.id, "unknown") == status]

                # Apply pagination to filtered results
                total_count = len(filtered_evs)
                evs = filtered_evs[offset : offset + limit]
            else:
                # Get total count before pagination
                total_count = q.count()

                # Apply pagination and ordering
                q = q.order_by(ExperimentModel.created_at.desc()).offset(offset).limit(limit)
                evs = q.all()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list experiments",
            ) from e

        # Get statuses for all experiments in one batch query
        # If status filter was applied, statuses were already computed
        experiment_ids = [exp.id for exp in evs]
        if status is not None:
            # Recompute statuses for the paginated subset
            statuses = self.get_experiment_statuses_batch(experiment_ids)
        else:
            statuses = self.get_experiment_statuses_batch(experiment_ids)

        # Batch fetch tags for all experiments to avoid N+1 queries
        tag_service = EvalTagService(self.session)
        all_tag_ids = set()
        for exp in evs:
            if exp.tag_ids:
                all_tag_ids.update(exp.tag_ids)

        # Fetch all tags at once
        tags_dict = {}
        if all_tag_ids:
            all_tags = tag_service.get_tags_by_ids(list(all_tag_ids))
            tags_dict = {tag.id: tag for tag in all_tags}

        # Enrich each experiment with models, traits, status, and tags
        enriched_experiments = []
        for exp in evs:
            exp_data = ExperimentSchema.from_orm(exp)
            # Add models and traits to the experiment
            exp_data.models = self.get_models_for_experiment(exp.id)
            exp_data.traits = self.get_traits_for_experiment(exp.id)
            # Add computed status
            exp_data.status = statuses.get(exp.id, "unknown")
            # Add tag objects
            if exp.tag_ids:
                exp_data.tag_objects = [tags_dict[tag_id] for tag_id in exp.tag_ids if tag_id in tags_dict]
            enriched_experiments.append(exp_data)

        return enriched_experiments, total_count

    def get_experiment(self, ev_id: uuid.UUID, user_id: uuid.UUID) -> ExperimentSchema:
        """Get a single Experiment by ID for a given user.

        Parameters:
            ev_id (uuid.UUID): ID of the experiment to retrieve.
            user_id (uuid.UUID): ID of the user attempting to access the experiment.

        Returns:
            ExperimentSchema: Pydantic schema of the requested Experiment.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
        """
        logger.info("Getting experiment - services")

        # Get the Experiment
        ev = self.session.get(ExperimentModel, ev_id)
        if not ev or ev.created_by != user_id or ev.status == "deleted":
            raise ClientException(
                message="Experiment not found or access denied",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Create experiment schema and enrich with models, traits, and status
        exp_data = ExperimentSchema.from_orm(ev)

        # Set default values for stats that are not yet available
        exp_data.stats = ExperimentStats(
            budget=BudgetStats(limit_usd=0.0, used_usd=0.0, used_pct=0),
            tokens=TokenStats(total=0, prefix=0, decode=0, unit="tokens"),
            runtime=RuntimeStats(active_seconds=0, estimated_total_seconds=0),
            processing_rate=ProcessingRate(current_per_min=0, target_per_min=0),
        )

        # Objective
        exp_data.objective = ev.description or ""

        # Traits and Models
        # exp_data.models = self.get_models_for_experiment(ev.id)

        # Get all evaluations for the experiment
        evaluations = (
            self.session.query(Evaluation)
            .filter(Evaluation.experiment_id == ev.id)
            .order_by(Evaluation.created_at.desc())
            .all()
        )

        # Extract unique trait IDs from all evaluations
        trait_ids_set = set()
        for evaluation in evaluations:
            if evaluation.trait_ids:
                trait_ids_set.update(evaluation.trait_ids)

        # Batch fetch all traits at once
        traits_list = []
        if trait_ids_set:
            traits_list = self.session.query(TraitModel).filter(TraitModel.id.in_(list(trait_ids_set))).all()

        # Get all the runs with metrics and get the run details as well as metric details
        # Build current metrics table: each row represents a run with its evaluation, dataset, model, traits, and scores

        # Get all runs for the experiment
        all_experiment_runs = (
            self.session.query(RunModel)
            .filter(
                RunModel.experiment_id == ev.id,
                RunModel.status != RunStatusEnum.DELETED.value,
            )
            .order_by(RunModel.created_at.desc())
            .all()
        )

        # Batch fetch all related data to avoid N+1 queries
        run_ids = [run.id for run in all_experiment_runs]
        evaluation_ids = [run.evaluation_id for run in all_experiment_runs if run.evaluation_id]
        endpoint_ids = [run.endpoint_id for run in all_experiment_runs if run.endpoint_id]
        dataset_version_ids = [run.dataset_version_id for run in all_experiment_runs if run.dataset_version_id]

        # Batch fetch evaluations
        evaluations_dict = {}
        if evaluation_ids:
            evaluations_batch = self.session.query(Evaluation).filter(Evaluation.id.in_(evaluation_ids)).all()
            evaluations_dict = {eval.id: eval for eval in evaluations_batch}

        # Collect all trait IDs from evaluations for batch lookup
        all_trait_ids = set()
        for eval_obj in evaluations_dict.values():
            if eval_obj.trait_ids:
                all_trait_ids.update(eval_obj.trait_ids)

        # Batch fetch trait names by ID
        traits_by_id = {}
        if all_trait_ids:
            # Convert string UUIDs to UUID objects for query
            trait_uuid_list = [uuid.UUID(tid) for tid in all_trait_ids if tid]
            traits_batch = self.session.query(TraitModel).filter(TraitModel.id.in_(trait_uuid_list)).all()
            traits_by_id = {str(trait.id): trait.name for trait in traits_batch}

        # Batch fetch endpoints
        endpoints_dict = {}
        endpoints_batch = []
        if endpoint_ids:
            endpoints_batch = self.session.query(EndpointModel).filter(EndpointModel.id.in_(endpoint_ids)).all()
            endpoints_dict = {endpoint.id: endpoint for endpoint in endpoints_batch}

        # Extract model_ids from endpoints
        model_ids = [ep.model_id for ep in endpoints_batch if ep.model_id]

        # Batch fetch models
        models_dict = {}
        if model_ids:
            models_batch = self.session.query(ModelTable).filter(ModelTable.id.in_(model_ids)).all()
            models_dict = {model.id: model for model in models_batch}

        # Batch fetch dataset versions and datasets
        datasets_dict = {}
        if dataset_version_ids:
            dataset_versions_batch = (
                self.session.query(ExpDatasetVersion).filter(ExpDatasetVersion.id.in_(dataset_version_ids)).all()
            )
            for dv in dataset_versions_batch:
                datasets_dict[dv.id] = dv.dataset

        # Batch fetch all metrics for all runs
        metrics_by_run = {}
        if run_ids:
            metrics_batch = self.session.query(MetricModel).filter(MetricModel.run_id.in_(run_ids)).all()
            for metric in metrics_batch:
                if metric.run_id not in metrics_by_run:
                    metrics_by_run[metric.run_id] = []
                metrics_by_run[metric.run_id].append(metric)

        # Build current metrics as a list of run records
        exp_data.current_metrics = []

        for run in all_experiment_runs:
            # Get evaluation details from batched data
            evaluation_name = "N/A"
            if run.evaluation_id and run.evaluation_id in evaluations_dict:
                evaluation_name = evaluations_dict[run.evaluation_id].name

            # Get model details from batched data
            model_name = "Unknown Model"
            deployment_name = None
            if run.endpoint_id and run.endpoint_id in endpoints_dict:
                endpoint = endpoints_dict[run.endpoint_id]
                if endpoint.model_id in models_dict:
                    model_name = models_dict[endpoint.model_id].name
                deployment_name = endpoint.name

            # Get dataset name from batched data
            dataset_name = "Unknown Dataset"
            if run.dataset_version_id and run.dataset_version_id in datasets_dict:
                dataset = datasets_dict[run.dataset_version_id]
                if dataset:
                    dataset_name = dataset.name

            # Get traits from evaluation's user-selected trait_ids
            traits_list = []
            if run.evaluation_id and run.evaluation_id in evaluations_dict:
                evaluation = evaluations_dict[run.evaluation_id]
                if evaluation.trait_ids:
                    traits_list = [traits_by_id.get(tid, "") for tid in evaluation.trait_ids if tid in traits_by_id]

            # Get metrics from batched data
            metrics = metrics_by_run.get(run.id, [])

            # Calculate average score
            score_value = 0.0
            judge_model = None  # TODO: Get judge model from config if available
            if metrics:
                total = sum(float(m.metric_value) for m in metrics)
                score_value = round(total / len(metrics), 2)

            # Format score with judge model if available
            score_display = f"{score_value}%"
            if judge_model:
                score_display = f"{score_value}% - {judge_model}"

            # Build the current metric record
            metric_record = {
                "evaluation": evaluation_name,
                "dataset": dataset_name,
                "deployment_name": deployment_name or "Not deployed",
                "score": score_display,
                "score_value": score_value,  # Raw value for sorting
                "traits": traits_list,
                "last_run": getattr(run, "updated_at", None) or getattr(run, "created_at", None),
                "status": run.status,
                "run_id": str(run.id),
                "model_name": model_name,
            }

            exp_data.current_metrics.append(metric_record)

        # Get evaluations with Running & Pending status
        evaluations_running = [
            eval
            for eval in evaluations
            if eval.status
            in [
                EvaluationStatusEnum.RUNNING.value,
                EvaluationStatusEnum.PENDING.value,
                EvaluationStatusEnum.COMPLETED.value,
            ]
        ]

        # Batch fetch all runs for running evaluations
        evaluation_ids = [eval.id for eval in evaluations_running]
        all_runs = []
        if evaluation_ids:
            all_runs = (
                self.session.query(RunModel)
                .filter(
                    RunModel.evaluation_id.in_(evaluation_ids),
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .order_by(RunModel.created_at.desc())
                .all()
            )

        # Group runs by evaluation_id
        evaluation_runs_map = {}
        for run in all_runs:
            if run.evaluation_id not in evaluation_runs_map:
                evaluation_runs_map[run.evaluation_id] = []
            evaluation_runs_map[run.evaluation_id].append(run)

        # Collect all unique endpoint IDs from runs
        endpoint_ids = set()
        for runs in evaluation_runs_map.values():
            for run in runs:
                if run.endpoint_id:
                    endpoint_ids.add(run.endpoint_id)

        # Batch fetch endpoints and models
        endpoints_dict = {}
        models_dict = {}
        if endpoint_ids:
            endpoints = self.session.query(EndpointModel).filter(EndpointModel.id.in_(list(endpoint_ids))).all()
            endpoints_dict = {endpoint.id: endpoint for endpoint in endpoints}

            model_ids = [ep.model_id for ep in endpoints if ep.model_id]
            if model_ids:
                models = self.session.query(ModelTable).filter(ModelTable.id.in_(model_ids)).all()
                models_dict = {model.id: model for model in models}

        # Build progress overview with cached model data
        progress_overview = []
        for evaluation in evaluations_running:
            eval_runs = evaluation_runs_map.get(evaluation.id, [])
            current_model_name = ""

            if eval_runs and eval_runs[0].endpoint_id:
                endpoint = endpoints_dict.get(eval_runs[0].endpoint_id)
                if endpoint:
                    model = models_dict.get(endpoint.model_id)
                    if model:
                        current_model_name = model.name
                    else:
                        logger.warning(f"Model {endpoint.model_id} not found in database")
                        current_model_name = "Unknown Model"
                else:
                    # Log missing endpoint but don't fail
                    logger.warning(f"Endpoint {eval_runs[0].endpoint_id} not found in database")
                    current_model_name = "Unknown Model"

            # Calculate average score for THIS specific evaluation
            # Filter current_metrics to only include runs from this evaluation
            eval_run_ids = {str(run.id) for run in eval_runs}
            eval_metrics = [metric for metric in exp_data.current_metrics if metric.get("run_id") in eval_run_ids]

            # Extract unique dataset names from runs in this evaluation
            dataset_names = []
            seen_datasets = set()
            for metric in eval_metrics:
                dataset = metric.get("dataset", "")
                if dataset and dataset != "Unknown Dataset" and dataset not in seen_datasets:
                    dataset_names.append(dataset)
                    seen_datasets.add(dataset)
            current_evaluation_datasets = ", ".join(dataset_names) if dataset_names else ""

            # Filter out failed/cancelled/skipped runs and runs with score of 0 from average calculation
            excluded_statuses = {
                RunStatusEnum.FAILED.value,
                RunStatusEnum.CANCELLED.value,
                RunStatusEnum.SKIPPED.value,
            }
            valid_metrics = [
                metric
                for metric in eval_metrics
                if metric.get("status") not in excluded_statuses and metric.get("score_value", 0) > 0
            ]

            evaluation_avg_score = 0.0
            if valid_metrics:
                total_score = sum(metric["score_value"] for metric in valid_metrics)
                evaluation_avg_score = round(total_score / len(valid_metrics), 2)

            progress_overview.append(
                ProgressOverview(
                    run_id=str(evaluation.id),
                    title=f"Progress Overview of {evaluation.name}",
                    objective=evaluation.description,
                    current=None,
                    progress=ProgressInfo(percent=0, completed=0, total=0),
                    current_evaluation=current_evaluation_datasets,
                    current_model=current_model_name,
                    processing_rate_per_min=0,
                    average_score_pct=evaluation_avg_score,
                    eta_minutes=evaluation.eta_seconds // 60 if evaluation.eta_seconds else 0,
                    duration_in_seconds=evaluation.duration_in_seconds,
                    status=evaluation.status,
                    actions=None,
                )
            )

        # Final Response
        exp_data.progress_overview = progress_overview

        # Populate tag objects if tag_ids exist
        if ev.tag_ids:
            tag_service = EvalTagService(self.session)
            exp_data.tag_objects = tag_service.get_tags_by_ids(ev.tag_ids)

        return exp_data

    def update_experiment(
        self,
        ev_id: uuid.UUID,
        req: UpdateExperimentRequest,
        user_id: uuid.UUID,
    ) -> ExperimentSchema:
        """Update fields of an existing Experiment.

        Parameters:
            ev_id (uuid.UUID): ID of the experiment to update.
            req (UpdateExperimentRequest): Payload with optional name/description.
            user_id (uuid.UUID): ID of the user attempting the update.

        Returns:
            ExperimentSchema: Pydantic schema of the updated Experiment.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
            HTTPException(status_code=500): If database update fails.
        """
        ev = self.session.get(ExperimentModel, ev_id)
        if not ev or ev.created_by != user_id or ev.status == "deleted":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )
        if req.name is not None:
            ev.name = req.name
        if req.description is not None:
            ev.description = req.description
        try:
            self.session.commit()
            self.session.refresh(ev)
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update experiment",
            ) from e

        # Create experiment schema and enrich with models, traits, and status
        exp_data = ExperimentSchema.from_orm(ev)
        exp_data.models = self.get_models_for_experiment(ev.id)
        exp_data.traits = self.get_traits_for_experiment(ev.id)
        exp_data.status = self.compute_experiment_status(ev.id)
        return exp_data

    def delete_experiment(self, ev_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Soft-delete an Experiment by setting its status to 'deleted'.

        Parameters:
            ev_id (uuid.UUID): ID of the experiment to delete.
            user_id (uuid.UUID): ID of the user attempting the delete.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
            HTTPException(status_code=500): If database commit fails.
        """
        ev = self.session.get(ExperimentModel, ev_id)
        if not ev or ev.created_by != user_id or ev.status == "deleted":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )
        ev.status = "deleted"
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete experiment",
            ) from e

    def list_traits(
        self,
        offset: int = 0,
        limit: int = 10,
        name: Optional[str] = None,
        unique_id: Optional[str] = None,
    ) -> Tuple[List[TraitBasic], int]:
        """List Trait entries with optional filters and pagination.

        Parameters:
            offset (int): Number of records to skip (for pagination).
            limit (int): Maximum number of records to return.
            name (Optional[str]): Optional case-insensitive substring filter on trait name.
            unique_id (Optional[str]): Optional exact UUID filter on trait ID.

        Returns:
            Tuple[List[TraitSchema], int]: A tuple of (list of TraitSchema, total count).

        Raises:
            HTTPException(status_code=500): If database query fails.
        """
        try:
            # Only return traits that have at least one associated dataset with eval_type 'gen'
            q = (
                self.session.query(TraitModel)
                .join(PivotModel, TraitModel.id == PivotModel.trait_id)
                .join(DatasetModel, PivotModel.dataset_id == DatasetModel.id)
                .filter(DatasetModel.eval_types.op("?")("gen"))  # Filter datasets with 'gen' key in eval_types
                .distinct()
            )

            # Apply filters
            if name:
                q = q.filter(TraitModel.name.ilike(f"%{name}%"))
            if unique_id:
                try:
                    trait_uuid = uuid.UUID(unique_id)
                    q = q.filter(TraitModel.id == trait_uuid)
                except ValueError:
                    # Invalid UUID format, return empty results
                    return [], 0

            # Get total count before applying pagination
            total_count = q.count()

            # Apply pagination
            traits = q.offset(offset).limit(limit).all()

            # Convert to lightweight schema objects without datasets
            trait_schemas = []
            from budapp.eval_ops.schemas import TraitBasic

            for trait in traits:
                trait_schema = TraitBasic(
                    id=trait.id,
                    name=trait.name,
                    description=trait.description or "",
                )
                trait_schemas.append(trait_schema)

            return trait_schemas, total_count

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list traits",
            ) from e

    # ------------------------ Experiment Enhancement Methods ------------------------

    def get_models_for_experiment(self, experiment_id: uuid.UUID) -> List[ModelSummary]:
        """Get all unique models used in an experiment's runs.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.

        Returns:
            List[ModelSummary]: List of model summaries with deployment names.
        """
        try:
            # Step 1: Get all runs for this experiment
            runs = (
                self.session.query(RunModel)
                .filter(
                    RunModel.experiment_id == experiment_id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .all()
            )

            # Step 2: Collect unique endpoint_ids from runs
            endpoint_ids = list({run.endpoint_id for run in runs})
            if not endpoint_ids:
                return []

            # Step 3: Query endpoints by IDs
            endpoints = self.session.query(EndpointModel).filter(EndpointModel.id.in_(endpoint_ids)).all()
            _endpoints_dict = {endpoint.id: endpoint for endpoint in endpoints}

            # Step 4: Extract unique model_ids from endpoints
            model_ids = list({ep.model_id for ep in endpoints if ep.model_id})
            if not model_ids:
                return []

            # Step 5: Query models by IDs
            models = self.session.query(ModelTable).filter(ModelTable.id.in_(model_ids)).all()

            # Step 6: Build result with deployment names from endpoints
            result = []
            seen_model_ids = set()
            for model in models:
                if model.id not in seen_model_ids:
                    seen_model_ids.add(model.id)
                    # Find an endpoint that uses this model
                    deployment_name = None
                    for endpoint in endpoints:
                        if endpoint.model_id == model.id:
                            deployment_name = endpoint.name  # ← Using endpoint.name here
                            break

                    result.append(
                        ModelSummary(
                            id=model.id,
                            name=model.name,
                            deployment_name=deployment_name,
                        )
                    )

            return result
        except Exception as e:
            logger.error(f"Error getting models for experiment {experiment_id}: {str(e)}")
            return []

    def get_traits_for_experiment(self, experiment_id: uuid.UUID) -> List[TraitSummary]:
        """Get all unique traits associated with datasets used in an experiment's runs.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.

        Returns:
            List[TraitSummary]: List of trait summaries.
        """
        try:
            # Query for unique traits through the dataset relationships
            traits = (
                self.session.query(
                    TraitModel.id,
                    TraitModel.name,
                    TraitModel.icon,
                )
                .join(PivotModel, TraitModel.id == PivotModel.trait_id)
                .join(DatasetModel, PivotModel.dataset_id == DatasetModel.id)
                .join(
                    ExpDatasetVersion,
                    DatasetModel.id == ExpDatasetVersion.dataset_id,
                )
                .join(
                    RunModel,
                    ExpDatasetVersion.id == RunModel.dataset_version_id,
                )
                .filter(
                    RunModel.experiment_id == experiment_id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .distinct()
                .all()
            )

            return [
                TraitSummary(
                    id=trait.id,
                    name=trait.name,
                    icon=trait.icon,
                )
                for trait in traits
            ]
        except Exception as e:
            logger.error(f"Failed to get traits for experiment {experiment_id}: {e}")
            return []

    def list_experiment_models(
        self, user_id: uuid.UUID, project_id: Optional[uuid.UUID] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get unique models from user's experiments with experiment counts.

        Parameters:
            user_id (uuid.UUID): ID of the user whose experiments to query.
            project_id (Optional[uuid.UUID]): Filter by project ID.

        Returns:
            Tuple[List[Dict], int]: List of model dicts with counts and total count.
        """
        try:
            from sqlalchemy import distinct

            # Base query for user's experiments
            exp_query = self.session.query(ExperimentModel.id).filter(
                ExperimentModel.created_by == user_id,
                ExperimentModel.status != "deleted",
            )

            if project_id is not None:
                exp_query = exp_query.filter(ExperimentModel.project_id == project_id)

            experiment_ids_subquery = exp_query.subquery()

            # Query to get models with experiment counts
            # Join: Experiments -> Runs -> Endpoints -> Models
            models_query = (
                self.session.query(
                    ModelTable.id,
                    ModelTable.name,
                    func.count(distinct(RunModel.experiment_id)).label("experiment_count"),
                )
                .join(EndpointModel, ModelTable.id == EndpointModel.model_id)
                .join(RunModel, EndpointModel.id == RunModel.endpoint_id)
                .filter(
                    RunModel.experiment_id.in_(experiment_ids_subquery),
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .group_by(ModelTable.id, ModelTable.name)
                .order_by(ModelTable.name)
                .all()
            )

            # For each model, get a deployment name (any endpoint using this model)
            result = []
            for model_id, model_name, exp_count in models_query:
                # Get any endpoint name for this model
                endpoint = self.session.query(EndpointModel.name).filter(EndpointModel.model_id == model_id).first()

                result.append(
                    {
                        "id": model_id,
                        "name": model_name,
                        "deployment_name": endpoint.name if endpoint else None,
                        "experiment_count": exp_count,
                    }
                )

            return result, len(result)
        except Exception as e:
            logger.error(f"Failed to list experiment models for user {user_id}: {e}", exc_info=True)
            return [], 0

    def compute_experiment_status(self, experiment_id: uuid.UUID) -> str:
        """Compute experiment status based on all runs' statuses.

        Simplified logic:
        - If any run is RUNNING → experiment is "running"
        - If no runs exist → "no_runs"
        - Otherwise → "completed" (regardless of failures, pending, cancelled, etc.)

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.

        Returns:
            str: Computed status string (running/completed/no_runs).
        """
        try:
            # Query all non-deleted runs for the experiment
            runs = (
                self.session.query(RunModel.status)
                .filter(
                    RunModel.experiment_id == experiment_id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .all()
            )

            if not runs:
                return "no_runs"

            statuses = [run.status for run in runs]

            # Simplified status determination
            if RunStatusEnum.RUNNING.value in statuses:
                return "running"
            else:
                # Everything else (completed, failed, pending, cancelled, skipped) → "completed"
                return "completed"
        except Exception as e:
            logger.error(f"Failed to compute status for experiment {experiment_id}: {e}")
            return "unknown"

    def get_experiment_statuses_batch(self, experiment_ids: List[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Get statuses for multiple experiments in one query for optimization.

        Simplified logic:
        - If any run is RUNNING → experiment is "running"
        - If no runs exist → "no_runs"
        - Otherwise → "completed" (regardless of failures, pending, cancelled, etc.)

        Parameters:
            experiment_ids (List[uuid.UUID]): List of experiment IDs.

        Returns:
            dict[uuid.UUID, str]: Mapping of experiment_id to computed status.
        """
        try:
            # Query all runs for all experiments in one go
            runs = (
                self.session.query(RunModel.experiment_id, RunModel.status)
                .filter(
                    RunModel.experiment_id.in_(experiment_ids),
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .all()
            )

            # Group runs by experiment_id
            runs_by_experiment = {}
            for run in runs:
                if run.experiment_id not in runs_by_experiment:
                    runs_by_experiment[run.experiment_id] = []
                runs_by_experiment[run.experiment_id].append(run.status)

            # Compute status for each experiment
            result = {}
            for exp_id in experiment_ids:
                if exp_id not in runs_by_experiment:
                    result[exp_id] = "no_runs"
                else:
                    statuses = runs_by_experiment[exp_id]

                    # Simplified status determination
                    if RunStatusEnum.RUNNING.value in statuses:
                        result[exp_id] = "running"
                    else:
                        # Everything else (completed, failed, pending, cancelled, skipped) → "completed"
                        result[exp_id] = "completed"

            return result
        except Exception as e:
            logger.error(f"Failed to compute statuses for experiments: {e}")
            # Return unknown status for all experiments on error
            return dict.fromkeys(experiment_ids, "unknown")

    # ------------------------ Run Methods ------------------------

    def list_runs(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> List[EvaluationListItem]:
        """List all evaluations for a given experiment with their runs.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.
            user_id (uuid.UUID): ID of the user.

        Returns:
            List[EvaluationListItem]: List of evaluations with nested runs showing dataset scores.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
        """
        from budapp.eval_ops.schemas import RunDatasetScore

        # Verify the experiment exists and belongs to the user
        experiment = (
            self.session.query(ExperimentModel)
            .filter(
                ExperimentModel.id == experiment_id,
                ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
            )
            .first()
        )

        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        # Get all evaluations for the experiment
        evaluations = (
            self.session.query(EvaluationModel)
            .filter(EvaluationModel.experiment_id == experiment_id)
            .order_by(EvaluationModel.created_at.desc())
            .all()
        )

        evaluation_items = []

        for evaluation in evaluations:
            # Get all runs for this evaluation
            runs = self.session.query(RunModel).filter(RunModel.evaluation_id == evaluation.id).all()

            if not runs:
                continue

            # Extract model and deployment info from first run (all runs use same model)
            first_run = runs[0]
            endpoint = self.session.query(EndpointModel).filter(EndpointModel.id == first_run.endpoint_id).first()

            model_name = "Unknown Model"
            deployment_name = None
            if endpoint:
                model = self.session.query(ModelTable).filter(ModelTable.id == endpoint.model_id).first()
                model_name = model.name if model else "Unknown Model"
                deployment_name = endpoint.name

            # Batch fetch dataset versions for all runs
            dataset_version_ids = [r.dataset_version_id for r in runs]
            dataset_versions = (
                self.session.query(ExpDatasetVersion).filter(ExpDatasetVersion.id.in_(dataset_version_ids)).all()
            )
            dataset_version_map = {dv.id: dv for dv in dataset_versions}

            # Batch fetch datasets
            dataset_ids = [dv.dataset_id for dv in dataset_versions]
            datasets = self.session.query(DatasetModel).filter(DatasetModel.id.in_(dataset_ids)).all()
            dataset_map = {d.id: d for d in datasets}

            # Batch fetch metrics for all runs
            run_ids = [r.id for r in runs]
            all_metrics = self.session.query(MetricModel).filter(MetricModel.run_id.in_(run_ids)).all()
            metrics_by_run = {}
            for metric in all_metrics:
                if metric.run_id not in metrics_by_run:
                    metrics_by_run[metric.run_id] = []
                metrics_by_run[metric.run_id].append(metric)

            # Build run scores list
            run_scores = []
            for run in runs:
                # Get dataset name
                dataset_name = "Unknown Dataset"
                if run.dataset_version_id in dataset_version_map:
                    dataset_version = dataset_version_map[run.dataset_version_id]
                    if dataset_version.dataset_id in dataset_map:
                        dataset = dataset_map[dataset_version.dataset_id]
                        dataset_name = dataset.name

                # Calculate average score from metrics
                score = None
                if run.id in metrics_by_run:
                    metrics = metrics_by_run[run.id]
                    if metrics:
                        score = sum(float(m.metric_value) for m in metrics) / len(metrics)

                run_scores.append(
                    RunDatasetScore(
                        run_id=run.id,
                        dataset_name=dataset_name,
                        score=score,
                    )
                )

            # Create evaluation item with runs
            duration_minutes = evaluation.duration_in_seconds // 60 if evaluation.duration_in_seconds else 0

            evaluation_item = EvaluationListItem(
                evaluation_id=evaluation.id,
                evaluation_name=evaluation.name,
                model_name=model_name,
                deployment_name=deployment_name,
                started_date=evaluation.created_at,
                duration_minutes=duration_minutes,
                status=evaluation.status,
                runs=run_scores,
            )
            evaluation_items.append(evaluation_item)

        return evaluation_items

    def get_run_with_results(self, run_id: uuid.UUID, user_id: uuid.UUID) -> RunWithResultsSchema:
        """Get a run with its metrics and results.

        Parameters:
            run_id (uuid.UUID): ID of the run.
            user_id (uuid.UUID): ID of the user.

        Returns:
            RunWithResultsSchema: Run schema with metrics and results.

        Raises:
            HTTPException(status_code=404): If run not found or access denied.
        """
        run = self.session.get(RunModel, run_id)
        if not run or run.experiment.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found or access denied",
            )

        # Get metrics for this run
        metrics = self.session.query(MetricModel).filter(MetricModel.run_id == run_id).all()
        metrics_data = [
            {
                "metric_name": metric.metric_name,
                "mode": metric.mode,
                "metric_value": float(metric.metric_value),
            }
            for metric in metrics
        ]

        # Get raw results for this run
        raw_result = self.session.query(RawResultModel).filter(RawResultModel.run_id == run_id).first()
        raw_results_data = raw_result.preview_results if raw_result else None

        return RunWithResultsSchema(
            id=run.id,
            experiment_id=run.experiment_id,
            run_index=run.run_index,
            endpoint_id=run.endpoint_id,
            dataset_version_id=run.dataset_version_id,
            status=RunStatusEnum(run.status),
            config=run.config,
            metrics=metrics_data,
            raw_results=raw_results_data,
        )

    def get_run_with_detailed_metrics(self, run_id: uuid.UUID, user_id: uuid.UUID) -> "RunDetailedWithMetrics":
        """Get a run with complete dataset details, model details, and metrics.

        Parameters:
            run_id (uuid.UUID): ID of the run.
            user_id (uuid.UUID): ID of the user.

        Returns:
            RunDetailedWithMetrics: Run schema with complete dataset, model, and metrics information.

        Raises:
            HTTPException(status_code=404): If run not found or access denied.
        """
        from budapp.eval_ops.schemas import RunDetailedWithMetrics

        run = self.session.get(RunModel, run_id)
        if not run or run.experiment.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found or access denied",
            )

        # Get metrics for this run
        metrics = self.session.query(MetricModel).filter(MetricModel.run_id == run_id).all()
        metrics_data = [
            {
                "metric_name": metric.metric_name,
                "mode": metric.mode,
                "metric_value": float(metric.metric_value),
            }
            for metric in metrics
        ]

        # Get raw results for this run
        raw_result = self.session.query(RawResultModel).filter(RawResultModel.run_id == run_id).first()
        raw_results_data = raw_result.preview_results if raw_result else None

        # Get model details
        model_details = None
        if run.endpoint_id:
            endpoint = self.session.query(EndpointModel).filter(EndpointModel.id == run.endpoint_id).first()
            if endpoint:
                model = self.session.query(ModelTable).filter(ModelTable.id == endpoint.model_id).first()
                if model:
                    model_details = {
                        "id": str(model.id),
                        "name": model.name,
                        "display_name": model.display_name,
                        "deployment_name": endpoint.name,
                        "description": model.description,
                    }

        # Get dataset details with version information
        dataset_details = None
        if run.dataset_version_id:
            dataset_version = (
                self.session.query(ExpDatasetVersion).filter(ExpDatasetVersion.id == run.dataset_version_id).first()
            )
            if dataset_version and dataset_version.dataset:
                dataset = dataset_version.dataset

                # Get traits associated with this dataset
                traits = (
                    self.session.query(TraitModel)
                    .join(PivotModel, TraitModel.id == PivotModel.trait_id)
                    .filter(PivotModel.dataset_id == dataset.id)
                    .all()
                )

                dataset_details = {
                    "id": str(dataset.id),
                    "name": dataset.name,
                    "description": dataset.description,
                    "version": dataset_version.version,
                    "version_id": str(dataset_version.id),
                    "estimated_input_tokens": dataset.estimated_input_tokens,
                    "estimated_output_tokens": dataset.estimated_output_tokens,
                    "language": dataset.language,
                    "domains": dataset.domains,
                    "modalities": dataset.modalities,
                    "task_type": dataset.task_type,
                    "traits": [
                        {
                            "id": str(trait.id),
                            "name": trait.name,
                            "description": trait.description,
                        }
                        for trait in traits
                    ],
                }

        return RunDetailedWithMetrics(
            id=run.id,
            experiment_id=run.experiment_id,
            run_index=run.run_index,
            status=RunStatusEnum(run.status),
            config=run.config,
            model=model_details,
            dataset=dataset_details,
            metrics=metrics_data,
            raw_results=raw_results_data,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def update_run(
        self,
        run_id: uuid.UUID,
        req: UpdateRunRequest,
        user_id: uuid.UUID,
    ) -> RunSchema:
        """Update fields of an existing run.

        Parameters:
            run_id (uuid.UUID): ID of the run to update.
            req (UpdateRunRequest): Payload with optional fields to update.
            user_id (uuid.UUID): ID of the user attempting the update.

        Returns:
            RunSchema: Pydantic schema of the updated run.

        Raises:
            HTTPException(status_code=404): If run not found or access denied.
            HTTPException(status_code=500): If database update fails.
        """
        run = self.session.get(RunModel, run_id)
        if not run or run.experiment.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found or access denied",
            )

        if req.status is not None:
            run.status = req.status.value
        if req.config is not None:
            run.config = req.config

        try:
            self.session.commit()
            self.session.refresh(run)
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update run",
            ) from e
        return RunSchema.from_orm(run)

    def delete_run(self, run_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Soft-delete a run by marking its status as DELETED.

        Parameters:
            run_id (uuid.UUID): ID of the run to delete.
            user_id (uuid.UUID): ID of the user attempting the delete.

        Raises:
            HTTPException(status_code=404): If run not found or access denied.
            HTTPException(status_code=500): If database commit fails.
        """
        run = self.session.get(RunModel, run_id)
        if not run or run.experiment.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found or access denied",
            )
        run.status = RunStatusEnum.DELETED.value
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete run",
            ) from e

    # ------------------------ Dataset Methods (Keep existing) ------------------------

    def get_dataset_by_id(self, dataset_id: uuid.UUID) -> DatasetSchema:
        """Get a dataset by ID with associated traits.

        Parameters:
            dataset_id (uuid.UUID): ID of the dataset to retrieve.

        Returns:
            DatasetSchema: Pydantic schema of the dataset with traits.

        Raises:
            HTTPException(status_code=404): If dataset not found.
            HTTPException(status_code=500): If database query fails.
        """
        try:
            # Get the dataset
            dataset = self.session.get(DatasetModel, dataset_id)
            if not dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dataset not found",
                )

            # Get associated traits through pivot table
            traits_query = (
                self.session.query(TraitModel)
                .join(PivotModel, TraitModel.id == PivotModel.trait_id)
                .filter(PivotModel.dataset_id == dataset_id)
                .all()
            )

            # Convert traits to schema
            from budapp.eval_ops.schemas import DatasetBasic

            traits = [
                TraitSchema(
                    id=trait.id,
                    name=trait.name,
                    description=trait.description or "",
                    category="",
                    exps_ids=[],
                    datasets=[
                        DatasetBasic(
                            id=dataset.id,
                            name=dataset.name,
                            description=dataset.description,
                            estimated_input_tokens=dataset.estimated_input_tokens,
                            estimated_output_tokens=dataset.estimated_output_tokens,
                            modalities=dataset.modalities,
                            sample_questions_answers=dataset.sample_questions_answers,
                            advantages_disadvantages=dataset.advantages_disadvantages,
                        )
                    ],  # This trait is associated with the current dataset
                )
                for trait in traits_query
            ]

            # Create dataset schema with traits
            dataset_schema = DatasetSchema(
                id=dataset.id,
                name=dataset.name,
                description=dataset.description,
                meta_links=dataset.meta_links,
                config_validation_schema=dataset.config_validation_schema,
                estimated_input_tokens=dataset.estimated_input_tokens,
                estimated_output_tokens=dataset.estimated_output_tokens,
                language=dataset.language,
                domains=dataset.domains,
                concepts=dataset.concepts,
                humans_vs_llm_qualifications=dataset.humans_vs_llm_qualifications,
                task_type=dataset.task_type,
                modalities=dataset.modalities,
                sample_questions_answers=dataset.sample_questions_answers,
                advantages_disadvantages=dataset.advantages_disadvantages,
                eval_types=dataset.eval_types,
                why_run_this_eval=dataset.why_run_this_eval,
                what_to_expect=dataset.what_to_expect,
                additional_info=dataset.additional_info,
                metrics=dataset.metrics,
                evaluator=dataset.evaluator,
                traits=traits,
            )

            return dataset_schema

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get dataset",
            ) from e

    def list_datasets(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[DatasetFilter] = None,
    ) -> Tuple[List[DatasetSchema], int]:
        """List datasets with optional filtering and pagination.

        Parameters:
            offset (int): Number of records to skip (for pagination).
            limit (int): Maximum number of records to return.
            filters (Optional[DatasetFilter]): Filter parameters.

        Returns:
            Tuple[List[DatasetSchema], int]: A tuple of (list of DatasetSchema, total count).

        Raises:
            HTTPException(status_code=500): If database query fails.
        """
        try:
            q = self.session.query(DatasetModel)

            # Apply filters
            if filters:
                if filters.name:
                    # Search in both name and description fields
                    q = q.filter(
                        or_(
                            DatasetModel.name.ilike(f"%{filters.name}%"),
                            DatasetModel.description.ilike(f"%{filters.name}%"),
                        )
                    )
                if filters.modalities:
                    # Filter by modalities (JSONB contains any of the specified modalities)
                    for modality in filters.modalities:
                        q = q.filter(DatasetModel.modalities.contains([modality]))
                if filters.language:
                    # Filter by language (JSONB contains any of the specified languages)
                    for lang in filters.language:
                        q = q.filter(DatasetModel.language.contains([lang]))
                if filters.domains:
                    # Filter by domains (JSONB contains any of the specified domains)
                    for domain in filters.domains:
                        q = q.filter(DatasetModel.domains.contains([domain]))
                if filters.trait_ids:
                    # Filter by trait UUIDs through the many-to-many relationship
                    q = q.join(DatasetModel.traits).filter(TraitModel.id.in_(filters.trait_ids))

                # Always apply has_gen_eval_type filter (defaults to True in route)
                if hasattr(filters, "has_gen_eval_type") and filters.has_gen_eval_type is not None:
                    # Filter by datasets that have 'gen' key in eval_types JSONB field
                    if filters.has_gen_eval_type:
                        q = q.filter(DatasetModel.eval_types.has_key("gen"))
                    else:
                        # Filter for datasets WITHOUT 'gen' key
                        q = q.filter(~DatasetModel.eval_types.has_key("gen"))

            # Get total count before applying pagination
            total_count = q.count()

            # Apply pagination and get results
            datasets = q.offset(offset).limit(limit).all()

            # For each dataset, get associated traits
            dataset_schemas = []
            for dataset in datasets:
                # Get traits associated with this dataset
                traits_query = (
                    self.session.query(TraitModel)
                    .join(PivotModel, TraitModel.id == PivotModel.trait_id)
                    .filter(PivotModel.dataset_id == dataset.id)
                    .all()
                )

                # Convert traits to schema (simplified for list view)
                traits = [
                    TraitSchema(
                        id=trait.id,
                        name=trait.name,
                        description=trait.description or "",
                        category="",
                        exps_ids=[],
                        datasets=[],  # Don't include datasets in list view to avoid circular references
                    )
                    for trait in traits_query
                ]

                dataset_schema = DatasetSchema(
                    id=dataset.id,
                    name=dataset.name,
                    description=dataset.description,
                    meta_links=dataset.meta_links,
                    config_validation_schema=dataset.config_validation_schema,
                    estimated_input_tokens=dataset.estimated_input_tokens,
                    estimated_output_tokens=dataset.estimated_output_tokens,
                    language=dataset.language,
                    domains=dataset.domains,
                    concepts=dataset.concepts,
                    humans_vs_llm_qualifications=dataset.humans_vs_llm_qualifications,
                    task_type=dataset.task_type,
                    modalities=dataset.modalities,
                    # sample_questions_answers=dataset.sample_questions_answers,
                    advantages_disadvantages=dataset.advantages_disadvantages,
                    eval_types=dataset.eval_types,
                    why_run_this_eval=dataset.why_run_this_eval,
                    what_to_expect=dataset.what_to_expect,
                    additional_info=dataset.additional_info,
                    metrics=dataset.metrics,
                    evaluator=dataset.evaluator,
                    traits=traits,
                )
                dataset_schemas.append(dataset_schema)

            return dataset_schemas, total_count

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list datasets",
            ) from e

    def create_dataset(self, req: CreateDatasetRequest) -> DatasetSchema:
        """Create a new dataset with traits.

        Parameters:
            req (CreateDatasetRequest): Payload containing dataset information and trait associations.

        Returns:
            DatasetSchema: Pydantic schema of the created dataset with traits.

        Raises:
            HTTPException(status_code=400): If validation fails.
            HTTPException(status_code=500): If database insertion fails.
        """
        try:
            # Create the dataset
            dataset = DatasetModel(
                name=req.name,
                description=req.description,
                meta_links=req.meta_links,
                config_validation_schema=req.config_validation_schema,
                estimated_input_tokens=req.estimated_input_tokens,
                estimated_output_tokens=req.estimated_output_tokens,
                language=req.language,
                domains=req.domains,
                concepts=req.concepts,
                humans_vs_llm_qualifications=req.humans_vs_llm_qualifications,
                task_type=req.task_type,
                modalities=req.modalities,
                sample_questions_answers=req.sample_questions_answers,
                advantages_disadvantages=req.advantages_disadvantages,
                metrics=req.metrics,
                evaluator=req.evaluator,
            )
            self.session.add(dataset)
            self.session.flush()  # Get the dataset ID

            # Create trait associations
            if req.trait_ids:
                for trait_id in req.trait_ids:
                    # Verify trait exists
                    trait = self.session.get(TraitModel, trait_id)
                    if not trait:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Trait with ID {trait_id} not found",
                        )

                    pivot = PivotModel(trait_id=trait_id, dataset_id=dataset.id)
                    self.session.add(pivot)

            self.session.commit()
            self.session.refresh(dataset)

            # Return the created dataset with traits
            return self.get_dataset_by_id(dataset.id)

        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            logger.warning(f"Failed to create dataset: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create dataset",
            ) from e

    def update_dataset(self, dataset_id: uuid.UUID, req: UpdateDatasetRequest) -> DatasetSchema:
        """Update an existing dataset and its traits.

        Parameters:
            dataset_id (uuid.UUID): ID of the dataset to update.
            req (UpdateDatasetRequest): Payload with optional dataset fields and trait associations.

        Returns:
            DatasetSchema: Pydantic schema of the updated dataset with traits.

        Raises:
            HTTPException(status_code=404): If dataset not found.
            HTTPException(status_code=400): If validation fails.
            HTTPException(status_code=500): If database update fails.
        """
        try:
            dataset = self.session.get(DatasetModel, dataset_id)
            if not dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dataset not found",
                )

            # Update dataset fields
            if req.name is not None:
                dataset.name = req.name
            if req.description is not None:
                dataset.description = req.description
            if req.meta_links is not None:
                dataset.meta_links = req.meta_links
            if req.config_validation_schema is not None:
                dataset.config_validation_schema = req.config_validation_schema
            if req.estimated_input_tokens is not None:
                dataset.estimated_input_tokens = req.estimated_input_tokens
            if req.estimated_output_tokens is not None:
                dataset.estimated_output_tokens = req.estimated_output_tokens
            if req.language is not None:
                dataset.language = req.language
            if req.domains is not None:
                dataset.domains = req.domains
            if req.concepts is not None:
                dataset.concepts = req.concepts
            if req.humans_vs_llm_qualifications is not None:
                dataset.humans_vs_llm_qualifications = req.humans_vs_llm_qualifications
            if req.task_type is not None:
                dataset.task_type = req.task_type
            if req.modalities is not None:
                dataset.modalities = req.modalities
            if req.sample_questions_answers is not None:
                dataset.sample_questions_answers = req.sample_questions_answers
            if req.advantages_disadvantages is not None:
                dataset.advantages_disadvantages = req.advantages_disadvantages
            if "metrics" in req.model_fields_set:
                dataset.metrics = req.metrics
            if "evaluator" in req.model_fields_set:
                dataset.evaluator = req.evaluator

            # Update trait associations if provided
            if req.trait_ids is not None:
                # Remove existing associations
                self.session.query(PivotModel).filter(PivotModel.dataset_id == dataset_id).delete()

                # Add new associations
                for trait_id in req.trait_ids:
                    # Verify trait exists
                    trait = self.session.get(TraitModel, trait_id)
                    if not trait:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Trait with ID {trait_id} not found",
                        )

                    pivot = PivotModel(trait_id=trait_id, dataset_id=dataset_id)
                    self.session.add(pivot)

            self.session.commit()
            self.session.refresh(dataset)

            # Return the updated dataset with traits
            return self.get_dataset_by_id(dataset_id)

        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            logger.warning(f"Failed to update dataset: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update dataset",
            ) from e

    def delete_dataset(self, dataset_id: uuid.UUID) -> None:
        """Delete a dataset and its trait associations.

        Parameters:
            dataset_id (uuid.UUID): ID of the dataset to delete.

        Raises:
            HTTPException(status_code=404): If dataset not found.
            HTTPException(status_code=500): If database deletion fails.
        """
        try:
            dataset = self.session.get(DatasetModel, dataset_id)
            if not dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dataset not found",
                )

            # Delete trait associations first
            self.session.query(PivotModel).filter(PivotModel.dataset_id == dataset_id).delete()

            # Delete the dataset
            self.session.delete(dataset)
            self.session.commit()

        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete dataset",
            ) from e

    def get_runs_history(
        self,
        experiment_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        sort_field: str = "started_at",
        sort_direction: str = "desc",
    ):
        """Get run history for an experiment with pagination.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.
            user_id (uuid.UUID): ID of the user.
            page (int): Page number (default: 1).
            page_size (int): Page size (default: 50).
            sort_field (str): Field to sort by (default: "started_at").
            sort_direction (str): Sort direction (default: "desc").

        Returns:
            RunHistoryData: Paginated run history data.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
        """
        from datetime import datetime

        from budapp.eval_ops.schemas import (
            BenchmarkScore,
            RunHistoryData,
            RunHistoryItem,
            SortInfo,
        )

        # Verify experiment exists and user has access
        experiment = self.session.get(ExperimentModel, experiment_id)
        if not experiment or experiment.created_by != user_id or experiment.status == "deleted":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        # Return dummy data for now
        import uuid as uuid_lib

        dummy_runs = []
        for _i in range(10):  # Create 10 dummy runs
            dummy_runs.append(
                RunHistoryItem(
                    run_id=str(uuid_lib.uuid4()),  # Generate actual UUID
                    model="model_name",
                    status="completed",
                    started_at=datetime.fromisoformat("2024-01-13T00:00:00Z"),
                    duration_seconds=4920,
                    benchmarks=[
                        BenchmarkScore(name="Benchmark", score="Score"),
                        BenchmarkScore(name="Benchmark", score="Score"),
                    ],
                )
            )

        # Return only the requested page
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_runs = dummy_runs[start_idx:end_idx] if start_idx < len(dummy_runs) else []

        return RunHistoryData(
            total=10,
            items=paginated_runs,
            sort=SortInfo(field=sort_field, direction=sort_direction),
            page=page,
            page_size=page_size,
        )

    def get_experiment_summary(self, experiment_id: uuid.UUID, user_id: uuid.UUID):
        """Get summary statistics for an experiment.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.
            user_id (uuid.UUID): ID of the user.

        Returns:
            ExperimentSummary: Summary statistics including evaluation counts and total duration.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
        """
        from budapp.eval_ops.schemas import ExperimentSummary

        # Verify experiment exists and user has access
        experiment = self.session.get(ExperimentModel, experiment_id)
        if not experiment or experiment.status == ExperimentStatusEnum.DELETED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        # Efficiently count evaluations by status in a single query using database-level aggregation
        evaluation_stats = (
            self.session.query(
                func.count(EvaluationModel.id).label("total"),
                func.sum(case((EvaluationModel.status == EvaluationStatusEnum.COMPLETED.value, 1), else_=0)).label(
                    "completed"
                ),
                func.sum(case((EvaluationModel.status == EvaluationStatusEnum.FAILED.value, 1), else_=0)).label(
                    "failed"
                ),
                func.sum(case((EvaluationModel.status == EvaluationStatusEnum.PENDING.value, 1), else_=0)).label(
                    "pending"
                ),
                func.sum(case((EvaluationModel.status == EvaluationStatusEnum.RUNNING.value, 1), else_=0)).label(
                    "running"
                ),
                func.coalesce(func.sum(EvaluationModel.duration_in_seconds), 0).label("total_duration"),
            )
            .filter(EvaluationModel.experiment_id == experiment_id)
            .one()
        )

        return ExperimentSummary(
            total_evaluations=evaluation_stats.total or 0,
            total_duration_seconds=int(evaluation_stats.total_duration),
            completed_evaluations=evaluation_stats.completed or 0,
            failed_evaluations=evaluation_stats.failed or 0,
            pending_evaluations=evaluation_stats.pending or 0,
            running_evaluations=evaluation_stats.running or 0,
        )

    # ------------------------ Experiment Evaluations Methods ------------------------

    async def get_experiment_evaluations(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """Get all evaluations for an experiment with model, trait, dataset details and scores.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.
            user_id (uuid.UUID): ID of the user.

        Returns:
            dict: Experiment with all evaluations and their details.

        Raises:
            HTTPException: If experiment not found or access denied.
        """
        # Get experiment
        experiment = self.session.get(ExperimentModel, experiment_id)
        if not experiment or experiment.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        # Get all runs for the experiment
        runs = (
            self.session.query(RunModel)
            .filter(
                RunModel.experiment_id == experiment_id,
                RunModel.status != RunStatusEnum.DELETED.value,
            )
            .order_by(RunModel.run_index)
            .all()
        )

        # Fetch evaluation details for each run
        evaluations = []
        evaluation_job_ids = []

        for run in runs:
            # Get model details
            model = self.get_endpoint_model_details(run.endpoint_id)

            # Get traits with datasets
            traits = self.get_traits_with_datasets_for_run(run.dataset_version_id)

            # Extract evaluation job ID if exists (from config or metrics)
            eval_job_id = run.config.get("evaluation_job_id") if run.config else None
            if eval_job_id:
                evaluation_job_ids.append((run.id, eval_job_id))

            evaluations.append(
                {
                    "run": run,
                    "model": model,
                    "traits": traits,
                    "evaluation_job_id": eval_job_id,
                }
            )

        # Fetch scores from budeval in parallel
        scores_map = {}
        if evaluation_job_ids:
            from budapp.eval_ops.budeval_client import BudEvalClient

            client = BudEvalClient()

            # Create a list of evaluation IDs
            eval_ids = [job_id for _, job_id in evaluation_job_ids]
            scores_map = await client.fetch_scores_batch(eval_ids)

        # Build response
        from budapp.eval_ops.schemas import (
            DatasetInfo,
            EvaluationScore,
            ModelDetail,
            RunWithEvaluations,
            TraitWithDatasets,
        )

        evaluation_results = []
        for eval_data in evaluations:
            run = eval_data["run"]
            eval_job_id = eval_data["evaluation_job_id"]

            # Get scores if available
            scores = None
            if eval_job_id and eval_job_id in scores_map:
                score_data = scores_map[eval_job_id]
                if score_data:
                    scores = EvaluationScore(
                        status="completed" if score_data.get("overall_accuracy") is not None else "running",
                        overall_accuracy=score_data.get("overall_accuracy"),
                        datasets=score_data.get("datasets", []),
                    )

            evaluation_results.append(
                RunWithEvaluations(
                    run_id=run.id,
                    run_index=run.run_index,
                    status=run.status,
                    model=eval_data["model"],
                    traits=eval_data["traits"],
                    evaluation_job_id=eval_job_id,
                    scores=scores,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                )
            )

        return {
            "experiment": ExperimentSchema.model_validate(experiment),
            "evaluations": evaluation_results,
        }

    async def get_all_evaluations(
        self,
        user_id: uuid.UUID,
        model_id: Optional[uuid.UUID] = None,
        endpoint_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Get all evaluations for a user with optional model_id and endpoint_id filters.

        Parameters:
            user_id (uuid.UUID): ID of the user.
            model_id (Optional[uuid.UUID]): Optional model ID to filter evaluations.
            endpoint_id (Optional[uuid.UUID]): Optional endpoint ID to filter evaluations.
            page (int): Page number for pagination (1-indexed).
            page_size (int): Number of items per page.

        Returns:
            dict: Paginated evaluations with their details.

        Raises:
            HTTPException: If access denied or error occurs.
        """
        from budapp.eval_ops.schemas import (
            AllEvaluationsItem,
            AllEvaluationsRunItem,
            EvaluationScore,
            ModelDetail,
        )

        # Build base query for evaluations
        query = (
            self.session.query(EvaluationModel)
            .join(ExperimentModel, EvaluationModel.experiment_id == ExperimentModel.id)
            .filter(
                ExperimentModel.created_by == user_id,
                EvaluationModel.status != EvaluationStatusEnum.PENDING.value,
            )
        )

        # Apply endpoint_id filter if provided (takes precedence over model_id)
        if endpoint_id:
            # Get evaluation IDs that have runs with this endpoint
            evaluation_ids_with_endpoint = (
                self.session.query(RunModel.evaluation_id)
                .filter(
                    RunModel.endpoint_id == endpoint_id,
                    RunModel.evaluation_id.isnot(None),
                )
                .distinct()
                .subquery()
            )

            query = query.filter(EvaluationModel.id.in_(evaluation_ids_with_endpoint))

        # Apply model_id filter if provided (only if endpoint_id is not provided)
        elif model_id:
            # Get all endpoint_ids that use this model
            endpoint_ids_with_model = (
                self.session.query(EndpointModel.id).filter(EndpointModel.model_id == model_id).subquery()
            )

            # Get evaluation IDs that have runs with these endpoints
            evaluation_ids_with_model = (
                self.session.query(RunModel.evaluation_id)
                .filter(
                    RunModel.endpoint_id.in_(endpoint_ids_with_model),
                    RunModel.evaluation_id.isnot(None),
                )
                .distinct()
                .subquery()
            )

            query = query.filter(EvaluationModel.id.in_(evaluation_ids_with_model))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        evaluations_db = query.order_by(EvaluationModel.created_at.desc()).offset(offset).limit(page_size).all()

        # Collect evaluation job IDs for batch score fetching
        evaluation_job_ids = []
        for eval_db in evaluations_db:
            # Get runs for this evaluation
            runs = (
                self.session.query(RunModel)
                .filter(
                    RunModel.evaluation_id == eval_db.id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .all()
            )
            for run in runs:
                eval_job_id = run.config.get("evaluation_job_id") if run.config else None
                if eval_job_id:
                    evaluation_job_ids.append((eval_db.id, run.id, eval_job_id))

        # Fetch scores from BudEval in parallel
        scores_map = {}
        if evaluation_job_ids:
            from budapp.eval_ops.budeval_client import BudEvalClient

            client = BudEvalClient()
            eval_ids = list({job_id for _, _, job_id in evaluation_job_ids})
            scores_map = await client.fetch_scores_batch(eval_ids)

        # Build response
        evaluation_results = []
        for eval_db in evaluations_db:
            # Get experiment
            experiment = self.session.get(ExperimentModel, eval_db.experiment_id)

            # Get runs for this evaluation
            runs = (
                self.session.query(RunModel)
                .filter(
                    RunModel.evaluation_id == eval_db.id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .order_by(RunModel.run_index)
                .all()
            )

            # Get model details from the first run
            model_detail = ModelDetail(id=uuid.uuid4(), name="Unknown Model", deployment_name=None)
            traits_list = []

            if runs:
                first_run = runs[0]
                model_detail = self.get_endpoint_model_details(first_run.endpoint_id)
                traits_list = self.get_traits_with_datasets_for_run(first_run.dataset_version_id)

            # Build run items
            run_items = []
            scores = None
            for run in runs:
                eval_job_id = run.config.get("evaluation_job_id") if run.config else None

                run_items.append(
                    AllEvaluationsRunItem(
                        run_id=run.id,
                        run_index=run.run_index,
                        status=run.status,
                        evaluation_job_id=eval_job_id,
                        created_at=run.created_at,
                    )
                )

                # Get scores from first run with scores
                if not scores and eval_job_id and eval_job_id in scores_map:
                    score_data = scores_map[eval_job_id]
                    if score_data:
                        scores = EvaluationScore(
                            status="completed" if score_data.get("overall_accuracy") is not None else "running",
                            overall_accuracy=score_data.get("overall_accuracy"),
                            datasets=score_data.get("datasets", []),
                        )

            evaluation_results.append(
                AllEvaluationsItem(
                    evaluation_id=eval_db.id,
                    evaluation_name=eval_db.name,
                    experiment_id=eval_db.experiment_id,
                    experiment_name=experiment.name if experiment else "Unknown Experiment",
                    model=model_detail,
                    traits=traits_list,
                    status=eval_db.status,
                    scores=scores,
                    runs=run_items,
                    created_at=eval_db.created_at,
                    updated_at=eval_db.updated_at,
                    duration_in_seconds=eval_db.duration_in_seconds,
                )
            )

        return {
            "evaluations": evaluation_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    def get_endpoint_model_details(self, endpoint_id: uuid.UUID) -> "ModelDetail":
        """Get detailed model information from endpoint.

        Parameters:
            endpoint_id (uuid.UUID): ID of the endpoint.

        Returns:
            ModelDetail: Model details with deployment information.
        """
        from budapp.endpoint_ops.models import Endpoint as EndpointModel
        from budapp.eval_ops.schemas import ModelDetail

        # Get endpoint first
        endpoint = self.session.query(EndpointModel).filter(EndpointModel.id == endpoint_id).first()

        if not endpoint:
            # Return placeholder if endpoint not found
            return ModelDetail(id=endpoint_id, name="Unknown Model", deployment_name=None)

        # Get model from endpoint
        model = self.session.query(ModelTable).filter(ModelTable.id == endpoint.model_id).first()

        if not model:
            return ModelDetail(
                id=endpoint_id,
                name="Unknown Model",
                deployment_name=endpoint.name,
            )

        return ModelDetail(
            id=model.id,
            name=model.name,
            deployment_name=endpoint.name,
        )

    async def get_first_active_project(self) -> uuid.UUID:
        """Get the first active project in the system.

        This is used to generate temporary credentials for evaluation runs.

        Returns:
            UUID of the first active project

        Raises:
            ClientException: If no active projects exist in the system
        """
        from sqlalchemy import select

        from budapp.project_ops.models import Project as ProjectModel

        # Get first active project ordered by creation date (async query)
        stmt = (
            select(ProjectModel)
            .filter(ProjectModel.status == ProjectStatusEnum.ACTIVE)
            .order_by(ProjectModel.created_at.asc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        project = result.scalars().first()

        if not project:
            raise ClientException("No active project found in the system. Please create a project first.")

        logger.info(f"Using project '{project.name}' (ID: {project.id}) for evaluation credential")

        return project.id

    async def _generate_temporary_evaluation_key(
        self,
        project_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> str:
        """Generate temporary API key for evaluation (no DB storage).

        The key is only cached in Redis with 24-hour TTL for automatic cleanup.

        Args:
            project_id: Project ID to associate the credential with
            experiment_id: Experiment ID for logging purposes

        Returns:
            The generated API key string

        Raises:
            Exception: If credential generation or cache update fails
        """
        from budapp.credential_ops.helpers import generate_secure_api_key
        from budapp.credential_ops.services import CredentialService

        # Generate secure API key (format: bud_client_<random>)
        api_key = generate_secure_api_key("admin_app")

        # Set 24-hour expiry
        expiry = datetime.now() + timedelta(hours=24)

        # Update Redis cache directly (no DB storage)
        await CredentialService(self.session).update_proxy_cache(
            project_id=project_id,
            api_key=api_key,
            expiry=expiry,
        )

        logger.info(
            f"Generated temporary evaluation key for experiment {experiment_id}, valid until {expiry.isoformat()}"
        )

        return api_key

    def get_traits_with_datasets_for_run(self, dataset_version_id: uuid.UUID) -> List["TraitWithDatasets"]:
        """Get traits with their datasets for a specific run.

        Parameters:
            dataset_version_id (uuid.UUID): ID of the dataset version used in the run.

        Returns:
            List[TraitWithDatasets]: List of traits with their associated datasets.
        """
        from budapp.eval_ops.schemas import DatasetInfo, TraitWithDatasets

        # Get the dataset version
        dataset_version = self.session.get(ExpDatasetVersion, dataset_version_id)
        if not dataset_version:
            return []

        # Get the dataset
        dataset = dataset_version.dataset
        if not dataset:
            return []

        # Get traits associated with this dataset through pivot table
        traits_query = (
            self.session.query(TraitModel)
            .join(PivotModel, TraitModel.id == PivotModel.trait_id)
            .filter(PivotModel.dataset_id == dataset.id)
            .all()
        )

        # Build trait with datasets response
        traits_with_datasets = []
        for trait in traits_query:
            # Get all datasets for this trait
            datasets_for_trait = (
                self.session.query(DatasetModel)
                .join(PivotModel, DatasetModel.id == PivotModel.dataset_id)
                .filter(PivotModel.trait_id == trait.id)
                .all()
            )

            # Convert datasets to DatasetInfo
            dataset_infos = []
            for ds in datasets_for_trait:
                # Get the version for this dataset
                version = self.session.query(ExpDatasetVersion).filter(ExpDatasetVersion.dataset_id == ds.id).first()

                dataset_infos.append(
                    DatasetInfo(
                        id=ds.id,
                        name=ds.name,
                        version=version.version if version else "1.0",
                        description=ds.description,
                    )
                )

            traits_with_datasets.append(
                TraitWithDatasets(
                    id=trait.id,
                    name=trait.name,
                    icon=trait.icon,
                    datasets=dataset_infos,
                )
            )

        return traits_with_datasets

    def _get_current_metrics(self, experiment_id: uuid.UUID) -> List["CurrentMetric"]:
        """Get current metrics for an experiment based on real run data.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.

        Returns:
            List[CurrentMetric]: List of current metrics derived from experiment runs.
        """
        try:
            from budapp.eval_ops.schemas import CurrentMetric

            # Query active runs for the experiment - use created_at for ordering to avoid NULL issues
            runs = (
                self.session.query(RunModel)
                .filter(
                    RunModel.experiment_id == experiment_id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .order_by(RunModel.created_at.desc())  # Use created_at instead of updated_at
                .all()
            )

            current_metrics = []
            for run in runs:
                try:
                    # Get model details with validation
                    model_detail = self.get_endpoint_model_details(run.endpoint_id)
                    if not model_detail or not hasattr(model_detail, "name") or not model_detail.name:
                        logger.warning(f"Invalid model details for run {run.id}, skipping")
                        continue

                    # Get dataset information with validation
                    dataset_version = self.session.get(ExpDatasetVersion, run.dataset_version_id)
                    dataset_name = "Unknown Dataset"
                    if dataset_version and dataset_version.dataset and dataset_version.dataset.name:
                        dataset_name = dataset_version.dataset.name

                    # Get traits for this run's dataset with validation
                    traits_with_datasets = self.get_traits_with_datasets_for_run(run.dataset_version_id)
                    trait_names = []
                    if traits_with_datasets:
                        trait_names = [
                            trait.name
                            for trait in traits_with_datasets
                            if trait and hasattr(trait, "name") and trait.name
                        ]

                    # Validate required fields before creating CurrentMetric
                    model_name = model_detail.name if model_detail.name else "Unknown Model"
                    deployment_name = (
                        model_detail.deployment_name
                        if hasattr(model_detail, "deployment_name") and model_detail.deployment_name
                        else model_name
                    )
                    evaluation_name = f"{model_name} on {dataset_name}"
                    last_run_time = run.updated_at or run.created_at

                    # Create CurrentMetric object with validated data
                    current_metric = CurrentMetric(
                        evaluation=evaluation_name,
                        dataset=dataset_name,
                        deployment_name=deployment_name,
                        judge=None,  # Judge models not available yet
                        traits=trait_names,
                        last_run_at=last_run_time,
                        run_id=str(run.id),
                    )

                    current_metrics.append(current_metric)

                except Exception as e:
                    logger.error(
                        f"Failed to process run {run.id} for current_metrics: {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(f"Generated {len(current_metrics)} current_metrics for experiment {experiment_id}")
            return current_metrics

        except Exception as e:
            logger.error(
                f"Failed to get current_metrics for experiment {experiment_id}: {e}",
                exc_info=True,
            )
            return []  # Return empty list instead of failing

    def get_dataset_scores(
        self,
        dataset_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
        """Get all model scores for a specific dataset.

        This method retrieves all completed evaluation runs for a dataset, groups them by model,
        averages the metrics (non-zero values only), and ranks models by accuracy.

        Parameters:
            dataset_id (uuid.UUID): ID of the dataset to get scores for.
            user_id (uuid.UUID): ID of the requesting user (for access control).
            page (int): Page number for pagination (default: 1).
            limit (int): Items per page (default: 50, max: 100).

        Returns:
            Tuple containing:
                - List[Dict]: List of model scores with rankings
                - int: Total count of models
                - Dict: Dataset information (id, name)

        Raises:
            HTTPException(status_code=404): If dataset not found.
            HTTPException(status_code=500): If database query fails.
        """
        try:
            # Verify dataset exists
            dataset = self.session.get(DatasetModel, dataset_id)
            if not dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dataset with ID {dataset_id} not found",
                )

            # Get all dataset versions for this dataset
            dataset_versions = (
                self.session.query(ExpDatasetVersion).filter(ExpDatasetVersion.dataset_id == dataset_id).all()
            )

            if not dataset_versions:
                # No versions means no runs, return empty result
                return [], 0, {"id": dataset.id, "name": dataset.name}

            dataset_version_ids = [dv.id for dv in dataset_versions]

            # Query all completed runs for this dataset's versions
            # Join with Endpoint, Model, and Experiment for access control and model info
            runs_query = (
                self.session.query(
                    RunModel.id.label("run_id"),
                    RunModel.created_at,
                    RunModel.endpoint_id,
                    EndpointModel.name.label("endpoint_name"),
                    ModelTable.id.label("model_id"),
                    ModelTable.name.label("model_name"),
                    ModelTable.icon.label("model_icon"),
                    ExperimentModel.id.label("experiment_id"),
                )
                .join(EndpointModel, RunModel.endpoint_id == EndpointModel.id)
                .join(ModelTable, EndpointModel.model_id == ModelTable.id)
                .join(ExperimentModel, RunModel.experiment_id == ExperimentModel.id)
                .filter(
                    RunModel.dataset_version_id.in_(dataset_version_ids),
                    RunModel.status == RunStatusEnum.COMPLETED.value,
                    ExperimentModel.created_by == user_id,  # Access control
                    ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
                )
                .all()
            )

            if not runs_query:
                # No completed runs for this user
                return [], 0, {"id": dataset.id, "name": dataset.name}

            # Group runs by model_id
            models_data: Dict[uuid.UUID, Dict[str, Any]] = {}

            for run_row in runs_query:
                model_id = run_row.model_id

                if model_id not in models_data:
                    models_data[model_id] = {
                        "model_id": model_id,
                        "model_name": run_row.model_name,
                        "model_icon": run_row.model_icon,
                        "endpoint_name": run_row.endpoint_name,
                        "run_ids": [],
                        "latest_created_at": run_row.created_at,
                        "metrics_by_name": {},  # {metric_name: [values]}
                    }
                else:
                    # Track latest created_at
                    if run_row.created_at > models_data[model_id]["latest_created_at"]:
                        models_data[model_id]["latest_created_at"] = run_row.created_at
                        models_data[model_id]["endpoint_name"] = run_row.endpoint_name

                models_data[model_id]["run_ids"].append(run_row.run_id)

            # Fetch all metrics for all runs
            all_run_ids = [run_row.run_id for run_row in runs_query]
            metrics_query = self.session.query(MetricModel).filter(MetricModel.run_id.in_(all_run_ids)).all()

            # Group metrics by run_id, then aggregate by model
            metrics_by_run: Dict[uuid.UUID, List[MetricModel]] = {}
            for metric in metrics_query:
                if metric.run_id not in metrics_by_run:
                    metrics_by_run[metric.run_id] = []
                metrics_by_run[metric.run_id].append(metric)

            # Aggregate metrics for each model
            for _model_id, model_info in models_data.items():
                for run_id in model_info["run_ids"]:
                    if run_id in metrics_by_run:
                        for metric in metrics_by_run[run_id]:
                            metric_name = metric.metric_name

                            if metric_name not in model_info["metrics_by_name"]:
                                model_info["metrics_by_name"][metric_name] = []

                            # Only include non-zero values for averaging
                            if metric.metric_value and metric.metric_value > 0:
                                model_info["metrics_by_name"][metric_name].append(float(metric.metric_value))

            # Calculate averaged metrics and extract accuracy
            model_scores = []
            for model_id, model_info in models_data.items():
                averaged_metrics = []
                accuracy_value = None

                for metric_name, values in model_info["metrics_by_name"].items():
                    if values:  # Only if we have non-zero values
                        avg_value = sum(values) / len(values)
                        averaged_metrics.append(
                            {
                                "metric_name": metric_name,
                                "metric_value": round(avg_value, 2),
                            }
                        )

                        # Extract accuracy for ranking
                        if metric_name.lower() == "accuracy":
                            accuracy_value = avg_value

                model_scores.append(
                    {
                        "model_id": model_id,
                        "model_name": model_info["model_name"],
                        "model_icon": model_info["model_icon"],
                        "endpoint_name": model_info["endpoint_name"],
                        "accuracy": accuracy_value,
                        "metrics": averaged_metrics,
                        "num_runs": len(model_info["run_ids"]),
                        "created_at": model_info["latest_created_at"],
                    }
                )

            # Sort by accuracy (nulls last)
            model_scores.sort(key=lambda x: (x["accuracy"] is None, -x["accuracy"] if x["accuracy"] else 0))

            # Assign ranks
            for rank, model_score in enumerate(model_scores, start=1):
                model_score["rank"] = rank

            # Calculate pagination
            total_count = len(model_scores)
            offset = (page - 1) * limit
            paginated_scores = model_scores[offset : offset + limit]

            dataset_info = {
                "id": dataset.id,
                "name": dataset.name,
            }

            return paginated_scores, total_count, dataset_info

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get dataset scores for dataset {dataset_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve dataset scores",
            ) from e

    # ------------------------ Comparison Methods ------------------------

    # Color palette for radar chart deployments
    DEPLOYMENT_COLORS = [
        "#10B981",  # Green
        "#8B5CF6",  # Purple
        "#3B82F6",  # Blue
        "#F59E0B",  # Amber
        "#EF4444",  # Red
        "#EC4899",  # Pink
        "#14B8A6",  # Teal
        "#6366F1",  # Indigo
    ]

    def get_comparison_deployments(
        self,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get all unique deployments with completed runs for comparison.

        Queries across ALL experiments globally to find unique endpoint/model
        combinations that have completed evaluation runs.

        Parameters:
            page (int): Page number for pagination (default: 1).
            limit (int): Items per page (default: 50, max: 100).

        Returns:
            Tuple containing:
                - List[Dict]: List of deployments with counts
                - int: Total count of deployments
        """
        try:
            # Query to get unique deployments across all experiments globally
            query = (
                self.session.query(
                    EndpointModel.id.label("deployment_id"),
                    EndpointModel.name.label("endpoint_name"),
                    ModelTable.id.label("model_id"),
                    ModelTable.name.label("model_name"),
                    ModelTable.icon.label("model_icon"),
                    func.count(func.distinct(ExperimentModel.id)).label("experiment_count"),
                    func.count(RunModel.id).label("run_count"),
                )
                .join(RunModel, RunModel.endpoint_id == EndpointModel.id)
                .join(ExperimentModel, RunModel.experiment_id == ExperimentModel.id)
                .join(ModelTable, EndpointModel.model_id == ModelTable.id)
                .filter(
                    ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
                    RunModel.status == RunStatusEnum.COMPLETED.value,
                )
                .group_by(
                    EndpointModel.id,
                    EndpointModel.name,
                    ModelTable.id,
                    ModelTable.name,
                    ModelTable.icon,
                )
                .order_by(func.count(RunModel.id).desc())
            )

            # Get total count
            total_count = query.count()

            # Apply pagination
            offset = (page - 1) * limit
            results = query.offset(offset).limit(limit).all()

            deployments = []
            for row in results:
                deployments.append(
                    {
                        "id": row.deployment_id,
                        "endpoint_name": row.endpoint_name,
                        "model_id": row.model_id,
                        "model_name": row.model_name,
                        "model_icon": row.model_icon,
                        "experiment_count": row.experiment_count,
                        "run_count": row.run_count,
                    }
                )

            return deployments, total_count

        except Exception as e:
            logger.error(f"Failed to get comparison deployments: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve comparison deployments",
            ) from e

    def get_comparison_traits(
        self,
        deployment_ids: Optional[List[uuid.UUID]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get all traits that have completed runs globally.

        Returns only traits that have at least one completed evaluation run,
        optionally filtered by specific deployments.

        Parameters:
            deployment_ids (Optional[List[uuid.UUID]]): Filter by specific deployments.

        Returns:
            Tuple containing:
                - List[Dict]: List of traits with counts
                - int: Total count of traits
        """
        try:
            # Base query: Find traits via dataset -> pivot -> runs
            query = (
                self.session.query(
                    TraitModel.id.label("trait_id"),
                    TraitModel.name.label("trait_name"),
                    TraitModel.icon.label("trait_icon"),
                    TraitModel.description.label("trait_description"),
                    func.count(func.distinct(DatasetModel.id)).label("dataset_count"),
                    func.count(func.distinct(RunModel.id)).label("run_count"),
                )
                .join(PivotModel, PivotModel.trait_id == TraitModel.id)
                .join(DatasetModel, PivotModel.dataset_id == DatasetModel.id)
                .join(ExpDatasetVersion, ExpDatasetVersion.dataset_id == DatasetModel.id)
                .join(RunModel, RunModel.dataset_version_id == ExpDatasetVersion.id)
                .join(ExperimentModel, RunModel.experiment_id == ExperimentModel.id)
                .filter(
                    ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
                    RunModel.status == RunStatusEnum.COMPLETED.value,
                )
            )

            # Apply deployment filter if provided
            if deployment_ids:
                query = query.filter(RunModel.endpoint_id.in_(deployment_ids))

            query = query.group_by(
                TraitModel.id,
                TraitModel.name,
                TraitModel.icon,
                TraitModel.description,
            ).order_by(func.count(RunModel.id).desc())

            results = query.all()

            traits = []
            for row in results:
                traits.append(
                    {
                        "id": row.trait_id,
                        "name": row.trait_name,
                        "icon": row.trait_icon,
                        "description": row.trait_description,
                        "dataset_count": row.dataset_count,
                        "run_count": row.run_count,
                    }
                )

            return traits, len(traits)

        except Exception as e:
            logger.error(f"Failed to get comparison traits: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve comparison traits",
            ) from e

    def get_radar_chart_data(
        self,
        deployment_ids: Optional[List[uuid.UUID]] = None,
        trait_ids: Optional[List[uuid.UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get radar chart data showing best trait scores per deployment.

        For each deployment, calculates the BEST (MAX) score across all runs
        for each trait. Traits are determined via dataset-trait relationships.

        Parameters:
            deployment_ids (Optional[List[uuid.UUID]]): List of deployment/endpoint IDs. If None, returns all.
            trait_ids (Optional[List[uuid.UUID]]): Filter by specific traits (max 6).
            start_date (Optional[datetime]): Filter runs after this date.
            end_date (Optional[datetime]): Filter runs before this date.

        Returns:
            Dict containing:
                - traits: List of trait info for axis labels
                - deployments: List of deployment data with trait scores
        """
        try:
            # Build base query for runs with trait information
            # Join: Run -> DatasetVersion -> Dataset -> Pivot -> Trait
            # Also join: Run -> ExpMetric for scores
            base_query = (
                self.session.query(
                    RunModel.endpoint_id,
                    EndpointModel.name.label("endpoint_name"),
                    ModelTable.name.label("model_name"),
                    TraitModel.id.label("trait_id"),
                    TraitModel.name.label("trait_name"),
                    TraitModel.icon.label("trait_icon"),
                    MetricModel.metric_value,
                    RunModel.id.label("run_id"),
                )
                .join(EndpointModel, RunModel.endpoint_id == EndpointModel.id)
                .join(ModelTable, EndpointModel.model_id == ModelTable.id)
                .join(ExperimentModel, RunModel.experiment_id == ExperimentModel.id)
                .join(ExpDatasetVersion, RunModel.dataset_version_id == ExpDatasetVersion.id)
                .join(DatasetModel, ExpDatasetVersion.dataset_id == DatasetModel.id)
                .join(PivotModel, PivotModel.dataset_id == DatasetModel.id)
                .join(TraitModel, PivotModel.trait_id == TraitModel.id)
                .join(MetricModel, MetricModel.run_id == RunModel.id)
                .filter(
                    ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
                    RunModel.status == RunStatusEnum.COMPLETED.value,
                    MetricModel.metric_name == "accuracy",  # Use accuracy metric
                )
            )

            # Apply deployment filter if provided
            if deployment_ids:
                base_query = base_query.filter(RunModel.endpoint_id.in_(deployment_ids))

            # Apply trait filter
            if trait_ids:
                base_query = base_query.filter(TraitModel.id.in_(trait_ids))

            # Apply date filters
            if start_date:
                base_query = base_query.filter(RunModel.created_at >= start_date)
            if end_date:
                base_query = base_query.filter(RunModel.created_at <= end_date)

            results = base_query.all()

            # Aggregate: For each deployment, for each trait, find MAX score
            deployments_data: Dict[uuid.UUID, Dict[str, Any]] = {}
            traits_data: Dict[uuid.UUID, Dict[str, Any]] = {}

            for row in results:
                endpoint_id = row.endpoint_id
                trait_id = row.trait_id

                # Track trait info
                if trait_id not in traits_data:
                    traits_data[trait_id] = {
                        "id": trait_id,
                        "name": row.trait_name,
                        "icon": row.trait_icon,
                    }

                # Initialize deployment if not exists
                if endpoint_id not in deployments_data:
                    deployments_data[endpoint_id] = {
                        "deployment_id": endpoint_id,
                        "deployment_name": row.endpoint_name,
                        "model_name": row.model_name,
                        "trait_scores": {},  # {trait_id: {"max_score": float, "run_count": int}}
                    }

                # Track best score per trait
                if trait_id not in deployments_data[endpoint_id]["trait_scores"]:
                    deployments_data[endpoint_id]["trait_scores"][trait_id] = {
                        "max_score": float(row.metric_value) if row.metric_value else 0,
                        "run_count": 1,
                        "trait_name": row.trait_name,
                    }
                else:
                    current = deployments_data[endpoint_id]["trait_scores"][trait_id]
                    if row.metric_value and float(row.metric_value) > current["max_score"]:
                        current["max_score"] = float(row.metric_value)
                    current["run_count"] += 1

            # Build response
            traits_list = list(traits_data.values())

            deployments_list = []
            for idx, (_endpoint_id, data) in enumerate(deployments_data.items()):
                trait_scores = []
                for trait_id, score_data in data["trait_scores"].items():
                    trait_scores.append(
                        {
                            "trait_id": trait_id,
                            "trait_name": score_data["trait_name"],
                            "score": round(score_data["max_score"], 2),
                            "run_count": score_data["run_count"],
                        }
                    )

                deployments_list.append(
                    {
                        "deployment_id": data["deployment_id"],
                        "deployment_name": data["deployment_name"],
                        "model_name": data["model_name"],
                        "color": self.DEPLOYMENT_COLORS[idx % len(self.DEPLOYMENT_COLORS)],
                        "trait_scores": trait_scores,
                    }
                )

            return {
                "traits": traits_list,
                "deployments": deployments_list,
            }

        except Exception as e:
            logger.error(f"Failed to get radar chart data: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve radar chart data",
            ) from e

    def get_heatmap_chart_data(
        self,
        deployment_ids: Optional[List[uuid.UUID]] = None,
        trait_ids: Optional[List[uuid.UUID]] = None,
        dataset_ids: Optional[List[uuid.UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get heatmap chart data showing dataset scores per deployment.

        For each deployment, calculates average scores per dataset.
        Returns a matrix of deployment x dataset with average accuracy scores.

        Parameters:
            deployment_ids (Optional[List[uuid.UUID]]): List of deployment/endpoint IDs. If None, returns all.
            trait_ids (Optional[List[uuid.UUID]]): Filter datasets by traits.
            dataset_ids (Optional[List[uuid.UUID]]): Filter by specific datasets.
            start_date (Optional[datetime]): Filter runs after this date.
            end_date (Optional[datetime]): Filter runs before this date.

        Returns:
            Dict containing:
                - datasets: List of dataset info for column headers
                - deployments: List of deployment data with dataset scores
                - stats: Min, max, avg scores for color scaling
        """
        try:
            # Build base query
            base_query = (
                self.session.query(
                    RunModel.endpoint_id,
                    EndpointModel.name.label("endpoint_name"),
                    ModelTable.name.label("model_name"),
                    DatasetModel.id.label("dataset_id"),
                    DatasetModel.name.label("dataset_name"),
                    MetricModel.metric_value,
                )
                .join(EndpointModel, RunModel.endpoint_id == EndpointModel.id)
                .join(ModelTable, EndpointModel.model_id == ModelTable.id)
                .join(ExperimentModel, RunModel.experiment_id == ExperimentModel.id)
                .join(ExpDatasetVersion, RunModel.dataset_version_id == ExpDatasetVersion.id)
                .join(DatasetModel, ExpDatasetVersion.dataset_id == DatasetModel.id)
                .join(MetricModel, MetricModel.run_id == RunModel.id)
                .filter(
                    ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
                    RunModel.status == RunStatusEnum.COMPLETED.value,
                    MetricModel.metric_name == "accuracy",
                )
            )

            # Apply deployment filter if provided
            if deployment_ids:
                base_query = base_query.filter(RunModel.endpoint_id.in_(deployment_ids))

            # Apply trait filter (filter datasets by their traits)
            if trait_ids:
                dataset_with_traits = (
                    self.session.query(PivotModel.dataset_id).filter(PivotModel.trait_id.in_(trait_ids)).subquery()
                )
                base_query = base_query.filter(DatasetModel.id.in_(dataset_with_traits))

            # Apply dataset filter
            if dataset_ids:
                base_query = base_query.filter(DatasetModel.id.in_(dataset_ids))

            # Apply date filters
            if start_date:
                base_query = base_query.filter(RunModel.created_at >= start_date)
            if end_date:
                base_query = base_query.filter(RunModel.created_at <= end_date)

            results = base_query.all()

            # Aggregate: For each deployment x dataset, calculate average score
            deployments_data: Dict[uuid.UUID, Dict[str, Any]] = {}
            datasets_data: Dict[uuid.UUID, Dict[str, Any]] = {}
            all_scores: List[float] = []

            for row in results:
                endpoint_id = row.endpoint_id
                dataset_id = row.dataset_id

                # Track dataset info
                if dataset_id not in datasets_data:
                    datasets_data[dataset_id] = {
                        "id": dataset_id,
                        "name": row.dataset_name,
                    }

                # Initialize deployment if not exists
                if endpoint_id not in deployments_data:
                    deployments_data[endpoint_id] = {
                        "deployment_id": endpoint_id,
                        "deployment_name": row.endpoint_name,
                        "model_name": row.model_name,
                        "dataset_scores": {},  # {dataset_id: {"scores": [], "run_count": int}}
                    }

                # Track scores per dataset
                if dataset_id not in deployments_data[endpoint_id]["dataset_scores"]:
                    deployments_data[endpoint_id]["dataset_scores"][dataset_id] = {
                        "scores": [],
                        "dataset_name": row.dataset_name,
                    }

                if row.metric_value and row.metric_value > 0:
                    deployments_data[endpoint_id]["dataset_scores"][dataset_id]["scores"].append(
                        float(row.metric_value)
                    )

            # Calculate averages and build response
            datasets_list = list(datasets_data.values())

            deployments_list = []
            for _endpoint_id, data in deployments_data.items():
                dataset_scores = []
                for dataset_id, score_data in data["dataset_scores"].items():
                    scores = score_data["scores"]
                    avg_score = sum(scores) / len(scores) if scores else None

                    if avg_score is not None:
                        all_scores.append(avg_score)

                    dataset_scores.append(
                        {
                            "dataset_id": dataset_id,
                            "dataset_name": score_data["dataset_name"],
                            "score": round(avg_score, 2) if avg_score is not None else None,
                            "run_count": len(scores),
                        }
                    )

                deployments_list.append(
                    {
                        "deployment_id": data["deployment_id"],
                        "deployment_name": data["deployment_name"],
                        "model_name": data["model_name"],
                        "dataset_scores": dataset_scores,
                    }
                )

            # Calculate stats for color scaling
            stats = {
                "min_score": round(min(all_scores), 2) if all_scores else 0,
                "max_score": round(max(all_scores), 2) if all_scores else 0,
                "avg_score": round(sum(all_scores) / len(all_scores), 2) if all_scores else 0,
            }

            return {
                "datasets": datasets_list,
                "deployments": deployments_list,
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"Failed to get heatmap chart data: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve heatmap chart data",
            ) from e


class ExperimentWorkflowService:
    """Service layer for Experiment Workflow operations."""

    def __init__(self, session: Session):
        """Initialize the service with a database session.

        Parameters:
            session (Session): SQLAlchemy database session.
        """
        self.session = session

    async def process_experiment_workflow_step(
        self, request: ExperimentWorkflowStepRequest, current_user_id: uuid.UUID
    ) -> "RetrieveWorkflowDataResponse":
        """Process a step in the experiment creation workflow.

        Parameters:
            request (ExperimentWorkflowStepRequest): The workflow step request.
            current_user_id (uuid.UUID): ID of the user creating the experiment.

        Returns:
            ExperimentWorkflowResponse: Response with workflow status and next step data.

        Raises:
            HTTPException: If validation fails or workflow errors occur.
        """
        try:
            # Validate step number
            if request.step_number < 1 or request.step_number > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid step number. Must be between 1 and 5.",
                )

            # Get or create workflow
            if request.workflow_id:
                # Continuing existing workflow
                workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                    WorkflowModel, {"id": request.workflow_id}
                )
                if not workflow:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workflow not found",
                    )
                workflow = cast(WorkflowModel, workflow)
                if workflow.created_by != current_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this workflow",
                    )
                if workflow.status != WorkflowStatusEnum.IN_PROGRESS:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Workflow is not in progress",
                    )
            else:
                # Creating new workflow (step 1 only)
                if request.step_number != 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="workflow_id is required for steps 2-5",
                    )
                workflow = await WorkflowDataManager(self.session).insert_one(
                    WorkflowModel(
                        created_by=current_user_id,
                        workflow_type=WorkflowTypeEnum.EVALUATE_MODEL,
                        status=WorkflowStatusEnum.IN_PROGRESS,
                        current_step=0,
                        total_steps=request.workflow_total_steps,
                        title="Experiment Creation",
                        progress={},
                    )
                )
                workflow = cast(WorkflowModel, workflow)

            # Validate step data based on current step
            await self._validate_step_data(request.step_number, request.stage_data)

            # Store workflow step data
            await self._store_workflow_step(workflow.id, request.step_number, request.stage_data)

            # Update workflow current step
            workflow_manager = WorkflowDataManager(self.session)
            await workflow_manager.update_by_fields(
                workflow,
                {"current_step": request.step_number},  # type: ignore
            )

            # If this is the final step and trigger_workflow is True, create the experiment
            if request.step_number == 5 and request.trigger_workflow:
                experiment_id = await self._create_experiment_from_workflow(workflow.id, current_user_id)

                # Store the experiment_id in a workflow step for retrieval
                await WorkflowStepDataManager(self.session).insert_one(
                    WorkflowStepModel(
                        workflow_id=workflow.id,
                        step_number=6,  # Use step 6 to store the result
                        data={"experiment_id": str(experiment_id)},
                    )
                )

                # Mark workflow as completed
                # await WorkflowDataManager(self.session).update_by_fields(
                #     workflow,
                #     {"status": WorkflowStatusEnum.COMPLETED.value},  # type: ignore
                # )

                # if experiment_id, then call the eval workflow
                # if experiment_id:
                #     await self._call_eval_workflow(experiment_id)

            # We now rely on unified workflow retrieval output; skip assembling local data
            _ = await self._get_accumulated_step_data(workflow.id)

            from budapp.workflow_ops.services import (
                WorkflowService as GenericWorkflowService,
            )

            # Return unified workflow response matching cluster creation
            return await GenericWorkflowService(self.session).retrieve_workflow_data(workflow.id)

        except HTTPException:
            raise
        except Exception as e:
            logger.warning(
                f"Failed to process experiment workflow step: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process workflow step",
            ) from e

    async def _validate_step_data(self, step_number: int, stage_data: dict) -> None:
        """Validate step data based on the current step.

        Parameters:
            step_number (int): Current step number.
            stage_data (dict): Data for the current step.

        Raises:
            HTTPException: If validation fails.
        """
        if step_number == 1:
            # Basic Info validation
            # project_id is now optional, only name is required
            required_fields = ["name"]  # Removed project_id from required fields
            for field in required_fields:
                if field not in stage_data or not stage_data[field]:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Field '{field}' is required for step 1",
                    )

            # Validate tags if provided
            if "tags" in stage_data and stage_data["tags"] is not None:
                tags = stage_data["tags"]
                if not isinstance(tags, list):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="tags must be a list of strings",
                    )
                # Validate each tag is a string
                for tag in tags:
                    if not isinstance(tag, str):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Each tag must be a string",
                        )
        elif step_number == 2:
            # Endpoint Selection validation
            if "endpoint_ids" not in stage_data or not stage_data["endpoint_ids"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="At least one endpoint must be selected in step 2",
                )
        elif step_number == 3:
            # Traits Selection validation
            if "trait_ids" not in stage_data or not stage_data["trait_ids"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="At least one trait must be selected in step 3",
                )

            # Validate trait_ids exist in database
            trait_ids = stage_data["trait_ids"]
            if not isinstance(trait_ids, list):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="trait_ids must be a list",
                )

            # Validate each trait_id is a valid UUID and exists in database
            for trait_id in trait_ids:
                try:
                    # Convert to UUID to validate format
                    trait_uuid = uuid.UUID(str(trait_id))
                except (ValueError, TypeError) as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid trait ID format: {trait_id}",
                    ) from e

                # Check if trait exists in database
                trait = self.session.get(TraitModel, trait_uuid)
                if not trait:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Trait with ID {trait_id} does not exist",
                    )

            # Validate dataset_ids if provided (optional field)
            if "dataset_ids" in stage_data and stage_data["dataset_ids"]:
                dataset_ids = stage_data["dataset_ids"]
                if not isinstance(dataset_ids, list):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="dataset_ids must be a list",
                    )

                # Validate each dataset_id is a valid UUID and exists in database
                for dataset_id in dataset_ids:
                    try:
                        # Convert to UUID to validate format
                        dataset_uuid = uuid.UUID(str(dataset_id))
                    except (ValueError, TypeError) as e:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid dataset ID format: {dataset_id}",
                        ) from e

                    # Check if dataset exists in database
                    dataset = self.session.get(DatasetModel, dataset_uuid)
                    if not dataset:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Dataset with ID {dataset_id} does not exist",
                        )
        elif step_number == 4:
            # Performance Point validation
            if "performance_point" not in stage_data:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Field 'performance_point' is required for step 4",
                )

            performance_point = stage_data["performance_point"]
            if not isinstance(performance_point, int) or performance_point < 0 or performance_point > 100:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Field 'performance_point' must be an integer between 0 and 100",
                )
        elif step_number == 5:
            # Finalization validation - optional fields
            pass

    async def _store_workflow_step(self, workflow_id: uuid.UUID, step_number: int, stage_data: dict) -> None:
        """Store workflow step data in the database.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID.
            step_number (int): Step number.
            stage_data (dict): Data for the step.
        """
        # Check if step already exists
        existing_step = await WorkflowStepDataManager(self.session).retrieve_by_fields(
            WorkflowStepModel,
            {"workflow_id": workflow_id, "step_number": step_number},
            missing_ok=True,
        )

        step_data = stage_data.copy()  # Create a copy to avoid modifying original
        if "experiment_id" in stage_data:
            step_data["experiment_id"] = str(stage_data["experiment_id"])

        if existing_step:
            # Update existing step
            await WorkflowStepDataManager(self.session).update_by_fields(
                existing_step,
                {"data": stage_data},  # type: ignore
            )
        else:
            # Create new step
            await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=workflow_id,
                    step_number=step_number,
                    data=stage_data,
                )
            )

    async def _prepare_next_step_data(self, next_step: int, current_user_id: uuid.UUID) -> dict:
        """Prepare data needed for the next step.

        Parameters:
            next_step (int): Next step number.
            current_user_id (uuid.UUID): Current user ID.

        Returns:
            dict: Data for the next step.
        """
        if next_step == 2:
            # Prepare available models - this would need to be implemented based on your model structure
            return {
                "message": "Select models for evaluation",
                "available_models": [],  # TODO: Implement model fetching
            }
        elif next_step == 3:
            # Prepare available traits using lightweight approach
            traits_service = ExperimentService(self.session)
            traits, _ = traits_service.list_traits(offset=0, limit=100)
            return {
                "message": "Select traits and datasets",
                "available_traits": [
                    {
                        "id": str(trait.id),
                        "name": trait.name,
                        "description": trait.description,
                    }
                    for trait in traits
                ],
            }
        elif next_step == 4:
            return {
                "message": "Set performance point (0-100)",
                "description": "Specify the performance threshold for this experiment",
            }
        elif next_step == 5:
            return {"message": "Review and finalize experiment"}
        return {}

    async def _get_accumulated_step_data(self, workflow_id: uuid.UUID) -> dict:
        """Get all accumulated step data for a workflow.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID to get data for.

        Returns:
            dict: Accumulated data from all steps organized by step type.
        """
        steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps({"workflow_id": workflow_id})

        accumulated_data = {}

        for step in steps:
            if step.step_number == 1:
                accumulated_data["basic_info"] = step.data
            elif step.step_number == 2:
                accumulated_data["model_selection"] = step.data
            elif step.step_number == 3:
                accumulated_data["traits_selection"] = step.data
            elif step.step_number == 4:
                accumulated_data["performance_point"] = step.data
            elif step.step_number == 5:
                accumulated_data["finalize"] = step.data

        return accumulated_data

    async def _create_experiment_from_workflow(self, workflow_id: uuid.UUID, current_user_id: uuid.UUID) -> uuid.UUID:
        """Create experiment and initial run from workflow data.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID.
            current_user_id (uuid.UUID): User ID.

        Returns:
            uuid.UUID: Created experiment ID.
        """
        # Get all workflow steps
        workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Combine data from all steps
        combined_data = ExperimentWorkflowStepData(performance_point=None)
        for step in workflow_steps:
            step_data = step.data
            if step.step_number == 1:
                combined_data.name = step_data.get("name")
                combined_data.description = step_data.get("description")
                combined_data.project_id = step_data.get("project_id")
                combined_data.tags = step_data.get("tags")
            elif step.step_number == 2:
                combined_data.endpoint_ids = step_data.get("endpoint_ids", [])
            elif step.step_number == 3:
                combined_data.trait_ids = step_data.get("trait_ids", [])
                combined_data.dataset_ids = step_data.get("dataset_ids", [])
            elif step.step_number == 4:
                combined_data.performance_point = step_data.get("performance_point")
            elif step.step_number == 5:
                combined_data.run_name = step_data.get("run_name")
                combined_data.run_description = step_data.get("run_description")
                combined_data.evaluation_config = step_data.get("evaluation_config", {})

        # Validate duplicate experiment name for this user (align with create_experiment)
        if combined_data.name:
            existing_experiment = (
                self.session.query(ExperimentModel)
                .filter(
                    ExperimentModel.name == combined_data.name,
                    ExperimentModel.created_by == current_user_id,
                    ExperimentModel.status != ExperimentStatusEnum.DELETED.value,
                )
                .first()
            )
            if existing_experiment:
                raise ClientException(
                    message=f"An experiment with the name '{combined_data.name}' already exists. Please choose a different name.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Create the experiment
        experiment = ExperimentModel(
            name=combined_data.name,
            description=combined_data.description,
            # project_id=combined_data.project_id,  # Commented out - made optional
            created_by=current_user_id,
            status=ExperimentStatusEnum.ACTIVE.value,
            tags=combined_data.tags or [],
        )

        # Only set project_id if provided
        if combined_data.project_id:
            experiment.project_id = combined_data.project_id
        self.session.add(experiment)
        self.session.flush()

        # Get datasets from traits if dataset_ids is empty but trait_ids exists
        dataset_ids_to_use = combined_data.dataset_ids or []
        if combined_data.trait_ids and not dataset_ids_to_use:
            # Fetch all datasets associated with the selected traits
            dataset_ids_from_traits = (
                self.session.query(PivotModel.dataset_id)
                .filter(PivotModel.trait_id.in_(combined_data.trait_ids))
                .distinct()
                .all()
            )
            dataset_ids_to_use = [str(dataset_id[0]) for dataset_id in dataset_ids_from_traits]
            logger.info(f"Found {len(dataset_ids_to_use)} datasets from {len(combined_data.trait_ids)} traits")

        # Create runs for each endpoint-dataset combination
        if combined_data.endpoint_ids and dataset_ids_to_use:
            run_index = 1
            for endpoint_id in combined_data.endpoint_ids:
                # Convert endpoint_id to UUID if it's a string
                try:
                    endpoint_id = uuid.UUID(str(endpoint_id))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid endpoint ID format: {endpoint_id}, skipping")
                    continue

                for dataset_id in dataset_ids_to_use:
                    # Get the latest version of the dataset
                    dataset_version = (
                        self.session.query(ExpDatasetVersion)
                        .filter(ExpDatasetVersion.dataset_id == dataset_id)
                        .order_by(ExpDatasetVersion.created_at.desc())
                        .first()
                    )

                    if not dataset_version:
                        logger.warning(f"No version found for dataset {dataset_id}, skipping")
                        continue

                    run = RunModel(
                        experiment_id=experiment.id,
                        run_index=run_index,
                        endpoint_id=endpoint_id,
                        dataset_version_id=dataset_version.id,
                        status=RunStatusEnum.RUNNING.value,
                        config=combined_data.evaluation_config,
                    )
                    self.session.add(run)
                    run_index += 1

        self.session.commit()
        return experiment.id

    async def _call_eval_workflow(self, experiment_id: uuid.UUID) -> None:
        """Delegate evaluation workflow to EvaluationWorkflowService.

        Parameters:
            experiment_id (uuid.UUID): The experiment ID to evaluate.
        """
        try:
            # Use EvaluationWorkflowService to trigger evaluations
            eval_service = EvaluationWorkflowService(self.session)
            await eval_service._trigger_evaluations_for_experiment(experiment_id)
        except Exception as e:
            logger.error(f"Failed to call eval workflow for experiment {experiment_id}: {e}")

    async def get_experiment_workflow_data(
        self, workflow_id: uuid.UUID, current_user_id: uuid.UUID
    ) -> "RetrieveWorkflowDataResponse":
        """Get complete experiment workflow data for review.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID to retrieve data for.
            current_user_id (uuid.UUID): Current user ID for authorization.

        Returns:
            ExperimentWorkflowResponse: Complete workflow data response.
        """
        try:
            # Get workflow record
            workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel,
                {"id": workflow_id, "created_by": current_user_id},
            )
            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found",
                )
            workflow = cast(WorkflowModel, workflow)

            # Get all accumulated step data
            await self._get_accumulated_step_data(workflow_id)

            # Determine completion state
            is_complete = workflow.current_step >= 5

            # Prepare next step data if not complete
            if not is_complete:
                await self._prepare_next_step_data(workflow.current_step + 1, current_user_id)

            from budapp.workflow_ops.services import (
                WorkflowService as GenericWorkflowService,
            )

            # Return unified workflow response matching cluster creation
            return await GenericWorkflowService(self.session).retrieve_workflow_data(workflow.id)

        except Exception as e:
            logger.error(f"Failed to get experiment workflow data: {e}")
            raise ClientException(f"Failed to retrieve workflow data: {str(e)}") from e


class EvaluationWorkflowService:
    """Service layer for Evaluation Workflow operations."""

    def __init__(self, session: Session):
        """Initialize the EvaluationWorkflowService.

        Parameters:
            session (Session): Database session.
        """
        self.session = session

    async def process_evaluation_workflow_step(
        self,
        experiment_id: uuid.UUID,
        request: EvaluationWorkflowStepRequest,
        current_user_id: uuid.UUID,
    ) -> RetrieveWorkflowDataResponse:
        """Process a step in the evaluation creation workflow.

        Parameters:
            experiment_id (uuid.UUID): The experiment ID to create evaluation runs for.
            request (EvaluationWorkflowStepRequest): The workflow step request.
            current_user_id (uuid.UUID): Current user ID for authorization.

        Returns:
            RetrieveWorkflowDataResponse: Unified workflow response for all steps

        Raises:
            HTTPException: If validation fails or workflow errors occur.
        """
        # from budapp.workflow_ops.services import WorkflowService as GenericWorkflowService

        try:
            # Verify experiment exists and user has access
            experiment = self.session.get(ExperimentModel, experiment_id)
            if not experiment or experiment.created_by != current_user_id or experiment.status == "deleted":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Experiment not found or access denied",
                )

            # Get or create workflow
            if request.workflow_id:
                # Continuing existing workflow
                workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                    WorkflowModel, {"id": request.workflow_id}
                )
                if not workflow:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workflow not found",
                    )
                workflow = cast(WorkflowModel, workflow)
                if workflow.created_by != current_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this workflow",
                    )
                if workflow.status != WorkflowStatusEnum.IN_PROGRESS:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Workflow is not in progress",
                    )
            else:
                # Creating new workflow (step 1 only)
                if request.step_number != 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="workflow_id is required for steps 2-5",
                    )
                workflow_title = request.stage_data.get("name") if isinstance(request.stage_data, dict) else None
                if isinstance(workflow_title, str) and workflow_title.strip():
                    workflow_title = workflow_title.strip()
                else:
                    workflow_title = "New Model Evaualtion"

                workflow = await WorkflowDataManager(self.session).insert_one(
                    WorkflowModel(
                        title=workflow_title,
                        workflow_type=WorkflowTypeEnum.EVALUATE_MODEL,
                        status=WorkflowStatusEnum.IN_PROGRESS,
                        current_step=0,  # Start at 0, will be updated to 1 after first step
                        total_steps=request.workflow_total_steps,
                        created_by=current_user_id,
                    )
                )
                workflow = cast(WorkflowModel, workflow)

            # Validate step sequence
            # Allow resubmitting current step or proceeding to next step
            if request.step_number > workflow.current_step + 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot skip steps. Current step is {workflow.current_step}, cannot jump to step {request.step_number}",
                )
            elif request.step_number < 1 or request.step_number > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid step number {request.step_number}. Must be between 1 and 5",
                )

            # Store workflow step data with experiment_id included
            stage_data_with_experiment = request.stage_data.copy()
            stage_data_with_experiment["experiment_id"] = str(experiment_id)

            # For step 3 (trait selection), enrich with trait details before storing
            if request.step_number == 3 and "trait_ids" in stage_data_with_experiment:
                trait_ids = stage_data_with_experiment.get("trait_ids", [])
                traits_details = []
                for trait_id in trait_ids:
                    try:
                        trait_uuid = uuid.UUID(str(trait_id))
                        trait = self.session.query(TraitModel).filter(TraitModel.id == trait_uuid).first()
                        if trait:
                            traits_details.append(
                                {
                                    "id": str(trait.id),
                                    "name": trait.name,
                                    "description": trait.description,
                                }
                            )
                    except (ValueError, TypeError):
                        continue
                stage_data_with_experiment["traits_details"] = traits_details

            await self._store_workflow_step(workflow.id, request.step_number, stage_data_with_experiment)

            # Validate step 4 dataset-trait relationships
            if request.step_number == 4:
                await self._validate_dataset_trait_relationships(workflow.id, request.stage_data)

            # Update workflow current step only if we're progressing forward
            if request.step_number > workflow.current_step:
                workflow_manager = WorkflowDataManager(self.session)
                await workflow_manager.update_by_fields(
                    workflow,
                    {"current_step": request.step_number},
                )

            evaluation_id: uuid.UUID | None = None
            # If this is the final step and trigger_workflow is True, create the runs
            if request.step_number == 5 and request.trigger_workflow:
                # Create The Evaluation & Runs
                evaluation_id = await self._create_runs_from_workflow(workflow.id, experiment_id, current_user_id)

                logger.warning(f"Created Evaluation ID: {evaluation_id}")

                await WorkflowDataManager(self.session).update_by_fields(
                    workflow,
                    {"status": WorkflowStatusEnum.COMPLETED.value},  # type: ignore
                )

            # After storing the workflow step, retrieve all accumulated data
            all_step_data = await self._get_accumulated_step_data(workflow.id)

            logger.warning(f"All Step Data: {all_step_data}")

            # Determine if workflow is complete
            is_complete = (
                request.step_number == 5 and request.trigger_workflow
            ) or workflow.status == WorkflowStatusEnum.COMPLETED.value

            # Determine next step
            next_step = None if is_complete else request.step_number + 1
            if next_step:
                await self._get_next_step_data(next_step, all_step_data, experiment_id)

            # Get The Evaluation ID

            # Trigger budeval evaluation if this is the final step
            if request.step_number == 5 and request.trigger_workflow:
                logger.info("*" * 10)
                logger.info(f"\n\nTriggering budeval evaluation for experiment {experiment_id} \n\n")

                if evaluation_id is None:
                    raise ClientException(
                        message="Error getting evaluation ID",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # Trigger Eval
                trigger_workflow_response = await self._trigger_evaluations_for_experiment_and_get_response(
                    experiment_id, current_user_id, workflow.id, evaluation_id
                )

                logger.warning(f"Triggered budeval evaluation for experiment {trigger_workflow_response}")

                # Add payload dict to response
                for step in trigger_workflow_response["steps"]:
                    step["payload"] = {}

                logger.warning(f"After Steps {trigger_workflow_response} \n\n")

                evaluation_events_payload = {
                    BudServeWorkflowStepEventName.EVALUATION_EVENTS.value: trigger_workflow_response
                }

                # Increment Step Number
                current_step_number = request.step_number + 1
                workflow_current_step = current_step_number

                logger.warning(f"workflow_current_step {workflow_current_step} \n\n")

                # Update or create next workflow step
                db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
                    workflow.id, current_step_number, evaluation_events_payload
                )

                logger.warning(f"db_workflow_step {db_workflow_step.id} \n\n")

                # Update The Progress
                trigger_workflow_response["progress_type"] = BudServeWorkflowStepEventName.EVALUATION_EVENTS.value
                workflow = await WorkflowDataManager(self.session).update_by_fields(
                    workflow,
                    {
                        "progress": trigger_workflow_response,
                        "current_step": workflow_current_step,
                    },
                )

                logger.debug(f"Updated progress, current step in workflow {workflow.id}")

            return await WorkflowService(self.session).retrieve_workflow_data(workflow.id)

        except HTTPException:
            raise
        except Exception as e:
            logger.warning(
                f"Failed to process evaluation workflow step: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process workflow step",
            ) from e

    async def _store_workflow_step(self, workflow_id: uuid.UUID, step_number: int, stage_data: dict) -> None:
        """Store workflow step data in the database.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID.
            step_number (int): Step number.
            stage_data (dict): Step data to store.
        """
        # Check if step already exists
        steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id, "step_number": step_number}
        )

        if steps:
            # Update existing step
            existing_step = steps[0]
            await WorkflowStepDataManager(self.session).update_by_fields(
                existing_step,
                {"data": stage_data},
            )
        else:
            # Create new step
            await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=workflow_id,
                    step_number=step_number,
                    data=stage_data,
                )
            )

    async def _get_accumulated_step_data(self, workflow_id: uuid.UUID) -> dict:
        """Get all accumulated step data for a workflow.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID.

        Returns:
            dict: Combined data from all steps with enriched information.
        """
        steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps({"workflow_id": workflow_id})

        logger.warning(f"Steps: {steps}")

        accumulated_data = {}
        for step in steps:
            step_data = step.data.copy()

            # Enrich step 2 data with endpoint and model details
            if step.step_number == 2 and "endpoint_id" in step_data:
                endpoint_id = step_data.get("endpoint_id")
                if endpoint_id:
                    try:
                        endpoint_uuid = uuid.UUID(str(endpoint_id))
                        # Query endpoint first
                        endpoint_row = (
                            self.session.query(EndpointModel).filter(EndpointModel.id == endpoint_uuid).first()
                        )
                        if endpoint_row:
                            # Query model from endpoint
                            model_row = (
                                self.session.query(ModelTable).filter(ModelTable.id == endpoint_row.model_id).first()
                            )
                            if model_row:
                                step_data["model_details"] = {
                                    "id": str(model_row.id),
                                    "name": model_row.name,
                                    "description": model_row.description,
                                    "modality": list(model_row.modality) if model_row.modality is not None else None,
                                    "provider_type": model_row.provider_type,
                                    "source": model_row.source,
                                    "uri": model_row.uri,
                                    "icon": model_row.icon,
                                    "deployment_name": endpoint_row.name,
                                }
                            else:
                                # Fallback if model not found
                                step_data["model_details"] = {
                                    "id": str(endpoint_uuid),
                                    "name": f"Endpoint {str(endpoint_uuid)[:8]}",
                                    "deployment_name": endpoint_row.name,
                                }
                        else:
                            # Fallback to minimal info if endpoint not found
                            step_data["model_details"] = {
                                "id": str(endpoint_uuid),
                                "name": f"Endpoint {str(endpoint_uuid)[:8]}",
                            }
                    except (ValueError, TypeError):
                        pass

            # Enrich step 3 data with trait details
            elif step.step_number == 3 and "trait_ids" in step_data:
                trait_ids = step_data.get("trait_ids", [])
                traits = []
                for trait_id in trait_ids:
                    try:
                        trait_uuid = uuid.UUID(str(trait_id))
                        trait = self.session.query(TraitModel).filter(TraitModel.id == trait_uuid).first()
                        if trait:
                            traits.append(
                                {
                                    "id": str(trait.id),
                                    "name": trait.name,
                                    "description": trait.description,
                                }
                            )
                    except (ValueError, TypeError):
                        continue
                step_data["traits_details"] = traits

            # Enrich step 4 data with dataset details
            elif step.step_number == 4 and "dataset_ids" in step_data:
                dataset_ids = step_data.get("dataset_ids", [])
                datasets = []
                for dataset_id in dataset_ids:
                    try:
                        dataset_uuid = uuid.UUID(str(dataset_id))
                        dataset = self.session.query(DatasetModel).filter(DatasetModel.id == dataset_uuid).first()
                        if dataset:
                            # Get associated traits for this dataset
                            associated_traits = (
                                self.session.query(TraitModel)
                                .join(
                                    PivotModel,
                                    TraitModel.id == PivotModel.trait_id,
                                )
                                .filter(PivotModel.dataset_id == dataset_uuid)
                                .all()
                            )

                            # Get latest version info
                            latest_version = (
                                self.session.query(ExpDatasetVersion)
                                .filter(ExpDatasetVersion.dataset_id == dataset_uuid)
                                .order_by(ExpDatasetVersion.created_at.desc())
                                .first()
                            )

                            datasets.append(
                                {
                                    "id": str(dataset.id),
                                    "name": dataset.name,
                                    "description": dataset.description,
                                    "meta_links": dataset.meta_links,
                                    "associated_traits": [
                                        {"id": str(t.id), "name": t.name} for t in associated_traits
                                    ],
                                    "latest_version": {
                                        "version": latest_version.version,
                                        "created_at": latest_version.created_at.isoformat(),
                                    }
                                    if latest_version
                                    else None,
                                }
                            )
                    except (ValueError, TypeError):
                        continue
                step_data["datasets_details"] = datasets

            accumulated_data[f"step_{step.step_number}"] = step_data

        return accumulated_data

    async def _validate_dataset_trait_relationships(self, workflow_id: uuid.UUID, step_data: dict) -> None:
        """Validate that selected datasets are linked to selected traits.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID.
            step_data (dict): Step 3 data containing dataset_ids.

        Raises:
            HTTPException: If validation fails.
        """
        # Get trait_ids from step 3
        all_data = await self._get_accumulated_step_data(workflow_id)
        trait_ids = all_data.get("step_3", {}).get("trait_ids", [])
        dataset_ids = step_data.get("dataset_ids", [])

        if not trait_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No traits selected in previous step",
            )

        if not dataset_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No datasets selected",
            )

        # Validate each dataset is linked to at least one selected trait
        for dataset_id in dataset_ids:
            linked_count = (
                self.session.query(PivotModel)
                .filter(
                    PivotModel.dataset_id == dataset_id,
                    PivotModel.trait_id.in_(trait_ids),
                )
                .count()
            )
            if linked_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dataset {dataset_id} is not linked to any of the selected traits",
                )

    async def _create_runs_from_workflow(
        self,
        workflow_id: uuid.UUID,
        experiment_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> uuid.UUID:
        """Create runs from workflow data.

        Parameters:
            workflow_id (uuid.UUID): Workflow ID.
            experiment_id (uuid.UUID): Experiment ID.
            current_user_id (uuid.UUID): Current user ID.

        Returns:
            int: Number of runs created.
        """
        # Get accumulated data
        all_data = await self._get_accumulated_step_data(workflow_id)
        endpoint_id = all_data.get("step_2", {}).get("endpoint_id")
        dataset_ids = all_data.get("step_4", {}).get("dataset_ids", [])
        trait_ids = all_data.get("step_3", {}).get("trait_ids", [])

        # Common details for evaluation
        evaluation_name = all_data.get("step_1", {}).get("name", "Evaluation")
        evaluation_description = all_data.get("step_1", {}).get("description")

        if not endpoint_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No endpoint selected",
            )

        if not dataset_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No datasets selected",
            )

        # Get experiment
        experiment = self.session.get(ExperimentModel, experiment_id)
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )

        # Convert endpoint_id to UUID if it's a string
        try:
            endpoint_uuid = uuid.UUID(str(endpoint_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid endpoint ID format: {endpoint_id}",
            )

        # Convert trait_ids to strings for JSONB storage
        trait_id_strings = []
        for trait_id in trait_ids:
            try:
                # Validate as UUID and convert to string for JSONB storage
                validated_uuid = uuid.UUID(str(trait_id))
                trait_id_strings.append(str(validated_uuid))
            except (ValueError, TypeError):
                logger.warning(f"Invalid trait ID format: {trait_id}, skipping")

        # Create Evaluation
        evaluation = Evaluation(
            experiment_id=experiment_id,
            name=evaluation_name,
            description=evaluation_description,
            workflow_id=workflow_id,
            created_by=current_user_id,
            status=EvaluationStatusEnum.RUNNING.value,
            trait_ids=trait_id_strings,
        )
        self.session.add(evaluation)
        self.session.flush()

        # Get next run index for this experiment
        next_run_index = (
            self.session.query(func.max(RunModel.run_index)).filter(RunModel.experiment_id == experiment_id).scalar()
            or 0
        ) + 1

        runs_created = 0
        # Create runs for each dataset with the selected model
        for dataset_id in dataset_ids:
            # Get the latest version of the dataset
            dataset_version = (
                self.session.query(ExpDatasetVersion)
                .filter(ExpDatasetVersion.dataset_id == dataset_id)
                .order_by(ExpDatasetVersion.created_at.desc())
                .first()
            )

            if not dataset_version:
                logger.warning(f"No version found for dataset {dataset_id}, skipping")
                continue

            run = RunModel(
                experiment_id=experiment.id,
                run_index=next_run_index,
                evaluation_id=evaluation.id,
                endpoint_id=endpoint_uuid,
                dataset_version_id=dataset_version.id,
                status=RunStatusEnum.RUNNING.value,
                config={},
            )
            self.session.add(run)
            next_run_index += 1
            runs_created += 1

        # commit changes
        self.session.commit()

        self.session.commit()

        # Trigger budeval evaluation for all created runs
        # await self._trigger_evaluations_for_experiment(experiment_id)

        return evaluation.id

    async def _get_next_step_data(
        self,
        next_step: Optional[int],
        accumulated_data: dict,
        experiment_id: uuid.UUID,
    ) -> Optional[dict]:
        """Get data for the next step.

        Parameters:
            next_step (Optional[int]): Next step number.
            accumulated_data (dict): Accumulated data from previous steps.
            experiment_id (uuid.UUID): The experiment ID.

        Returns:
            Optional[dict]: Data for next step.
        """
        if not next_step:
            return None

        if next_step == 2:
            # Return available models from experiment's existing runs
            existing_runs = self.session.query(RunModel).filter(RunModel.experiment_id == experiment_id).all()

            if not existing_runs:
                return {
                    "available_endpoints": [],
                    "message": "No endpoints found in experiment. Please create runs first.",
                }

            # Collect unique endpoint_ids from existing runs
            unique_endpoint_ids = list({run.endpoint_id for run in existing_runs})

            # Query endpoints
            endpoints = self.session.query(EndpointModel).filter(EndpointModel.id.in_(unique_endpoint_ids)).all()
            endpoint_id_to_row = {row.id: row for row in endpoints}

            # Query models
            model_ids = [ep.model_id for ep in endpoints]
            models = self.session.query(ModelTable).filter(ModelTable.id.in_(model_ids)).all()
            model_id_to_row = {row.id: row for row in models}

            # Build response list
            available_endpoints = []
            for endpoint_id in unique_endpoint_ids:
                endpoint_row = endpoint_id_to_row.get(endpoint_id)
                model_row = model_id_to_row.get(endpoint_row.model_id) if endpoint_row else None
                if endpoint_row and model_row:
                    available_endpoints.append(
                        {
                            "id": str(endpoint_id),
                            "name": model_row.name,
                            "deployment_name": endpoint_row.name,
                            "description": model_row.description,
                            "modality": list(model_row.modality) if model_row.modality is not None else None,
                            "provider_type": model_row.provider_type,
                            "source": model_row.source,
                            "uri": model_row.uri,
                            "icon": model_row.icon,
                        }
                    )
                else:
                    available_endpoints.append(
                        {
                            "id": str(endpoint_id),
                            "name": f"Endpoint {str(endpoint_id)[:8]}",
                            "deployment_name": endpoint_row.name if endpoint_row else None,
                        }
                    )

            return {
                "available_endpoints": available_endpoints,
                "message": "Select an endpoint for evaluation",
            }

        elif next_step == 3:
            # Return available traits
            traits = self.session.query(TraitModel).all()
            return {
                "available_traits": [
                    {
                        "id": trait.id,
                        "name": trait.name,
                        "description": trait.description,
                    }
                    for trait in traits
                ]
            }

        elif next_step == 4:
            # Return datasets linked to selected traits
            trait_ids = accumulated_data.get("step_3", {}).get("trait_ids", [])
            if not trait_ids:
                return {"available_datasets": []}

            # datasets = (
            #     self.session.query(DatasetModel)
            #     .join(PivotModel, DatasetModel.id == PivotModel.dataset_id)
            #     .filter(PivotModel.trait_id.in_(trait_ids))
            #     .distinct()
            #     .all()
            # )

            return {
                "available_datasets": [
                    # {"id": dataset.id, "name": dataset.name, "description": dataset.description}
                    # for dataset in datasets
                ]
            }

        elif next_step == 5:
            # Return summary data for final confirmation
            endpoint_id = accumulated_data.get("step_2", {}).get("endpoint_id")
            trait_ids = accumulated_data.get("step_3", {}).get("trait_ids", [])
            dataset_ids = accumulated_data.get("step_4", {}).get("dataset_ids", [])

            # Prepare model details
            model_details = accumulated_data.get("step_2", {}).get("model_details")
            if not model_details and endpoint_id:
                try:
                    endpoint_id_uuid = uuid.UUID(str(endpoint_id))
                    # Query endpoint and model details
                    endpoint = self.session.query(EndpointModel).filter(EndpointModel.id == endpoint_id_uuid).first()
                    if endpoint:
                        model = self.session.query(ModelTable).filter(ModelTable.id == endpoint.model_id).first()
                        if model:
                            model_details = {
                                "id": str(model.id),
                                "name": model.name,
                                "description": model.description,
                                "modality": list(model.modality) if model.modality is not None else None,
                                "provider_type": model.provider_type,
                                "source": model.source,
                                "uri": model.uri,
                                "icon": model.icon,
                                "deployment_name": endpoint.name,
                            }
                except (ValueError, TypeError):
                    model_details = None

            # Inject static fields into model details as requested
            if model_details is None:
                model_details = {}
            # Always include static tags
            model_details["tags"] = ["LLM", "SLM"]
            # Ensure icon has some value
            if not model_details.get("icon"):
                model_details["icon"] = "https://example.com/icon.png"

            # Prepare traits details
            traits_details = accumulated_data.get("step_3", {}).get("traits_details") or []
            if not traits_details and trait_ids:
                traits_details = []
                for t_id in trait_ids:
                    try:
                        t_uuid = uuid.UUID(str(t_id))
                        trait = self.session.query(TraitModel).filter(TraitModel.id == t_uuid).first()
                        if trait:
                            traits_details.append(
                                {
                                    "id": str(trait.id),
                                    "name": trait.name,
                                    "description": trait.description,
                                }
                            )
                    except (ValueError, TypeError):
                        continue

            # Prepare datasets details
            datasets_details = accumulated_data.get("step_4", {}).get("datasets_details") or []
            if not datasets_details and dataset_ids:
                datasets_details = []
                for d_id in dataset_ids:
                    try:
                        d_uuid = uuid.UUID(str(d_id))
                        dataset = self.session.query(DatasetModel).filter(DatasetModel.id == d_uuid).first()
                        if dataset:
                            datasets_details.append(
                                {
                                    "id": str(dataset.id),
                                    "name": dataset.name,
                                    "description": dataset.description,
                                }
                            )
                    except (ValueError, TypeError):
                        continue

            return {
                "summary": {
                    # Keep existing fields for backward compatibility
                    "endpoint_selected": str(endpoint_id) if endpoint_id else "None",
                    "traits_selected": len(trait_ids),
                    "datasets_selected": len(dataset_ids),
                    # New detailed fields
                    "model": model_details,
                    "traits": traits_details,
                    "datasets": datasets_details,
                    "runs_to_create": len(datasets_details) if datasets_details else len(dataset_ids),
                    # New evaluation info (static values)
                    "eva_info": {
                        "ETA": "2hr",
                        "Cost": "100$",
                        "Max QPS": "652 req/sec",
                        "Total Tokens": "5321",
                    },
                },
                "message": "Review and confirm to create evaluation runs",
            }

        return None

    async def get_evaluation_workflow_data(
        self,
        experiment_id: uuid.UUID,
        workflow_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> RetrieveWorkflowDataResponse:
        """Get complete evaluation workflow data for review.

        Parameters:
            experiment_id (uuid.UUID): The experiment ID.
            workflow_id (uuid.UUID): Workflow ID to retrieve data for.
            current_user_id (uuid.UUID): Current user ID for authorization.

        Returns:
            RetrieveWorkflowDataResponse: Complete workflow data response.
        """
        from budapp.workflow_ops.services import (
            WorkflowService as GenericWorkflowService,
        )

        try:
            # Verify experiment exists and user has access
            experiment = self.session.get(ExperimentModel, experiment_id)
            if not experiment or experiment.created_by != current_user_id or experiment.status == "deleted":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Experiment not found or access denied",
                )

            # Get workflow record
            workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel,
                {"id": workflow_id, "created_by": current_user_id},
            )
            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found",
                )
            workflow = cast(WorkflowModel, workflow)

            # Return unified workflow response
            return await GenericWorkflowService(self.session).retrieve_workflow_data(workflow.id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get evaluation workflow data: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve workflow data",
            ) from e

    async def trigger_budeval_evaluation(
        self,
        run_id: uuid.UUID,
        evaluation_request: Dict[str, Any],
        workflow_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Any:
        """Trigger evaluation in budeval service via Dapr.

        Parameters:
            run_id (uuid.UUID): The run ID to execute evaluation for.
            evaluation_request (Dict[str, Any]): The evaluation request data.

        Returns:
            WorkflowMetadataResponse: Workflow metadata response from budeval service.

        Raises:
            ClientException: If the budeval request fails.
        """
        try:
            # Prepare request for budeval - use correct endpoint
            budeval_endpoint = (
                f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_eval_app_id}/method/evals/start"
            )
            eval_request = {
                "eval_id": str(evaluation_request.get("evaluation_id")),
                "experiment_id": str(evaluation_request.get("experiment_id"))
                if evaluation_request.get("experiment_id")
                else None,
                "eval_model_info": {
                    "model_name": evaluation_request["model_name"],
                    "endpoint": evaluation_request["endpoint"],
                    "api_key": evaluation_request["api_key"],
                    "extra_args": evaluation_request.get("extra_args", {}),
                },
                "eval_datasets": evaluation_request["datasets"],
                "eval_configs": evaluation_request.get("eval_configs", []),
                "kubeconfig": evaluation_request.get("kubeconfig", ""),  # Not required as we use the incluster config
                "notification_metadata": {
                    "name": BUD_INTERNAL_WORKFLOW,
                    "subscriber_ids": str(current_user_id),
                    "workflow_id": str(workflow_id),
                },
                "source_topic": f"{app_settings.source_topic}",
            }

            logger.info(f"Triggering budeval evaluation for run {run_id} with request: {eval_request}")

            # Make async request to budeval
            async with aiohttp.ClientSession() as session:
                async with session.post(budeval_endpoint, json=eval_request) as response:
                    response_data = await response.json()
                    logger.warning(f"Response from budeval service: {response_data}")

                    if response.status != 200:
                        error_message = response_data.get("message", "Failed to start evaluation")
                        logger.error(f"Failed to start evaluation with budeval service: {error_message}")
                        raise ClientException(error_message)

                    logger.info(f"Successfully triggered evaluation in budeval service for run {run_id}")
                    # Parse the response as WorkflowMetadataResponse
                    return response_data
                    # return WorkflowMetadataResponse(**response_data)

        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Failed to trigger budeval evaluation: {e}")
            raise ClientException("Unable to start evaluation with budeval service") from e

    async def get_evaluation_status(self, job_id: str) -> Dict[str, Any]:
        """Get evaluation job status from budeval.

        Parameters:
            job_id (str): The evaluation job ID.

        Returns:
            Dict[str, Any]: Job status information from budeval.

        Raises:
            ClientException: If the status request fails.
        """
        try:
            status_endpoint = (
                f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_eval_app_id}/method/evals/status/{job_id}"
            )

            logger.warning(f"Getting evaluation status for job {job_id}")

            async with aiohttp.ClientSession() as session:
                async with session.get(status_endpoint) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        error_message = response_data.get("message", "Failed to get evaluation status")
                        logger.error(f"Failed to get evaluation status: {error_message}")
                        raise ClientException(error_message)

                    return response_data

        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Failed to get evaluation status: {e}")
            raise ClientException("Unable to get evaluation status from budeval service") from e

    async def cleanup_evaluation_job(self, job_id: str) -> Dict[str, Any]:
        """Clean up an evaluation job and its resources.

        Parameters:
            job_id (str): The evaluation job ID to cleanup.

        Returns:
            Dict[str, Any]: Cleanup status information from budeval.

        Raises:
            ClientException: If the cleanup request fails.
        """
        try:
            cleanup_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_eval_app_id}/method/evals/cleanup/{job_id}"

            logger.info(f"Cleaning up evaluation job {job_id}")

            async with aiohttp.ClientSession() as session:
                async with session.delete(cleanup_endpoint) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        error_message = response_data.get("message", "Failed to cleanup evaluation job")
                        logger.error(f"Failed to cleanup evaluation job: {error_message}")
                        raise ClientException(error_message)

                    logger.info(f"Successfully cleaned up evaluation job {job_id}")
                    return response_data

        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Failed to cleanup evaluation job: {e}")
            raise ClientException("Unable to cleanup evaluation job with budeval service") from e

    async def update_run_evaluation_status(self, run_id: uuid.UUID, status_data: Dict[str, Any]) -> None:
        """Update run evaluation status based on budeval feedback.

        Parameters:
            run_id (uuid.UUID): The run ID to update.
            status_data (Dict[str, Any]): Status data from budeval.
        """
        try:
            run = self.session.get(RunModel, run_id)
            if not run:
                logger.warning(f"Run {run_id} not found for status update")
                return

            # Update run status and budeval-specific fields
            update_data = {
                "evaluation_status": status_data.get("status"),
                "budeval_job_id": status_data.get("job_id"),
                "budeval_workflow_id": status_data.get("workflow_id"),
            }

            # Set timestamps based on status
            if status_data.get("status") == "running" and not run.evaluation_started_at:
                update_data["evaluation_started_at"] = func.now()
            elif status_data.get("status") in ["completed", "failed"]:
                update_data["evaluation_completed_at"] = func.now()

            # Update the run
            for field, value in update_data.items():
                if value is not None and hasattr(run, field):
                    setattr(run, field, value)

            self.session.commit()
            logger.info(f"Updated run {run_id} evaluation status to {status_data.get('status')}")

        except Exception as e:
            logger.error(f"Failed to update run evaluation status: {e}")
            self.session.rollback()
            raise

    async def _trigger_evaluations_for_experiment_and_get_response(
        self,
        experiment_id: uuid.UUID,
        current_user_id: uuid.UUID,
        workflow_id: uuid.UUID,
        evaluation_id: uuid.UUID,
    ) -> dict:
        """Trigger budeval evaluation for all pending runs in experiment and return first WorkflowMetadataResponse.

        Parameters:
            experiment_id (uuid.UUID): The experiment ID to evaluate.

        Returns:
            Optional[WorkflowMetadataResponse]: The WorkflowMetadataResponse from first triggered evaluation, or None if no runs.
        """
        try:
            # Get pending runs for the experiment
            runs = (
                self.session.query(RunModel)
                .filter(
                    RunModel.evaluation_id == evaluation_id,
                    RunModel.experiment_id == experiment_id,
                )
                .all()
            )

            if not runs:
                logger.info(f"No pending runs found for experiment {experiment_id}")
                raise ClientException("No pending runs found for experiment")

            logger.info(f"Triggering budeval evaluation for {len(runs)} runs in experiment {experiment_id}")
            logger.info("*" * 10)

            # Collect all datasets from runs by extracting eval_type configurations from database
            all_datasets = []

            # Add datasets from each run (avoiding duplicates)
            for run in runs:
                try:
                    if run.dataset_version and run.dataset_version.dataset:
                        dataset = run.dataset_version.dataset
                        eval_types = dataset.eval_types

                        if eval_types and isinstance(eval_types, dict):
                            # Extract the "gen" evaluation type configuration
                            # You can make this configurable based on run.config if needed
                            if "gen" in eval_types:
                                dataset_config = eval_types["gen"]
                                if dataset_config and dataset_config not in all_datasets:
                                    dataset_item = {
                                        "dataset_id": dataset_config,
                                        "run_id": str(run.id),
                                    }
                                    all_datasets.append(dataset_item)
                                    logger.info(f"Added dataset config '{dataset_config}' from run {run.id}")
                            else:
                                logger.warning(f"Run {run.id}: Dataset '{dataset.name}' has no 'gen' eval_type")
                        else:
                            logger.warning(f"Run {run.id}: Dataset '{dataset.name}' has no eval_types configured")
                except Exception as e:
                    logger.error(
                        f"Could not retrieve dataset configuration for run {run.id}: {e}",
                        exc_info=True,
                    )

            # Prepare single evaluation request with all datasets
            if not all_datasets:
                logger.error(f"No datasets with eval_types found for experiment {experiment_id}")
                raise ClientException("No datasets with valid eval_type configurations found")

            logger.info(f"Collected {len(all_datasets)} dataset configurations: {all_datasets}")

            # Get first run to determine model and endpoint
            first_run = runs[0]

            # Get endpoint details (async query)
            from sqlalchemy import select

            stmt = select(EndpointModel).filter(EndpointModel.id == first_run.endpoint_id)
            endpoint = self.session.execute(stmt).scalars().first()

            if not endpoint:
                raise ClientException(f"Endpoint {first_run.endpoint_id} not found")

            # Get model from endpoint (async query)
            stmt = select(ModelTable).filter(ModelTable.id == endpoint.model_id)
            model = self.session.execute(stmt).scalars().first()

            if not model:
                raise ClientException(f"Model {endpoint.model_id} not found for endpoint '{endpoint.name}'")

            # Get first active project for credential generation
            experiment_service = ExperimentService(self.session)
            project_id = await experiment_service.get_first_active_project()

            # Generate temporary evaluation credential
            _api_key = await experiment_service._generate_temporary_evaluation_key(
                project_id=project_id, experiment_id=experiment_id
            )

            # Build evaluation request with dynamic values
            evaluation_request = {
                "model_name": endpoint.namespace,  # Endpoint name for identification
                "endpoint": f"{endpoint.url}/v1",  # Dynamic from endpoint table (endpoint.url contains the actual endpoint URL)
                "api_key": _api_key,  # Generated temporary credential
                "extra_args": {},
                "datasets": all_datasets,
                "kubeconfig": "",  # TODO: Get actual kubeconfig
                # Use service name as source for CloudEvent metadata (not the topic)
                "source": app_settings.name,
                "source_topic": app_settings.source_topic,
                "experiment_id": experiment_id,  # Include experiment ID for tracking
                "evaluation_id": str(evaluation_id),
            }

            logger.warning(f"::BUDEVAL:: Triggering budeval evaluation {evaluation_request}")

            # Update all runs status to running
            for run in runs:
                run.status = RunStatusEnum.RUNNING.value
            self.session.commit()

            # Trigger single budeval evaluation for all runs
            try:
                response = await self.trigger_budeval_evaluation(
                    run_id=runs[0].id,  # this is ignored
                    evaluation_request=evaluation_request,
                    workflow_id=workflow_id,
                    current_user_id=current_user_id,
                )

                # Store budeval job information for all runs
                for run in runs:
                    if hasattr(run, "budeval_job_id"):
                        run.budeval_job_id = (
                            response.get("job_id") if isinstance(response, dict) else getattr(response, "job_id", None)
                        )
                    if hasattr(run, "budeval_workflow_id"):
                        run.budeval_workflow_id = (
                            response.get("workflow_id")
                            if isinstance(response, dict)
                            else getattr(response, "workflow_id", None)
                        )
                    if hasattr(run, "evaluation_status"):
                        run.evaluation_status = "initiated"

                self.session.commit()
                logger.info(
                    f"Successfully triggered single evaluation for {len(runs)} runs with datasets: {all_datasets}"
                )

                logger.warning(f"Response X01: {response}")

                return response
            except Exception as e:
                logger.error(f"Failed to trigger evaluation for experiment {experiment_id}: {e}")
                # Mark all runs as failed
                for run in runs:
                    run.status = RunStatusEnum.FAILED.value
                    if hasattr(run, "evaluation_error"):
                        run.evaluation_error = str(e)
                self.session.commit()

                raise ClientException(f"Failed to trigger evaluation for experiment {experiment_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to trigger evaluations for experiment {experiment_id}: {e}")
            raise ClientException(f"Failed to trigger evaluations for experiment {experiment_id}: {e}")

    async def update_eval_run_status_from_notification(self, payload) -> None:
        from sqlalchemy import select

        from budapp.commons.constants import NotificationTypeEnum
        from budapp.core.schemas import NotificationResult
        from budapp.shared.notification_service import (
            BudNotifyService,
            NotificationBuilder,
        )

        logger.warning("Evaluation Error")

        try:
            # Get workflow and steps
            workflow_id = payload.workflow_id
            db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel, {"id": workflow_id}
            )
            if not db_workflow:
                logger.error(f"::EvalResult:: Workflow {workflow_id} not found for evaluation completion")
                raise ClientException(f"Workflow {workflow_id} not found")

            db_workflow = cast(WorkflowModel, db_workflow)
            logger.warning(f"::EvalResult:: Workflow {db_workflow.id} found")

            # Get the result from payload
            eval_raw = payload.content.result.get("evaluation_id", None)

            if not eval_raw:
                logger.error(f"::EvalResult:: Evaluation ID not found for workflow {db_workflow.id}")
                raise ClientException("Evaluation ID not found")  # if empty

            eval_id = uuid.UUID(eval_raw)
            # from one of the run , get the evaluation
            evaluation = self.session.get(EvaluationModel, eval_id)
            if not evaluation:
                logger.error(f"::EvalResult:: Evaluation {eval_id} not found")
                raise ClientException(f"Evaluation {eval_id} not found")

            # Get all the runs associated with the evaluation
            runs = self.session.query(RunModel).filter(RunModel.evaluation_id == eval_id).all()
            if not runs:
                logger.error(f"::EvalResult:: No runs found for evaluation {eval_id}")
                raise ClientException(f"No runs found for evaluation {eval_id}")
            # Update the status of all runs to failed
            for run in runs:
                run.status = RunStatusEnum.FAILED.value

            # Update the eval status to failed
            evaluation.status = EvaluationStatusEnum.FAILED.value
            evaluation.eta_seconds = 0  # Reset ETA when evaluation completes

            self.session.commit()

            try:
                notification_request = (
                    NotificationBuilder()
                    .set_content(
                        title=evaluation.name,
                        message=f"Evaluation {evaluation.status}",
                        icon=None,
                        result=NotificationResult(
                            target_id=db_workflow.id,
                            target_type="workflow",
                        ).model_dump(exclude_none=True, exclude_unset=True),
                    )
                    .set_payload(
                        workflow_id=str(db_workflow.id),
                        type=NotificationTypeEnum.EVALUATION_FAILED.value,
                    )
                    .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
                    .build()
                )
                await BudNotifyService().send_notification(notification_request)
            except Exception as e:
                logger.warning(f"::EvalResult:: Failed to send notification: {e}")

        except Exception as e:
            self.session.rollback()
            logger.exception(f"::EvalResult:: Failed to handle evaluation completion event: {e}")
            raise ClientException(f"::EvalResult:: Failed to process evaluation completion: {str(e)}")

    async def create_evaluation_from_notification_event(self, payload) -> None:
        """Create/update evaluation records from notification event.

        This method handles the completion notification from budeval service,
        similar to how cluster_ops handles cluster creation completion.

        Args:
            payload: The notification payload from budeval service

        Raises:
            ClientException: If the evaluation update fails
        """
        from sqlalchemy import select

        from budapp.commons.constants import NotificationTypeEnum
        from budapp.core.schemas import NotificationResult
        from budapp.shared.notification_service import (
            BudNotifyService,
            NotificationBuilder,
        )

        logger.warning("Received event for evaluation completion")

        try:
            # Get workflow and steps
            workflow_id = payload.workflow_id
            db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel, {"id": workflow_id}
            )
            if not db_workflow:
                logger.error(f"::EvalResult:: Workflow {workflow_id} not found for evaluation completion")
                raise ClientException(f"Workflow {workflow_id} not found")

            db_workflow = cast(WorkflowModel, db_workflow)
            logger.warning(f"::EvalResult:: Workflow {db_workflow.id} found")

            # Get the result from payload
            results = payload.content.result.get("results", [])
            eval_raw = payload.content.result.get("evaluation_id", None)

            if not eval_raw:
                logger.error(f"::EvalResult:: Evaluation ID not found for workflow {db_workflow.id}")
                raise ClientException("Evaluation ID not found")  # if empty

            if not results:
                logger.warning(f"::EvalResult:: No results found for workflow {db_workflow.id}")
            eval_id = uuid.UUID(eval_raw)
            # from one of the run , get the evaluation
            evaluation = self.session.get(EvaluationModel, eval_id)
            if not evaluation:
                logger.error(f"::EvalResult:: Evaluation {eval_id} not found")
                raise ClientException(f"Evaluation {eval_id} not found")

            # Dictionary to accumulate trait scores
            # Format: {trait_id_str: {"total_score": float, "count": int}}
            trait_score_accumulator = {}

            has_failures = False

            # Update runs
            for run in results:
                # Fix 1: Access run_id from dictionary
                run_id = run.get("run_id")
                if not run_id:
                    logger.warning(f"::EvalResult:: Missing run_id in payload for workflow {db_workflow.id}")
                    continue

                logger.debug(f"::EvalResult:: Updating run from payload {run_id}")

                # get the run - Fix 2: Use run_id variable
                runs_stmt = select(RunModel).where(RunModel.id == run_id)
                dbrun = self.session.execute(runs_stmt).scalars().one_or_none()

                if not dbrun:
                    logger.warning(f"::EvalResult:: Run {run_id} not found for workflow {db_workflow.id}")
                    continue

                # Update run status - Fix 3: Update dbrun, not run dict
                run_status = run.get("status", "failed")
                if run_status == "success":
                    dbrun.status = RunStatusEnum.COMPLETED.value
                else:
                    dbrun.status = RunStatusEnum.FAILED.value
                    has_failures = True

                # Raw Result
                raw_result = RawResultModel(
                    run_id=dbrun.id,
                    preview_results=run.get("run", {}),
                )
                self.session.add(raw_result)

                # Update The Metrics
                accuracy_score_ar = run.get("scores", [])
                if len(accuracy_score_ar) > 0:
                    final_acc = 0.0
                    for acc in accuracy_score_ar:
                        final_acc = float(acc.get("score", 0.0))
                    metric = MetricModel(
                        run_id=run_id,  # Fix 4: Use run_id variable
                        metric_name="accuracy",
                        mode="gen",
                        metric_value=float(final_acc),
                    )
                    self.session.add(metric)

                    # Calculate trait scores for this run
                    # Get the dataset for this run and find associated traits
                    try:
                        dataset_version = self.session.get(ExpDatasetVersion, dbrun.dataset_version_id)
                        if dataset_version and dataset_version.dataset:
                            dataset = dataset_version.dataset
                            # Get all traits associated with this dataset
                            traits = (
                                self.session.query(TraitModel)
                                .join(
                                    PivotModel,
                                    TraitModel.id == PivotModel.trait_id,
                                )
                                .filter(PivotModel.dataset_id == dataset.id)
                                .all()
                            )

                            # Accumulate scores for each trait
                            for trait in traits:
                                trait_id_str = str(trait.id)
                                if trait_id_str not in trait_score_accumulator:
                                    trait_score_accumulator[trait_id_str] = {
                                        "total_score": 0.0,
                                        "count": 0,
                                    }

                                trait_score_accumulator[trait_id_str]["total_score"] += final_acc
                                trait_score_accumulator[trait_id_str]["count"] += 1
                                logger.debug(
                                    f"::EvalResult:: Accumulated score for trait {trait.name} ({trait_id_str}): "
                                    f"{final_acc} (total: {trait_score_accumulator[trait_id_str]['total_score']}, "
                                    f"count: {trait_score_accumulator[trait_id_str]['count']})"
                                )
                    except Exception as trait_err:
                        logger.warning(
                            f"::EvalResult:: Failed to calculate trait scores for run {run_id}: {trait_err}"
                        )

                self.session.commit()
                logger.warning("::EvalResult:: Successfully updated evaluation runs with metrics")

            evaluation.status = EvaluationStatusEnum.COMPLETED.value
            if has_failures:
                # Update the eval status
                evaluation.status = EvaluationStatusEnum.FAILED.value

            # Reset ETA when evaluation completes
            evaluation.eta_seconds = 0

            # Calculate duration in seconds from created_at to now
            completion_time = datetime.now(timezone.utc)
            if evaluation.created_at:
                duration_seconds = int((completion_time - evaluation.created_at).total_seconds())
                evaluation.duration_in_seconds = duration_seconds
                logger.info(
                    f"::EvalResult:: Evaluation {eval_id} duration: {duration_seconds} seconds "
                    f"({duration_seconds // 60} minutes)"
                )

            # Calculate average scores for each trait and update evaluation.trait_scores
            trait_scores_final = {}
            for trait_id_str, accumulated in trait_score_accumulator.items():
                if accumulated["count"] > 0:
                    avg_score = accumulated["total_score"] / accumulated["count"]
                    trait_scores_final[trait_id_str] = str(avg_score)
                    logger.info(
                        f"::EvalResult:: Trait {trait_id_str} average score: {avg_score} "
                        f"(from {accumulated['count']} runs)"
                    )

            # Update evaluation with calculated trait scores
            if trait_scores_final:
                evaluation.trait_scores = trait_scores_final
                self.session.commit()
                logger.info(f"::EvalResult:: Updated evaluation {eval_id} with trait scores: {trait_scores_final}")
            else:
                logger.warning(f"::EvalResult:: No trait scores calculated for evaluation {eval_id}")

            # Send Success Notification
            try:
                notification_request = (
                    NotificationBuilder()
                    .set_content(
                        title=evaluation.name,
                        message=f"Evaluation {evaluation.status}",
                        icon=None,
                        result=NotificationResult(
                            target_id=db_workflow.id,
                            target_type="workflow",
                        ).model_dump(exclude_none=True, exclude_unset=True),
                    )
                    .set_payload(
                        workflow_id=str(db_workflow.id),
                        type=NotificationTypeEnum.EVALUATION_SUCCESS.value,
                    )
                    .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
                    .build()
                )
                await BudNotifyService().send_notification(notification_request)
            except Exception as e:
                logger.warning(f"::EvalResult:: Failed to send notification: {e}")

        except Exception as e:
            self.session.rollback()
            logger.exception(f"::EvalResult:: Failed to handle evaluation completion event: {e}")
            raise ClientException(f"::EvalResult:: Failed to process evaluation completion: {str(e)}")
