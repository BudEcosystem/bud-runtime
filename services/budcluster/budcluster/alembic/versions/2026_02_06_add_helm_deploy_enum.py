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

"""Add helm_deploy value to job_type_enum.

Revision ID: a1b2c3d4e5f6
Revises: 9c0d1e2f3g4h
Create Date: 2026-02-06

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "9c0d1e2f3g4h"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add helm_deploy value to job_type_enum."""
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'helm_deploy'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values in a transaction."""
    pass
