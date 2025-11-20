# budapp/eval_ops/schemas.py

import re
from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_validator

from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse
from budapp.eval_ops.models import RunStatusEnum


# ------------------------ Summary Schemas for Experiments ------------------------


class ModelSummary(BaseModel):
    """Summary of a model used in an experiment."""

    id: UUID4 = Field(..., description="The UUID of the model.")
    name: str = Field(..., description="The name of the model.")
    deployment_name: Optional[str] = Field(None, description="The deployment name/namespace if deployed.")


class TraitSummary(BaseModel):
    """Summary of a trait associated with datasets in an experiment."""

    id: UUID4 = Field(..., description="The UUID of the trait.")
    name: str = Field(..., description="The name of the trait.")
    icon: Optional[str] = Field(None, description="The icon for the trait.")


class ExperimentModelListItem(BaseModel):
    """Model item for filtering experiments."""

    id: UUID4 = Field(..., description="The UUID of the model.")
    name: str = Field(..., description="The name of the model.")
    deployment_name: Optional[str] = Field(None, description="The deployment name/namespace if deployed.")
    experiment_count: int = Field(..., description="Number of experiments using this model.")


# ------------------------ New Experiment Detail Schemas ------------------------


class BudgetStats(BaseModel):
    """Budget statistics for an experiment."""

    limit_usd: float = Field(..., description="Budget limit in USD")
    used_usd: float = Field(..., description="Budget used in USD")
    used_pct: int = Field(..., description="Percentage of budget used")


class TokenStats(BaseModel):
    """Token statistics for an experiment."""

    total: int = Field(..., description="Total tokens")
    prefix: int = Field(..., description="Prefix tokens")
    decode: int = Field(..., description="Decode tokens")
    unit: str = Field(default="tokens", description="Unit of measurement")


class RuntimeStats(BaseModel):
    """Runtime statistics for an experiment."""

    active_seconds: int = Field(..., description="Active runtime in seconds")
    estimated_total_seconds: int = Field(..., description="Estimated total runtime in seconds")


class ProcessingRate(BaseModel):
    """Processing rate for an experiment."""

    current_per_min: int = Field(..., description="Current processing rate per minute")
    target_per_min: int = Field(..., description="Target processing rate per minute")


class ExperimentStats(BaseModel):
    """Combined statistics for an experiment."""

    budget: BudgetStats = Field(..., description="Budget statistics")
    tokens: TokenStats = Field(..., description="Token statistics")
    runtime: RuntimeStats = Field(..., description="Runtime statistics")
    processing_rate: ProcessingRate = Field(..., description="Processing rate statistics")


class JudgeInfo(BaseModel):
    """Judge information for evaluation metrics."""

    mode: str = Field(..., description="Judge mode (e.g., llm_as_judge)")
    model_name: str = Field(..., description="Name of the judge model")
    score_pct: int = Field(..., description="Score percentage")


class CurrentMetric(BaseModel):
    """Current metric for an evaluation."""

    evaluation: str | None = Field(..., description="Evaluation name")
    dataset: str | None = Field(..., description="Dataset name")
    deployment_name: str | None = Field(..., description="Deployment name")
    judge: Optional[JudgeInfo] = Field(None, description="Judge information")
    traits: List[str] | None = Field(..., description="List of traits")
    last_run_at: datetime | None = Field(..., description="Last run timestamp")
    run_id: str | None = Field(..., description="UUID of the latest run")


class ProgressDataset(BaseModel):
    """Dataset information in progress overview."""

    dataset_label: str = Field(..., description="Dataset label")


class ProgressInfo(BaseModel):
    """Progress information."""

    percent: int = Field(..., description="Progress percentage")
    completed: int = Field(..., description="Number of completed items")
    total: int = Field(..., description="Total number of items")


class ProgressActions(BaseModel):
    """Available actions for a run."""

    can_pause: bool = Field(..., description="Whether the run can be paused")
    pause_url: str = Field(..., description="URL to pause the run")


