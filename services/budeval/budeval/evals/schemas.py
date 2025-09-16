"""Simplified schemas for OpenCompass evaluation requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase
from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Supported model types."""

    API = "api"


class Dataset(BaseModel):
    """Dataset configuration for evaluation."""

    name: str = Field(..., description="Dataset name (e.g., 'mmlu', 'gsm8k')")


class ModelConfig(BaseModel):
    """Model configuration for OpenCompass evaluation."""

    name: str = Field(..., description="Model name/identifier")
    api_key: str = Field(..., description="API key for the model")
    base_url: str = Field(..., description="Base URL for the API")
    type: ModelType = Field(default=ModelType.API, description="Model type")

    # OpenCompass specific parameters
    max_out_len: int = Field(default=2048, description="Maximum output length")
    max_seq_len: int = Field(default=4096, description="Maximum sequence length")
    batch_size: int = Field(default=1, description="Batch size for evaluation")
    query_per_second: int = Field(default=1, description="Rate limiting")


class EvaluationRequest(CloudEventBase):
    """Request to start an evaluation."""

    eval_request_id: UUID = Field(..., description="Unique evaluation ID")
    experiment_id: UUID | None = Field(None, description="Associated experiment ID")

    model: ModelConfig = Field(..., description="Model configuration")
    datasets: List[Dataset] = Field(..., description="Datasets to evaluate on")

    # Kubernetes configuration
    namespace: str = Field(default="budeval", description="K8s namespace")
    kubeconfig: str | None = Field(None, description="Kubeconfig as JSON string")

    # Execution parameters
    num_workers: int = Field(default=1, description="Number of parallel workers")
    timeout_minutes: int = Field(default=60, description="Job timeout")
    debug: bool = Field(default=False, description="Enable debug mode")


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: JobStatus
    message: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float | None = None


class DatasetScore(BaseModel):
    """Score for a single dataset."""

    dataset_name: str
    accuracy: float = Field(..., description="Accuracy score (0-100)")
    total_examples: int
    correct_examples: int


class EvaluationResults(BaseModel):
    """Complete evaluation results."""

    job_id: str
    model_name: str
    experiment_id: str | None = None

    overall_accuracy: float
    datasets: List[DatasetScore]

    start_time: datetime
    end_time: datetime
    duration_seconds: float

    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationJobRecord(BaseModel):
    """Schema describing a single row from budeval.evaluation_jobs."""

    job_id: str
    experiment_id: str | None = None
    model_name: str
    engine: str
    status: str | None = None
    job_start_time: datetime | None = None
    job_end_time: datetime | None = None
    job_duration_seconds: float | None = None
    overall_accuracy: float | None = None
    total_datasets: int | None = None
    total_examples: int | None = None
    total_correct: int | None = None
    extracted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# Legacy compatibility schemas for existing APIs
class EvalModelInfo(BaseModel):
    """Legacy model info structure for backward compatibility."""

    model_name: str
    endpoint: str
    api_key: str
    extra_args: Dict[str, Any] = Field(default_factory=dict)


class EvalDataset(BaseModel):
    """Legacy dataset structure for backward compatibility."""

    dataset_id: str


class LegacyEvaluationRequest(BaseModel):
    """Legacy evaluation request format for backward compatibility."""

    uuid: UUID
    experiment_id: UUID | None = None
    eval_model_info: EvalModelInfo
    eval_datasets: List[EvalDataset]
    kubeconfig: str | None = None

    def to_new_format(self) -> EvaluationRequest:
        """Convert legacy format to new simplified format."""
        return EvaluationRequest(
            eval_request_id=self.uuid,
            experiment_id=self.experiment_id,
            model=ModelConfig(
                name=self.eval_model_info.model_name,
                api_key=self.eval_model_info.api_key,
                base_url=self.eval_model_info.endpoint,
                **self.eval_model_info.extra_args,
            ),
            datasets=[Dataset(name=d.dataset_id) for d in self.eval_datasets],
            kubeconfig=self.kubeconfig,
        )
