from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase, TimestampMixin
from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..commons.constants import BenchmarkStatusEnum


if TYPE_CHECKING:
    from ..cluster_ops.models import Cluster


class BenchmarkSchema(PSQLBase, TimestampMixin):
    """Benchmark model.

    model_id and cluster_id are kept nullable True, because
    we don't want model delete or cluster delete to have any
    effect on benchmark data.
    """

    __tablename__ = "benchmark"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    benchmark_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    cluster_id: Mapped[UUID] = mapped_column(ForeignKey("cluster.id"), nullable=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    model_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    # nodes = [{"name": "fl4u44", "type": "cpu", "vendor": "amd"}]
    nodes: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    num_of_users: Mapped[int] = mapped_column(Integer, nullable=False)
    max_input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    # use_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    # embedding_model: Mapped[str] = mapped_column(String, nullable=True)
    # eviction_policy: Mapped[str] = mapped_column(String, nullable=True)
    # max_size: Mapped[int] = mapped_column(Integer, nullable=True)
    # ttl: Mapped[int] = mapped_column(Integer, nullable=True)
    # score_threshold: Mapped[float] = mapped_column(Float, nullable=True)
    datasets: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            BenchmarkStatusEnum,
            name="benchmark_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String, nullable=True)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="benchmarks")
    result: Mapped["BenchmarkResultSchema"] = relationship(
        "BenchmarkResultSchema", cascade="all,delete", back_populates="benchmark"
    )


class BenchmarkResultSchema(PSQLBase, TimestampMixin):
    """BenchmarkResult model."""

    __tablename__ = "benchmark_result"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    benchmark_id: Mapped[UUID] = mapped_column(ForeignKey("benchmark.id", ondelete="CASCADE"), nullable=False)
    # benchmark results
    duration: Mapped[float] = mapped_column(Float)
    successful_requests: Mapped[int] = mapped_column(Integer)
    total_input_tokens: Mapped[int] = mapped_column(Integer)
    total_output_tokens: Mapped[int] = mapped_column(Integer)
    request_throughput: Mapped[float] = mapped_column(Float, nullable=True)
    input_throughput: Mapped[float] = mapped_column(Float, nullable=True)
    output_throughput: Mapped[float] = mapped_column(Float, nullable=True)
    mean_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    p25_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    p75_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    p95_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    p99_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    min_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    max_output_throughput_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    mean_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    median_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p25_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p75_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p95_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p99_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    min_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    max_ttft_ms: Mapped[float] = mapped_column(Float, nullable=True)
    mean_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    median_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p25_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p75_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p95_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p99_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    min_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    max_tpot_ms: Mapped[float] = mapped_column(Float, nullable=True)
    mean_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    median_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p25_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p75_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p95_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p99_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    min_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    max_itl_ms: Mapped[float] = mapped_column(Float, nullable=True)
    mean_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    median_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p25_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p75_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p95_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    p99_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    min_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    max_e2el_ms: Mapped[float] = mapped_column(Float, nullable=True)
    # cache_hit: Mapped[int] = mapped_column(Integer)
    # mean_cache_latency: Mapped[float] = mapped_column(Float, nullable=True)

    benchmark: Mapped["BenchmarkSchema"] = relationship("BenchmarkSchema", back_populates="result")


class BenchmarkCRUD(CRUDMixin[BenchmarkSchema, None, None]):
    __model__ = BenchmarkSchema

    def __init__(self):
        """Initialize benchmark crud methods."""
        super().__init__(model=self.__model__)


class BenchmarkResultCRUD(CRUDMixin[BenchmarkResultSchema, None, None]):
    __model__ = BenchmarkResultSchema

    def __init__(self):
        """Initialize benchmark result crud methods."""
        super().__init__(model=self.__model__)
