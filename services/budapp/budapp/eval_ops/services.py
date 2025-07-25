import uuid
from typing import List, Optional, Tuple, cast

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import WorkflowTypeEnum
from budapp.commons.exceptions import ClientException
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
    CreateDatasetRequest,
    CreateExperimentRequest,
    DatasetFilter,
    ExperimentWorkflowResponse,
    ExperimentWorkflowStepData,
    ExperimentWorkflowStepRequest,
    TraitBasic,
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
from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.models import WorkflowStatusEnum
from budapp.workflow_ops.models import WorkflowStep as WorkflowStepModel


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
        """Create a new Experiment record with automatic run creation.

        Parameters:
            req (CreateExperimentRequest): Payload containing name, description, project_id, model_ids, dataset_ids.
            user_id (uuid.UUID): ID of the user creating the experiment.

        Returns:
            ExperimentSchema: Pydantic schema of the created Experiment.

        Raises:
            HTTPException(status_code=500): If database insertion fails.
        """
        ev = ExperimentModel(
            name=req.name,
            description=req.description,
            project_id=req.project_id,
            created_by=user_id,
            status="active",
            tags=req.tags or [],
        )
        try:
            self.session.add(ev)
            self.session.flush()  # Get the experiment ID without committing

            # Create runs for each model-dataset combination
            run_index = 1
            for model_id in req.model_ids:
                for dataset_id in req.dataset_ids:
                    # Note: Assuming dataset_id maps to a dataset_version_id
                    # You might need to query the latest version of the dataset here
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
                        experiment_id=ev.id,
                        run_index=run_index,
                        model_id=model_id,
                        dataset_version_id=dataset_version.id,
                        status=RunStatusEnum.PENDING.value,
                        config={},
                    )
                    self.session.add(run)
                    run_index += 1

            self.session.commit()
            self.session.refresh(ev)
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            logger.debug(f"Failed to create experiment: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create experiment"
            ) from e
        return ExperimentSchema.from_orm(ev)

    def list_experiments(self, user_id: uuid.UUID) -> List[ExperimentSchema]:
        """List all non-deleted Experiments for a given user.

        Parameters:
            user_id (uuid.UUID): ID of the user whose experiments to list.

        Returns:
            List[ExperimentSchema]: List of Pydantic schemas for each Experiment.

        Raises:
            HTTPException(status_code=500): If database query fails.
        """
        try:
            q = (
                self.session.query(ExperimentModel)
                .filter(
                    ExperimentModel.created_by == user_id,
                    ExperimentModel.status != "deleted",
                )
                .order_by(ExperimentModel.created_at.desc())
            )
            evs = q.all()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list experiments"
            ) from e
        return [ExperimentSchema.from_orm(e) for e in evs]

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found or access denied")
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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update experiment"
            ) from e
        return ExperimentSchema.from_orm(ev)

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found or access denied")
        ev.status = "deleted"
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete experiment"
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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list traits"
            ) from e

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found or access denied")

        runs = (
            self.session.query(RunModel)
            .filter(RunModel.experiment_id == experiment_id, RunModel.status != RunStatusEnum.DELETED.value)
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found or access denied")

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found or access denied")

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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update run"
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found or access denied")
        run.status = RunStatusEnum.DELETED.value
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete run"
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get dataset"
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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list datasets"
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
                            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Trait with ID {trait_id} not found"
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
            logger.debug(f"Failed to create dataset: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create dataset"
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

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
                            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Trait with ID {trait_id} not found"
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
            logger.debug(f"Failed to update dataset: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update dataset"
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete dataset"
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
    ) -> ExperimentWorkflowResponse:
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
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid step number. Must be between 1 and 5."
                )

            # Get or create workflow
            if request.workflow_id:
                # Continuing existing workflow
                workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                    WorkflowModel, {"id": request.workflow_id}
                )
                if not workflow:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
                workflow = cast(WorkflowModel, workflow)
                if workflow.created_by != current_user_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this workflow")
                if workflow.status != WorkflowStatusEnum.IN_PROGRESS:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow is not in progress")
            else:
                # Creating new workflow (step 1 only)
                if request.step_number != 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="workflow_id is required for steps 2-5"
                    )
                workflow = await WorkflowDataManager(self.session).insert_one(
                    WorkflowModel(
                        created_by=current_user_id,
                        workflow_type=WorkflowTypeEnum.EXPERIMENT_CREATION,
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
            experiment_id = None
            if request.step_number == 5 and request.trigger_workflow:
                experiment_id = await self._create_experiment_from_workflow(workflow.id, current_user_id)
                # Mark workflow as completed
                await WorkflowDataManager(self.session).update_by_fields(
                    workflow,
                    {"status": WorkflowStatusEnum.COMPLETED.value},  # type: ignore
                )

            # After storing the workflow step, retrieve all accumulated data
            all_step_data = await self._get_accumulated_step_data(workflow.id)

            # Determine if workflow is complete
            is_complete = (
                request.step_number == 5 and request.trigger_workflow
            ) or workflow.status == WorkflowStatusEnum.COMPLETED.value
            next_step = None if is_complete else request.step_number + 1

            # Prepare next step data only if not complete
            next_step_data = None
            if not is_complete and next_step is not None:
                next_step_data = await self._prepare_next_step_data(next_step, current_user_id)

            return ExperimentWorkflowResponse(
                code=status.HTTP_200_OK,
                object="experiment.workflow.step",
                message=f"Step {request.step_number} completed successfully",
                workflow_id=workflow.id,
                current_step=request.step_number,
                total_steps=request.workflow_total_steps,
                next_step=next_step,
                is_complete=is_complete,
                status=workflow.status,
                experiment_id=experiment_id,
                data=all_step_data,
                next_step_data=next_step_data,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Failed to process experiment workflow step: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process workflow step"
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
            required_fields = ["name", "project_id"]
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
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tags must be a list of strings"
                    )
                # Validate each tag is a string
                for tag in tags:
                    if not isinstance(tag, str):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Each tag must be a string"
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
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="trait_ids must be a list"
                )

            # Validate each trait_id is a valid UUID and exists in database
            for trait_id in trait_ids:
                try:
                    # Convert to UUID to validate format
                    trait_uuid = uuid.UUID(str(trait_id))
                except (ValueError, TypeError) as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid trait ID format: {trait_id}"
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
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="dataset_ids must be a list"
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
            WorkflowStepModel, {"workflow_id": workflow_id, "step_number": step_number}, missing_ok=True
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
                WorkflowStepModel(workflow_id=workflow_id, step_number=step_number, data=stage_data)
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
                    {"id": str(trait.id), "name": trait.name, "description": trait.description} for trait in traits
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

        # Create the experiment
        experiment = ExperimentModel(
            name=combined_data.name,
            description=combined_data.description,
            project_id=combined_data.project_id,
            created_by=current_user_id,
            status=ExperimentStatusEnum.ACTIVE.value,
            tags=combined_data.tags or [],
        )
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

    async def get_experiment_workflow_data(
        self, workflow_id: uuid.UUID, current_user_id: uuid.UUID
    ) -> ExperimentWorkflowResponse:
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
                WorkflowModel, {"id": workflow_id, "created_by": current_user_id}
            )
            if not workflow:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
            workflow = cast(WorkflowModel, workflow)

            # Get all accumulated step data
            all_step_data = await self._get_accumulated_step_data(workflow_id)

            # Determine completion state
            is_complete = workflow.current_step >= 5
            next_step = None if is_complete else workflow.current_step + 1

            # Prepare next step data if not complete
            next_step_data = None
            if not is_complete:
                next_step_data = await self._prepare_next_step_data(workflow.current_step + 1, current_user_id)

            return ExperimentWorkflowResponse(
                code=status.HTTP_200_OK,
                object="experiment.workflow.review",
                message="Workflow data retrieved successfully",
                workflow_id=workflow.id,
                current_step=workflow.current_step,
                total_steps=5,
                next_step=next_step,
                is_complete=is_complete,
                status=workflow.status,
                experiment_id=None,  # Will be populated when workflow is complete
                data=all_step_data,
                next_step_data=next_step_data,
            )

        except Exception as e:
            logger.error(f"Failed to get experiment workflow data: {e}")
            raise ClientException(f"Failed to retrieve workflow data: {str(e)}") from e
