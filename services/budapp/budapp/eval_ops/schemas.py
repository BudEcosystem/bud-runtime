# budapp/eval_ops/schemas.py

from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field

from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse
from budapp.eval_ops.models import RunStatusEnum


# ------------------------ Experiment Schemas ------------------------


class CreateExperimentRequest(BaseModel):
    """The request to create an experiment."""

    name: str = Field(..., description="The name of the experiment.")
    description: Optional[str] = Field(None, description="The description of the experiment.")
    project_id: UUID4 = Field(..., description="The project ID for the experiment.")
    tags: Optional[List[str]] = Field(None, description="List of tags for the experiment.")


class Experiment(BaseModel):
    """Represents an experiment record."""

    id: UUID4 = Field(..., description="The UUID of the experiment.")
    name: str = Field(..., description="The name of the experiment.")
    description: Optional[str] = Field(None, description="The description of the experiment.")
    project_id: UUID4 = Field(..., description="The project ID for the experiment.")
    tags: Optional[List[str]] = Field(None, description="List of tags for the experiment.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class CreateExperimentResponse(SuccessResponse):
    """The response to create an experiment."""

    experiment: Experiment = Field(..., description="The created experiment.")


class ListExperimentsResponse(PaginatedSuccessResponse):
    """The response to list experiments with pagination."""

    experiments: List[Experiment] = Field(..., description="The experiments.")


class UpdateExperimentRequest(BaseModel):
    """Request schema to update an experiment."""

    name: Optional[str] = Field(None, description="The name of the experiment.")
    description: Optional[str] = Field(None, description="The description of the experiment.")


class UpdateExperimentResponse(SuccessResponse):
    """Response schema for updating an experiment."""

    experiment: Experiment = Field(..., description="The updated experiment.")


class GetExperimentResponse(SuccessResponse):
    """Response schema for getting an experiment by ID."""

    experiment: Experiment = Field(..., description="The requested experiment.")


class DeleteExperimentResponse(SuccessResponse):
    """Response schema for deleting an experiment."""

    pass


# ------------------------ Run Schemas ------------------------


class Run(BaseModel):
    """Represents a run (model-dataset evaluation pair) within an experiment."""

    id: UUID4 = Field(..., description="The UUID of the run.")
    experiment_id: UUID4 = Field(..., description="The UUID of the parent experiment.")
    run_index: int = Field(..., description="Auto-incrementing index within the experiment.")
    model_id: UUID4 = Field(..., description="The UUID of the model being evaluated.")
    dataset_version_id: UUID4 = Field(..., description="The UUID of the dataset version.")
    status: RunStatusEnum = Field(..., description="Current status of the run.")
    config: Optional[dict] = Field(None, description="Run-specific configuration.")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the run was created.")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the run was last updated.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class RunWithResults(BaseModel):
    """Run with metrics and results included."""

    id: UUID4 = Field(..., description="The UUID of the run.")
    experiment_id: UUID4 = Field(..., description="The UUID of the parent experiment.")
    run_index: int = Field(..., description="Auto-incrementing index within the experiment.")
    model_id: UUID4 = Field(..., description="The UUID of the model being evaluated.")
    dataset_version_id: UUID4 = Field(..., description="The UUID of the dataset version.")
    status: RunStatusEnum = Field(..., description="Current status of the run.")
    config: Optional[dict] = Field(None, description="Run-specific configuration.")
    metrics: List[dict] = Field([], description="List of metrics for this run.")
    raw_results: Optional[dict] = Field(None, description="Raw results for this run.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class ListRunsResponse(SuccessResponse):
    """Response schema for listing runs."""

    runs: List[Run] = Field(..., description="List of runs.")


class GetRunResponse(SuccessResponse):
    """Response schema for getting a single run."""

    run: RunWithResults = Field(..., description="The run with results.")


class UpdateRunRequest(BaseModel):
    """Request to update a run."""

    status: Optional[RunStatusEnum] = Field(None, description="New status of the run.")
    config: Optional[dict] = Field(None, description="Updated configuration for the run.")


class UpdateRunResponse(SuccessResponse):
    """Response after updating a run."""

    run: Run = Field(..., description="The updated run.")


class DeleteRunResponse(SuccessResponse):
    """Response schema for deleting a run."""

    pass


# ------------------------ Configure Runs Schemas ------------------------


class ConfigureRunsRequest(BaseModel):
    """Request to configure runs for an experiment."""

    model_ids: List[UUID4] = Field(..., description="List of model IDs to evaluate.")
    dataset_ids: List[UUID4] = Field(..., description="List of dataset IDs to evaluate against.")
    evaluation_config: Optional[dict] = Field(None, description="Default evaluation configuration for runs.")


class ConfigureRunsResponse(SuccessResponse):
    """Response after configuring runs for an experiment."""

    runs: List[Run] = Field(..., description="List of created runs.")
    total_runs: int = Field(..., description="Total number of runs created.")


# ------------------------ Dataset Schemas (Keep existing) ------------------------


class DatasetBasic(BaseModel):
    """Basic dataset information for trait responses."""

    id: UUID4 = Field(..., description="The UUID of the dataset.")
    name: str = Field(..., description="The name of the dataset.")
    description: Optional[str] = Field(None, description="The description of the dataset.")
    estimated_input_tokens: Optional[int] = Field(None, description="Estimated input tokens.")
    estimated_output_tokens: Optional[int] = Field(None, description="Estimated output tokens.")
    modalities: Optional[List[str]] = Field(None, description="List of modalities.")
    sample_questions_answers: Optional[dict] = Field(None, description="Sample questions and answers in JSON format.")
    advantages_disadvantages: Optional[dict] = Field(
        None,
        description="Advantages and disadvantages with structure {'advantages': ['str1'], 'disadvantages': ['str2']}.",
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


# ------------------------ Trait Schemas ------------------------


class TraitBasic(BaseModel):
    """Basic trait information for lightweight listing."""

    id: UUID4 = Field(..., description="The UUID of the trait.")
    name: str = Field(..., description="The name of the trait.")
    description: Optional[str] = Field(None, description="The description of the trait.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class Trait(BaseModel):
    """A trait that experiments can be grouped by."""

    id: UUID4 = Field(..., description="The UUID of the trait.")
    name: str = Field(..., description="The name of the trait.")
    description: Optional[str] = Field(None, description="The description of the trait.")
    category: Optional[str] = Field(None, description="Optional category metadata.")
    exps_ids: List[UUID4] = Field([], description="Optional list of experiment UUIDs.")
    datasets: List[DatasetBasic] = Field([], description="List of datasets associated with this trait.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class ListTraitsResponse(SuccessResponse):
    """The response schema for listing traits."""

    traits: List[TraitBasic] = Field(..., description="The traits.")
    total_record: int = Field(..., description="Total number of traits matching the query.")
    page: int = Field(..., description="Current page number.")
    limit: int = Field(..., description="Number of traits per page.")


class ExpDataset(BaseModel):
    """Represents an evaluation dataset with traits."""

    id: UUID4 = Field(..., description="The UUID of the dataset.")
    name: str = Field(..., description="The name of the dataset.")
    description: Optional[str] = Field(None, description="The description of the dataset.")
    meta_links: Optional[dict] = Field(None, description="Links to GitHub, paper, website, etc.")
    config_validation_schema: Optional[dict] = Field(None, description="Configuration validation schema.")
    estimated_input_tokens: Optional[int] = Field(None, description="Estimated input tokens.")
    estimated_output_tokens: Optional[int] = Field(None, description="Estimated output tokens.")
    language: Optional[List[str]] = Field(None, description="Languages supported by the dataset.")
    domains: Optional[List[str]] = Field(None, description="Domains covered by the dataset.")
    concepts: Optional[List[str]] = Field(None, description="Concepts covered by the dataset.")
    humans_vs_llm_qualifications: Optional[List[str]] = Field(None, description="Human vs LLM qualifications.")
    task_type: Optional[List[str]] = Field(None, description="Types of tasks in the dataset.")
    modalities: Optional[List[str]] = Field(
        None,
        description="List of modalities. Allowed values: 'text' (Textual data), 'image' (Image data), 'video' (Video data)",
    )
    sample_questions_answers: Optional[dict] = Field(None, description="Sample questions and answers in JSON format.")
    advantages_disadvantages: Optional[dict] = Field(
        None,
        description="Advantages and disadvantages with structure {'advantages': ['str1'], 'disadvantages': ['str2']}.",
    )
    traits: List[Trait] = Field([], description="Traits associated with this dataset.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class GetDatasetResponse(SuccessResponse):
    """Response schema for getting a dataset by ID."""

    dataset: ExpDataset = Field(..., description="The dataset with traits information.")


class ListDatasetsResponse(SuccessResponse):
    """Response schema for listing datasets."""

    datasets: List[ExpDataset] = Field(..., description="List of datasets with traits.")
    total_record: int = Field(..., description="Total number of datasets matching the query.")
    page: int = Field(..., description="Current page number.")
    limit: int = Field(..., description="Number of datasets per page.")


class DatasetFilter(BaseModel):
    """Filter parameters for dataset listing."""

    name: Optional[str] = Field(None, description="Filter by dataset name (case-insensitive substring).")
    modalities: Optional[List[str]] = Field(None, description="Filter by modalities.")
    language: Optional[List[str]] = Field(None, description="Filter by languages.")
    domains: Optional[List[str]] = Field(None, description="Filter by domains.")
    trait_ids: Optional[List[UUID4]] = Field(None, description="Filter by trait UUIDs.")


class CreateDatasetRequest(BaseModel):
    """Request schema for creating a new dataset."""

    name: str = Field(..., description="The name of the dataset.")
    description: Optional[str] = Field(None, description="The description of the dataset.")
    meta_links: Optional[dict] = Field(None, description="Links to GitHub, paper, website, etc.")
    config_validation_schema: Optional[dict] = Field(None, description="Configuration validation schema.")
    estimated_input_tokens: Optional[int] = Field(None, description="Estimated input tokens.")
    estimated_output_tokens: Optional[int] = Field(None, description="Estimated output tokens.")
    language: Optional[List[str]] = Field(None, description="Languages supported by the dataset.")
    domains: Optional[List[str]] = Field(None, description="Domains covered by the dataset.")
    concepts: Optional[List[str]] = Field(None, description="Concepts covered by the dataset.")
    humans_vs_llm_qualifications: Optional[List[str]] = Field(None, description="Human vs LLM qualifications.")
    task_type: Optional[List[str]] = Field(None, description="Types of tasks in the dataset.")
    modalities: Optional[List[str]] = Field(
        None,
        description="List of modalities. Allowed values: 'text' (Textual data), 'image' (Image data), 'video' (Video data)",
    )
    sample_questions_answers: Optional[dict] = Field(None, description="Sample questions and answers in JSON format.")
    advantages_disadvantages: Optional[dict] = Field(
        None,
        description="Advantages and disadvantages with structure {'advantages': ['str1'], 'disadvantages': ['str2']}.",
    )
    trait_ids: Optional[List[UUID4]] = Field([], description="List of trait IDs to associate with the dataset.")


class UpdateDatasetRequest(BaseModel):
    """Request schema for updating a dataset."""

    name: Optional[str] = Field(None, description="The name of the dataset.")
    description: Optional[str] = Field(None, description="The description of the dataset.")
    meta_links: Optional[dict] = Field(None, description="Links to GitHub, paper, website, etc.")
    config_validation_schema: Optional[dict] = Field(None, description="Configuration validation schema.")
    estimated_input_tokens: Optional[int] = Field(None, description="Estimated input tokens.")
    estimated_output_tokens: Optional[int] = Field(None, description="Estimated output tokens.")
    language: Optional[List[str]] = Field(None, description="Languages supported by the dataset.")
    domains: Optional[List[str]] = Field(None, description="Domains covered by the dataset.")
    concepts: Optional[List[str]] = Field(None, description="Concepts covered by the dataset.")
    humans_vs_llm_qualifications: Optional[List[str]] = Field(None, description="Human vs LLM qualifications.")
    task_type: Optional[List[str]] = Field(None, description="Types of tasks in the dataset.")
    modalities: Optional[List[str]] = Field(
        None,
        description="List of modalities. Allowed values: 'text' (Textual data), 'image' (Image data), 'video' (Video data)",
    )
    sample_questions_answers: Optional[dict] = Field(None, description="Sample questions and answers in JSON format.")
    advantages_disadvantages: Optional[dict] = Field(
        None,
        description="Advantages and disadvantages with structure {'advantages': ['str1'], 'disadvantages': ['str2']}.",
    )
    trait_ids: Optional[List[UUID4]] = Field(None, description="List of trait IDs to associate with the dataset.")


class CreateDatasetResponse(SuccessResponse):
    """Response schema for creating a dataset."""

    dataset: ExpDataset = Field(..., description="The created dataset with traits information.")


class UpdateDatasetResponse(SuccessResponse):
    """Response schema for updating a dataset."""

    dataset: ExpDataset = Field(..., description="The updated dataset with traits information.")


class DeleteDatasetResponse(SuccessResponse):
    """Response schema for deleting a dataset."""

    pass


# ------------------------ Experiment Workflow Schemas ------------------------


class ExperimentWorkflowStepRequest(BaseModel):
    """Base request for experiment workflow steps."""

    workflow_id: Optional[UUID4] = Field(None, description="Workflow ID for continuing existing workflow")
    step_number: int = Field(..., description="Current step number (1-5)")
    workflow_total_steps: int = Field(default=5, description="Total steps in workflow")
    trigger_workflow: bool = Field(default=False, description="Whether to trigger workflow completion")
    stage_data: dict = Field(..., description="Stage-specific data")


class ExperimentWorkflowResponse(SuccessResponse):
    """Response for experiment workflow steps."""

    workflow_id: UUID4 = Field(..., description="Workflow ID")
    current_step: int = Field(..., description="Current step number")
    total_steps: int = Field(..., description="Total steps")
    next_step: Optional[int] = Field(None, description="Next step number (null if complete)")
    is_complete: bool = Field(..., description="Whether workflow is complete")
    status: str = Field(..., description="Workflow status")
    experiment_id: Optional[UUID4] = Field(None, description="Created experiment ID (only on completion)")
    data: Optional[dict] = Field(None, description="Accumulated data from all completed steps")
    next_step_data: Optional[dict] = Field(None, description="Data for next step (e.g., available models/traits)")


class ExperimentWorkflowStepData(BaseModel):
    """Combined data from all workflow steps."""

    # Step 1 data - Basic Info
    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[UUID4] = None
    tags: Optional[List[str]] = None

    # Step 2 data - Model Selection
    model_ids: Optional[List[UUID4]] = None

    # Step 3 data - Traits Selection
    trait_ids: Optional[List[UUID4]] = None
    dataset_ids: Optional[List[UUID4]] = None

    # Step 4 data - Performance Point
    performance_point: Optional[int] = Field(None, ge=0, le=100, description="Performance point value between 0-100")


# ------------------------ Evaluation Workflow Schemas ------------------------


class EvaluationWorkflowStepRequest(BaseModel):
    """Base request for evaluation workflow steps."""

    workflow_id: Optional[UUID4] = Field(None, description="Workflow ID (required for steps 2-5)")
    step_number: int = Field(..., description="Current step number (1-5)", ge=1, le=5)
    workflow_total_steps: int = Field(default=5, description="Total steps in workflow")
    trigger_workflow: bool = Field(default=False, description="Whether to trigger workflow completion")
    stage_data: dict = Field(..., description="Step-specific data")


class EvaluationWorkflowResponse(SuccessResponse):
    """Response for evaluation workflow steps."""

    workflow_id: UUID4 = Field(..., description="Workflow ID")
    current_step: int = Field(..., description="Current step number")
    total_steps: int = Field(..., description="Total steps in workflow")
    is_complete: bool = Field(..., description="Whether workflow is complete")
    next_step: Optional[int] = Field(None, description="Next step number (null if complete)")
    next_step_data: Optional[dict] = Field(None, description="Data for next step")
    status: str = Field(..., description="Workflow status")
    runs_created: Optional[int] = Field(None, description="Number of runs created (only on completion)")
    data: Optional[dict] = Field(None, description="Accumulated workflow data from all steps")


# Step-specific schemas for evaluation workflow
class EvaluationBasicInfoData(BaseModel):
    """Step 1: Basic information for evaluation."""

    name: str = Field(..., description="Evaluation name")
    description: Optional[str] = Field(None, description="Evaluation description")


class EvaluationTraitsData(BaseModel):
    """Step 2: Trait selection for evaluation."""

    trait_ids: List[UUID4] = Field(..., description="Selected trait IDs")


class EvaluationDatasetsData(BaseModel):
    """Step 3: Dataset selection for evaluation."""

    dataset_ids: List[UUID4] = Field(..., description="Selected dataset IDs")

    # Step 5 data - Finalization
    run_name: Optional[str] = None
    run_description: Optional[str] = None
    evaluation_config: Optional[dict] = None
