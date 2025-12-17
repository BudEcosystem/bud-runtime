from typing import Any, Literal, Optional
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase
from pydantic import BaseModel


class RunBenchmarkRequest(CloudEventBase):
    """Request body for running a benchmark."""

    benchmark_id: UUID
    name: str
    tags: Optional[list[dict[str, str]]] = None
    description: str
    concurrent_requests: int
    eval_with: Literal["dataset", "configuration"]
    datasets: Optional[list[dict]] = None
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    # use_cache: Optional[bool]
    # embedding_model: Optional[str]
    # eviction_policy: Optional[str]
    # max_size: Optional[int]
    # ttl: Optional[int]
    # score_threshold: Optional[float]
    user_id: UUID
    cluster_id: UUID
    bud_cluster_id: UUID
    nodes: Optional[list[dict[str, Any]]]
    model_id: UUID
    model: str
    provider_type: str
    user_confirmation: bool
    run_as_simulation: bool
    credential_id: Optional[UUID] = None
    simulator_id: Optional[UUID] = None
    # Configuration options from benchmark workflow step 6
    hardware_mode: Optional[str] = None
    selected_device_type: Optional[str] = None
    tp_size: Optional[int] = None
    pp_size: Optional[int] = None
    replicas: Optional[int] = None
    num_prompts: Optional[int] = None  # Total prompts to run (defaults to sum of dataset num_samples)
    # Storage configuration (from cluster settings)
    default_storage_class: Optional[str] = None
    default_access_mode: Optional[str] = None
    storage_size_gb: Optional[float] = None


class LLMBenchmarkResultSchema(BaseModel):
    duration: float
    successful_requests: int
    total_input_tokens: Optional[int] = 0
    total_output_tokens: Optional[int] = 0
    request_throughput: Optional[float] = None
    input_throughput: Optional[float] = None
    output_throughput: Optional[float] = None
    mean_output_throughput_per_user: Optional[float] = None
    p25_output_throughput_per_user: Optional[float] = None
    p75_output_throughput_per_user: Optional[float] = None
    p95_output_throughput_per_user: Optional[float] = None
    p99_output_throughput_per_user: Optional[float] = None
    min_output_throughput_per_user: Optional[float] = None
    max_output_throughput_per_user: Optional[float] = None
    mean_ttft_ms: Optional[float] = None
    median_ttft_ms: Optional[float] = None
    p25_ttft_ms: Optional[float] = None
    p75_ttft_ms: Optional[float] = None
    p95_ttft_ms: Optional[float] = None
    p99_ttft_ms: Optional[float] = None
    min_ttft_ms: Optional[float] = None
    max_ttft_ms: Optional[float] = None
    mean_tpot_ms: Optional[float] = None
    median_tpot_ms: Optional[float] = None
    p25_tpot_ms: Optional[float] = None
    p75_tpot_ms: Optional[float] = None
    p95_tpot_ms: Optional[float] = None
    p99_tpot_ms: Optional[float] = None
    min_tpot_ms: Optional[float] = None
    max_tpot_ms: Optional[float] = None
    mean_itl_ms: Optional[float] = None
    median_itl_ms: Optional[float] = None
    p25_itl_ms: Optional[float] = None
    p75_itl_ms: Optional[float] = None
    p95_itl_ms: Optional[float] = None
    p99_itl_ms: Optional[float] = None
    min_itl_ms: Optional[float] = None
    max_itl_ms: Optional[float] = None
    mean_e2el_ms: Optional[float] = None
    median_e2el_ms: Optional[float] = None
    p25_e2el_ms: Optional[float] = None
    p75_e2el_ms: Optional[float] = None
    p95_e2el_ms: Optional[float] = None
    p99_e2el_ms: Optional[float] = None
    min_e2el_ms: Optional[float] = None
    max_e2el_ms: Optional[float] = None
