# budapp/eval_ops/models.py

from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin


# ------------------------ Enums ------------------------


class ExperimentStatusEnum(PyEnum):
    ACTIVE = "active"
    DELETED = "deleted"
    DRAFT = "draft"


class RunStatusEnum(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    DELETED = "deleted"


class ModalityEnum(PyEnum):
    TEXT = "text"  # Textual data, e.g., documents, sentences
    IMAGE = "image"  # Image data, e.g., photographs, diagrams
    VIDEO = "video"  # Video data, e.g., video clips, animations
    ACTIONS = "actions"  # Action data, e.g., button clicks, mouse movements
    EMBEDDING = "embedding"  # Embedding data, e.g., vector representations of text, images, or audio


class EvaluationStatusEnum(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ------------------------ Core Tables ------------------------


class Experiment(Base, TimestampMixin):
    """Experiments are what users create to organize their evaluation work."""

    __tablename__ = "experiments"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        PG_ENUM(
            *[e.value for e in ExperimentStatusEnum],
            name="experiment_status_enum",
        ),
        nullable=False,
        default=ExperimentStatusEnum.ACTIVE.value,
    )
    created_by: Mapped[uuid4] = mapped_column(ForeignKey("user.id"), nullable=False)
    project_id: Mapped[uuid4] = mapped_column(ForeignKey("project.id"), nullable=True)
    tags: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True, default=list)  # DEPRECATED - use tag_ids
    tag_ids: Mapped[Optional[list[uuid4]]] = mapped_column(
        PG_ARRAY(PG_UUID(as_uuid=True)), nullable=True, default=list
    )  # NEW - array of EvalTag IDs

    # Relationships
    runs = relationship("Run", back_populates="experiment", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="experiment", cascade="all, delete-orphan")


class Evaluation(Base, TimestampMixin):
    """Evaluations represent grouped model-dataset testing sessions within an experiment."""

    __tablename__ = "evaluations"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[uuid4] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    workflow_id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid4] = mapped_column(ForeignKey("user.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        PG_ENUM(
            *[e.value for e in EvaluationStatusEnum],
            name="evaluation_status_enum",
        ),
        nullable=False,
        default=EvaluationStatusEnum.PENDING.value,
    )
    trait_ids: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    duration_in_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eta_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Traits Score
    trait_scores: Mapped[Optional[dict[str, str]]] = mapped_column(JSONB, nullable=True)

    # Relationships
    experiment = relationship("Experiment", back_populates="evaluations")
    runs = relationship("Run", back_populates="evaluation", cascade="all, delete-orphan")


