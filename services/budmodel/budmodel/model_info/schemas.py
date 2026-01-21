import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from budmicroframe.commons.schemas import CloudEventBase, ResponseBase
from budmicroframe.commons.types import lowercase_string
from pydantic import UUID4, BaseModel, Field

from ..commons.constants import ModelExtractionStatus


class LicenseCreate(BaseModel):
    """License create schema."""

    license_id: str | None = None
    name: str | None = None
    url: str | None = None
    faqs: List[Dict[str, Union[str, List[str]]]] | None = None
    type: str | None = None
    description: str | None = None
    suitability: str | None = None
    is_extracted: bool = False


class LicenseUpdate(LicenseCreate):
    """License update schema."""

    pass


class LicenseInfo(LicenseCreate):
    """License info."""

    id: UUID4 | None = None


class PaperInfo(BaseModel):
    title: str
    authors: List[str]
    url: str
    # Other models linked to the paper


class ModelDerivatives(BaseModel):
    base_model: Optional[List[str]] = None
    is_finetune: Optional[bool] = None
    is_adapter: Optional[bool] = None
    is_quantization: Optional[bool] = None
    is_merge: Optional[bool] = None


class LLMConfig(BaseModel):
    num_layers: Optional[int] = None
    hidden_size: Optional[int] = None
    intermediate_size: Optional[int] = None
    context_length: Optional[int] = None
    vocab_size: Optional[int] = None
    torch_dtype: Optional[str] = None
    num_attention_heads: Optional[int] = None
    num_key_value_heads: Optional[int] = None
    rope_scaling: Optional[Dict[str, Any]] = None


class VisionConfig(BaseModel):
    num_layers: Optional[int] = None
    hidden_size: Optional[int] = None
    intermediate_size: Optional[int] = None
    torch_dtype: Optional[str] = None


class AudioConfig(BaseModel):
    """Audio encoder configuration for speech/audio models."""

    num_layers: Optional[int] = None
    hidden_size: Optional[int] = None
    num_attention_heads: Optional[int] = None
    num_mel_bins: Optional[int] = None
    sample_rate: Optional[int] = None
    max_source_positions: Optional[int] = None
    max_target_positions: Optional[int] = None
    torch_dtype: Optional[str] = None


class EmbeddingConfig(BaseModel):
    embedding_dimension: Optional[int] = None


class ClassifierConfig(BaseModel):
    num_labels: Optional[int] = None
    label2id: Optional[Dict[str, int]] = None
    id2label: Optional[Dict[int, str]] = None
    task: Optional[
        Literal[
            "sequence_classification",
            "token_classification",
            "object_detection",
            "question_answering",
            "image_classification",
            "audio_classification",
            "semantic_segmentation",
        ]
    ] = None


class ModelArchitecture(BaseModel):
    class Config:
        """Configuration class for ModelArchitecture."""

        protected_namespaces = ()

    type: Optional[str] = None
    family: Optional[str] = None
    num_params: Optional[int] = None
    model_weights_size: Optional[int] = None
    kv_cache_size: Optional[int] = None
    text_config: Optional[LLMConfig] = None
    vision_config: Optional[VisionConfig] = None
    audio_config: Optional[AudioConfig] = None
    embedding_config: Optional[EmbeddingConfig] = None


class ModelInfoBase(BaseModel):
    """Base model for model info."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    author: Optional[str] = None
    description: Optional[str] = None
    uri: str
    modality: Optional[str] = None
    tags: Optional[List[str]] = None
    tasks: Optional[List[str]] = None
    papers: Optional[List[PaperInfo]] = None
    github_url: Optional[str] = None
    provider_url: Optional[str] = None
    website_url: Optional[str] = None
    license: Optional[LicenseInfo] = None
    logo_url: Optional[str] = None
    use_cases: Optional[List[str]] = None
    strengths: Optional[List[str]] = None
    limitations: Optional[List[str]] = None
    model_tree: Optional[ModelDerivatives] = None
    languages: Optional[List[str]] = None
    architecture: Optional[ModelArchitecture] = None
    extraction_status: ModelExtractionStatus = ModelExtractionStatus.PARTIAL


class ModelInfo(ModelInfoBase):
    """Model info."""

    author: str
    description: str
    modality: str
    tasks: List[str]


class ModelExtractionRequest(CloudEventBase):
    """Request to extract model information from a given model URI."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    model_name: str
    model_uri: str
    provider_type: Literal["cloud_model", "hugging_face", "url", "disk"]
    hf_token: str | None = None


class ModelExtractionResponse(ResponseBase):
    """Response schema for model extraction."""

    object: lowercase_string = "model_extraction"
    workflow_id: uuid.UUID
    model_info: ModelInfo
    local_path: str
    created: int = Field(default_factory=lambda: int(time.time()))


class ModelIssue(BaseModel):
    title: str
    severity: str
    description: str
    source: str


class ModelSecurityScanRequest(CloudEventBase):
    """Request to perform security scan on a given model."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    model_path: str


class ModelSecurityScanResponse(ResponseBase):
    """Response schema for model security scan."""

    object: lowercase_string = "security_scan"
    workflow_id: uuid.UUID
    scan_result: Dict[str, Any]
    created: int = Field(default_factory=lambda: int(time.time()))


class UploadFile(BaseModel):
    """File to upload to the store."""

    file_path: str
    object_name: str


class LicenseFAQRequest(CloudEventBase):
    """Request to perform security scan on a given model."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    license_source: str


class LicenseFAQResponse(ResponseBase):
    """Response schema for model license faqs."""

    object: lowercase_string = "license_faqs_fetch"
    workflow_id: uuid.UUID
    license_details: Dict[str, Any]
    created: int = Field(default_factory=lambda: int(time.time()))


class ModelExtractionETAObserverRequest(ModelExtractionRequest):
    """Request to perform security scan on a given model."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    workflow_id: str
    start_time: Optional[float] = None


class ModelscanETAObserverRequest(ModelSecurityScanRequest):
    """Request to perform security scan on a given model."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    workflow_id: str
    start_time: Optional[float] = None


class CloudModelExtractionRequest(CloudEventBase):
    """Request to extract cloud model information from external service."""

    class Config:
        """Pydantic configuration."""

        protected_namespaces = ()

    model_uri: str
    external_service_url: Optional[str] = None


class CloudModelExtractionResponse(ResponseBase):
    """Response schema for cloud model extraction."""

    object: lowercase_string = "cloud_model_extraction"
    model_info: ModelInfo
    created: int = Field(default_factory=lambda: int(time.time()))