class ProgressOverview(BaseModel):
    """Progress overview for a run."""

    run_id: str = Field(..., description="UUID of the run")
    title: str = Field(..., description="Title of the progress overview")
    objective: str = Field(..., description="Objective of the run")
    current: ProgressDataset | None = Field(..., description="Current dataset being processed")
    progress: ProgressInfo | None = Field(..., description="Progress information")
    current_evaluation: str = Field(..., description="Current evaluation being performed")
    current_model: str = Field(..., description="Current model being evaluated")
    processing_rate_per_min: int = Field(..., description="Processing rate per minute")
    average_score_pct: float = Field(..., description="Average score percentage")
    eta_minutes: int = Field(..., description="Estimated time to completion in minutes")
    status: str = Field(..., description="Status of the run")
    actions: ProgressActions | None = Field(..., description="Available actions")


# ------------------------ Experiment Schemas ------------------------


class CreateExperimentRequest(BaseModel):
    """The request to create an experiment."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The name of the experiment.",
    )
    description: Optional[str] = Field(None, max_length=500, description="The description of the experiment.")
    project_id: Optional[UUID4] = Field(None, description="The project ID for the experiment (optional).")
    tags: Optional[List[str]] = Field(None, description="DEPRECATED: List of tag names. Use tag_ids instead.")
    tag_ids: Optional[List[UUID4]] = Field(None, description="List of EvalTag IDs to associate with experiment.")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate experiment name."""
        if not v or not v.strip():
            raise ValueError("Experiment name cannot be empty or only whitespace")

        # Strip leading/trailing whitespace
        v = v.strip()

        # Check length after stripping
        if len(v) < 1:
            raise ValueError("Experiment name must be at least 1 character long")
        if len(v) > 255:
            raise ValueError("Experiment name must not exceed 255 characters")

        # Validate allowed characters (alphanumeric, spaces, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9\s\-_]+$", v):
            raise ValueError("Experiment name can only contain letters, numbers, spaces, hyphens, and underscores")

        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate experiment description."""
        if v is not None:
            v = v.strip()
            if v and len(v) > 500:
                raise ValueError("Description must not exceed 500 characters")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags."""
        if v is not None:
            # Remove duplicates and strip whitespace
            cleaned_tags = []
            seen = set()
            for tag in v:
                if tag:
                    tag = tag.strip()
                    if tag and tag not in seen:
                        if len(tag) > 20:
                            raise ValueError(f"Tag '{tag}' exceeds 20 characters")
                        if not re.match(r"^[a-zA-Z0-9\-_]+$", tag):
                            raise ValueError(
                                f"Tag '{tag}' can only contain letters, numbers, hyphens, and underscores"
                            )
                        cleaned_tags.append(tag)
                        seen.add(tag)

            if len(cleaned_tags) > 10:
                raise ValueError("Maximum 10 tags allowed")

            return cleaned_tags if cleaned_tags else None
        return v


