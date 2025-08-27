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

"""The credential ops package, containing essential business logic, services, and routing configurations for the credential ops."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.constants import ApiCredentialTypeEnum, CredentialTypeEnum
from budapp.commons.database import Base, TimestampMixin
from budapp.commons.security import hash_token


class ProprietaryCredential(Base, TimestampMixin):
    """Proprietary model creds at global level : Credential model."""

    __tablename__ = "proprietary_credential"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum(
            CredentialTypeEnum,
            name="proprietary_credential_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("provider.id"), nullable=False)

    # placeholder for api base, project, organization, etc.
    other_provider_creds: Mapped[dict] = mapped_column(JSONB, nullable=True)

    endpoints: Mapped[list["Endpoint"]] = relationship("Endpoint", back_populates="credential")
    provider: Mapped["Provider"] = relationship("Provider")


class Credential(Base, TimestampMixin):
    """Project API Keys : Credential model."""

    __tablename__ = "credential"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(String, nullable=False)  # Encrypted storage only
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=True)
    expiry: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    max_budget: Mapped[float] = mapped_column(Float, nullable=True)

    # placeholder for per model budgets : {"model_id": "budget"}
    model_budgets: Mapped[dict] = mapped_column(JSONB, nullable=True)

    last_used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_key: Mapped[str] = mapped_column(String, nullable=True)

    # New fields for enhanced security
    credential_type: Mapped[str] = mapped_column(
        Enum(
            ApiCredentialTypeEnum,
            name="api_credential_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ApiCredentialTypeEnum.CLIENT_APP.value,
    )
    ip_whitelist: Mapped[dict] = mapped_column(JSONB, nullable=True)  # List of allowed IPs

    project: Mapped["Project"] = relationship("Project", foreign_keys=[project_id])

    @staticmethod
    def set_hashed_key(key: str):
        hashed_key = hash_token(f"bud-{key}")
        return hashed_key


class CloudCredentials(Base, TimestampMixin):
    """Cloud Credentials : model for cloud credentials."""

    __tablename__ = "cloud_credentials"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("cloud_providers.id", ondelete="CASCADE"), nullable=False)
    encrypted_credential: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Encrypted storage only
    credential_name: Mapped[str] = mapped_column(String, nullable=False, default="No Name")

    provider = relationship("CloudProviders", back_populates="credentials")


class CloudProviders(Base, TimestampMixin):
    """Cloud Providers : model for cloud providers."""

    __tablename__ = "cloud_providers"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    logo_url: Mapped[str] = mapped_column(String, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schema_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    unique_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    credentials = relationship("CloudCredentials", back_populates="provider")
