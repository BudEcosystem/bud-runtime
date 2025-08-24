"""add resource_name to audit_trail

Revision ID: 7c028d42c0df
Revises: 1235cf2dae2
Create Date: 2025-08-24 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c028d42c0df'
down_revision = '1235cf2dae2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add resource_name column to audit_trail table."""
    op.add_column('audit_trail', 
        sa.Column('resource_name', sa.String(length=255), nullable=True, 
                  comment='Name of the affected resource for display and search')
    )
    
    # Create index for better search performance
    op.create_index('ix_audit_trail_resource_name', 'audit_trail', ['resource_name'])


def downgrade() -> None:
    """Remove resource_name column from audit_trail table."""
    op.drop_index('ix_audit_trail_resource_name', table_name='audit_trail')
    op.drop_column('audit_trail', 'resource_name')