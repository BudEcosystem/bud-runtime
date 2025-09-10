"""Generic evaluation schemas that are engine-agnostic."""

from enum import Enum
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field

from budeval.commons.storage_config import StorageConfig


class EvaluationEngine(str, Enum):
    """Supported evaluation engines."""

    OPENCOMPASS = "opencompass"


class ModelType(str, Enum):
    """Types of models supported."""

    API = "api"  # API-based models (OpenAI, Anthropic, etc.)
    LOCAL = "local"  # Local models (HuggingFace, etc.)
    CUSTOM = "custom"  # Custom model implementations


class DatasetCategory(str, Enum):
    """Categories of evaluation datasets."""

    REASONING = "reasoning"
    KNOWLEDGE = "knowledge"
    LANGUAGE = "language"
    MATH = "math"
    CODING = "coding"
    MULTIMODAL = "multimodal"
    CUSTOM = "custom"


class GenericModelConfig(BaseModel):
    """Generic model configuration that can be transformed to engine-specific formats."""

    name: str = Field(..., description="Model identifier")
    type: ModelType = Field(..., description="Type of model")

    # API model fields
    api_key: str | None = Field(None, description="API key for API-based models")
    base_url: str | None = Field(None, description="Base URL for API endpoints")
    api_version: str | None = Field(None, description="API version")

    # Local model fields
    model_path: str | None = Field(None, description="Path to local model")
    tokenizer_path: str | None = Field(None, description="Path to tokenizer")

    # Model parameters
    temperature: float | None = Field(0.7, description="Temperature for generation")
    max_tokens: int | None = Field(None, description="Maximum tokens to generate")
    top_p: float | None = Field(1.0, description="Top-p sampling parameter")

    # Additional engine-specific parameters
    extra_params: dict[str, str] = Field(default_factory=dict, description="Engine-specific parameters")


class GenericDatasetConfig(BaseModel):
    """Generic dataset configuration."""

    name: str = Field(..., description="Dataset identifier")
    category: DatasetCategory = Field(..., description="Dataset category")
    version: str | None = Field(None, description="Dataset version")
    subset: str | None = Field(None, description="Dataset subset")
    split: str = Field("test", description="Dataset split to use")

    # Sampling parameters
    sample_size: int | None = Field(None, description="Number of samples to evaluate")
    random_seed: int | None = Field(None, description="Random seed for sampling")

    # Custom dataset fields
    custom_path: str | None = Field(None, description="Path to custom dataset")
    custom_format: str | None = Field(None, description="Format of custom dataset")

    # Additional parameters
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Engine-specific parameters")


class GenericEvaluationRequest(BaseModel):
    """Generic evaluation request that is engine-agnostic."""

    # Core fields
    eval_request_id: UUID = Field(..., description="Unique evaluation request ID")
    engine: EvaluationEngine = Field(..., description="Evaluation engine to use")

    # Model configuration
    model: GenericModelConfig = Field(..., description="Model configuration")

    # Dataset configuration
    datasets: List[GenericDatasetConfig] = Field(..., description="Datasets to evaluate on")

    # Evaluation parameters
    batch_size: int = Field(1, description="Batch size for evaluation")
    num_workers: int = Field(1, description="Number of parallel workers")
    timeout_minutes: int = Field(30, description="Timeout for evaluation job")

    # Infrastructure configuration
    kubeconfig: str | None = Field(None, description="Kubernetes configuration")
    namespace: str = Field(default_factory=StorageConfig.get_current_namespace, description="Kubernetes namespace")

    # Additional parameters
    debug: bool = Field(False, description="Enable debug mode")
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Engine-specific parameters")


class GenericJobConfig(BaseModel):
    """Generic job configuration for Kubernetes deployment."""

    job_id: str = Field(..., description="Unique job identifier")
    engine: EvaluationEngine = Field(..., description="Evaluation engine")

    # Container configuration
    image: str = Field(..., description="Docker image to use")
    command: List[str] = Field(..., description="Container command")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")

    # Volume configuration
    config_volume: Dict[str, Any] = Field(..., description="Configuration volume details")
    data_volumes: List[Dict[str, Any]] = Field(default_factory=list, description="Data volumes")
    output_volume: Dict[str, Any] = Field(..., description="Output volume details")

    # Resource configuration
    cpu_request: str = Field("500m", description="CPU request")
    cpu_limit: str = Field("2000m", description="CPU limit")
    memory_request: str = Field("1Gi", description="Memory request")
    memory_limit: str = Field("4Gi", description="Memory limit")

    # Job configuration
    ttl_seconds: int = Field(3600, description="TTL after job completion")
    backoff_limit: int = Field(2, description="Number of retries")

    # Additional parameters
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Engine-specific parameters")


class TransformedEvaluationData(BaseModel):
    """Data structure after transformation for a specific engine."""

    engine: EvaluationEngine = Field(..., description="Target engine")
    job_config: GenericJobConfig = Field(..., description="Job configuration")
    config_files: Dict[str, str] = Field(..., description="Configuration files content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
