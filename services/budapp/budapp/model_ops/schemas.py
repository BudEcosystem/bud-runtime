#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------


"""Contains core Pydantic schemas used for data validation and serialization within the model ops services."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import UploadFile
from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from budapp.commons.constants import (
    AddModelModalityEnum,
    BaseModelRelationEnum,
    ModalityEnum,
    ModelEndpointEnum,
    ModelProviderTypeEnum,
    ModelSecurityScanStatusEnum,
    ModelStatusEnum,
    ProviderCapabilityEnum,
    WorkflowStatusEnum,
)
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag, Task
from budapp.user_ops.schemas import UserInfo

from ..commons.config import app_settings
from ..commons.constants import ModelLicenseObjectTypeEnum, ScalingMetricEnum, ScalingTypeEnum
from ..commons.helpers import validate_icon
from ..commons.schemas import BudNotificationMetadata
from ..shared.minio_store import ModelStore


class ProviderFilter(BaseModel):
    """Provider filter schema."""

    name: str | None = None
    capabilities: ProviderCapabilityEnum | None = None


class ProviderCreate(BaseModel):
    """Provider create schema."""

    name: str
    description: str
    type: str
    icon: str
    capabilities: list[ProviderCapabilityEnum]
    is_active: bool = True


class Provider(BaseModel):
    """Provider schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    description: str
    type: str
    icon: str
    capabilities: list[ProviderCapabilityEnum]

    @field_validator("capabilities", mode="before")
    @classmethod
    def handle_none_capabilities(cls, v):
        """Convert None to empty list for capabilities."""
        return v if v is not None else []


class ProviderResponse(PaginatedSuccessResponse):
    """Provider response schema."""

    model_config = ConfigDict(extra="ignore")

    providers: list[Provider] = []


class CloudModelCreate(BaseModel):
    """Cloud model create schema."""

    name: str
    modality: List[ModalityEnum]
    provider_id: UUID4
    uri: str
    source: str  # provider type
    provider_type: ModelProviderTypeEnum = Field(default=ModelProviderTypeEnum.CLOUD_MODEL)
    max_input_tokens: int | None = None
    input_cost: dict | None = None
    output_cost: dict | None = None
    supported_endpoints: list[ModelEndpointEnum]
    deprecation_date: datetime | None = None


class CloudModel(BaseModel):
    """Cloud model schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID4
    name: str
    description: str | None = None
    modality: List[ModalityEnum]
    source: str
    provider_type: ModelProviderTypeEnum
    uri: str
    model_size: int | None = None
    tags: list[Tag] | None = None
    tasks: list[Tag] | None = None
    is_present_in_model: bool = False
    supported_endpoints: list[ModelEndpointEnum]

    @field_serializer("modality")
    def serialized_modality(self, modalities: List[ModalityEnum], _info) -> Dict[str, Any]:
        """Serialize the modality."""
        return ModalityEnum.serialize_modality(modalities)

    @field_serializer("supported_endpoints")
    def serialized_endpoints(self, endpoints: List[ModelEndpointEnum], _info) -> Dict[str, Any]:
        """Serialize the endpoints."""
        return ModelEndpointEnum.serialize_endpoints(endpoints)


class PaperPublishedModel(BaseModel):
    """Paper Published Model Schema."""

    id: UUID4
    title: str | None = None
    authors: list[str] | None = None
    url: str | None = None
    model_id: UUID4

    class Config:
        orm_mode = True
        from_attributes = True


class PaperPublishedModelEditRequest(BaseModel):
    """Paper Published Edit Model Schema."""

    id: UUID4 | None = None
    title: str | None = None
    url: str


class ModelLicensesModel(BaseModel):
    """Model Licenses Model Schema."""

    id: UUID4
    name: str | None = None
    url: str | None = None
    path: str | None = None
    faqs: list[dict] | None = None
    license_type: str | None = None
    description: str | None = None
    suitability: str | None = None
    model_id: UUID4
    data_type: ModelLicenseObjectTypeEnum = ModelLicenseObjectTypeEnum.URL

    class Config:
        orm_mode = True
        from_attributes = True

    @model_validator(mode="after")
    def validate_fields(self) -> "ModelLicensesModel":
        if self.data_type == ModelLicenseObjectTypeEnum.MINIO:
            minio_store = ModelStore()
            is_minio_object_exists = minio_store.check_file_exists(app_settings.minio_model_bucket, self.url)
            if is_minio_object_exists:
                self.url = minio_store.get_object_url(app_settings.minio_model_bucket, self.url)
            else:
                self.url = None
        return self


class ModelLicenseTypeSchema(BaseModel):
    """Model Licenses Model Schema."""

    license_type: str | None = None

    class Config:
        from_attributes = True


# Model related schemas


class ModelBase(BaseModel):
    """Base model schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    name: str
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None
    tasks: Optional[List[Tag]] = None
    github_url: Optional[str] = None
    huggingface_url: Optional[str] = None
    website_url: Optional[str] = None


