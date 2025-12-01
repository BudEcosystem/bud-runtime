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


"""Contains core Pydantic schemas used for data validation and serialization within the core services."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, List, Literal, Optional, Union
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from budapp.cluster_ops.schemas import ClusterResponse
from budapp.commons.constants import AdapterStatusEnum, EndpointStatusEnum, ModelEndpointEnum, ProxyProviderEnum
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse
from budapp.model_ops.schemas import ModelDetailResponse, ModelResponse


# Endpoint schemas


class EndpointCreate(BaseModel):
    """Create endpoint schema."""

    project_id: UUID4
    model_id: UUID4
    cluster_id: Optional[UUID4] = None
    bud_cluster_id: Optional[UUID4] = None
    name: str
    url: str
    namespace: str
    status: EndpointStatusEnum
    created_by: UUID4
    status_sync_at: datetime
    credential_id: UUID4 | None
    active_replicas: int
    total_replicas: int
    number_of_nodes: int
    deployment_config: dict | None
    node_list: list | None
    supported_endpoints: list[ModelEndpointEnum]


class EndpointFilter(BaseModel):
    """Filter endpoint schema for filtering endpoints based on specific criteria."""

    name: str | None = None
    status: EndpointStatusEnum | None = None
    is_published: Optional[bool] = None


class EndpointResponse(BaseModel):
    """Endpoint response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    status: EndpointStatusEnum
    deployment_config: dict
    created_at: datetime
    modified_at: datetime


class EndpointListResponse(BaseModel):
    """Endpoint list response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    status: EndpointStatusEnum
    model: ModelResponse
    cluster: Optional[ClusterResponse] = None
    created_at: datetime
    modified_at: datetime
    is_deprecated: bool
    supported_endpoints: list[ModelEndpointEnum]
    # Publication fields
    is_published: bool
    published_date: Optional[datetime] = None
    published_by: Optional[UUID4] = None


class EndpointPaginatedResponse(PaginatedSuccessResponse):
    """Endpoint paginated response schema."""

    endpoints: list[EndpointListResponse] = []


class WorkerInfoFilter(BaseModel):
    """Filter for worker info."""

    status: str | None = None
    hardware: str | None = None
    utilization_min: int | None = None
    utilization_max: int | None = None


class DeploymentStatusEnum(str, Enum):
    READY = "ready"
    PENDING = "pending"
    INGRESS_FAILED = "ingress_failed"
    FAILED = "failed"


class WorkerData(BaseModel):
    """Worker data."""

    cluster_id: Optional[UUID] = None
    namespace: Optional[str] = None
    name: str
    status: str
    node_name: str
    device_name: str
    utilization: Optional[str] = None
    hardware: str
    uptime: str
    last_restart_datetime: Optional[datetime] = None
    last_updated_datetime: Optional[datetime] = None
    created_datetime: datetime
    node_ip: str
    cores: int
    memory: str
    deployment_status: Optional[DeploymentStatusEnum] = None
    concurrency: int


class WorkerInfo(WorkerData):
    """Worker info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID


class WorkerInfoResponse(PaginatedSuccessResponse):
    """Response body for getting worker info."""

    model_config = ConfigDict(extra="allow")

    workers: list[WorkerInfo]


class WorkerLogsResponse(SuccessResponse):
    """Worker logs response."""

    model_config = ConfigDict(extra="allow")

    logs: Any


class WorkerDetailResponse(SuccessResponse):
    """Worker detail response."""

    model_config = ConfigDict(extra="allow")
    worker: WorkerInfo


class ModelClusterDetail(BaseModel):
    """Model cluster detail."""

    model_config = ConfigDict(extra="allow")

    id: UUID
    name: str
    status: str
    model: ModelDetailResponse
    cluster: Optional[ClusterResponse] = None
    deployment_config: Optional[dict] = None


class ModelClusterDetailResponse(SuccessResponse):
    """Model cluster detail response."""

    model_config = ConfigDict(extra="allow")

    result: ModelClusterDetail


class AddWorkerRequest(BaseModel):
    """Add worker request."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    endpoint_id: UUID4 | None = None
    additional_concurrency: int | None = Field(None, gt=0)

    @model_validator(mode="after")
    def validate_fields(self) -> "AddWorkerRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        return self


class AddWorkerWorkflowStepData(BaseModel):
    """Add worker workflow step data."""

    endpoint_id: UUID4 | None = None
    additional_concurrency: int | None = None


class DeleteWorkerRequest(BaseModel):
    """Delete worker request."""

    endpoint_id: UUID4
    worker_id: UUID4
    worker_name: str


class WorkerMetricsResponse(SuccessResponse):
    """Worker metrics response."""

    model_config = ConfigDict(extra="allow")

    metrics: Union[dict[str, Any], None] = None


class AddAdapterRequest(BaseModel):
    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    endpoint_id: UUID4 | None = None
    adapter_name: str | None = None
    adapter_model_id: UUID4 | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "AddAdapterRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        return self


class AddAdapterWorkflowStepData(BaseModel):
    """Add adapter workflow step data."""

    endpoint_id: UUID4 | None = None
    project_id: UUID4 | None = None
    adapter_name: str | None = None
    adapter_model_id: UUID4 | None = None
    adapter_id: UUID4 | None = None


class AdapterFilter(BaseModel):
    """Adapter filter."""

    name: str | None = None
    status: AdapterStatusEnum | None = None


class AdapterResponse(BaseModel):
    """Adapter response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    status: AdapterStatusEnum
    model: ModelResponse
    created_at: datetime