class Run(Base, TimestampMixin):
    """Runs represent individual model-dataset evaluation pairs within an experiment."""

    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("experiment_id", "run_index", name="uq_run_experiment_index"),)

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[uuid4] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    evaluation_id: Mapped[uuid4] = mapped_column(
        ForeignKey("evaluations.id"), nullable=True
    )  # Nullable for backward compatibility
    run_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Auto-incrementing index per experiment
    endpoint_id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dataset_version_id: Mapped[uuid4] = mapped_column(ForeignKey("exp_dataset_versions.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        PG_ENUM(*[e.value for e in RunStatusEnum], name="run_status_enum"),
        nullable=False,
        default=RunStatusEnum.PENDING.value,
    )
    config: Mapped[dict] = mapped_column(JSONB, nullable=True)  # Run-specific configuration

    # Relationships
    experiment = relationship("Experiment", back_populates="runs")
    evaluation = relationship("Evaluation", back_populates="runs")
    dataset_version = relationship("ExpDatasetVersion", back_populates="runs")
    metrics = relationship("ExpMetric", back_populates="run", cascade="all, delete-orphan")
    raw_results = relationship("ExpRawResult", back_populates="run", cascade="all, delete-orphan")


# ------------------------ Lookup Tables ------------------------


class ExpModel(Base, TimestampMixin):
    __tablename__ = "exp_models"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    model_in_db: Mapped[str] = mapped_column(String, nullable=False)  # Should be valid_endpoint_id

    # Relationships
    # Note: No longer has relationship with runs table


class ExpTrait(Base, TimestampMixin):
    __tablename__ = "exp_traits"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    icon: Mapped[str] = mapped_column(String, nullable=True)

    # Relationships
    datasets = relationship(
        "ExpDataset",
        secondary="exp_traits_dataset_pivot",
        back_populates="traits",
        lazy="select",
    )


class EvalTag(Base, TimestampMixin):
    """Tags for organizing experiments. Global scope - shared across all users."""

    __tablename__ = "eval_tags"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Note: Unique constraint on LOWER(name) will be added via migration for case-insensitive uniqueness


class ExpDataset(Base, TimestampMixin):
    __tablename__ = "exp_datasets"
    __table_args__ = (UniqueConstraint("name", name="uq_expdataset_name"),)

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)

    meta_links: Mapped[dict] = mapped_column(JSONB, nullable=True)  # Storing Github, Paper, etc. links
    config_validation_schema: Mapped[dict] = mapped_column(
        JSONB, nullable=True
    )  # Required to validate the config shared

    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)

    language: Mapped[list] = mapped_column(JSONB, nullable=True)
    domains: Mapped[list] = mapped_column(JSONB, nullable=True)
    concepts: Mapped[list] = mapped_column(JSONB, nullable=True)
    humans_vs_llm_qualifications: Mapped[list] = mapped_column(JSONB, nullable=True)
    task_type: Mapped[list] = mapped_column(JSONB, nullable=True)

    modalities: Mapped[list] = mapped_column(JSONB, nullable=True)  # List of modalities, e.g., ["text", "image"]

    sample_questions_answers: Mapped[dict] = mapped_column(JSONB, nullable=True)  # Sample Q&A data in JSON format
    advantages_disadvantages: Mapped[dict] = mapped_column(
        JSONB, nullable=True
    )  # {"advantages": ["str1"], "disadvantages": ["str2"]}

    eval_types: Mapped[dict] = mapped_column(
        JSONB, nullable=True
    )  # Stores evaluation type configurations like {"gen": "demo_gsm8k_chat_gen", "ppl": "config_name"}

    # New fields for enriched dataset information (stored as JSONB for list support)
    why_run_this_eval: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # List of reasons to run eval
    what_to_expect: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # List of expectations from eval
    additional_info: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # Flexible JSON field for top_5 lists, age_distribution, and future metadata

    # Evaluation configuration fields
    metrics: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # List of metric names (e.g., ["accuracy"])
    evaluator: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Evaluator class name

    # Relationships
    versions = relationship(
        "ExpDatasetVersion",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    traits = relationship(
        "ExpTrait",
        secondary="exp_traits_dataset_pivot",
        back_populates="datasets",
        lazy="select",
    )


class ExpTraitsDatasetPivot(Base, TimestampMixin):
    __tablename__ = "exp_traits_dataset_pivot"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    trait_id: Mapped[uuid4] = mapped_column(ForeignKey("exp_traits.id"), nullable=False)
    dataset_id: Mapped[uuid4] = mapped_column(ForeignKey("exp_datasets.id"), nullable=False)


class ExpDatasetVersion(Base, TimestampMixin):
    __tablename__ = "exp_dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_expdatasetversion_dataset_version"),)

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[uuid4] = mapped_column(ForeignKey("exp_datasets.id"), nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Relationships
    dataset = relationship("ExpDataset", back_populates="versions")
    runs = relationship("Run", back_populates="dataset_version", cascade="all, delete-orphan")


# ------------------------ Evaluation Results ------------------------


class ExpMetric(Base):
    __tablename__ = "exp_metrics"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "metric_name",
            "mode",
            name="uq_expmetrics_run_metric_mode",
        ),
    )

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[uuid4] = mapped_column(ForeignKey("runs.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    metric_value: Mapped[float] = mapped_column(NUMERIC(6, 2), nullable=False)

    # Relationships
    run = relationship("Run", back_populates="metrics")


class ExpRawResult(Base, TimestampMixin):
    __tablename__ = "exp_raw_results"
    __table_args__ = (UniqueConstraint("run_id", name="uq_exprawresults_run"),)

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[uuid4] = mapped_column(ForeignKey("runs.id"), nullable=False)
    preview_results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    full_results_uri: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    run = relationship("Run", back_populates="raw_results")


# ------------------------ Sync State Table ------------------------


class EvalSyncState(Base, TimestampMixin):
    """Track evaluation dataset synchronization state and history."""

    __tablename__ = "eval_sync_state"

    id: Mapped[uuid4] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    manifest_version: Mapped[str] = mapped_column(String(50), nullable=False)
    sync_timestamp: Mapped[str] = mapped_column(String, nullable=False)  # ISO format timestamp
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'completed', 'failed', 'in_progress'
    sync_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=True
    )  # Store manifest details, datasets synced, errors, etc.