class Model(ModelBase):
    """Model schema."""

    id: UUID4
    icon: str | None = None
    modality: List[ModalityEnum]
    source: str
    provider_type: ModelProviderTypeEnum
    uri: str
    model_size: Optional[int] = None
    created_by: Optional[UUID4] = None
    author: Optional[str] = None
    created_at: datetime
    modified_at: datetime
    provider: Provider | None = None
    supported_endpoints: list[ModelEndpointEnum]

    @field_serializer("modality")
    def serialized_modality(self, modalities: List[ModalityEnum], _info) -> Dict[str, Any]:
        """Serialize the modality."""
        return ModalityEnum.serialize_modality(modalities)

    @field_serializer("supported_endpoints")
    def serialized_endpoints(self, endpoints: List[ModelEndpointEnum], _info) -> Dict[str, Any]:
        """Serialize the endpoints."""
        return ModelEndpointEnum.serialize_endpoints(endpoints)


class ModelArchitectureLLMConfig(BaseModel):
    """Model architecture schema."""

    num_layers: int | None = None
    hidden_size: int | None = None
    intermediate_size: int | None = None
    context_length: int | None = None
    vocab_size: int | None = None
    torch_dtype: str | None = None
    num_attention_heads: int | None = None
    num_key_value_heads: int | None = None
    rope_scaling: dict | None = None


class ModelArchitectureVisionConfig(BaseModel):
    """Model architecture schema."""

    num_layers: int | None = None
    hidden_size: int | None = None
    intermediate_size: int | None = None
    torch_dtype: str | None = None


class ModelCreate(ModelBase):
    """Schema for creating a new AI Model."""

    modality: List[ModalityEnum]
    source: str
    provider_type: ModelProviderTypeEnum
    uri: str
    model_size: Optional[int] = None
    created_by: UUID4
    author: Optional[str] = None
    provider_id: UUID4 | None = None
    local_path: str | None = None
    strengths: list[str] | None = None
    limitations: list[str] | None = None
    languages: list[str] | None = None
    use_cases: list[str] | None = None
    minimum_requirements: dict | None = None
    examples: list[dict] | None = None
    base_model: list[str] | None = None
    base_model_relation: BaseModelRelationEnum | None = None
    model_type: str | None = None
    family: str | None = None
    model_weights_size: int | None = None
    kv_cache_size: int | None = None
    architecture_text_config: ModelArchitectureLLMConfig | None = None
    architecture_vision_config: ModelArchitectureVisionConfig | None = None
    scan_verified: bool | None = None
    icon: str | None = None
    supported_endpoints: list[ModelEndpointEnum]


class ModelDetailResponse(BaseModel):
    """Response schema for model details."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID4
    name: str
    description: str | None = None
    tags: list[Tag] | None = None
    tasks: list[Task] | None = None
    author: str | None = None
    model_size: int | None = None
    icon: str | None = None
    github_url: str | None = None
    huggingface_url: str | None = None
    website_url: str | None = None
    bud_verified: bool = False
    scan_verified: bool | None = None
    eval_verified: bool = False
    strengths: list[str] | None = None
    limitations: list[str] | None = None
    languages: list[str] | None = None
    use_cases: list[str] | None = None
    minimum_requirements: dict | None = None
    examples: list[dict] | None = None
    base_model: list[str] | None = None
    model_type: str | None = None
    family: str | None = None
    model_weights_size: int | None = None
    kv_cache_size: int | None = None
    architecture_text_config: ModelArchitectureLLMConfig | None = None
    architecture_vision_config: ModelArchitectureVisionConfig | None = None
    modality: List[ModalityEnum]
    source: str
    provider_type: ModelProviderTypeEnum
    uri: str
    paper_published: list[PaperPublishedModel] | None = None
    model_licenses: ModelLicensesModel | None = None
    provider: Provider | None = None
    supported_endpoints: List[ModelEndpointEnum]
    created_at: datetime
    # Pricing information
    pricing: Optional[DeploymentPricingInfo] = None

    @field_serializer("modality")
    def serialized_modality(self, modalities: List[ModalityEnum], _info) -> Dict[str, Any]:
        """Serialize the modality."""
        return ModalityEnum.serialize_modality(modalities)

    @field_serializer("supported_endpoints")
    def serialized_endpoints(self, endpoints: List[ModelEndpointEnum], _info) -> Dict[str, Any]:
        """Serialize the endpoints."""
        return ModelEndpointEnum.serialize_endpoints(endpoints)


class ModelTree(BaseModel):
    """Model tree schema."""

    adapters_count: int = 0
    finetunes_count: int = 0
    merges_count: int = 0
    quantizations_count: int = 0


# Schemas related to Model Security Scan Results


class ModelIssue(BaseModel):
    """Model issue schema."""

    title: str
    severity: str
    description: str
    source: str


class ModelSecurityScanResultCreate(BaseModel):
    """Model security scan result create schema."""

    model_id: UUID4
    status: ModelSecurityScanStatusEnum
    total_issues: int
    total_scanned_files: int
    total_skipped_files: int
    scanned_files: list[str]
    low_severity_count: int
    medium_severity_count: int
    high_severity_count: int
    critical_severity_count: int
    model_issues: dict


class ModelSecurityScanResult(ModelSecurityScanResultCreate):
    """Model security scan result schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID4
    created_at: datetime
    modified_at: datetime


