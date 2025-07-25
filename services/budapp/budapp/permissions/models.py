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

"""The core package, containing essential business logic, services, and routing configurations for the permissions."""

import json
from datetime import datetime
from typing import List, Union
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin


class Permission(Base, TimestampMixin):
    """Permission model."""

    __tablename__ = "permission"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    auth_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    scopes: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["User"] = relationship(back_populates="permission")  # one-to-one

    @hybrid_property
    def scopes_list(self) -> Union[List[str], None]:
        """Get the scopes as a list of strings."""
        if not self.scopes:
            return []
        return json.loads(self.scopes)


class ProjectPermission(Base):
    """Project Permission model."""

    __tablename__ = "project_permission"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    auth_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    scopes: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="project_permissions", foreign_keys=[user_id])
    project: Mapped["Project"] = relationship(back_populates="project_permissions", foreign_keys=[project_id])

    @hybrid_property
    def scopes_list(self):
        if not self.scopes:
            return []
        return json.loads(self.scopes)
