from typing import List, Optional

from budmicroframe.commons import logging
from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from .schemas import Feedback


logger = logging.get_logger(__name__)


class SimulationResultsSchema(PSQLBase):
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(UUID(as_uuid=True), nullable=False)
    model_name = Column(String(255), nullable=False)
    model_version = Column(String(50), nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    target_concurrency = Column(Integer, nullable=False)
    target_ttft = Column(Float, nullable=False)
    target_throughput_per_user = Column(Float, nullable=False)
    target_e2e_latency = Column(Float, nullable=False)
    cluster_id = Column(String(255), nullable=False)
    node_id = Column(String(255), nullable=False)
    node_name = Column(String(255), nullable=False)
    device_id = Column(String(255), nullable=False)
    device_name = Column(String(255), nullable=False)
    device_type = Column(String(10), nullable=False)
    device_model = Column(String(255), nullable=True)
    raw_name = Column(String(255), nullable=True)
    available_count = Column(Integer, nullable=False)
    mem_per_gpu_in_gb = Column(Float, nullable=False)
    hbm_bandwidth_in_gb_per_sec = Column(Float, nullable=False)
    intra_node_bandwidth_in_gb_per_sec = Column(Float, nullable=False)
    intra_node_min_message_latency = Column(Float, nullable=False)
    peak_fp16_tflops = Column(Float, nullable=False)
    peak_i8_tflops = Column(Float, nullable=False)
    peak_i4_tflops = Column(Float, nullable=False)
    inter_node_bandwidth_in_gb_per_sec = Column(Float, nullable=False)
    engine = Column(String(255), nullable=False)
    engine_image = Column(String(255), nullable=False)
    engine_version = Column(String(50), nullable=True)
    tool_calling_parser_type = Column(String(100), nullable=True)
    reasoning_parser_type = Column(String(100), nullable=True)
    architecture_family = Column(String(100), nullable=True)
    chat_template = Column(String(500), nullable=True)
    supports_lora = Column(Boolean, nullable=True, default=False)
    supports_pipeline_parallelism = Column(Boolean, nullable=True, default=False)
    top_k_configs = Column(JSONB)
    is_blacklisted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    modified_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        """Return a string representation of the SimulationResultsSchema."""
        return f"<SimulationSchema(id={self.id}, model_name={self.model_name}, workflow_id={self.workflow_id})>"


class SimulationResultsCRUD(CRUDMixin[SimulationResultsSchema, None, None]):
    __model__ = SimulationResultsSchema

    def __init__(self):
        """Initialize the simulation results CRUD handler."""
        super().__init__(model=self.__model__)

    def fetch_topk_configs_by_cluster(
        self,
        workflow_id: str,
        cluster_id: Optional[str] = None,
        error_rate_threshold: float = 0.5,
        limit: int = 10,
        skip: int = 0,
        session: Optional[Session] = None,
    ):
        """Fetch top-k configurations by cluster using optimized query."""
        _session = session or self.get_session()
        try:
            # Use a single CTE query instead of nested subqueries for better performance
            # This leverages the new indexes we created
            base_query = _session.query(self.model).filter(
                self.model.workflow_id == workflow_id,
                self.model.top_k_configs.isnot(None),
                func.cast(func.jsonb_extract_path_text(self.model.top_k_configs, "error_rate"), Float)
                <= float(error_rate_threshold),
                self.model.is_blacklisted.isnot(True),
            )

            if cluster_id is not None:
                base_query = base_query.filter(self.model.cluster_id == cluster_id)

            # Use window function to rank by cost within each cluster
            # This is more efficient than the nested subquery approach

            ranked_query = _session.query(
                self.model,
                func.row_number()
                .over(
                    partition_by=self.model.cluster_id,
                    order_by=func.cast(
                        func.jsonb_extract_path_text(self.model.top_k_configs, "cost_per_million_tokens"), Float
                    ),
                )
                .label("cost_rank"),
            ).filter(
                self.model.workflow_id == workflow_id,
                self.model.top_k_configs.isnot(None),
                func.cast(func.jsonb_extract_path_text(self.model.top_k_configs, "error_rate"), Float)
                <= float(error_rate_threshold),
                self.model.is_blacklisted.isnot(True),
            )

            if cluster_id is not None:
                ranked_query = ranked_query.filter(self.model.cluster_id == cluster_id)

            # Convert to subquery and get the best result per cluster
            ranked_subquery = ranked_query.subquery()

            best_per_cluster = (
                _session.query(ranked_subquery)
                .filter(ranked_subquery.c.cost_rank == 1)
                .order_by(
                    func.cast(
                        func.jsonb_extract_path_text(ranked_subquery.c.top_k_configs, "cost_per_million_tokens"), Float
                    )
                )
            )

            # Get total count before applying pagination
            total_count = best_per_cluster.count()

            # Apply pagination
            paginated_results = best_per_cluster.offset(skip).limit(limit).all()

            # Convert back to the expected format - group results by cluster_id
            results = []
            for row in paginated_results:
                # Extract the simulation_results object from the row
                sim_result = _session.query(self.model).filter(self.model.id == row.id).first()
                results.append(sim_result)  # Return individual result for node group format

            return results, total_count
        except SQLAlchemyError as e:
            logger.exception("Failed to read data from %s: %s", self.model.__tablename__, str(e))
            return [], 0
        finally:
            self.cleanup_session(_session if session is None else None)

    def update_feedback(self, feedback: List[Feedback], session: Optional[Session] = None):
        """Update feedback for simulation results."""
        _session = session or self.get_session()

        failed_nodes = [int(f.config_id) for f in feedback if f.failed]
        successful_nodes = [int(f.config_id) for f in feedback if not f.failed]
        if not len(failed_nodes) and not len(successful_nodes):
            return

        try:
            _session.query(self.model).filter(self.model.id.in_(failed_nodes)).update({"is_blacklisted": True})
            _session.query(self.model).filter(self.model.id.in_(successful_nodes)).update({"is_blacklisted": False})
            _session.commit()
        except SQLAlchemyError as e:
            logger.exception("Failed to update feedback for %s configs: %s", len(failed_nodes), str(e))
            raise e