class ModelDetailSuccessResponse(SuccessResponse):
    """Model detail success response schema."""

    model: ModelDetailResponse
    scan_result: ModelSecurityScanResult | None = None
    eval_result: dict | None = None  # TODO: integrate actual eval result
    model_tree: ModelTree
    endpoints_count: int
    endpoint_id: str | None = None
    endpoint_name: str | None = None


class CreateCloudModelWorkflowRequest(BaseModel):
    """Cloud model workflow request schema."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    provider_type: ModelProviderTypeEnum | None = None
    provider_id: UUID4 | None = None
    name: str | None = None
    modality: List[ModalityEnum] | None = None
    uri: str | None = None
    tags: list[Tag] | None = None
    cloud_model_id: UUID4 | None = None
    add_model_modality: list[AddModelModalityEnum] | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "CreateCloudModelWorkflowRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        # Check if at least one of the other fields is provided
        other_fields = [
            self.provider_type,
            self.provider_id,
            self.modality,
            self.uri,
            self.tags,
            self.name,
        ]
        required_fields = ["provider_type", "provider_id", "modality", "uri", "tags", "name"]
        if not any(other_fields):
            # Allow if cloud model id is explicitly provided
            input_data = self.model_dump(exclude_unset=True)
            if "cloud_model_id" in input_data:
                return self
            raise ValueError(f"At least one of {', '.join(required_fields)} is required when workflow_id is provided")

        return self


class CreateLocalModelWorkflowRequest(BaseModel):
    """Local model workflow request schema."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    provider_type: ModelProviderTypeEnum | None = None
    proprietary_credential_id: UUID4 | None = None
    name: str | None = None
    uri: str | None = None
    author: str | None = None
    tags: list[Tag] | None = None
    icon: str | None = None
    add_model_modality: list[AddModelModalityEnum] | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "CreateLocalModelWorkflowRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        # Validate proprietary_credential_id based on provider_type
        if (
            self.provider_type is not None
            and self.provider_type != ModelProviderTypeEnum.HUGGING_FACE
            and self.proprietary_credential_id is not None
        ):
            raise ValueError("proprietary_credential_id should be None for non-HuggingFace providers")

        if (
            self.provider_type is not None
            and self.provider_type == ModelProviderTypeEnum.HUGGING_FACE
            and self.icon is not None
        ):
            raise ValueError("Icon is not supported for HuggingFace models")

        # Validate provider type
        if self.provider_type and self.provider_type == ModelProviderTypeEnum.CLOUD_MODEL:
            raise ValueError("Cloud model provider type not supported for local model workflow")

        return self

    @field_validator("icon", mode="before")
    @classmethod
    def icon_validate(cls, value: str | None) -> str | None:
        """Validate the icon."""
        if value is not None and not validate_icon(value):
            raise ValueError("invalid icon")
        return value


class CreateLocalModelWorkflowSteps(BaseModel):
    """Create cluster workflow step data schema."""

    provider_type: ModelProviderTypeEnum | None = None
    proprietary_credential_id: UUID4 | None = None
    name: str | None = None
    icon: str | None = None
    uri: str | None = None
    author: str | None = None
    tags: list[Tag] | None = None
    provider_id: UUID4 | None
    add_model_modality: list[AddModelModalityEnum] | None = None