class AdapterPaginatedResponse(PaginatedSuccessResponse):
    """Adapter paginated response."""

    adapters: list[AdapterResponse] = []


class VLLMConfig(BaseModel):
    """VLLM config."""

    type: str = "vllm"
    model_name: str
    api_base: str
    api_key_location: str


class OpenAIConfig(BaseModel):
    """OpenAI provider config."""

    type: str = "openai"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None
    api_base: Optional[str] = None
    organization: Optional[str] = None


class AnthropicConfig(BaseModel):
    """Anthropic provider config."""

    type: str = "anthropic"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class AWSBedrockConfig(BaseModel):
    """AWS Bedrock provider config."""

    type: str = "aws_bedrock"
    model_id: str
    region: str
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    api_key_location: Optional[str] = None


class AWSSageMakerConfig(BaseModel):
    """AWS SageMaker provider config."""

    type: str = "aws_sagemaker"
    endpoint_name: str
    region: str
    model_name: str
    hosted_provider: str
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    api_key_location: Optional[str] = None


class AzureConfig(BaseModel):
    """Azure OpenAI provider config."""

    type: str = "azure"
    deployment_id: str
    endpoint: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None
    api_version: Optional[str] = None
    azure_ad_token: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class DeepSeekConfig(BaseModel):
    """DeepSeek provider config."""

    type: str = "deepseek"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class FireworksConfig(BaseModel):
    """Fireworks provider config."""

    type: str = "fireworks"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class GCPVertexConfig(BaseModel):
    """GCP Vertex AI provider config."""

    type: str = "gcp-vertex"
    project_id: str
    region: str
    model_name: str
    vertex_credentials: Optional[str] = None
    vertex_location: Optional[str] = None
    api_key_location: Optional[str] = None


class GoogleAIStudioConfig(BaseModel):
    """Google AI Studio provider config."""

    type: str = "google-ai-studio"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class HyperbolicConfig(BaseModel):
    """Hyperbolic provider config."""

    type: str = "hyperbolic"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class MistralConfig(BaseModel):
    """Mistral provider config."""

    type: str = "mistral"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class TogetherConfig(BaseModel):
    """Together provider config."""

    type: str = "together"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class XAIConfig(BaseModel):
    """XAI provider config."""

    type: str = "xai"
    model_name: str
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


class BudDocConfig(BaseModel):
    """BudDoc provider config for document processing."""

    type: str = "buddoc"
    api_base: str
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    api_key_location: Optional[str] = None


ProviderConfig = Union[
    VLLMConfig,
    OpenAIConfig,
    AnthropicConfig,
    AWSBedrockConfig,
    AWSSageMakerConfig,
    AzureConfig,
    DeepSeekConfig,
    FireworksConfig,
    GCPVertexConfig,
    GoogleAIStudioConfig,
    HyperbolicConfig,
    MistralConfig,
    TogetherConfig,
    XAIConfig,
    BudDocConfig,
]


class ProxyModelPricing(BaseModel):
    """Pricing configuration for proxy models."""

    input_cost: float = Field(..., ge=0, lt=10000, description="Cost per input tokens (max 9999.999999)")
    output_cost: float = Field(..., ge=0, lt=10000, description="Cost per output tokens (max 9999.999999)")
    currency: str = Field(default="USD", description="Currency code")
    per_tokens: int = Field(default=1000, description="Number of tokens for the pricing unit")


class ProxyModelConfig(BaseModel):
    """Proxy model config with pricing information."""

    routing: list[ProxyProviderEnum]
    providers: dict[ProxyProviderEnum, ProviderConfig]
    endpoints: list[str]
    api_key: Optional[str] = None
    pricing: Optional[ProxyModelPricing] = None