class Experiment(BaseModel):
    """Represents an experiment record."""

    id: UUID4 = Field(..., description="The UUID of the experiment.")
    name: str = Field(..., description="The name of the experiment.")
    description: Optional[str] = Field(None, description="The description of the experiment.")
    project_id: Optional[UUID4] = Field(None, description="The project ID for the experiment.")
    tags: Optional[List[str]] = Field(
        None,
        description="DEPRECATED: List of tag names. Use tag_objects instead.",
    )
    tag_ids: Optional[List[UUID4]] = Field(None, description="List of EvalTag IDs.")
    tag_objects: Optional[List["EvalTag"]] = Field(None, description="Complete tag objects with details.")
    status: Optional[str] = Field(
        None,
        description="Computed status based on runs (running/completed/no_runs).",
    )
    models: Optional[List[ModelSummary]] = Field(default_factory=list, description="Models used in the experiment.")
    traits: Optional[List[TraitSummary]] = Field(
        default_factory=list,
        description="Traits associated with the experiment.",
    )
    created_at: Optional[datetime] = Field(None, description="Timestamp when the experiment was created")
    # New fields for experiment detail
    stats: Optional[ExperimentStats] = Field(None, description="Experiment statistics")
    objective: Optional[str] = Field(None, description="Experiment objective")
    current_metrics: Optional[List[dict]] = Field(None, description="Current evaluation metrics")
    progress_overview: Optional[List[ProgressOverview]] = Field(None, description="Progress overview for runs")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class Evaluation(BaseModel):
    """Represents an evaluation record."""

    id: UUID4 = Field(..., description="The UUID of the evaluation.")
    experiment_id: UUID4 = Field(
        ...,
        description="The UUID of the experiment this evaluation belongs to.",
    )
    name: str = Field(..., description="The name of the evaluation.")
    description: Optional[str] = Field(None, description="The description of the evaluation.")
    workflow_id: Optional[UUID4] = Field(None, description="The workflow ID that created this evaluation.")
    created_by: UUID4 = Field(..., description="The UUID of the user who created this evaluation.")
    status: str = Field(..., description="The status of the evaluation.")
    trait_ids: Optional[List[str]] = Field(
        None,
        description="List of trait UUIDs (as strings) selected for this evaluation.",
    )
    created_at: Optional[datetime] = Field(None, description="Timestamp when the evaluation was created.")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp.")

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


class ListExperimentModelsResponse(SuccessResponse):
    """Response for listing models used in experiments."""

    models: List[ExperimentModelListItem] = Field(..., description="List of models used in experiments.")
    total_count: int = Field(..., description="Total number of unique models.")


# ------------------------ Run Schemas ------------------------


class Run(BaseModel):
    """Represents a run (model-dataset evaluation pair) within an experiment."""

    id: UUID4 = Field(..., description="The UUID of the run.")
    experiment_id: UUID4 = Field(..., description="The UUID of the parent experiment.")
    run_index: int = Field(..., description="Auto-incrementing index within the experiment.")
    endpoint_id: UUID4 = Field(..., description="The UUID of the endpoint being evaluated.")
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
    endpoint_id: UUID4 = Field(..., description="The UUID of the endpoint being evaluated.")

    dataset_version_id: UUID4 = Field(..., description="The UUID of the dataset version.")
    status: RunStatusEnum = Field(..., description="Current status of the run.")
    config: Optional[dict] = Field(None, description="Run-specific configuration.")
    metrics: List[dict] = Field([], description="List of metrics for this run.")
    raw_results: Optional[dict] = Field(None, description="Raw results for this run.")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class RunDetailedWithMetrics(BaseModel):
    """Run with complete dataset details, model details, and metrics."""

    id: UUID4 = Field(..., description="The UUID of the run.")
    experiment_id: UUID4 = Field(..., description="The UUID of the parent experiment.")
    run_index: int = Field(..., description="Auto-incrementing index within the experiment.")
    status: RunStatusEnum = Field(..., description="Current status of the run.")
    config: Optional[dict] = Field(None, description="Run-specific configuration.")

    # Model details
    model: Optional[dict] = Field(
        None,
        description="Complete model information including id, name, and deployment details.",
    )

    # Dataset details
    dataset: Optional[dict] = Field(None, description="Complete dataset information with version details.")

    # Metrics
    metrics: List[dict] = Field(
        [],
        description="List of metrics for this run with metric_name, mode, and metric_value.",
    )
    raw_results: Optional[dict] = Field(None, description="Raw results preview for this run.")

    # Timestamps
    created_at: Optional[datetime] = Field(None, description="Timestamp when the run was created.")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp.")

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

    endpoint_ids: List[UUID4] = Field(..., description="List of endpoint IDs to evaluate.")

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


# ------------------------ EvalTag Schemas ------------------------


class EvalTagBase(BaseModel):
    """Base schema for EvalTag."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Tag name (alphanumeric, hyphens, underscores)",
    )
    description: Optional[str] = Field(None, max_length=255, description="Tag description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate tag name format."""
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("Tag name can only contain letters, numbers, hyphens, and underscores")
        return v


