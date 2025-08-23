"""add audit trail table

Revision ID: 1235cf2dae2
Revises: c220a336acbf
Create Date: 2025-01-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1235cf2dae2"
down_revision: Union[str, None] = "c220a336acbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create audit_trail table
    op.create_table(
        "audit_trail",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        
        # User tracking
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actioned_by", postgresql.UUID(as_uuid=True), nullable=True),
        
        # Action details
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        
        # Timestamp
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        
        # Additional context
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        
        # State tracking
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Timestamps from TimestampMixin
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actioned_by"], ["user.id"], ondelete="SET NULL"),
    )
    
    # Create indexes for performance
    # Index for user activity queries
    op.create_index(
        "ix_audit_trail_user_timestamp",
        "audit_trail",
        ["timestamp", "user_id"],
        unique=False
    )
    
    # Index for resource history queries
    op.create_index(
        "ix_audit_trail_resource",
        "audit_trail",
        ["resource_type", "resource_id"],
        unique=False
    )
    
    # Index for timestamp-based queries
    op.create_index(
        "ix_audit_trail_timestamp",
        "audit_trail",
        ["timestamp"],
        unique=False
    )
    
    # Index for action type queries
    op.create_index(
        "ix_audit_trail_action",
        "audit_trail",
        ["action"],
        unique=False
    )
    
    # Index for user_id queries
    op.create_index(
        "ix_audit_trail_user_id",
        "audit_trail",
        ["user_id"],
        unique=False
    )
    
    # Index for actioned_by queries
    op.create_index(
        "ix_audit_trail_actioned_by",
        "audit_trail",
        ["actioned_by"],
        unique=False
    )
    
    # Index for resource_type queries
    op.create_index(
        "ix_audit_trail_resource_type",
        "audit_trail",
        ["resource_type"],
        unique=False
    )
    
    # Index for resource_id queries
    op.create_index(
        "ix_audit_trail_resource_id",
        "audit_trail",
        ["resource_id"],
        unique=False
    )
    
    # Add CHECK constraint to prevent updates (PostgreSQL specific)
    # This will prevent any UPDATE operations on the table
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_trail_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit trail records cannot be updated. They are immutable.';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER audit_trail_no_update
        BEFORE UPDATE ON audit_trail
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_trail_update();
    """)
    
    # Add comment to the table
    op.execute("""
        COMMENT ON TABLE audit_trail IS 'Immutable audit log for tracking all user actions and system events for compliance and security purposes';
    """)


def downgrade() -> None:
    # Drop the trigger and function first
    op.execute("DROP TRIGGER IF EXISTS audit_trail_no_update ON audit_trail;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_trail_update();")
    
    # Drop all indexes
    op.drop_index("ix_audit_trail_resource_id", table_name="audit_trail")
    op.drop_index("ix_audit_trail_resource_type", table_name="audit_trail")
    op.drop_index("ix_audit_trail_actioned_by", table_name="audit_trail")
    op.drop_index("ix_audit_trail_user_id", table_name="audit_trail")
    op.drop_index("ix_audit_trail_action", table_name="audit_trail")
    op.drop_index("ix_audit_trail_timestamp", table_name="audit_trail")
    op.drop_index("ix_audit_trail_resource", table_name="audit_trail")
    op.drop_index("ix_audit_trail_user_timestamp", table_name="audit_trail")
    
    # Drop the table
    op.drop_table("audit_trail")