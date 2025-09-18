import uuid
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import aiohttp
from budmicroframe.commons.schemas import WorkflowMetadataResponse
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import (
    BUD_INTERNAL_WORKFLOW,
    BudServeWorkflowStepEventName,
    WorkflowTypeEnum,
)
from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.eval_ops.models import ExpDataset as DatasetModel
from budapp.eval_ops.models import (
    ExpDatasetVersion,
    ExperimentStatusEnum,
    RunStatusEnum,
)
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
    ConfigureRunsRequest,
    CreateDatasetRequest,
    CreateExperimentRequest,
    DatasetFilter,
    EvaluationWorkflowResponse,
    EvaluationWorkflowStepRequest,
    ExperimentWorkflowResponse,
    ExperimentWorkflowStepData,
    ExperimentWorkflowStepRequest,
    ModelSummary,
    TraitBasic,
    TraitSummary,
    UpdateDatasetRequest,
    UpdateExperimentRequest,
    UpdateRunRequest,
)
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
                        status=RunStatusEnum.PENDING.value,
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
        from datetime import datetime

        from budapp.eval_ops.schemas import (
            BudgetStats,
            CurrentMetric,
            ExperimentStats,
            JudgeInfo,
            ProcessingRate,
            ProgressActions,
            ProgressDataset,
            ProgressInfo,
            ProgressOverview,
            RuntimeStats,
            TokenStats,
        )

        ev = self.session.get(ExperimentModel, ev_id)
        if not ev or ev.created_by != user_id or ev.status == "deleted":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        # Create experiment schema and enrich with models, traits, and status
        exp_data = ExperimentSchema.from_orm(ev)
        exp_data.models = self.get_models_for_experiment(ev.id)
        exp_data.traits = self.get_traits_for_experiment(ev.id)
        exp_data.status = self.compute_experiment_status(ev.id)

        # Set default values for stats that are not yet available
        exp_data.stats = ExperimentStats(
            budget=BudgetStats(limit_usd=0.0, used_usd=0.0, used_pct=0),
            tokens=TokenStats(total=0, prefix=0, decode=0, unit="tokens"),
            runtime=RuntimeStats(active_seconds=0, estimated_total_seconds=0),
            processing_rate=ProcessingRate(current_per_min=0, target_per_min=0),
        )

        exp_data.objective = ev.description or ""

        import uuid as uuid_lib

        # Generate actual UUIDs for run IDs
        run_id_1 = str(uuid_lib.uuid4())
        run_id_2 = str(uuid_lib.uuid4())
        latest_run_id = str(uuid_lib.uuid4())

        exp_data.current_metrics = [
            CurrentMetric(
                evaluation="TruthfulQA",
                dataset="dataset_name",
                deployment_name="deployment_name",
                judge=None,
                traits=["trait_name_1", "trait_name_2"],
                last_run_at=datetime.fromisoformat("2024-01-13T00:00:00Z"),
                run_id=latest_run_id,
            )
        ]

        exp_data.progress_overview = [
            ProgressOverview(
                run_id=run_id_1,
                title="Progress Overview of Run 1",
                objective="Compare GPT-4 and Claude-3 performance across academic benchmarks",
                current=ProgressDataset(dataset_label="MMLU - Mathematical Reasoning"),
                progress=ProgressInfo(percent=65, completed=813, total=1247),
                current_evaluation="TruthfulQA",
                current_model="GPT-4 Turbo",
                processing_rate_per_min=47,
                average_score_pct=78.5,
                eta_minutes=45,
                status="running",
                actions=ProgressActions(
                    can_pause=True,
                    pause_url=f"/experiments/{ev_id}/runs/{run_id_1}/pause",
                ),
            ),
            ProgressOverview(
                run_id=run_id_2,
                title="Progress Overview of Run 2",
                objective="Compare GPT-4 and Claude-3 performance across academic benchmarks",
                current=ProgressDataset(dataset_label="MMLU - Mathematical Reasoning"),
                progress=ProgressInfo(percent=65, completed=813, total=1247),
                current_evaluation="TruthfulQA",
                current_model="GPT-4 Turbo",
                processing_rate_per_min=47,
                average_score_pct=78.5,
                eta_minutes=45,
                status="running",
                actions=ProgressActions(
                    can_pause=True,
                    pause_url=f"/experiments/{ev_id}/runs/{run_id_2}/pause",
                ),
            ),
        ]

        exp_data.updated_at = datetime.fromisoformat("2024-01-13T00:00:00Z")

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
            # Query for unique models used in the experiment's runs
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
                .distinct()
                .all()
            )

            return [
                ModelSummary(
                    id=model.id,
                    name=model.name,
                    deployment_name=model.deployment_name,
                )
                for model in models
            ]
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

    def list_runs(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> List[RunSchema]:
        """List all runs for a given experiment.

        Parameters:
            experiment_id (uuid.UUID): ID of the experiment.
            user_id (uuid.UUID): ID of the user.

        Returns:
            List[RunSchema]: List of run schemas.

        Raises:
            HTTPException(status_code=404): If experiment not found or access denied.
        """
        ev = self.session.get(ExperimentModel, experiment_id)
        if not ev or ev.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or access denied",
            )

        runs = (
            self.session.query(RunModel)
            .filter(
                RunModel.experiment_id == experiment_id,
                RunModel.status != RunStatusEnum.DELETED.value,
            )
            .order_by(RunModel.created_at.desc())
            .all()
        )
        return [RunSchema.from_orm(r) for r in runs]

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
                await self._create_experiment_from_workflow(workflow.id, current_user_id)
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
                        status=RunStatusEnum.PENDING.value,
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

            # Store workflow step data
            await self._store_workflow_step(workflow.id, request.step_number, request.stage_data)

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

            # If this is the final step and trigger_workflow is True, create the runs
            if request.step_number == 5 and request.trigger_workflow:
                await self._create_runs_from_workflow(workflow.id, experiment_id, current_user_id)
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

            # Trigger budeval evaluation if this is the final step
            if request.step_number == 5 and request.trigger_workflow:
                logger.info("*" * 10)
                logger.info(f"\n\nTriggering budeval evaluation for experiment {experiment_id} \n\n")

                # Trigger Eval
                trigger_workflow_response = await self._trigger_evaluations_for_experiment_and_get_response(
                    experiment_id, current_user_id, workflow.id
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
    ) -> int:
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
                model_id=model_uuid,
                dataset_version_id=dataset_version.id,
                status=RunStatusEnum.PENDING.value,
                config={},
            )
            self.session.add(run)
            next_run_index += 1
            runs_created += 1

        self.session.commit()

        # Trigger budeval evaluation for all created runs
        # await self._trigger_evaluations_for_experiment(experiment_id)

        return runs_created

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
                "uuid": str(evaluation_request.get("evaluation_id")),
                "experiment_id": str(evaluation_request.get("experiment_id"))
                if evaluation_request.get("experiment_id")
                else None,
                "eval_model_info": {
                    "model_name": evaluation_request["model_name"],
                    "endpoint": evaluation_request["endpoint"],
                    "api_key": evaluation_request["api_key"],
                    "extra_args": evaluation_request.get("extra_args", {}),
                },
                "eval_datasets": [{"dataset_id": ds} for ds in evaluation_request["datasets"]],
                "eval_configs": evaluation_request.get("eval_configs", []),
                "kubeconfig": evaluation_request.get("kubeconfig", ""),  # Add required kubeconfig field
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
                    RunModel.experiment_id == experiment_id,
                    RunModel.status == RunStatusEnum.PENDING.value,
                )
                .all()
            )

            if not runs:
                logger.info(f"No pending runs found for experiment {experiment_id}")
                raise ClientException("No pending runs found for experiment")

            logger.info(f"Triggering budeval evaluation for {len(runs)} runs in experiment {experiment_id}")
            logger.info("*" * 10)

            # Collect all datasets from runs, starting with the demo dataset
            all_datasets = ["demo_gsm8k_chat_gen"]

            # Get model and endpoint information from the first run
            # first_run = runs[0]
            # model = self.session.query(ModelTable).filter(ModelTable.id == first_run.model_id).first()
            # endpoint = self.session.query(EndpointModel).filter(EndpointModel.model_id == first_run.model_id).first()

            # if not model or not endpoint:
            #     logger.error(f"Model or endpoint not found for first run {first_run.id}")
            #     return None

            # Add datasets from each run (avoiding duplicates)
            # for run in runs:
            #     try:
            #         if hasattr(run, 'dataset_version') and run.dataset_version and run.dataset_version.dataset:
            #             dataset_id = run.dataset_version.dataset.dataset_id
            #             if dataset_id not in all_datasets:
            #                 all_datasets.append(dataset_id)
            #     except Exception as e:
            #         logger.warning(f"Could not retrieve dataset for run {run.id}: {e}")

            # Prepare single evaluation request with all datasets

            evaluation_request = {
                "model_name": "qwen3-32b",
                "endpoint": "http://20.66.97.208/v1",
                "api_key": "sk-BudLiteLLMMasterKey_123",
                "extra_args": {},
                "datasets": ["demo_gsm8k_chat_gen"],  # all_datasets,
                "kubeconfig": "",  # TODO: Get actual kubeconfig
                # Use service name as source for CloudEvent metadata (not the topic)
                "source": app_settings.name,
                "source_topic": app_settings.source_topic,
                "experiment_id": experiment_id,  # Include experiment ID for tracking
                "evaluation_id": str(workflow_id),  # TODO: Update to actual evaluation ID
            }

            # Update all runs status to running
            for run in runs:
                run.status = RunStatusEnum.RUNNING.value
            self.session.commit()

            # Trigger single budeval evaluation for all runs
            try:
                response = await self.trigger_budeval_evaluation(
                    run_id=runs[0].id,  # Use first run's ID as representative
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

    async def create_evaluation_from_notification_event(self, payload) -> None:
        """Create/update evaluation records from notification event.

        This method handles the completion notification from budeval service,
        similar to how cluster_ops handles cluster creation completion.

        Args:
            payload: The notification payload from budeval service

        Raises:
            ClientException: If the evaluation update fails
        """
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
                logger.error(f"Workflow {workflow_id} not found for evaluation completion")
                raise ClientException(f"Workflow {workflow_id} not found")

            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )

            # Define the keys required for evaluation completion
            keys_of_interest = [
                "experiment_id",
                "run_ids",
                "evaluation_id",
            ]

            # From workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                if db_workflow_step.data:
                    for key in keys_of_interest:
                        if key in db_workflow_step.data:
                            required_data[key] = db_workflow_step.data[key]

            logger.warning("Collected required data from workflow steps")

            # Get experiment details
            experiment_id = required_data.get("experiment_id")
            if not experiment_id:
                # Try to extract from stage_data if available
                for step in db_workflow_steps:
                    if step.data and "stage_data" in step.data:
                        stage_data = step.data["stage_data"]
                        if "experiment_id" in stage_data:
                            experiment_id = stage_data["experiment_id"]
                            break

            if not experiment_id:
                logger.error("Could not find experiment_id in workflow steps")
                raise ClientException("Experiment ID not found in workflow data")

            # Get the experiment
            experiment = self.session.get(ExperimentModel, experiment_id)
            if not experiment:
                logger.error(f"Experiment {experiment_id} not found")
                raise ClientException(f"Experiment {experiment_id} not found")

            # Extract evaluation results from payload
            evaluation_results = payload.content.result if payload.content and payload.content.result else {}
            evaluation_status = evaluation_results.get("status", "completed")

            # Update workflow step data with final status
            execution_status = {
                "status": "success" if evaluation_status == "completed" else "error",
                "message": f"Evaluation {evaluation_status}",
                "results": evaluation_results,
            }

            workflow_data = {}
            try:
                # Update runs if we have run information
                run_ids = required_data.get("run_ids", [])
                if run_ids:
                    for run_id in run_ids:
                        try:
                            run = self.session.get(RunModel, run_id)
                            if run:
                                run.status = (
                                    RunStatusEnum.COMPLETED.value
                                    if evaluation_status == "completed"
                                    else RunStatusEnum.FAILED.value
                                )
                                if hasattr(run, "evaluation_status"):
                                    run.evaluation_status = evaluation_status
                                if evaluation_results.get("scores"):
                                    run.scores = evaluation_results["scores"]
                        except Exception as e:
                            logger.error(f"Failed to update run {run_id}: {e}")

                    self.session.commit()
                    logger.info(f"Updated {len(run_ids)} runs with evaluation results")

                # Mark workflow as completed
                workflow_data = {"status": WorkflowStatusEnum.COMPLETED}

            except Exception as e:
                logger.exception(f"Failed to update evaluation results: {e}")
                execution_status.update(
                    {
                        "status": "error",
                        "message": f"Failed to update evaluation results: {str(e)}",
                    }
                )
                workflow_data = {
                    "status": WorkflowStatusEnum.FAILED,
                    "reason": str(e),
                }

            finally:
                # Update workflow step with execution status
                workflow_step_data = {
                    "workflow_execution_status": execution_status,
                    "experiment_id": str(experiment_id),
                }

                # Update current step number
                current_step_number = db_workflow.current_step + 1
                workflow_current_step = current_step_number

                # Update or create next workflow step
                db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
                    db_workflow.id, current_step_number, workflow_step_data
                )
                logger.warning(f"Updated workflow step {db_workflow_step.id} with evaluation completion status")

                # Update workflow
                workflow_data.update({"current_step": workflow_current_step})
                await WorkflowDataManager(self.session).update_by_fields(db_workflow, workflow_data)

                # Send success notification to workflow creator
                notification_request = (
                    NotificationBuilder()
                    .set_content(
                        title=experiment.name,
                        message=f"Evaluation {evaluation_status}",
                        icon=getattr(experiment, "icon", None),
                        result=NotificationResult(target_id=experiment.id, target_type="workflow").model_dump(
                            exclude_none=True, exclude_unset=True
                        ),
                    )
                    .set_payload(
                        workflow_id=str(db_workflow.id),
                        type=NotificationTypeEnum.EVALUATION_SUCCESS.value,
                    )
                    .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
                    .build()
                )
                await BudNotifyService().send_notification(notification_request)
                logger.info(f"Sent evaluation completion notification for experiment {experiment_id}")

        except Exception as e:
            logger.exception(f"Failed to handle evaluation completion event: {e}")
            raise ClientException(f"Failed to process evaluation completion: {str(e)}")