class EvalTag(EvalTagBase):
    """Complete EvalTag schema with ID and timestamps."""

    id: UUID4 = Field(..., description="The UUID of the tag.")
    created_at: datetime = Field(..., description="Timestamp when the tag was created")
    modified_at: datetime = Field(..., description="Last modification timestamp")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class EvalTagCreate(BaseModel):
    """Schema for creating a new EvalTag."""

    name: str = Field(..., min_length=1, max_length=20, description="Tag name")
    description: Optional[str] = Field(None, max_length=255, description="Tag description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate tag name format."""
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("Tag name can only contain letters, numbers, hyphens, and underscores")
        return v


class EvalTagSearchResponse(SuccessResponse):
    """Response schema for tag search."""

    tags: List[EvalTag] = Field(..., description="List of matching tags")
    total: int = Field(..., description="Total number of matches")


class EvalTagListResponse(PaginatedSuccessResponse):
    """Response schema for listing tags with pagination."""

    tags: List[EvalTag] = Field(..., description="List of tags")


class CreateEvalTagResponse(SuccessResponse):
    """Response schema for creating a tag."""

    tag: EvalTag = Field(..., description="The created tag")


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
    eval_types: Optional[dict] = Field(
        None,
        description="Evaluation type configurations like {'gen': 'gsm8k_gen', 'agent': 'gsm8k_agent'}.",
    )
    why_run_this_eval: Optional[List[str]] = Field(
        None,
        description="List of reasons why running this evaluation is valuable and what insights it provides.",
    )
    what_to_expect: Optional[List[str]] = Field(
        None,
        description="List of expectations when evaluating this dataset, including patterns, trends, and characteristics.",
    )
    additional_info: Optional[dict] = Field(
        None,
        description="Additional metadata including top_5_task_types, top_5_domains, top_5_skills, top_5_concepts, top_5_qualifications, top_5_languages, age_distribution, and evaluation_description.",
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

    name: Optional[str] = Field(
        None, description="Search in dataset name and description (case-insensitive substring)."
    )
    modalities: Optional[List[str]] = Field(None, description="Filter by modalities.")
    language: Optional[List[str]] = Field(None, description="Filter by languages.")
    domains: Optional[List[str]] = Field(None, description="Filter by domains.")
    trait_ids: Optional[List[UUID4]] = Field(None, description="Filter by trait UUIDs.")
    has_gen_eval_type: Optional[bool] = Field(
        None,
        description="Filter datasets that have 'gen' key in eval_types. True to include only datasets with 'gen' key.",
    )


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
    endpoint_ids: Optional[List[UUID4]] = None

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


# ------------------------ Experiment Evaluation Schemas ------------------------


class ModelDetail(BaseModel):
    """Detailed model information for evaluations."""

    id: UUID4 = Field(..., description="Model UUID")
    name: str = Field(..., description="Model name")
    deployment_name: Optional[str] = Field(None, description="Deployment name/namespace if deployed")


class DatasetInfo(BaseModel):
    """Basic dataset information."""

    id: UUID4 = Field(..., description="Dataset UUID")
    name: str = Field(..., description="Dataset name")
    version: str = Field(..., description="Dataset version")
    description: Optional[str] = Field(None, description="Dataset description")


class TraitWithDatasets(BaseModel):
    """Trait information with associated datasets."""

    id: UUID4 = Field(..., description="Trait UUID")
    name: str = Field(..., description="Trait name")
    icon: Optional[str] = Field(None, description="Trait icon")
    datasets: List[DatasetInfo] = Field(default_factory=list, description="Datasets associated with this trait")


class EvaluationScore(BaseModel):
    """Evaluation score information from BudEval."""

    status: str = Field(
        ...,
        description="Evaluation job status (pending/running/completed/failed)",
    )
    overall_accuracy: Optional[float] = Field(None, description="Overall accuracy percentage (0-100)")
    datasets: Optional[List[dict]] = Field(None, description="Individual dataset scores")


class RunWithEvaluations(BaseModel):
    """Run information with evaluation details and scores."""

    run_id: UUID4 = Field(..., description="Run UUID")
    run_index: int = Field(..., description="Run index within experiment")
    status: str = Field(..., description="Run status")
    model: ModelDetail = Field(..., description="Model details")
    traits: List[TraitWithDatasets] = Field(..., description="Traits with their associated datasets")
    evaluation_job_id: Optional[str] = Field(None, description="BudEval job ID if evaluation was triggered")
    scores: Optional[EvaluationScore] = Field(None, description="Evaluation scores from BudEval")
    created_at: Optional[datetime] = Field(None, description="Run creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Run update timestamp")


class ExperimentEvaluationsResponse(SuccessResponse):
    """Response for getting experiment evaluations with scores."""

    experiment: Experiment = Field(..., description="Experiment information")
    evaluations: List[RunWithEvaluations] = Field(..., description="List of runs with evaluation details")


# ------------------------ Evaluation Listing Schemas ------------------------


class RunDatasetScore(BaseModel):
    """Individual run with dataset and score."""

    run_id: UUID4 = Field(..., description="UUID of the run")
    dataset_name: str = Field(..., description="Name of the dataset")
    score: Optional[float] = Field(None, description="Score for this run")


class EvaluationListItem(BaseModel):
    """A single evaluation with its runs."""

    evaluation_id: UUID4 = Field(..., description="UUID of the evaluation")
    evaluation_name: str = Field(..., description="Name of the evaluation")
    model_name: str = Field(..., description="Name of the model used")
    deployment_name: Optional[str] = Field(None, description="Deployment/endpoint name")
    started_date: datetime = Field(..., description="When evaluation started")
    duration_minutes: int = Field(..., description="Duration in minutes")
    status: str = Field(
        ...,
        description="Status (pending/running/completed/failed)",
    )
    runs: List[RunDatasetScore] = Field(default_factory=list, description="Runs with dataset scores")


class ListEvaluationsResponse(SuccessResponse):
    """Response schema for listing completed evaluations."""

    evaluations: List[EvaluationListItem] = Field(..., description="List of completed evaluations")


# ------------------------ Run History Schemas ------------------------


class BenchmarkScore(BaseModel):
    """Benchmark score for a run."""

    name: str = Field(..., description="Benchmark name")
    score: str = Field(..., description="Benchmark score")


class RunHistoryItem(BaseModel):
    """A single item in run history."""

    run_id: str = Field(..., description="UUID of the run")
    model: str = Field(..., description="Model name")
    status: str = Field(..., description="Run status")
    started_at: datetime = Field(..., description="Run start timestamp")
    duration_seconds: int = Field(..., description="Run duration in seconds")
    benchmarks: List[BenchmarkScore] = Field(..., description="List of benchmark scores")


class SortInfo(BaseModel):
    """Sorting information for run history."""

    field: str = Field(..., description="Field to sort by")
    direction: str = Field(..., description="Sort direction (asc/desc)")


class RunHistoryData(BaseModel):
    """Run history data with pagination."""

    total: int = Field(..., description="Total number of runs")
    items: List[RunHistoryItem] = Field(..., description="List of run history items")
    sort: SortInfo = Field(..., description="Sorting information")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")


class RunHistoryResponse(SuccessResponse):
    """Response for run history endpoint."""

    runs_history: RunHistoryData = Field(..., description="Run history data")


class ExperimentSummary(BaseModel):
    """Summary statistics for an experiment."""

    total_runs: int = Field(..., description="Total number of runs in the experiment")
    total_duration_seconds: int = Field(..., description="Total duration of all evaluations in seconds")
    completed_runs: int = Field(..., description="Number of completed runs")
    failed_runs: int = Field(..., description="Number of failed runs")
    pending_runs: int = Field(..., description="Number of pending runs")
    running_runs: int = Field(..., description="Number of currently running runs")


class ExperimentSummaryResponse(SuccessResponse):
    """Response for experiment summary endpoint."""

    summary: ExperimentSummary = Field(..., description="Experiment summary data")
