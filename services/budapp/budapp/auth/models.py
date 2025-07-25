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


"""Implements auth models. Use sqlalchemy to define models."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from budapp.commons.constants import TokenTypeEnum
from budapp.commons.database import Base, TimestampMixin


class Token(Base, TimestampMixin):
    """Token model."""

    __tablename__ = "token"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    auth_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    secret_key: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(
        Enum(
            TokenTypeEnum,
            name="token_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