class EditModel(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=400)
    tags: List[Tag] | None = None
    tasks: List[Task] | None = None
    icon: str | None = None
    paper_urls: List[HttpUrl] | None = None
    github_url: HttpUrl | None = None
    huggingface_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    license_file: UploadFile | None = None
    license_url: HttpUrl | None = None
    remove_license: bool = False

    @field_validator("name", mode="before")
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            value = value.strip()
            if len(value) == 0:
                raise ValueError("Model name cannot be empty or only whitespace.")
        return value

    @field_validator("icon", mode="before")
    @classmethod
    def icon_validate(cls, value: str | None) -> str | None:
        """Validate the icon."""
        if value is not None and not validate_icon(value):
            raise ValueError("invalid icon")
        return value

    @model_validator(mode="before")
    def validate_license(cls, values):
        license_file = values.get("license_file")
        license_url = values.get("license_url")

        # Ensure only one of license_file or license_url is provided
        if license_file and license_url:
            raise ValueError("Please provide either a license file or a license URL, but not both.")

        if license_file:
            filename = license_file.filename
            allowed_extensions = ["pdf", "txt", "doc", "docx", "md"]

            if not filename or "." not in filename:
                raise ValueError("File does not have a valid extension")

            # Get the file extension from the filename
            file_extension = filename.split(".")[-1].lower()

            # Check if the file extension is in the allowed list
            if file_extension not in allowed_extensions:
                raise ValueError("Invalid file extension for license file")
        return values

    @field_serializer("github_url", "huggingface_url", "website_url", "license_url")
    def str_url(self, url: HttpUrl | None) -> str:
        return str(url) if url else None

    @field_serializer("paper_urls")
    def str_paper_urls(self, urls: List[HttpUrl] | None) -> List[str]:
        return [str(url) for url in urls] if urls else urls


class RecommendedCluster(BaseModel):
    """Recommended cluster schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    name: str
    cpu_total_workers: int
    cpu_available_workers: int
    gpu_total_workers: int
    gpu_available_workers: int
    hpu_total_workers: int
    hpu_available_workers: int

    @computed_field
    def total_workers(self) -> int:
        """Get sum of all total workers."""
        return self.cpu_total_workers + self.gpu_total_workers + self.hpu_total_workers

    @computed_field
    def available_workers(self) -> int:
        """Get sum of all available workers."""
        return self.cpu_available_workers + self.gpu_available_workers + self.hpu_available_workers

    @computed_field
    def availability_percentage(self) -> float:
        """Calculate overall availability percentage."""
        if self.total_workers == 0:
            return 0.0

        return round((self.available_workers / self.total_workers) * 100, 1)


class ModelClusterRecommended(BaseModel):
    """Model cluster recommended schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    cost_per_million_tokens: float
    hardware_type: list[str]
    cluster: RecommendedCluster


