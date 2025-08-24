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

"""The models package, containing the database models for the user ops."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Boolean, DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.cluster_ops.models import Cluster
from budapp.commons.constants import UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.database import Base, TimestampMixin
from budapp.commons.security import RSAHandler
from budapp.endpoint_ops.models import Endpoint
from budapp.model_ops.models import Model
from budapp.permissions.models import ProjectPermission
from budapp.project_ops.models import Project, project_user_association


class User(Base, TimestampMixin):
    """User model."""

    __tablename__ = "user"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    auth_id: Mapped[UUID] = mapped_column(
        Uuid, unique=True, default=uuid4
    )  # repurpose the auth_id to store keycloak id
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(
            UserRoleEnum,
            name="user_role_enum",
            values_callable=lambda x: [e.value for e in x],
        )
    )
    status: Mapped[str] = mapped_column(
        Enum(
            UserStatusEnum,
            name="user_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserStatusEnum.INVITED.value,
    )
    password: Mapped[str] = mapped_column(String, nullable=True)  # Made nullable since we use Keycloak
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reset_password: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str] = mapped_column(String, nullable=False)
    first_login: Mapped[bool] = mapped_column(Boolean, default=True)
    is_subscriber: Mapped[bool] = mapped_column(Boolean, default=False)
    reset_password_attempt: Mapped[int] = mapped_column(Integer, default=0)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_type: Mapped[str] = mapped_column(
        Enum(
            UserTypeEnum,
            name="user_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserTypeEnum.CLIENT.value,
    )

    permission: Mapped["Permission"] = relationship(back_populates="user")  # one-to-one
    created_models: Mapped[list[Model]] = relationship(back_populates="created_user")
    tenant_mappings: Mapped[list["TenantUserMapping"]] = relationship(back_populates="user")

    # TODO: uncomment when implement individual fields
    benchmarks: Mapped[list["BenchmarkSchema"]] = relationship(back_populates="user")
    # benchmark_results: Mapped[list["BenchmarkResult"]] = relationship(back_populates="user")
    projects: Mapped[list[Project]] = relationship(secondary=project_user_association, back_populates="users")
    project_permissions: Mapped[list[ProjectPermission]] = relationship(back_populates="user")
    created_projects: Mapped[list[Project]] = relationship(back_populates="created_user")
    created_clusters: Mapped[list[Cluster]] = relationship(back_populates="created_user")
    created_endpoints: Mapped[list[Endpoint]] = relationship(
        back_populates="created_user", foreign_keys="[Endpoint.created_by]"
    )
    published_endpoints: Mapped[list[Endpoint]] = relationship(
        back_populates="published_user", foreign_keys="[Endpoint.published_by]"
    )


class Tenant(Base, TimestampMixin):
    """Tenant model."""

    __tablename__ = "tenant"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    realm_name: Mapped[str] = mapped_column(String, nullable=False)  # Keycloak realm name
    tenant_identifier: Mapped[str] = mapped_column(String, nullable=False)  # Will be same as realm name
    description: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Add relationships
    clients: Mapped[list["TenantClient"]] = relationship(back_populates="tenant")
    user_mappings: Mapped[list["TenantUserMapping"]] = relationship(back_populates="tenant")


class TenantClient(Base, TimestampMixin):
    """Tenant client model with encrypted client secret storage."""

    __tablename__ = "tenant_clients"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenant.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    client_secret: Mapped[str] = mapped_column(String, nullable=False)  # Stores encrypted value
    client_named_id: Mapped[str] = mapped_column(String, nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Add relationship
    tenant: Mapped["Tenant"] = relationship(back_populates="clients")

    @staticmethod
    def _is_encrypted(value: str) -> bool:
        """Check if a value appears to be encrypted.

        Args:
            value: The value to check

        Returns:
            True if the value appears to be encrypted (hex string), False otherwise
        """
        if not value:
            return False

        # Check if it's a valid hex string and has reasonable length for encrypted data
        try:
            bytes.fromhex(value)
            # Encrypted values are typically much longer than plain secrets
            return len(value) > 100
        except (ValueError, TypeError):
            return False

    async def set_client_secret(self, plaintext_secret: str):
        """Set the client secret, encrypting it before storage.

        Args:
            plaintext_secret: The plaintext client secret to encrypt and store
        """
        if not plaintext_secret:
            raise ValueError("Client secret cannot be empty")

        # Check if the value is already encrypted to avoid double encryption
        if not self._is_encrypted(plaintext_secret):
            self.client_secret = await RSAHandler.encrypt(plaintext_secret)
        else:
            # Already encrypted, store as-is
            self.client_secret = plaintext_secret

    async def get_decrypted_client_secret(self) -> str:
        """Get the decrypted client secret.

        Returns:
            The decrypted plaintext client secret
        """
        if not self.client_secret:
            raise ValueError("No client secret stored")

        # Check if the value is encrypted
        if self._is_encrypted(self.client_secret):
            return await RSAHandler.decrypt(self.client_secret)
        else:
            # Legacy plaintext value - will be encrypted on next save
            return self.client_secret


class TenantUserMapping(Base, TimestampMixin):
    """Tenant user mapping model."""

    __tablename__ = "tenant_user_mapping"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenant.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Add relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="user_mappings")
    user: Mapped["User"] = relationship(back_populates="tenant_mappings")
