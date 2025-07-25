"""Updated license table.

Revision ID: 20d36fea791f
Revises: 27e74d56736e
Create Date: 2025-04-04 07:12:34.420691

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20d36fea791f"
down_revision: Union[str, None] = "27e74d56736e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    sa.Enum("url", "minio", name="model_license_object_type_enum").create(op.get_bind())
    op.add_column(
        "model_licenses",
        sa.Column(
            "data_type",
            postgresql.ENUM("url", "minio", name="model_license_object_type_enum", create_type=False),
            nullable=False,
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("model_licenses", "data_type")
    sa.Enum("url", "minio", name="model_license_object_type_enum").drop(op.get_bind())
    # ### end Alembic commands ###
