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

"""Database models for evaluation sync state tracking and dataset metadata."""

from datetime import datetime
from uuid import uuid4

from budmicroframe.shared.psql_service import PSQLBase
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship


class ExpTrait(PSQLBase):
    """Evaluation traits that datasets can be associated with."""

    __tablename__ = "exp_traits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    datasets = relationship("ExpDataset", secondary="exp_traits_dataset_pivot", back_populates="traits", lazy="select")


class ExpDataset(PSQLBase):
    """Evaluation datasets with comprehensive metadata."""

    __tablename__ = "exp_datasets"
    __table_args__ = (UniqueConstraint("name", name="uq_expdataset_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    meta_links = Column(JSONB, nullable=True)  # Storing Github, Paper, etc. links
    config_validation_schema = Column(JSONB, nullable=True)  # Required to validate the config shared

    estimated_input_tokens = Column(Integer, nullable=True)
    estimated_output_tokens = Column(Integer, nullable=True)

    language = Column(JSONB, nullable=True)
    domains = Column(JSONB, nullable=True)
    concepts = Column(JSONB, nullable=True)
    humans_vs_llm_qualifications = Column(JSONB, nullable=True)
    task_type = Column(JSONB, nullable=True)

    modalities = Column(JSONB, nullable=True)  # List of modalities, e.g., ["text", "image"]

    sample_questions_answers = Column(JSONB, nullable=True)  # Sample Q&A data in JSON format
    advantages_disadvantages = Column(JSONB, nullable=True)  # {"advantages": ["str1"], "disadvantages": ["str2"]}

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    versions = relationship("ExpDatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    traits = relationship("ExpTrait", secondary="exp_traits_dataset_pivot", back_populates="datasets", lazy="select")


class ExpTraitsDatasetPivot(PSQLBase):
    """Many-to-many relationship between traits and datasets."""

    __tablename__ = "exp_traits_dataset_pivot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    trait_id = Column(UUID(as_uuid=True), ForeignKey("exp_traits.id"), nullable=False)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("exp_datasets.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExpDatasetVersion(PSQLBase):
    """Specific versions of evaluation datasets."""

    __tablename__ = "exp_dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_expdatasetversion_dataset_version"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("exp_datasets.id"), nullable=False)
    version = Column(String, nullable=False)
    meta = Column(JSONB, nullable=True)  # URL, size, checksum, sample_count, metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dataset = relationship("ExpDataset", back_populates="versions")


class EvalSyncState(PSQLBase):
    """Track evaluation dataset synchronization state and history."""

    __tablename__ = "eval_sync_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    manifest_version = Column(String(50), nullable=False)
    sync_timestamp = Column(String, nullable=False)  # ISO format timestamp to match budapp
    sync_status = Column(String(20), nullable=False)  # 'completed', 'failed', 'in_progress'
    sync_metadata = Column(JSONB, nullable=True)  # Store manifest details, datasets synced, errors, etc.
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
