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

"""The workflow ops package, containing essential business logic, services, and routing configurations for the workflow ops."""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin

from ..commons.constants import VisibilityEnum, WorkflowStatusEnum, WorkflowTypeEnum


class Workflow(Base, TimestampMixin):
    """Workflow model."""

    __tablename__ = "workflow"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum(
            WorkflowStatusEnum,
            name="workflow_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=WorkflowStatusEnum.IN_PROGRESS.value,
    )
    workflow_type: Mapped[str] = mapped_column(
        Enum(
            WorkflowTypeEnum,
            name="workflow_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    progress: Mapped[Union[Dict[str, Any], List[Any]]] = mapped_column(JSONB, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    visibility: Mapped[str] = mapped_column(
        Enum(
            VisibilityEnum,
            name="visibility_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=VisibilityEnum.PUBLIC,
    )

    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )


class WorkflowStep(Base, TimestampMixin):
    """Workflow step model."""

    __tablename__ = "workflow_step"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflow.id"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=True)

    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="steps")
