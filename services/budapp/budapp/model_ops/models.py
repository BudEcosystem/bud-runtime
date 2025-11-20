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

"""The model ops package, containing essential business logic, services, and routing configurations for the model ops."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import false as sa_false

from budapp.commons.constants import (
    BaseModelRelationEnum,
    CloudModelStatusEnum,
    ModalityEnum,
    ModelEndpointEnum,
    ModelLicenseObjectTypeEnum,
    ModelProviderTypeEnum,
    ModelSecurityScanStatusEnum,
    ModelStatusEnum,
    ProviderCapabilityEnum,
)
from budapp.commons.database import Base, TimestampMixin


class Model(Base, TimestampMixin):
    """Model for a AI model."""

    __tablename__ = "model"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    tasks: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=True)
    model_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    huggingface_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bud_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    scan_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    eval_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    strengths: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True)
    limitations: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True)
    languages: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True)
    use_cases: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True)
    minimum_requirements: Mapped[dict] = mapped_column(JSONB, nullable=True)
    examples: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    base_model: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True)
    base_model_relation: Mapped[str] = mapped_column(
        Enum(
            BaseModelRelationEnum,
            name="base_model_relation_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    model_type: Mapped[str] = mapped_column(String, nullable=True)
    family: Mapped[str] = mapped_column(String, nullable=True)
    model_weights_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    storage_size_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kv_cache_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    architecture_text_config: Mapped[dict] = mapped_column(JSONB, nullable=True)
    architecture_vision_config: Mapped[dict] = mapped_column(JSONB, nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            ModelStatusEnum,
            name="model_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ModelStatusEnum.ACTIVE,
    )
    modality: Mapped[List[str]] = mapped_column(
        PG_ARRAY(
            PG_ENUM(
                ModalityEnum,
                name="modality_enum",
                values_callable=lambda x: [e.value for e in x],
                create_type=False,
            ),
        ),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        Enum(
            ModelProviderTypeEnum,
            name="model_provider_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    uri: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("provider.id"), nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    recommended_cluster_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    supported_endpoints: Mapped[List[str]] = mapped_column(
        PG_ARRAY(
            PG_ENUM(
                ModelEndpointEnum,
                name="model_endpoint_enum",
                values_callable=lambda x: [e.value for e in x],
                create_type=False,
            ),
        ),
        nullable=False,
    )
    token_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    endpoints: Mapped[list["Endpoint"]] = relationship(back_populates="model")
    adapters: Mapped[list["Adapter"]] = relationship(back_populates="model")
    benchmarks: Mapped[list["BenchmarkSchema"]] = relationship(back_populates="model")
    created_user: Mapped["User"] = relationship(back_populates="created_models", foreign_keys=[created_by])
    paper_published: Mapped[List["PaperPublished"]] = relationship("PaperPublished", back_populates="model")
    model_licenses: Mapped["ModelLicenses"] = relationship("ModelLicenses", back_populates="model")
    provider: Mapped[Optional["Provider"]] = relationship("Provider", back_populates="models")
    model_security_scan_result: Mapped["ModelSecurityScanResult"] = relationship(
        "ModelSecurityScanResult", back_populates="model"
    )
    model_cluster_recommended: Mapped["ModelClusterRecommended"] = relationship(
        "ModelClusterRecommended",
        back_populates="model",
    )


class PaperPublished(Base, TimestampMixin):
    """Model for Paper Published."""

    __tablename__ = "paper_published"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String, nullable=True)
    authors: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=True)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id"), nullable=False)

    model: Mapped["Model"] = relationship("Model", back_populates="paper_published")


class ModelLicenses(Base, TimestampMixin):
    """Model for a AI model licenses."""

    __tablename__ = "model_licenses"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=True)
    path: Mapped[str] = mapped_column(String, nullable=True)
    faqs: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id"), nullable=False)
    license_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    suitability: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    data_type: Mapped[str] = mapped_column(
        Enum(
            ModelLicenseObjectTypeEnum,
            name="model_license_object_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ModelLicenseObjectTypeEnum.URL,
    )
    model: Mapped["Model"] = relationship("Model", back_populates="model_licenses")


class Provider(Base):
    """Model for a AI model provider."""

    __tablename__ = "provider"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capabilities: Mapped[List[str]] = mapped_column(
        PG_ARRAY(
            PG_ENUM(
                ProviderCapabilityEnum,
                name="provider_capability_enum",
                values_callable=lambda x: [e.value for e in x],
                create_type=False,
            ),
        ),
        nullable=True,
    )

    models: Mapped[Optional[list["Model"]]] = relationship("Model", back_populates="provider")
    cloud_models: Mapped[list["CloudModel"]] = relationship("CloudModel", back_populates="provider")


class CloudModel(Base, TimestampMixin):
    """Model for a AI cloud model."""

    __tablename__ = "cloud_model"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    tasks: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=True)
    model_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    huggingface_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            CloudModelStatusEnum,
            name="cloud_model_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=CloudModelStatusEnum.ACTIVE,
    )
    modality: Mapped[List[str]] = mapped_column(
        PG_ARRAY(
            PG_ENUM(
                ModalityEnum,
                name="modality_enum",
                values_callable=lambda x: [e.value for e in x],
                create_type=False,
            ),
        ),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        PG_ENUM(
            ModelProviderTypeEnum,
            name="model_provider_type_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("provider.id"), nullable=False)
    is_present_in_model: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deprecation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    max_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_cost: Mapped[dict] = mapped_column(JSONB, nullable=True)
    output_cost: Mapped[dict] = mapped_column(JSONB, nullable=True)
    supported_endpoints: Mapped[List[str]] = mapped_column(
        PG_ARRAY(
            PG_ENUM(
                ModelEndpointEnum,
                name="model_endpoint_enum",
                values_callable=lambda x: [e.value for e in x],
                create_type=False,
            ),
        ),
        nullable=False,
    )

    provider: Mapped[Optional["Provider"]] = relationship("Provider", back_populates="cloud_models")


class ModelSecurityScanResult(Base, TimestampMixin):
    """Model for a AI model security scan result."""

    __tablename__ = "model_security_scan_result"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        PG_ENUM(
            ModelSecurityScanStatusEnum,
            name="model_security_scan_status_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    total_issues: Mapped[int] = mapped_column(Integer, nullable=False)
    total_scanned_files: Mapped[int] = mapped_column(Integer, nullable=False)
    total_skipped_files: Mapped[int] = mapped_column(Integer, nullable=False)
    scanned_files: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=False)
    low_severity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    medium_severity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    high_severity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    critical_severity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_issues: Mapped[dict] = mapped_column(JSONB, nullable=False)

    model: Mapped["Model"] = relationship("Model", back_populates="model_security_scan_result")


class QuantizationMethod(Base):
    """Model for a AI model quantization method."""

    __tablename__ = "quantization_method"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    hardware_support: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=False)
    method_type: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=False)
    runtime_hardware_support: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=False)
