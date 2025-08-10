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

"""The project ops package, containing essential business logic, services, and routing configurations for the project ops."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Table, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin

from ..commons.constants import ProjectStatusEnum, ProjectTypeEnum
from ..permissions.models import ProjectPermission


project_user_association = Table(
    "project_user_association",
    Base.metadata,
    Column("project_id", Uuid, ForeignKey("project.id"), primary_key=True),
    Column("user_id", Uuid, ForeignKey("user.id"), primary_key=True),
)


class Project(Base, TimestampMixin):
    """Project model."""

    __tablename__ = "project"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    icon: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            ProjectStatusEnum,
            name="project_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ProjectStatusEnum.ACTIVE,
    )
    project_type: Mapped[str] = mapped_column(
        Enum(
            ProjectTypeEnum,
            name="project_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ProjectTypeEnum.CLIENT_APP,
    )
    benchmark: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)

    users: Mapped[list["User"]] = relationship("User", secondary=project_user_association, back_populates="projects")
    endpoints: Mapped[list["Endpoint"]] = relationship(
        "Endpoint",
        back_populates="project",
    )
    routers: Mapped[list["Router"]] = relationship(
        "Router",
        back_populates="project",
    )
    project_permissions: Mapped[list[ProjectPermission]] = relationship(
        back_populates="project", cascade="all, delete"
    )
    created_user: Mapped["User"] = relationship(back_populates="created_projects", foreign_keys=[created_by])
