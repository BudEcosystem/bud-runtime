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

"""OAuth-related database models for SSO integration."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin


if TYPE_CHECKING:
    from budapp.user_ops.models import Tenant, User


class OAuthSession(Base, TimestampMixin):
    """Track OAuth session states for security and flow management."""

    __tablename__ = "oauth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("user.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    code_verifier: Mapped[str | None] = mapped_column(String(128), nullable=True)  # For PKCE
    redirect_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("tenant.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])


class TenantOAuthConfig(Base, TimestampMixin):
    """Store OAuth provider configurations per tenant."""

    __tablename__ = "tenant_oauth_configs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenant.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # Will be encrypted
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_domains: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    auto_create_users: Mapped[bool] = mapped_column(Boolean, default=False)
    config_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Additional provider-specific config

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])


class UserOAuthProvider(Base, TimestampMixin):
    """Track OAuth providers linked to users."""

    __tablename__ = "user_oauth_providers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Encrypted
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Encrypted
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Store additional provider data
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
