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

"""Add job table for unified job tracking.

Revision ID: 9c0d1e2f3g4h
Revises: 8b9c0d1e2f3g
Create Date: 2026-02-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9c0d1e2f3g4h"
down_revision: str | None = "8b9c0d1e2f3g"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum type definitions
job_type_enum = postgresql.ENUM(
    "model_deployment",
    "custom_job",
    "fine_tuning",
    "batch_inference",
    "usecase_component",
    "benchmark",
    "data_pipeline",
    name="job_type_enum",
    create_type=False,
)

job_status_enum = postgresql.ENUM(
    "pending",
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "timeout",
    "retrying",
    name="job_status_enum",
    create_type=False,
)

job_source_enum = postgresql.ENUM(
    "budusecases",
    "budpipeline",
    "manual",
    "budapp",
    "scheduler",
    name="job_source_enum",
    create_type=False,
)


def upgrade() -> None:
    """Add job table for unified job tracking."""
    # Create enum types first
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE job_type_enum AS ENUM (
                'model_deployment',
                'custom_job',
                'fine_tuning',
                'batch_inference',
                'usecase_component',
                'benchmark',
                'data_pipeline'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE job_status_enum AS ENUM (
                'pending',
                'queued',
                'running',
                'succeeded',
                'failed',
                'cancelled',
                'timeout',
                'retrying'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE job_source_enum AS ENUM (
                'budusecases',
                'budpipeline',
                'manual',
                'budapp',
                'scheduler'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # Create job table
    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("job_type", job_type_enum, nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("source", job_source_enum, nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(255), nullable=True),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster.id"], ondelete="CASCADE"),
    )

    # Create indexes for common query patterns
    op.create_index("ix_job_status", "job", ["status"])
    op.create_index("ix_job_cluster_id", "job", ["cluster_id"])
    op.create_index("ix_job_source", "job", ["source"])
    op.create_index("ix_job_job_type", "job", ["job_type"])
    op.create_index("ix_job_created_at", "job", ["created_at"])
    op.create_index("ix_job_source_source_id", "job", ["source", "source_id"])


def downgrade() -> None:
    """Remove job table and related enums."""
    # Drop indexes
    op.drop_index("ix_job_source_source_id", table_name="job")
    op.drop_index("ix_job_created_at", table_name="job")
    op.drop_index("ix_job_job_type", table_name="job")
    op.drop_index("ix_job_source", table_name="job")
    op.drop_index("ix_job_cluster_id", table_name="job")
    op.drop_index("ix_job_status", table_name="job")

    # Drop table
    op.drop_table("job")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS job_source_enum")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
    op.execute("DROP TYPE IF EXISTS job_type_enum")