class RateLimitConfig(BaseModel):
    """Rate limiting configuration for endpoints."""

    algorithm: str = "token_bucket"
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    burst_size: Optional[int] = None
    enabled: bool = True

    @field_validator("algorithm")
    def validate_algorithm(cls, v):
        allowed_algorithms = ["token_bucket", "fixed_window", "sliding_window"]
        if v not in allowed_algorithms:
            raise ValueError(f"Algorithm must be one of {allowed_algorithms}")
        return v

    @field_validator("requests_per_second", "requests_per_minute", "requests_per_hour", "burst_size")
    def validate_positive_integers(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Rate limit values must be positive integers")
        return v


class RetryConfig(BaseModel):
    """Retry configuration for failed requests."""

    num_retries: int = 0
    max_delay_s: float = 1.0

    @field_validator("num_retries")
    def validate_num_retries(cls, v):
        if v < 0:
            raise ValueError("Number of retries cannot be negative")
        if v > 10:
            raise ValueError("Number of retries cannot exceed 10")
        return v

    @field_validator("max_delay_s")
    def validate_max_delay(cls, v):
        if v <= 0:
            raise ValueError("Max delay must be positive")
        if v > 60:
            raise ValueError("Max delay cannot exceed 60 seconds")
        return v


class FallbackConfig(BaseModel):
    """Fallback endpoint configuration for primary endpoint failures."""

    fallback_models: List[str] = []  # Endpoint IDs (UUIDs)

    @field_validator("fallback_models")
    def validate_fallback_models(cls, v):
        if len(v) > 5:
            raise ValueError("Cannot have more than 5 fallback models")
        return v


class DeploymentSettingsConfig(BaseModel):
    """Main deployment settings configuration for endpoints."""

    rate_limits: Optional[RateLimitConfig] = None
    retry_config: Optional[RetryConfig] = None
    fallback_config: Optional[FallbackConfig] = None


class DeploymentSettingsResponse(SuccessResponse):
    """Response schema for deployment settings."""

    model_config = ConfigDict(from_attributes=True)

    endpoint_id: UUID4
    deployment_settings: DeploymentSettingsConfig
    object: str = "endpoint.deployment_settings"
    message: Optional[str] = "Successfully retrieved deployment settings"


class UpdateDeploymentSettingsRequest(BaseModel):
    """Request schema for updating deployment settings."""

    rate_limits: Optional[RateLimitConfig] = None
    retry_config: Optional[RetryConfig] = None
    fallback_config: Optional[FallbackConfig] = None


# Publication schemas


class UserSummary(BaseModel):
    """Summary schema for user details in publication history."""

    id: UUID4
    email: str
    name: str


class DeploymentPricingInput(BaseModel):
    """Input schema for deployment pricing."""

    input_cost: Decimal = Field(
        ..., decimal_places=6, ge=0, lt=10000, description="Cost per input tokens (max 9999.999999)"
    )
    output_cost: Decimal = Field(
        ..., decimal_places=6, ge=0, lt=10000, description="Cost per output tokens (max 9999.999999)"
    )
    currency: str = Field(default="USD", max_length=3, description="Currency code (ISO 4217)")
    per_tokens: int = Field(default=1000, gt=0, description="Number of tokens for the pricing unit")


class UpdatePublicationStatusRequest(BaseModel):
    """Request schema for updating publication status (publish/unpublish)."""

    action: Literal["publish", "unpublish"]
    pricing: Optional[DeploymentPricingInput] = Field(None, description="Required when action='publish'")
    action_metadata: Optional[dict] = None

    @model_validator(mode="after")
    def validate_pricing_required(self):
        """Validate that pricing is provided when publishing."""
        if self.action == "publish" and not self.pricing:
            raise ValueError("Pricing information is required when publishing an endpoint")
        return self


class PublicationHistoryEntry(BaseModel):
    """Schema for a single publication history entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    deployment_id: UUID4
    action: str
    performed_by: UUID4
    performed_at: datetime
    action_metadata: Optional[dict] = None
    previous_state: Optional[dict] = None
    new_state: Optional[dict] = None
    created_at: datetime
    modified_at: datetime
    # Include user details
    performed_by_user: Optional[UserSummary] = None


class PublicationHistoryResponse(PaginatedSuccessResponse):
    """Response schema for publication history endpoint."""

    history: list[PublicationHistoryEntry] = []
    object: str = "endpoint.publication_history"


class DeploymentPricingResponse(BaseModel):
    """Response schema for deployment pricing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    endpoint_id: UUID4
    input_cost: Decimal
    output_cost: Decimal
    currency: str
    per_tokens: int
    is_current: bool
    created_by: UUID4
    created_at: datetime
    modified_at: datetime


class PublishEndpointResponse(SuccessResponse):
    """Response schema for publish endpoint operations."""

    model_config = ConfigDict(from_attributes=True)

    endpoint_id: UUID4
    is_published: bool
    published_date: Optional[datetime] = None
    published_by: Optional[UUID4] = None
    pricing: Optional[DeploymentPricingResponse] = None
    object: str = "endpoint.publish"


# Use alias to avoid duplication and maintain DRY principle
UpdatePricingRequest = DeploymentPricingInput


class PricingHistoryResponse(PaginatedSuccessResponse):
    """Paginated pricing history response."""

    pricing_history: List[DeploymentPricingResponse] = []
    object: str = "endpoint.pricing_history"