class ModelResponse(BaseModel):
    """Model response schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID4
    name: str
    author: str | None = None
    modality: List[ModalityEnum]
    source: str
    uri: str
    created_user: UserInfo | None = None
    model_size: int | None = None
    tasks: list[Task] | None = None
    tags: list[Tag] | None = None
    icon: str | None = None
    description: str | None = None
    provider_type: ModelProviderTypeEnum
    created_at: datetime
    modified_at: datetime
    provider: Provider | None = None
    is_present_in_model: bool | None = None
    model_cluster_recommended: ModelClusterRecommended | None = None
    supported_endpoints: list[ModelEndpointEnum]

    @field_serializer("modality")
    def serialized_modality(self, modalities: List[ModalityEnum], _info) -> Dict[str, Any]:
        """Serialize the modality."""
        return ModalityEnum.serialize_modality(modalities)

    @field_serializer("supported_endpoints")
    def serialized_endpoints(self, endpoints: List[ModelEndpointEnum], _info) -> Dict[str, Any]:
        """Serialize the endpoints."""
        return ModelEndpointEnum.serialize_endpoints(endpoints)


class ModelDeploymentResponse(ModelResponse):
    """Model deployment response schema."""

    strengths: list[str] | None = None
    limitations: list[str] | None = None
    model_licenses: ModelLicenseTypeSchema | None = None


class ModelListResponse(BaseModel):
    """Model list response schema."""

    model: ModelResponse
    endpoints_count: int | None = None


class ModelPaginatedResponse(PaginatedSuccessResponse):
    """Model paginated response schema."""

    models: list[ModelListResponse] = []


class ModelFilter(BaseModel):
    """Filter model schema for filtering models based on specific criteria."""

    model_config = ConfigDict(protected_namespaces=())

    name: str | None = None
    source: str | None = None
    model_size_min: int | None = Field(None, ge=0, le=500)
    model_size_max: int | None = Field(None, ge=0, le=500)
    provider_type: ModelProviderTypeEnum | None = None
    table_source: Literal["cloud_model", "model"] = "cloud_model"
    base_model: str | None = None
    base_model_relation: BaseModelRelationEnum | None = None
    exclude_adapters: bool | None = Field(None, description="Exclude adapter-type models from results")
    supported_endpoints: List[ModelEndpointEnum] | None = None

    # @field_validator("source")
    # @classmethod
    # def change_to_string(cls, v: CredentialTypeEnum | None) -> str | None:
    #     """Convert the source enum value to a string."""
    #     return v.value if v else None

    @field_validator("model_size_min", "model_size_max")
    @classmethod
    def convert_to_billions(cls, v: Optional[int]) -> Optional[int]:
        """Convert the input value to billions."""
        if v is not None:
            return v * 1000000000  # Convert to billions
        return v


class Leaderboard(BaseModel):
    """Leaderboard schema."""

    # APAC Eval Leaderboard fields
    lc_win_rate: float | None = None

    # Berkeley Leaderboard fields
    bcfl: float | None = None

    # LiveCodeBench Leaderboard fields
    live_code_bench: float | None = None

    # MTEB Leaderboard fields
    classification: float | None = None
    clustering: float | None = None
    pair_classification: float | None = None
    reranking: float | None = None
    retrieval: float | None = None
    semantic: float | None = None
    summarization: float | None = None

    # UGI Leaderboard fields (with _score suffixes)
    ugi_score: float | None = None

    # VLLM Leaderboard fields
    mmbench: float | None = None
    mmstar: float | None = None
    mmmu: float | None = None
    math_vista: float | None = None
    ocr_bench: float | None = None
    ai2d: int | None = None
    hallucination_bench: float | None = None
    mmvet: float | None = None

    # Chatbot Arena Leaderboard fields
    lmsys_areana: int | None = None


class LeaderboardModelInfo(BaseModel):
    """Leaderboard model info schema."""

    uri: str
    model_size: int | None = None
    is_selected: bool = False


class LeaderboardBenchmark(BaseModel):
    """Leaderboard benchmark schema."""

    type: str | None = None
    label: str
    value: int | float | None = None


class LeaderboardTable(BaseModel):
    """Leaderboard table schema."""

    model: LeaderboardModelInfo
    benchmarks: dict[str, LeaderboardBenchmark]


class LeaderboardTableResponse(SuccessResponse):
    """Leaderboard response schema."""

    leaderboards: list[LeaderboardTable] = []


class TopLeaderboardBenchmark(BaseModel):
    """Top leaderboard benchmark schema."""

    field: str
    value: int | float | None = None
    type: str | None = None
    label: str


class TopLeaderboard(BaseModel):
    """Top leaderboard response schema."""

    benchmarks: list[dict]
    name: str
    provider_type: str


class TopLeaderboardResponse(SuccessResponse):
    """Top leaderboard response schema."""

    leaderboards: list[TopLeaderboard] = []


# Cloud model related schemas


class CreateCloudModelWorkflowSteps(BaseModel):
    """Cloud model workflow step data schema."""

    provider_type: ModelProviderTypeEnum | None = None
    source: str | None = None
    name: str | None = None
    modality: list[ModalityEnum] | None = None
    uri: str | None = None
    tags: list[Tag] | None = None
    icon: str | None = None
    provider_id: UUID4 | None = None
    cloud_model_id: UUID4 | None = None
    add_model_modality: list[AddModelModalityEnum] | None = None


class CreateCloudModelWorkflowStepData(BaseModel):
    """Cloud model workflow step data schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    provider_type: ModelProviderTypeEnum | None = None
    provider: Provider | None = None
    cloud_model: CloudModel | None = None
    cloud_model_id: UUID4 | None = None
    provider_id: UUID4 | None = None
    model_id: UUID4 | None = None
    model: Model | None = None
    workflow_execution_status: dict | None = None
    leaderboard: list | None = None


class CreateCloudModelWorkflowResponse(SuccessResponse):
    """Add Cloud Model Workflow Response."""

    workflow_id: UUID4
    status: WorkflowStatusEnum
    current_step: int
    total_steps: int
    reason: str | None = None
    workflow_steps: CreateCloudModelWorkflowStepData | None = None


