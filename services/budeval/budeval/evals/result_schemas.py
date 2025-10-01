"""Data models for evaluation results."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PredictionItem(BaseModel):
    """Individual prediction with model output and gold answer."""

    example_abbr: str = Field(..., description="Unique identifier for this example")
    pred: List[str] = Field(..., description="Model prediction(s)")
    answer: List[str] = Field(..., description="Gold standard answer(s)")
    correct: List[bool] = Field(..., description="Whether prediction matches answer")
    origin_prompt: Optional[str] = Field(None, description="Original input prompt")
    prediction: Optional[str] = Field(None, description="Raw model prediction text")


class DatasetResult(BaseModel):
    """Results for a single dataset evaluation."""

    dataset_name: str = Field(..., description="Name of the evaluated dataset")
    accuracy: float = Field(..., description="Overall accuracy score")
    total_examples: int = Field(..., description="Total number of examples")
    correct_examples: int = Field(..., description="Number of correct predictions")
    predictions: List[PredictionItem] = Field(..., description="Individual predictions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional dataset metadata")


class EvaluationSummary(BaseModel):
    """Aggregated summary across all datasets."""

    overall_accuracy: float = Field(..., description="Average accuracy across all datasets")
    total_datasets: int = Field(..., description="Number of datasets evaluated")
    total_examples: int = Field(..., description="Total examples across all datasets")
    total_correct: int = Field(..., description="Total correct predictions across all datasets")
    dataset_accuracies: Dict[str, float] = Field(..., description="Accuracy per dataset")
    model_name: str = Field(..., description="Name of the evaluated model")


class OpenCompassOutputStructure(BaseModel):
    """Raw OpenCompass output directory structure."""

    timestamp_dir: str = Field(..., description="Timestamp directory name")
    configs_files: List[str] = Field(default_factory=list, description="Configuration files")
    prediction_files: Dict[str, str] = Field(default_factory=dict, description="Prediction files by dataset")
    result_files: Dict[str, str] = Field(default_factory=dict, description="Result files by dataset")
    summary_files: Dict[str, str] = Field(default_factory=dict, description="Summary files by format")
    log_files: Dict[str, List[str]] = Field(default_factory=dict, description="Log files by type")


class ProcessedEvaluationResults(BaseModel):
    """Complete processed evaluation results."""

    job_id: str = Field(..., description="Kubernetes job identifier")
    evaluation_id: Optional[str] = Field(None, description="Original evaluation request UUID")
    model_name: str = Field(..., description="Name of the evaluated model")
    engine: str = Field(..., description="Evaluation engine used")
    experiment_id: Optional[str] = Field(None, description="Experiment ID this evaluation belongs to")

    # Results
    datasets: List[DatasetResult] = Field(..., description="Results for each dataset")
    summary: EvaluationSummary = Field(..., description="Aggregated summary")

    # Raw output information
    raw_output: OpenCompassOutputStructure = Field(..., description="Raw OpenCompass output structure")

    # Metadata
    extracted_at: datetime = Field(..., description="When results were extracted")
    extraction_path: str = Field(..., description="Local path where files were extracted")
    output_pvc_name: str = Field(..., description="Name of the output PVC")

    # Job execution metadata
    job_start_time: Optional[datetime] = Field(None, description="When the job started")
    job_end_time: Optional[datetime] = Field(None, description="When the job completed")
    job_duration_seconds: Optional[float] = Field(None, description="Job execution duration")

    class Config:
        """Pydantic configuration for JSON encoding."""

        json_encoders = {datetime: lambda dt: dt.isoformat()}


class ResultsProcessingError(BaseModel):
    """Error information during results processing."""

    job_id: str = Field(..., description="Job ID that failed")
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    occurred_at: datetime = Field(..., description="When the error occurred")
    extraction_path: Optional[str] = Field(None, description="Path where extraction was attempted")

    class Config:
        """Pydantic configuration for JSON encoding."""

        json_encoders = {datetime: lambda dt: dt.isoformat()}
