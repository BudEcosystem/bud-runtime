import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import aiohttp
from budmicroframe.commons.schemas import WorkflowMetadataResponse
from fastapi import HTTPException, status
from sqlalchemy import func, or_
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

        # Create experiment without project_id initially
        ev = ExperimentModel(
            name=req.name,
            description=req.description,
            # project_id=req.project_id,  # Commented out - made optional
            created_by=user_id,
            status=ExperimentStatusEnum.ACTIVE.value,
            tags=req.tags or [],
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
            req (ConfigureRunsRequest): Payload containing model_ids, dataset_ids, evaluation_config.
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
            for model_id in req.model_ids:
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
                        model_id=model_id,
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
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[ExperimentSchema], int]:
        """List all non-deleted Experiments for a given user with optional filters and pagination.

        Parameters:
            user_id (uuid.UUID): ID of the user whose experiments to list.
            project_id (Optional[uuid.UUID]): Filter by project ID.
            experiment_id (Optional[uuid.UUID]): Filter by experiment ID.
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
        experiment_ids = [exp.id for exp in evs]
        statuses = self.get_experiment_statuses_batch(experiment_ids)

        # Enrich each experiment with models, traits, and status
        enriched_experiments = []
        for exp in evs:
            exp_data = ExperimentSchema.from_orm(exp)
            # Add models and traits to the experiment
            exp_data.models = self.get_models_for_experiment(exp.id)
            exp_data.traits = self.get_traits_for_experiment(exp.id)
            # Add computed status
            exp_data.status = statuses.get(exp.id, "unknown")
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
        model_ids = [run.model_id for run in all_experiment_runs if run.model_id]
        dataset_version_ids = [run.dataset_version_id for run in all_experiment_runs if run.dataset_version_id]

        # Batch fetch evaluations
        evaluations_dict = {}
        if evaluation_ids:
            evaluations_batch = self.session.query(Evaluation).filter(Evaluation.id.in_(evaluation_ids)).all()
            evaluations_dict = {eval.id: eval for eval in evaluations_batch}

        # Batch fetch models
        models_dict = {}
        if model_ids:
            models_batch = self.session.query(ModelTable).filter(ModelTable.id.in_(model_ids)).all()
            models_dict = {model.id: model for model in models_batch}

        # Batch fetch endpoints
        endpoints_dict = {}
        if model_ids:
            endpoints_batch = self.session.query(EndpointModel).filter(EndpointModel.model_id.in_(model_ids)).all()
            endpoints_dict = {endpoint.model_id: endpoint for endpoint in endpoints_batch}

        # Batch fetch dataset versions and datasets
        datasets_dict = {}
        dataset_ids_for_traits = []
        if dataset_version_ids:
            dataset_versions_batch = (
                self.session.query(ExpDatasetVersion).filter(ExpDatasetVersion.id.in_(dataset_version_ids)).all()
            )
            for dv in dataset_versions_batch:
                datasets_dict[dv.id] = dv.dataset
                if dv.dataset:
                    dataset_ids_for_traits.append(dv.dataset.id)

        # Batch fetch traits for all datasets
        traits_by_dataset = {}
        if dataset_ids_for_traits:
            traits_pivot = (
                self.session.query(PivotModel, TraitModel)
                .join(TraitModel, PivotModel.trait_id == TraitModel.id)
                .filter(PivotModel.dataset_id.in_(dataset_ids_for_traits))
                .all()
            )
            for pivot, trait in traits_pivot:
                if pivot.dataset_id not in traits_by_dataset:
                    traits_by_dataset[pivot.dataset_id] = []
                traits_by_dataset[pivot.dataset_id].append(trait.name)

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
            if run.model_id and run.model_id in models_dict:
                model_name = models_dict[run.model_id].name
                if run.model_id in endpoints_dict:
                    deployment_name = endpoints_dict[run.model_id].namespace

            # Get dataset and its traits from batched data
            dataset_name = "Unknown Dataset"
            traits_list = []
            if run.dataset_version_id and run.dataset_version_id in datasets_dict:
                dataset = datasets_dict[run.dataset_version_id]
                if dataset:
                    dataset_name = dataset.name
                    traits_list = traits_by_dataset.get(dataset.id, [])

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

        # Collect all unique model IDs from runs
        model_ids = set()
        for runs in evaluation_runs_map.values():
            for run in runs:
                if run.model_id:
                    model_ids.add(run.model_id)

        # Batch fetch all models at once
        models_dict = {}
        if model_ids:
            models = self.session.query(ModelTable).filter(ModelTable.id.in_(list(model_ids))).all()
            models_dict = {model.id: model for model in models}

        # Build progress overview with cached model data
        progress_overview = []
        for evaluation in evaluations_running:
            eval_runs = evaluation_runs_map.get(evaluation.id, [])
            current_model_name = ""

            if eval_runs and eval_runs[0].model_id:
                model = models_dict.get(eval_runs[0].model_id)
                if model:
                    current_model_name = model.name
                else:
                    # Log missing model but don't fail
                    logger.warning(f"Model {eval_runs[0].model_id} not found in database")
                    current_model_name = "Unknown Model"

            # Calculate average score for THIS specific evaluation
            # Filter current_metrics to only include runs from this evaluation
            eval_run_ids = {str(run.id) for run in eval_runs}
            eval_metrics = [metric for metric in exp_data.current_metrics if metric.get("run_id") in eval_run_ids]

            evaluation_avg_score = 0.0
            if eval_metrics:
                total_score = sum(metric["score_value"] for metric in eval_metrics)
                evaluation_avg_score = round(total_score / len(eval_metrics), 2)

            progress_overview.append(
                ProgressOverview(
                    run_id=str(evaluation.id),
                    title=f"Progress Overview of {evaluation.name}",
                    objective=evaluation.description,
                    current=None,
                    progress=ProgressInfo(percent=0, completed=0, total=0),
                    current_evaluation="",
                    current_model=current_model_name,
                    processing_rate_per_min=0,
                    average_score_pct=evaluation_avg_score,
                    eta_minutes=25,
                    status=evaluation.status,
                    actions=None,
                )
            )

        # Final Response
        exp_data.progress_overview = progress_overview

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
            q = self.session.query(TraitModel)

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

            # Apply pagination - no need to load datasets for listing
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
            # Query for models used in the experiment's runs
            # Join with endpoints to get deployment names
            models = (
                self.session.query(
                    ModelTable.id,
                    ModelTable.name,
                    EndpointModel.namespace.label("deployment_name"),
                )
                .join(RunModel, RunModel.model_id == ModelTable.id)
                .outerjoin(EndpointModel, EndpointModel.model_id == ModelTable.id)
                .filter(
                    RunModel.experiment_id == experiment_id,
                    RunModel.status != RunStatusEnum.DELETED.value,
                )
                .all()
            )

            # Filter out duplicate models by ID (keep first occurrence)
            seen_model_ids = set()
            unique_models = []
            for model in models:
                if model.id not in seen_model_ids:
                    seen_model_ids.add(model.id)
                    unique_models.append(
                        ModelSummary(
                            id=model.id,
                            name=model.name,
                            deployment_name=model.deployment_name,
                        )
                    )

            return unique_models
        except Exception as e:
            logger.error(f"Failed to get models for experiment {experiment_id}: {e}")
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

    def compute_experiment_status(self, experiment_id: uuid.UUID) -> str:
        """Compute experiment status based on all runs' statuses.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.

        Returns:
            str: Computed status string (running/failed/completed/pending/cancelled/skipped/no_runs).
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

            # Priority order for status determination
            if RunStatusEnum.RUNNING.value in statuses:
                return "running"
            if RunStatusEnum.FAILED.value in statuses:
                return "failed"
            if RunStatusEnum.CANCELLED.value in statuses:
                return "cancelled"
            if RunStatusEnum.PENDING.value in statuses:
                return "pending"
            if all(s == RunStatusEnum.COMPLETED.value for s in statuses):
                return "completed"
            if all(s == RunStatusEnum.SKIPPED.value for s in statuses):
                return "skipped"

            # Fallback for mixed completed/skipped states
            return "completed"
        except Exception as e:
            logger.error(f"Failed to compute status for experiment {experiment_id}: {e}")
            return "unknown"

    def get_experiment_statuses_batch(self, experiment_ids: List[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Get statuses for multiple experiments in one query for optimization.

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

                    # Apply the same priority logic
                    if RunStatusEnum.RUNNING.value in statuses:
                        result[exp_id] = "running"
                    elif RunStatusEnum.FAILED.value in statuses:
                        result[exp_id] = "failed"
                    elif RunStatusEnum.CANCELLED.value in statuses:
                        result[exp_id] = "cancelled"
                    elif RunStatusEnum.PENDING.value in statuses:
                        result[exp_id] = "pending"
                    elif all(s == RunStatusEnum.COMPLETED.value for s in statuses):
                        result[exp_id] = "completed"
                    elif all(s == RunStatusEnum.SKIPPED.value for s in statuses):
                        result[exp_id] = "skipped"
                    else:
                        result[exp_id] = "completed"  # Fallback for mixed completed/skipped

            return result
        except Exception as e:
            logger.error(f"Failed to compute statuses for experiments: {e}")
            # Return unknown status for all experiments on error
            return dict.fromkeys(experiment_ids, "unknown")

    # ------------------------ Run Methods ------------------------

    def list_runs(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> List[EvaluationListItem]:
        """List all completed evaluations for a given experiment.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.
            user_id (uuid.UUID): ID of the user.

        Returns:
            List[EvaluationListItem]: List of completed evaluation items with model, traits, and scores.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
        """
        # First verify the experiment exists and belongs to the user
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

        # 1. Get all evaluations for the experiment
        evaluations = (
            self.session.query(EvaluationModel)
            .filter(EvaluationModel.experiment_id == experiment_id)
            .order_by(EvaluationModel.created_at.desc())
            .all()
        )

        evaluation_items = []

        # 2. For each evaluation, process its data
        for evaluation in evaluations:
            # Get runs associated with this evaluation
            runs = self.session.query(RunModel).filter(RunModel.evaluation_id == evaluation.id).all()

            if not runs:
                continue

            # Get the first run to extract model info (all runs in an evaluation typically use the same model)
            first_run = runs[0]

            # 4. Get model details and name
            model = self.session.query(ModelTable).filter(ModelTable.id == first_run.model_id).first()
            model_name = model.name if model else "Unknown Model"

            # 2. Identify associated traits from evaluation.trait_ids
            trait_ids = evaluation.trait_ids if evaluation.trait_ids else []

            if trait_ids:
                # Batch fetch all traits
                traits = (
                    self.session.query(TraitModel)
                    .filter(TraitModel.id.in_([uuid.UUID(tid) for tid in trait_ids]))
                    .all()
                )

                # 3. For each trait, get associated datasets
                trait_dataset_map = {}
                for trait in traits:
                    # Get datasets associated with this trait
                    datasets = (
                        self.session.query(DatasetModel)
                        .join(PivotModel, DatasetModel.id == PivotModel.dataset_id)
                        .filter(PivotModel.trait_id == trait.id)
                        .all()
                    )
                    trait_dataset_map[str(trait.id)] = {
                        "trait": trait,
                        "datasets": datasets,
                    }

                # 6. Map trait_id with trait_scores
                trait_scores_map = evaluation.trait_scores if evaluation.trait_scores else {}

                # Create evaluation items for each trait
                for trait_id_str in trait_ids:
                    trait_data = trait_dataset_map.get(trait_id_str)
                    if not trait_data:
                        continue

                    trait = trait_data["trait"]

                    # Get trait score from trait_scores mapping, or use default
                    trait_score = float(trait_scores_map.get(trait_id_str, 0.0))

                    # Calculate duration in minutes from duration_in_seconds
                    duration_minutes = evaluation.duration_in_seconds // 60 if evaluation.duration_in_seconds else 0

                    evaluation_item = EvaluationListItem(
                        evaluation_name=evaluation.name,
                        evaluation_id=evaluation.id,
                        model_name=model_name,
                        started_date=evaluation.created_at,
                        duration_minutes=duration_minutes,
                        trait_name=trait.name,
                        trait_score=trait_score,
                        status=evaluation.status,
                    )
                    evaluation_items.append(evaluation_item)
            else:
                # If no traits associated, create a single evaluation item with default trait
                duration_minutes = evaluation.duration_in_seconds // 60 if evaluation.duration_in_seconds else 0

                evaluation_item = EvaluationListItem(
                    evaluation_name=evaluation.name,
                    evaluation_id=evaluation.id,
                    model_name=model_name,
                    started_date=evaluation.created_at,
                    duration_minutes=duration_minutes,
                    trait_name="General",
                    trait_score=0.0,
                    status=evaluation.status,
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
            model_id=run.model_id,
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
        if run.model_id:
            model = self.session.query(ModelTable).filter(ModelTable.id == run.model_id).first()
            if model:
                # Get deployment name from endpoint if exists
                endpoint = self.session.query(EndpointModel).filter(EndpointModel.model_id == run.model_id).first()
                model_details = {
                    "id": str(model.id),
                    "name": model.name,
                    "display_name": model.display_name,
                    "deployment_name": endpoint.namespace if endpoint else None,
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
                    q = q.filter(DatasetModel.name.ilike(f"%{filters.name}%"))
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
                    sample_questions_answers=dataset.sample_questions_answers,
                    advantages_disadvantages=dataset.advantages_disadvantages,
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
            model = self.get_model_details(run.model_id)

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

    def get_model_details(self, model_id: uuid.UUID) -> "ModelDetail":
        """Get detailed model information.

        Parameters:
            model_id (uuid.UUID): ID of the model.

        Returns:
            ModelDetail: Model details with deployment information.
        """
        from budapp.endpoint_ops.models import Endpoint as EndpointModel
        from budapp.eval_ops.schemas import ModelDetail

        # Get model from models table
        model = self.session.query(ModelTable).filter(ModelTable.id == model_id).first()
        if not model:
            # Return placeholder if model not found
            return ModelDetail(id=model_id, name="Unknown Model", deployment_name=None)

        # Try to get deployment name from endpoints
        endpoint = self.session.query(EndpointModel).filter(EndpointModel.model_id == model_id).first()

        return ModelDetail(
            id=model.id,
            name=model.name,
            deployment_name=endpoint.namespace if endpoint else None,
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
        api_key = generate_secure_api_key("client_app")

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
                    model_detail = self.get_model_details(run.model_id)
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
            # Model Selection validation
            if "model_ids" not in stage_data or not stage_data["model_ids"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="At least one model must be selected in step 2",
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
                combined_data.model_ids = step_data.get("model_ids", [])
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

        # Create runs for each model-dataset combination
        if combined_data.model_ids and dataset_ids_to_use:
            run_index = 1
            for model_id in combined_data.model_ids:
                # Convert model_id to UUID if it's a string
                try:
                    model_uuid = uuid.UUID(str(model_id))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid model ID format: {model_id}, skipping")
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
                        model_id=model_uuid,
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

            # Enrich step 2 data with model details
            if step.step_number == 2 and "model_id" in step_data:
                model_id = step_data.get("model_id")
                if model_id:
                    try:
                        model_uuid = uuid.UUID(str(model_id))
                        model_row = self.session.query(ModelTable).filter(ModelTable.id == model_uuid).first()
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
                            }
                        else:
                            # Fallback to minimal info if model row is not found
                            step_data["model_details"] = {
                                "id": str(model_uuid),
                                "name": f"Model {str(model_uuid)[:8]}",
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
        model_id = all_data.get("step_2", {}).get("model_id")
        dataset_ids = all_data.get("step_4", {}).get("dataset_ids", [])
        trait_ids = all_data.get("step_3", {}).get("trait_ids", [])

        # Common details for evaluation
        evaluation_name = all_data.get("step_1", {}).get("name", "Evaluation")
        evaluation_description = all_data.get("step_1", {}).get("description")

        if not model_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No model selected",
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

        # Convert model_id to UUID if it's a string
        try:
            model_uuid = uuid.UUID(str(model_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model ID format: {model_id}",
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
                experiment_id=experiment_id,
                run_index=next_run_index,
                evaluation_id=evaluation.id,
                model_id=model_uuid,
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
                    "available_models": [],
                    "message": "No models found in experiment. Please create runs first.",
                }

            unique_model_ids = list({run.model_id for run in existing_runs})

            # Fetch model details for these IDs
            models = self.session.query(ModelTable).filter(ModelTable.id.in_(unique_model_ids)).all()
            model_id_to_row = {row.id: row for row in models}

            available_models = []
            for model_id in unique_model_ids:
                row = model_id_to_row.get(model_id)
                if row:
                    available_models.append(
                        {
                            "id": str(row.id),
                            "name": row.name,
                            "description": row.description,
                            "modality": list(row.modality) if row.modality is not None else None,
                            "provider_type": row.provider_type,
                            "source": row.source,
                            "uri": row.uri,
                            "icon": row.icon,
                        }
                    )
                else:
                    available_models.append(
                        {
                            "id": str(model_id),
                            "name": f"Model {str(model_id)[:8]}",
                        }
                    )

            return {
                "available_models": available_models,
                "message": "Select a model for evaluation",
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
            model_id = accumulated_data.get("step_2", {}).get("model_id")
            trait_ids = accumulated_data.get("step_3", {}).get("trait_ids", [])
            dataset_ids = accumulated_data.get("step_4", {}).get("dataset_ids", [])

            # Prepare model details
            model_details = accumulated_data.get("step_2", {}).get("model_details")
            if not model_details and model_id:
                try:
                    model_uuid = uuid.UUID(str(model_id))
                    model_row = self.session.query(ModelTable).filter(ModelTable.id == model_uuid).first()
                    if model_row:
                        model_details = {
                            "id": str(model_row.id),
                            "name": model_row.name,
                            "description": model_row.description,
                            "modality": list(model_row.modality) if model_row.modality is not None else None,
                            "provider_type": model_row.provider_type,
                            "source": model_row.source,
                            "uri": model_row.uri,
                            "icon": model_row.icon,
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
                    "model_selected": str(model_id) if model_id else "None",
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

            # Get model details (async query)
            from sqlalchemy import select

            stmt = select(ModelTable).filter(ModelTable.id == first_run.model_id)
            model = self.session.execute(stmt).scalars().first()

            if not model:
                raise ClientException(f"Model {first_run.model_id} not found")

            # Get endpoint for the model (async query)
            stmt = select(EndpointModel).filter(EndpointModel.model_id == first_run.model_id)
            endpoint = self.session.execute(stmt).scalars().first()

            if not endpoint:
                raise ClientException(
                    f"No active endpoint found for model '{model.name}'. "
                    "Please deploy the model before running evaluations."
                )

            # Get first active project for credential generation
            experiment_service = ExperimentService(self.session)
            project_id = await experiment_service.get_first_active_project()

            # Generate temporary evaluation credential
            api_key = await experiment_service._generate_temporary_evaluation_key(
                project_id=project_id, experiment_id=experiment_id
            )

            # Build evaluation request with dynamic values
            evaluation_request = {
                "model_name": model.name,  # Dynamic from model table
                "endpoint": "https://gateway.dev.bud.studio/v1",  # Dynamic from endpoint table
                "api_key": api_key,  # Generated temporary credential
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
        pass

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