class CloudModelFilter(BaseModel):
    """Cloud model filter schema."""

    model_config = ConfigDict(protected_namespaces=())

    source: str | None = None
    modality: ModalityEnum | None = None
    model_size: int | None = None
    name: str | None = None

    # @field_validator("source")
    # def change_to_string(cls, v: CredentialTypeEnum | None) -> str | None:
    #     """Change the source to a string."""
    #     return v.value if v else None


class CloudModelResponse(PaginatedSuccessResponse):
    """Cloud model response schema."""

    model_config = ConfigDict(extra="ignore")

    cloud_models: list[CloudModel] = []


class TagWithCount(BaseModel):
    """Tag with count schema."""

    name: str
    color: str = Field(..., pattern="^#[0-9A-Fa-f]{6}$")
    count: int

    @field_validator("color")
    def validate_hex_color(cls, v: str) -> str:
        """Validate that color is a valid hex color code."""
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code (e.g., #FF0000)")
        return v.upper()  # Normalize to uppercase


class RecommendedTagsResponse(PaginatedSuccessResponse):
    """Recommended tags response schema."""

    tags: List[TagWithCount] = []

    @field_validator("tags", mode="before")
    def validate_tags(cls, v: List[Tuple[str, str, int]]) -> List[TagWithCount]:
        """Convert tuples to TagWithCount objects."""
        return [TagWithCount(name=tag[0], color=tag[1], count=tag[2]) for tag in v]


class TagsListResponse(PaginatedSuccessResponse):
    """Response schema for tags list."""

    tags: List[Tag] = Field(..., description="List of matching tags")


class TasksListResponse(PaginatedSuccessResponse):
    """Response schema for tasks list."""

    tasks: List[Task] = []


class ModelAuthorResponse(PaginatedSuccessResponse):
    """Response schema for searching tags by name."""

    authors: List[str] = Field(..., description="List of matching authors")


class ModelAuthorFilter(BaseModel):
    """Filter schema for model authors."""

    author: str | None = None


# Schemas related to Paper Published


class PaperPublishedCreate(BaseModel):
    """Paper Published Create Schema."""

    title: str | None = None
    authors: list[str] | None = None
    url: str | None = None
    model_id: UUID4


# Schemas related to Model Licenses


class ModelLicensesCreate(BaseModel):
    """Model Licenses Create Schema."""

    name: str | None = None
    url: str | None = None
    path: str | None = None
    faqs: list[dict] | None = None
    license_type: str | None = None
    description: str | None = None
    suitability: str | None = None
    model_id: UUID4
    data_type: ModelLicenseObjectTypeEnum = ModelLicenseObjectTypeEnum.URL


# Local model related schemas


class LocalModelScanRequest(BaseModel):
    """Local model scan request schema."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    model_id: UUID4 | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "LocalModelScanRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        # Check if at least one of the other fields is provided
        other_fields = [self.model_id]
        required_fields = ["model_id"]
        if not any(other_fields):
            raise ValueError(f"At least one of {', '.join(required_fields)} is required")

        return self


class LocalModelScanWorkflowStepData(BaseModel):
    """Local model scan workflow step data schema."""

    model_id: UUID4 | None


class CancelDeploymentWorkflowRequest(BaseModel):
    """Cancel deployment workflow request schema."""

    workflow_id: UUID4


class DeploymentTemplateCreate(BaseModel):
    """Deployment template request schema."""

    concurrent_requests: int = Field(gt=0)
    avg_sequence_length: int = Field(ge=0, le=10000)
    avg_context_length: int = Field(ge=0, le=200000)
    per_session_tokens_per_sec: Optional[list[int]] = None
    ttft: Optional[list[int]] = None
    e2e_latency: Optional[list[int]] = None

    @field_validator("per_session_tokens_per_sec", "ttft", "e2e_latency", mode="before")
    @classmethod
    def validate_int_range(cls, value):
        if value is not None and (
            not isinstance(value, list) or len(value) != 2 or not all(isinstance(x, int) for x in value)
        ):
            raise ValueError("Must be a list of two integers")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "DeploymentTemplateCreate":
        # Define range validations
        range_validations = {
            "ttft": (1, 60000),
            "per_session_tokens_per_sec": (0, 1000),
            "e2e_latency": (0, 600),
        }
        for field, (min_val, max_val) in range_validations.items():
            field_value = getattr(self, field)
            if field_value is None:
                continue
            field_value_min, field_value_max = field_value
            if field_value_min < min_val:
                raise ValueError(f"{field} must be greater than or equal to {min_val}")
            if field_value_max > max_val:
                raise ValueError(f"{field} must be less than or equal to {max_val}")
        return self


class ScalingSpecification(BaseModel):
    """Scaling specification schema."""

    enabled: bool = Field(default=False)
    scalingType: ScalingTypeEnum = Field(...)
    scalingMetric: ScalingMetricEnum = Field(...)
    scalingValue: int = Field(ge=0)
    minReplicas: int = Field(ge=1)
    maxReplicas: int = Field(ge=1)
    scaleUpTolerance: float = Field(ge=0)
    scaleDownTolerance: float = Field(ge=0)
    window: int = Field(ge=1)


class ModelDeployStepRequest(BaseModel):
    """Request to deploy a model by step."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    model_id: UUID4 | None = None
    cluster_id: UUID4 | None = None
    project_id: UUID4 | None = None
    template_id: UUID4 | None = None
    endpoint_name: str | None = Field(None, min_length=1, max_length=100)
    deploy_config: DeploymentTemplateCreate | None = None
    credential_id: UUID4 | None = None
    scaling_specification: ScalingSpecification | None = None
    # Hardware resource mode (dedicated vs shared/time-slicing)
    hardware_mode: Literal["dedicated", "shared"] | None = Field(default=None)
    # Parser configuration options
    enable_tool_calling: bool | None = None
    enable_reasoning: bool | None = None
    # Parser metadata from simulator/cluster
    tool_calling_parser_type: str | None = None
    reasoning_parser_type: str | None = None
    chat_template: str | None = None
    # Engine capability flags from simulator
    supports_lora: bool | None = None
    supports_pipeline_parallelism: bool | None = None

    @field_validator("endpoint_name")
    @classmethod
    def validate_endpoint_name(cls, v: str | None) -> str | None:
        """Validate and transform endpoint name."""
        if v is None:
            return None

        # Replace spaces with hyphens
        v = v.replace(" ", "-")

        # Define allowed pattern: alphanumeric, hyphens
        pattern = r"^[a-zA-Z0-9-]+$"

        if not re.match(pattern, v):
            raise ValueError("Endpoint name can only contain letters, numbers, hyphens (-)")

        # strip leading and trailing hyphens and spaces convert it to lowercase
        v = v.strip("- ").lower()

        return v

    @model_validator(mode="after")
    def validate_fields(self) -> "ModelDeployStepRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        # NOTE: commenting out since Model deployment contain a Skip step so doesn't need to check for other fields
        # Check if at least one of the other fields is provided
        # other_fields = [
        #     self.model_id,
        #     self.cluster_id,
        #     self.project_id,
        #     self.endpoint_name,
        #     self.template_id,
        #     self.deploy_config,
        #     self.credential_id,
        # ]
        # if not any(other_fields):
        #     raise ValueError(
        #         "At least one of model_id, cluster_id, project_id, or endpoint_name is required when workflow_id is provided"
        #     )

        return self


class DeploymentWorkflowStepData(BaseModel):
    """Workflow step data schema."""

    model_id: UUID4 | None = None
    cluster_id: UUID4 | None = None
    project_id: UUID4 | None = None
    endpoint_name: str | None = None
    created_by: UUID4 | None = None
    template_id: UUID4 | None = None
    deploy_config: DeploymentTemplateCreate | None = None
    credential_id: UUID4 | None = None
    scaling_specification: ScalingSpecification | None = None
    # Hardware resource mode (dedicated vs shared/time-slicing)
    hardware_mode: Literal["dedicated", "shared"] | None = None
    enable_tool_calling: bool | None = None
    enable_reasoning: bool | None = None
    # Parser metadata from simulator/cluster
    tool_calling_parser_type: str | None = None
    reasoning_parser_type: str | None = None
    chat_template: str | None = None
    # Engine capability flags from simulator
    supports_lora: bool | None = None
    supports_pipeline_parallelism: bool | None = None


class ModelDeploymentRequest(BaseModel):
    """Request to deploy a model to a cluster."""

    cluster_id: UUID4
    simulator_id: UUID4
    endpoint_name: str
    hf_token: str | None = None
    model: str
    model_size: Optional[int] = None
    storage_size_gb: Optional[float] = None
    target_ttft: Optional[int] = None
    target_e2e_latency: Optional[int] = None
    target_throughput_per_user: Optional[int] = None
    concurrency: int
    input_tokens: int
    output_tokens: int
    notification_metadata: BudNotificationMetadata
    source_topic: str
    credential_id: UUID4 | None = None
    podscaler: ScalingSpecification | None = None
    provider: str | None = None
    # User preferences for parser features
    enable_tool_calling: bool | None = None
    enable_reasoning: bool | None = None
    default_storage_class: str | None = None
    default_access_mode: str | None = None


class TopLeaderboardRequest(BaseModel):
    """Top leaderboard request schema."""

    benchmarks: list[str] = Field(..., description="The benchmarks to list")
    k: int = Field(5, description="Maximum number of leaderboards", ge=1)

    @model_validator(mode="after")
    def validate_benchmarks(self) -> "TopLeaderboardRequest":
        """Validate the benchmarks."""
        if not self.benchmarks:
            raise ValueError("Benchmarks are required")
        return self


class QuantizeConfig(BaseModel):
    """Quantize config schema."""

    bit: Literal[8, 4, 2]
    granularity: Literal["per_tensor", "per_channel", "per_group", "per_head", "per_token"]
    symmetric: bool


class QuantizeModelWorkflowRequest(BaseModel):
    """Quantize model workflow request schema."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    model_id: UUID4 | None = None
    quantized_model_name: str | None = None
    target_type: Literal["INT8", "INT4", "INT2"] | None = None
    target_device: Literal["CPU", "CUDA"] | None = None
    method: str | None = None
    weight_config: QuantizeConfig | None = None
    activation_config: QuantizeConfig | None = None
    cluster_id: UUID4 | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "QuantizeModelWorkflowRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        return self


class QuantizeModelWorkflowStepData(BaseModel):
    """Quantize model workflow step data schema."""

    model_id: UUID4 | None = None
    quantized_model_name: str | None
    target_type: str | None
    target_device: str | None
    method: str | None = None
    weight_config: QuantizeConfig | None = None
    activation_config: QuantizeConfig | None = None
    cluster_id: UUID4 | None = None
    simulation_id: UUID4 | None = None
    quantization_data: dict | None = None
    quantized_model_id: UUID4 | None = None


class QuantizationMethod(BaseModel):
    """Quantization method schema."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    hardware_support: list[str]
    method_type: list[str]
    runtime_hardware_support: list[str]


class QuantizationMethodResponse(PaginatedSuccessResponse):
    """Quantization method response schema."""

    quantization_methods: list[QuantizationMethod] = []


class QuantizationMethodFilter(BaseModel):
    """Quantization method filter schema."""

    name: str | None = None


# Model Catalog Schemas
class DeploymentPricingInfo(BaseModel):
    """Simplified pricing info for catalog."""

    input_cost: float
    output_cost: float
    currency: str = "USD"
    per_tokens: int = 1000


class ModelCatalogItem(BaseModel):
    """Single model in catalog with pricing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    modality: List[ModalityEnum]
    status: ModelStatusEnum
    description: Optional[str] = None
    capabilities: List[str] = []  # From strengths + tags
    token_limit: Optional[int] = None
    max_input_tokens: Optional[int] = None
    use_cases: Optional[List[str]] = None
    author: Optional[str] = None
    model_size: Optional[int] = None
    provider_type: ModelProviderTypeEnum
    uri: str
    source: str
    provider_icon: Optional[str] = None
    # Pricing information
    pricing: Optional[DeploymentPricingInfo] = None
    # Publication metadata
    published_date: datetime
    endpoint_id: UUID4
    endpoint_name: str
    supported_endpoints: List[ModelEndpointEnum]

    @field_serializer("modality")
    def serialized_modality(self, modalities: List[ModalityEnum], _info) -> Dict[str, Any]:
        """Serialize the modality."""
        return ModalityEnum.serialize_modality(modalities)

    @field_serializer("supported_endpoints")
    def serialized_endpoints(self, endpoints: List[ModelEndpointEnum], _info) -> Dict[str, Any]:
        """Serialize the endpoints."""
        return ModelEndpointEnum.serialize_endpoints(endpoints)


class ModelCatalogResponse(PaginatedSuccessResponse):
    """Paginated catalog response."""

    models: List[ModelCatalogItem] = []
    object: str = "models.catalog"


class ModelCatalogDetailResponse(SuccessResponse):
    """Detailed model information response."""

    model: ModelCatalogItem
    object: str = "models.catalog.detail"


class ModelCatalogFilter(BaseModel):
    """Filter options for model catalog."""

    status: Optional[ModelStatusEnum] = None
    search: Optional[str] = None
