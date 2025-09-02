"""Add unique constraint to license_info and clean duplicates

Revision ID: cb66c22394fb
Revises: 870aca89b7db
Create Date: 2025-09-02 05:54:35.117289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from alembic_postgresql_enum import TableReference

# revision identifiers, used by Alembic.
revision: str = 'cb66c22394fb'
down_revision: Union[str, None] = '870aca89b7db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, clean up any existing duplicates
    # Keep only the most recent record for each (license_id, url) combination
    op.execute(text("""
        DELETE FROM license_info
        WHERE id NOT IN (
            SELECT DISTINCT ON (license_id, url) id
            FROM license_info
            ORDER BY license_id, url, created_at DESC NULLS LAST, id
        )
    """))

    # Now add the unique constraint
    op.create_unique_constraint('uq_license_info_license_id_url', 'license_info', ['license_id', 'url'])

    # Note: Removed the foreign key creation as it already exists
    # The foreign key from model_info.license_id to license_info.id should already be present

    # Handle the enum values for model download status
    op.sync_enum_values(
        enum_schema='public',
        enum_name='modeldownloadstatus',
        new_values=['RUNNING', 'COMPLETED', 'UPLOADED', 'FAILED'],
        affected_columns=[TableReference(table_schema='public', table_name='model_download_history', column_name='status')],
        enum_values_to_rename=[],
    )


def downgrade() -> None:
    # Remove the unique constraint
    op.drop_constraint('uq_license_info_license_id_url', 'license_info', type_='unique')

    # Revert enum values
    op.sync_enum_values(
        enum_schema='public',
        enum_name='modeldownloadstatus',
        new_values=['RUNNING', 'COMPLETED'],
        affected_columns=[TableReference(table_schema='public', table_name='model_download_history', column_name='status')],
        enum_values_to_rename=[],
    )
