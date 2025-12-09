from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, computed_field, model_validator

from budapp.commons.constants import BenchmarkFilterResourceEnum, BenchmarkStatusEnum
from budapp.commons.schemas import PaginatedSuccessResponse

from ..cluster_ops.schemas import ClusterResponse
from ..model_ops.schemas import ModelResponse


class RunBenchmarkWorkflowStepData(BaseModel):
    """Run Benchmark workflow step data."""

    # step 1
    name: str
    tags: list
    description: str
    concurrent_requests: int
    eval_with: Literal["dataset", "configuration"]
    user_id: Optional[UUID] = None

    # step 2
    datasets: Optional[list[UUID]] = None
    # or
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None

    # step 3
    # use_cache: Optional[bool]
    # embedding_model: Optional[str]
    # eviction_policy: Optional[str]
    # max_size: Optional[int]
    # ttl: Optional[int]
    # score_threshold: Optional[float]

    # step 3
    cluster_id: Optional[UUID] = None
    bud_cluster_id: Optional[UUID] = None

    # step 3.5 - hardware mode
    hardware_mode: Optional[Literal["dedicated", "shared"]] = None

    # step 4
    nodes: Optional[list[dict[str, Any]]] = None

    # step 5
    model_id: Optional[UUID] = None
    model: Optional[str] = None
    provider_type: Optional[str] = None

    # step 6
    credential_id: Optional[UUID] = None

    # step 7
    user_confirmation: Optional[bool] = None

    # step 8
    run_as_simulation: Optional[bool] = None


class RunBenchmarkWorkflowRequest(RunBenchmarkWorkflowStepData):
    """Run Benchmark Workflow Request."""

    # workflow metadata
    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False

    @model_validator(mode="after")
    def validate_fields(self) -> "RunBenchmarkWorkflowRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        # if self.use_cache is True and (self.embedding_model is None or self.eviction_policy is None or self.score_threshold is None):  # noqa: E501
        #     raise ValueError("embedding_model, eviction_policy and score_threshold must be provided if use_cache is True")

        return self


class BenchmarkFilter(BaseModel):
    name: str | None = None
    status: BenchmarkStatusEnum | None = None
    model_name: str | None = None
    cluster_name: str | None = None
    min_concurrency: int | None = None
    max_concurrency: int | None = None
    min_tpot: float | None = None
    max_tpot: float | None = None
    min_ttft: float | None = None
    max_ttft: float | None = None


class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    status: BenchmarkStatusEnum
    model: ModelResponse
    cluster: ClusterResponse
    node_type: str
    vendor_type: str
    concurrency: int
    tpot: float = 0.5
    ttft: float = 0.5
    created_at: datetime
    eval_with: Literal["dataset", "configuration"]
    dataset_ids: Optional[list[UUID4]]
    max_input_tokens: Optional[int]
    max_output_tokens: Optional[int]

    @model_validator(mode="before")
    @classmethod
    def extract_node_info(cls, values):
        """Extract Node type and Vendor type values."""
        if not isinstance(values, dict):  # Ensure values is a dictionary
            values = values.__dict__  # Convert object to dictionary

        nodes = values.get("nodes", [])
        # Handle both list and single object formats
        nodes_list = nodes if isinstance(nodes, list) else [nodes] if nodes else []

        # Extract device types and vendor names in a single iteration
        node_types = set()
        vendor_types = set()

        for node in nodes_list:
            if not isinstance(node, dict):
                continue
            for device in node.get("devices", []):
                # Ensure device is a dictionary
                if isinstance(device, dict):
                    # Extract device type
                    device_type = device.get("type")
                    if device_type:
                        node_types.add(device_type)

                    # Extract vendor name
                    device_config = device.get("device_config")
                    if isinstance(device_config, dict):
                        vendor = device_config.get("vendor")
                        if vendor:
                            vendor_types.add(vendor)

        values["node_type"] = ", ".join(sorted(node_types)) or "Unknown"
        values["vendor_type"] = ", ".join(sorted(vendor_types)) or "Unknown"
        return values


class BenchmarkPaginatedResponse(PaginatedSuccessResponse):
    benchmarks: list[BenchmarkResponse]


class BenchmarkResultResponse(BaseModel):
    id: UUID4
    benchmark_id: UUID4
    duration: float
    successful_requests: int
    total_input_tokens: int
    total_output_tokens: int
    request_throughput: float
    input_throughput: float
    output_throughput: float
    p25_throughput: float
    p75_throughput: float
    p95_throughput: float
    p99_throughput: float
    min_throughput: float
    max_throughput: float
    mean_ttft_ms: float
    median_ttft_ms: float
    p25_ttft_ms: float
    p75_ttft_ms: float
    p95_ttft_ms: float
    p99_ttft_ms: float
    min_ttft_ms: float
    max_ttft_ms: float
    mean_tpot_ms: float
    median_tpot_ms: float
    p25_tpot_ms: float
    p75_tpot_ms: float
    p95_tpot_ms: float
    p99_tpot_ms: float
    min_tpot_ms: float
    max_tpot_ms: float
    mean_itl_ms: float
    median_itl_ms: float
    p25_itl_ms: float
    p75_itl_ms: float
    p95_itl_ms: float
    p99_itl_ms: float
    min_itl_ms: float
    max_itl_ms: float
    mean_e2el_ms: float
    median_e2el_ms: float
    p25_e2el_ms: float
    p75_e2el_ms: float
    p95_e2el_ms: float
    p99_e2el_ms: float
    min_e2el_ms: float
    max_e2el_ms: float
    created_at: datetime
    modified_at: datetime


class BenchmarkRequestMetrics(BaseModel):
    benchmark_id: UUID
    dataset_id: UUID | None = None
    latency: float | None = None
    success: bool | None = None
    error: str | None = None
    prompt_len: int | None = None
    output_len: int | None = None
    req_output_throughput: float | None = None
    ttft: float | None = None
    tpot: float | None = None
    itl: list | None = None

    model_config = ConfigDict(extra="allow")

    @computed_field(return_type=float)
    @property
    def itl_sum(self) -> float:
        """Compute sum of inter-token latencies (itl) if available."""
        return sum(self.itl) if self.itl else 0.0


class AddRequestMetricsRequest(BaseModel):
    metrics: list[BenchmarkRequestMetrics]


# Benchmark Filter Listing API


class BenchmarkFilterFields(BaseModel):
    """Benchmark filter fields schema."""

    model_name: str | None = None
    cluster_name: str | None = None
    resource: BenchmarkFilterResourceEnum = Field(default=BenchmarkFilterResourceEnum.MODEL)


class BenchmarkFilterValueResponse(PaginatedSuccessResponse):
    """Benchmark filter values response schema."""

    result: list[str]
