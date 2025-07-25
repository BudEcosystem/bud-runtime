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


from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin


class Router(Base, TimestampMixin):
    """Router model."""

    __tablename__ = "router"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    routing_strategy: Mapped[dict] = mapped_column(JSONB, nullable=True)

    endpoints: Mapped[list["RouterEndpoint"]] = relationship(
        "RouterEndpoint",
        back_populates="router",
    )
    project: Mapped["Project"] = relationship("Project", back_populates="routers", foreign_keys=[project_id])


class RouterEndpoint(Base, TimestampMixin):
    """Router endpoint model."""

    __tablename__ = "router_endpoint"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    router_id: Mapped[UUID] = mapped_column(ForeignKey("router.id", ondelete="CASCADE"), nullable=False)
    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=False)
    fallback_endpoint_ids: Mapped[list[UUID]] = mapped_column(JSONB, nullable=True)
    tpm: Mapped[float] = mapped_column(Float, nullable=True)
    rpm: Mapped[float] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=True)
    # complexity_threshold: Mapped[float] = mapped_column(Float, nullable=True)
    cool_down_period: Mapped[int] = mapped_column(Integer, nullable=True)

    router: Mapped["Router"] = relationship("Router", back_populates="endpoints", foreign_keys=[router_id])
    endpoint: Mapped["Endpoint"] = relationship("Endpoint", back_populates="routers", foreign_keys=[endpoint_id])
