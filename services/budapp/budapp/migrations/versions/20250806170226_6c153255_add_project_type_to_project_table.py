"""add project_type to project table

Revision ID: 20250806170226_6c153255
Revises: 20250730155527
Create Date: 2025-08-06 17:02:26.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20250806170226_6c153255"
down_revision: Union[str, None] = "20250730155527"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the project_type_enum type
    sa.Enum("client_app", "admin_app", name="project_type_enum").create(op.get_bind())

    # Add project_type column to project table with temporary nullable
    op.add_column(
        "project",
        sa.Column(
            "project_type",
            postgresql.ENUM("client_app", "admin_app", name="project_type_enum", create_type=False),
            nullable=True,
        ),
    )

    # Set all existing projects to admin_app for backward compatibility
    op.execute("UPDATE project SET project_type = 'admin_app' WHERE project_type IS NULL")

    # Now make the column non-nullable with client_app as default for new projects
    op.alter_column("project", "project_type", nullable=False, server_default="client_app")


def downgrade() -> None:
    # Drop the project_type column
    op.drop_column("project", "project_type")

    # Drop the enum type
    sa.Enum("client_app", "admin_app", name="project_type_enum").drop(op.get_bind())
