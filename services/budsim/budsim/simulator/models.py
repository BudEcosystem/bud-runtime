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
        """Fetch top-k configurations by cluster."""
        _session = session or self.get_session()
        try:
            min_cost_subquery = _session.query(
                self.model.cluster_id,
                func.min(func.jsonb_extract_path_text(self.model.top_k_configs, "cost_per_million_tokens")).label(
                    "min_cost_per_million_tokens"
                ),
            ).filter(
                self.model.workflow_id == workflow_id,
                self.model.top_k_configs.isnot(None),
                func.cast(func.jsonb_extract_path_text(self.model.top_k_configs, "error_rate"), Float)
                <= float(error_rate_threshold),
                self.model.is_blacklisted.isnot(True),
            )

            if cluster_id is not None:
                min_cost_subquery = min_cost_subquery.filter(self.model.cluster_id == cluster_id)

            min_cost_subquery = min_cost_subquery.group_by(self.model.cluster_id).subquery()

            total_count = _session.query(func.count().label("group_count")).select_from(min_cost_subquery).scalar()

            unique_groups = (
                _session.query(
                    min_cost_subquery.c.cluster_id,
                    min_cost_subquery.c.min_cost_per_million_tokens,
                )
                .order_by(min_cost_subquery.c.min_cost_per_million_tokens.asc())
                .offset(skip)
                .limit(limit)
                .all()
            )

            results = []
            for group in unique_groups:
                cluster_id, _ = group
                subquery = (
                    _session.query(
                        self.model.node_id,
                        self.model.device_id,
                        func.min(
                            func.jsonb_extract_path_text(self.model.top_k_configs, "cost_per_million_tokens")
                        ).label("min_cost"),
                    )
                    .filter(
                        self.model.workflow_id == workflow_id,
                        self.model.cluster_id == cluster_id,
                        self.model.top_k_configs.isnot(None),
                        func.cast(func.jsonb_extract_path_text(self.model.top_k_configs, "error_rate"), Float)
                        <= float(error_rate_threshold),
                        self.model.is_blacklisted.isnot(True),
                    )
                    .group_by(self.model.node_id, self.model.device_id)
                ).subquery()

                matches = (
                    _session.query(self.model)
                    .join(
                        subquery,
                        (subquery.c.node_id == self.model.node_id) & (subquery.c.device_id == self.model.device_id),
                    )
                    .filter(
                        func.jsonb_extract_path_text(self.model.top_k_configs, "cost_per_million_tokens")
                        == subquery.c.min_cost
                    )
                    .distinct(self.model.node_id, self.model.device_id)
                    .all()
                )
                results.append(matches)

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
