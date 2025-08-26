from typing import Any, Dict, List, Optional
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase
from pydantic import BaseModel, Field

from budeval.core.schemas import EvaluationEngine


# Sub-schemas for nested structure
class EvalModelInfo(BaseModel):
    """Model information for evaluation."""

    model_name: str = Field(..., description="Name of the model to be evaluated")
    endpoint: str = Field(..., description="Endpoint of the model to be evaluated")
    api_key: str = Field(..., description="API key for authentication")
    extra_args: Dict[str, Any] = Field(default_factory=dict, description="Extra arguments for the model")


class EvalDataset(BaseModel):
    """Dataset information for evaluation."""

    dataset_id: str = Field(..., description="ID of the dataset to be evaluated")


class EvalConfig(BaseModel):
    """Configuration for evaluation."""

    config_name: str = Field(..., description="Name of the evaluation configuration")
    config_value: Dict[str, Any] = Field(..., description="Value of the evaluation configuration")


class EvaluationRequest(CloudEventBase):
    """Schema for evaluation request with nested structure."""

    # Using uuid as primary identifier to match bud-eval
    uuid: UUID = Field(..., description="Unique identifier for the evaluation request")

    # Experiment ID to track evaluation back to experiment
    experiment_id: Optional[UUID] = Field(None, description="The experiment ID this evaluation belongs to")

    # Nested model info structure
    eval_model_info: EvalModelInfo = Field(..., description="Model information for evaluation")

    # Structured datasets instead of simple strings
    eval_datasets: List[EvalDataset] = Field(..., description="Evaluation datasets")

    # New field for evaluation configurations
    eval_configs: List[EvalConfig] = Field(default_factory=list, description="Evaluation configurations")

    # Keep engine field for compatibility
    engine: EvaluationEngine = Field(default=EvaluationEngine.OPENCOMPASS, description="Evaluation engine to use")

    # Kubeconfig remains optional
    kubeconfig: Optional[str] = Field(
        None, description="Kubernetes configuration JSON content (optional, uses local config if not provided)"
    )

    class Config:  # noqa
        json_schema_extra = {
            "example": {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "experiment_id": "987f6543-e89b-12d3-a456-426614174000",
                "engine": "opencompass",
                "eval_model_info": {
                    "model_name": "gpt-4",
                    "endpoint": "https://api.openai.com/v1",
                    "api_key": "sk-...",
                    "extra_args": {},
                },
                "eval_datasets": [{"dataset_id": "mmlu"}, {"dataset_id": "gsm8k"}],
                "eval_configs": [],
                "kubeconfig": "<Kubernetes config JSON content>",
            }
        }


# Workflow Schemas
class StartEvaluationRequest(CloudEventBase):
    """Schema for start evaluation request - matches EvaluationRequest structure."""

    # Using uuid as primary identifier to match bud-eval
    uuid: UUID = Field(..., description="Unique identifier for the evaluation request")

    # Experiment ID to track evaluation back to experiment
    experiment_id: Optional[UUID] = Field(None, description="The experiment ID this evaluation belongs to")

    # Nested model info structure
    eval_model_info: EvalModelInfo = Field(..., description="Model information for evaluation")

    # Structured datasets instead of simple strings
    eval_datasets: List[EvalDataset] = Field(..., description="Evaluation datasets")

    # New field for evaluation configurations
    eval_configs: List[EvalConfig] = Field(default_factory=list, description="Evaluation configurations")

    # Keep engine field for compatibility
    engine: EvaluationEngine = Field(default=EvaluationEngine.OPENCOMPASS, description="Evaluation engine to use")

    # Kubeconfig remains optional
    kubeconfig: Optional[str] = Field(
        None, description="Kubernetes configuration JSON content (optional, uses local config if not provided)"
    )

    class Config:  # noqa
        json_schema_extra = {
            "example": {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "experiment_id": "987f6543-e89b-12d3-a456-426614174000",
                "engine": "opencompass",
                "eval_model_info": {
                    "model_name": "gpt-4",
                    "endpoint": "https://api.openai.com/v1",
                    "api_key": "sk-...",
                    "extra_args": {},
                },
                "eval_datasets": [{"dataset_id": "mmlu"}, {"dataset_id": "gsm8k"}],
                "eval_configs": [],
                "kubeconfig": "<Kubernetes config JSON content>",
            }
        }


class DeployEvalJobRequest(BaseModel):
    """Schema for deploy evaluation job request."""

    engine: str = Field(..., description="Engine to use for the evaluation job")
    eval_request_id: str = Field(..., description="Unique identifier for the job")
    kubeconfig: Optional[str] = Field(
        None, description="Kubernetes configuration JSON content (optional, uses local config if not provided)"
    )
    api_key: str = Field(..., description="API key for authentication")
    base_url: str = Field(..., description="Base URL for the model API")
    dataset: List[str] = Field(..., description="Datasets to evaluate on")

    class Config:  # noqa
        json_schema_extra = {
            "example": {
                "engine": "OpenCompass",
                "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "api_key": "sk-...",
                "base_url": "https://api.openai.com/v1",
                "kubeconfig": "<Kubernetes config JSON content>",
                "dataset": ["dataset1"],
            }
        }


# Job Schemas
class VolumeMount(BaseModel):
    name: str = Field(..., description="Name of the volume")
    claim_name: str = Field(..., description="Name of the PVC to use")
    mount_path: str = Field(..., description="Path to mount in the container")


class Job(BaseModel):
    # Existing fields...

    # Volume mount configurations
    read_only_mounts: Optional[List[VolumeMount]] = Field(None, description="Read-only volume mounts for the job")
    writable_mounts: Optional[List[VolumeMount]] = Field(None, description="Writable volume mounts for the job")

    class Config:  # noqa
        schema_extra = {
            "example": {
                # Existing example fields...
                "read_only_mounts": [
                    {"name": "datasets-volume", "claim_name": "datasets-pvc", "mount_path": "/data/datasets"}
                ],
                "writable_mounts": [
                    {"name": "results-volume", "claim_name": "results-pvc", "mount_path": "/data/results"}
                ],
            }
        }
