from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase, TimestampMixin
from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Uuid,
    and_,
    cast,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from ..cluster_ops.models import Cluster as ClusterModel
from ..commons.constants import BenchmarkFilterResourceEnum, BenchmarkStatusEnum
from ..model_ops.models import Model


if TYPE_CHECKING:
    from ..cluster_ops.models import Cluster
    from ..model_ops.models import Model
    from ..user_ops.models import User


class BenchmarkSchema(PSQLBase, TimestampMixin):
    """Benchmark model.

    model_id and cluster_id are kept nullable True, because
    we don't want model delete or cluster delete to have any
    effect on benchmark data.
    """

    __tablename__ = "benchmark"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    bud_cluster_benchmark_id: Mapped[UUID] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    eval_with: Mapped[str] = mapped_column(String, nullable=True)
    max_input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    dataset_ids: Mapped[list] = mapped_column(JSONB, nullable=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id"), nullable=True)
    cluster_id: Mapped[UUID] = mapped_column(ForeignKey("cluster.id"), nullable=True)
    nodes: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            BenchmarkStatusEnum,
            name="benchmark_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String, nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=True)

    model: Mapped["Model"] = relationship("Model", back_populates="benchmarks")
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="benchmarks")
    user: Mapped["User"] = relationship("User", back_populates="benchmarks")
    request_metrics: Mapped[list["BenchmarkRequestMetricsSchema"]] = relationship(
        "BenchmarkRequestMetricsSchema", back_populates="benchmark"
    )


class BenchmarkCRUD(CRUDMixin[BenchmarkSchema, None, None]):
    __model__ = BenchmarkSchema

    def __init__(self):
        """Initialize benchmark crud methods."""
        super().__init__(model=self.__model__)

    async def fetch_many_with_search(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List] = None,
        search: bool = False,
    ):
        """Fetch many with search."""
        filters = filters or {}
        order_by = order_by or []

        translated_filters = filters.copy()
        translated_order_by = order_by.copy()
        for field in translated_filters:
            if field in [
                "model_name",
                "cluster_name",
                "min_concurrency",
                "max_concurrency",
                "min_tpot",
                "max_tpot",
                "min_ttft",
                "max_ttft",
            ]:
                filters.pop(field)

        print(translated_filters)
        print(translated_order_by)

        await self.validate_fields(self.model, filters)

        # explicit conditions for order by model_name, cluster_name, modality
        explicit_conditions = []
        for field in translated_order_by:
            if field[0] == "model_name":
                sorting_stmt = await self.generate_sorting_stmt(
                    Model,
                    [
                        ("name", field[1]),
                    ],
                )
                explicit_conditions.extend(sorting_stmt)
                order_by.remove(field)
            elif field[0] == "cluster_name":
                sorting_stmt = await self.generate_sorting_stmt(
                    ClusterModel,
                    [
                        ("name", field[1]),
                    ],
                )
                explicit_conditions.extend(sorting_stmt)
                order_by.remove(field)

        if search:
            search_conditions = []
            for field, value in translated_filters.items():
                if field == "model_name":
                    search_conditions.extend(await self.generate_search_stmt(Model, {"name": value}))
                elif field == "cluster_name":
                    search_conditions.extend(await self.generate_search_stmt(ClusterModel, {"name": value}))
                elif field == "min_concurrency":
                    search_conditions.append(self.model.concurrency >= value)
                elif field == "max_concurrency":
                    search_conditions.append(self.model.concurrency <= value)
                elif field == "min_tpot":
                    search_conditions.append(cast(self.model.result["mean_tpot_ms"], Float) >= value)
                elif field == "max_tpot":
                    search_conditions.append(cast(self.model.result["mean_tpot_ms"], Float) <= value)
                elif field == "min_ttft":
                    search_conditions.append(cast(self.model.result["mean_ttft_ms"], Float) >= value)
                elif field == "max_ttft":
                    search_conditions.append(cast(self.model.result["mean_ttft_ms"], Float) <= value)
            search_conditions.extend(await self.generate_search_stmt(self.model, filters))

            stmt = select(self.model).join(Model).join(ClusterModel).filter(and_(*search_conditions))
            count_stmt = (
                select(func.count())
                .select_from(self.model)
                .join(Model)
                .join(ClusterModel)
                .filter(and_(*search_conditions))
            )
        else:
            stmt = select(BenchmarkSchema).join(Model).join(ClusterModel)
            count_stmt = select(func.count()).select_from(self.model).join(Model).join(ClusterModel)
            for key, value in translated_filters.items():
                if key == "model_name":
                    stmt = stmt.filter(Model.name == value)
                    count_stmt = count_stmt.filter(Model.name == value)
                elif key == "cluster_name":
                    stmt = stmt.filter(ClusterModel.name == value)
                    count_stmt = count_stmt.filter(ClusterModel.name == value)
                elif key == "min_concurrency":
                    stmt = stmt.filter(self.model.concurrency >= value)
                    count_stmt = count_stmt.filter(self.model.concurrency >= value)
                elif key == "max_concurrency":
                    stmt = stmt.filter(self.model.concurrency <= value)
                    count_stmt = count_stmt.filter(self.model.concurrency <= value)
                elif key == "min_tpot":
                    stmt = stmt.filter(cast(self.model.result["mean_tpot_ms"], Float) >= value)
                    count_stmt = count_stmt.filter(cast(self.model.result["mean_tpot_ms"], Float) >= value)
                elif key == "max_tpot":
                    stmt = stmt.filter(cast(self.model.result["mean_tpot_ms"], Float) <= value)
                    count_stmt = count_stmt.filter(cast(self.model.result["mean_tpot_ms"], Float) <= value)
                elif key == "min_ttft":
                    stmt = stmt.filter(cast(self.model.result["mean_ttft_ms"], Float) >= value)
                    count_stmt = count_stmt.filter(cast(self.model.result["mean_ttft_ms"], Float) >= value)
                elif key == "max_ttft":
                    stmt = stmt.filter(cast(self.model.result["mean_ttft_ms"], Float) <= value)
                    count_stmt = count_stmt.filter(cast(self.model.result["mean_ttft_ms"], Float) <= value)
            for key, value in filters.items():
                stmt = stmt.filter(getattr(self.model, key) == value)
                count_stmt = count_stmt.filter(getattr(self.model, key) == value)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if translated_order_by:
            sort_conditions = await self.generate_sorting_stmt(self.model, order_by)
            # Extend sort conditions with explicit conditions
            sort_conditions.extend(explicit_conditions)
            stmt = stmt.order_by(*sort_conditions)

        print(stmt)

        result = self.scalars_all(stmt)

        return result, count

    async def list_unique_model_cluster_names(
        self,
        resource: BenchmarkFilterResourceEnum,
        value: str,
        search: bool,
        offset: int,
        limit: int,
        session: Session,
    ) -> Tuple[List[str], int]:
        """List distinct model or cluster names used in benchmarks.

        Args:
            resource: The resource to filter by.
            value: The value to filter by.
            search: Whether to search for the value.
            offset: The offset to start the fetch from.
            limit: The limit to fetch.

        Returns:
            Tuple[List[str], int]: A tuple containing the list of unique model or cluster names and the total count.
        """
        if resource == BenchmarkFilterResourceEnum.MODEL:
            col_name = Model.name
            join_model = Model
            join_condition = self.model.model_id == Model.id
        else:
            col_name = ClusterModel.name
            join_model = ClusterModel
            join_condition = self.model.cluster_id == ClusterModel.id

        # Create query and count query
        stmt = select(func.distinct(col_name).label("name")).select_from(self.model).join(join_model, join_condition)
        count_stmt = (
            select(func.count(func.distinct(col_name))).select_from(self.model).join(join_model, join_condition)
        )

        # Generate search or filter query
        if value:
            if search:
                stmt = stmt.where(col_name.ilike(f"%{value}%"))
                count_stmt = count_stmt.where(col_name.ilike(f"%{value}%"))
            else:
                stmt = stmt.where(col_name == value)
                count_stmt = count_stmt.where(col_name == value)

        # Apply limit and offset
        stmt = stmt.order_by(col_name).offset(offset).limit(limit)

        # Execute query
        result = session.execute(stmt).scalars().all()
        count = self.execute_scalar(count_stmt)

        return result, count


class BenchmarkRequestMetricsSchema(PSQLBase, TimestampMixin):
    """BenchmarkRequestMetricsSchema model."""

    __tablename__ = "benchmark_request_metrics"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    benchmark_id: Mapped[UUID] = mapped_column(ForeignKey("benchmark.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("dataset.id"), nullable=True)

    # benchmark results
    latency: Mapped[float] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str] = mapped_column(String, nullable=True)
    prompt_len: Mapped[int] = mapped_column(Integer, nullable=False)
    output_len: Mapped[int] = mapped_column(Integer, nullable=True)
    req_output_throughput: Mapped[float] = mapped_column(Float, nullable=True)
    ttft: Mapped[float] = mapped_column(Float, nullable=True)
    tpot: Mapped[float] = mapped_column(Float, nullable=True)
    itl: Mapped[list] = mapped_column(JSONB, nullable=True)

    benchmark: Mapped["BenchmarkSchema"] = relationship("BenchmarkSchema", back_populates="request_metrics")


class BenchmarkRequestMetricsCRUD(CRUDMixin[BenchmarkRequestMetricsSchema, None, None]):
    __model__ = BenchmarkRequestMetricsSchema

    def __init__(self):
        """Initialize benchmark request metrics crud methods."""
        super().__init__(model=self.__model__)

    def fetch_count(self, conditions: Dict[str, Any]):
        """Fetch count of benchmark request metrics based on conditions."""
        stmt = select(func.count()).select_from(self.model).filter_by(**conditions)
        return self.execute_scalar(stmt)
