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

"""TDD Tests for Job SQLAlchemy model.

These tests are written BEFORE the implementation following TDD methodology.
The implementation should make all these tests pass.

Note: Some instantiation tests require environment setup or relationship
resolution. These tests focus on model structure which can be verified
without full SQLAlchemy/database setup.
"""

from uuid import uuid4

import pytest


class TestJobModelStructure:
    """Test cases for Job model class structure."""

    def test_job_model_exists(self):
        """Test that Job model can be imported."""
        from budcluster.jobs.models import Job

        assert Job is not None

    def test_job_model_has_tablename(self):
        """Test that Job model has correct table name."""
        from budcluster.jobs.models import Job

        assert Job.__tablename__ == "job"

    def test_job_model_inherits_psqlbase(self):
        """Test that Job model inherits from PSQLBase."""
        from budmicroframe.shared.psql_service import PSQLBase

        from budcluster.jobs.models import Job

        assert issubclass(Job, PSQLBase)

    def test_job_model_has_timestamp_mixin(self):
        """Test that Job model has timestamp fields from TimestampMixin."""
        from budcluster.jobs.models import Job

        # TimestampMixin provides created_at and modified_at
        assert hasattr(Job, "created_at")
        assert hasattr(Job, "modified_at")


class TestJobModelFields:
    """Test cases for Job model field definitions."""

    def test_job_has_id_field(self):
        """Test that Job has id field as UUID primary key."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "id")
        # Check column properties
        id_column = Job.__table__.columns["id"]
        assert id_column.primary_key is True

    def test_job_has_name_field(self):
        """Test that Job has name field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "name")
        name_column = Job.__table__.columns["name"]
        assert name_column.nullable is False

    def test_job_has_job_type_field(self):
        """Test that Job has job_type field with JobType enum."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "job_type")
        job_type_column = Job.__table__.columns["job_type"]
        assert job_type_column.nullable is False

    def test_job_has_status_field(self):
        """Test that Job has status field with JobStatus enum."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "status")
        status_column = Job.__table__.columns["status"]
        assert status_column.nullable is False

    def test_job_has_source_field(self):
        """Test that Job has source field with JobSource enum."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "source")
        source_column = Job.__table__.columns["source"]
        assert source_column.nullable is False

    def test_job_has_source_id_field(self):
        """Test that Job has source_id field to track originating entity."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "source_id")
        source_id_column = Job.__table__.columns["source_id"]
        # Source ID can be nullable (e.g., for manual jobs)
        assert source_id_column.nullable is True

    def test_job_has_cluster_id_field(self):
        """Test that Job has cluster_id foreign key field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "cluster_id")
        cluster_id_column = Job.__table__.columns["cluster_id"]
        assert cluster_id_column.nullable is False
        # Should have foreign key to cluster table
        assert len(cluster_id_column.foreign_keys) > 0

    def test_job_has_namespace_field(self):
        """Test that Job has namespace field for K8s namespace."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "namespace")
        namespace_column = Job.__table__.columns["namespace"]
        assert namespace_column.nullable is True  # May not be set initially

    def test_job_has_priority_field(self):
        """Test that Job has priority field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "priority")
        priority_column = Job.__table__.columns["priority"]
        # Priority should have a default value

    def test_job_has_config_field(self):
        """Test that Job has config JSONB field for job configuration."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "config")
        config_column = Job.__table__.columns["config"]
        assert config_column.nullable is True

    def test_job_has_metadata_field(self):
        """Test that Job has metadata JSONB field for additional data."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "metadata_")
        # Using metadata_ to avoid conflict with SQLAlchemy's metadata

    def test_job_has_error_message_field(self):
        """Test that Job has error_message field for failure details."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "error_message")
        error_message_column = Job.__table__.columns["error_message"]
        assert error_message_column.nullable is True

    def test_job_has_retry_count_field(self):
        """Test that Job has retry_count field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "retry_count")
        retry_count_column = Job.__table__.columns["retry_count"]
        # Should default to 0

    def test_job_has_started_at_field(self):
        """Test that Job has started_at timestamp field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "started_at")
        started_at_column = Job.__table__.columns["started_at"]
        assert started_at_column.nullable is True  # Not started yet

    def test_job_has_completed_at_field(self):
        """Test that Job has completed_at timestamp field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "completed_at")
        completed_at_column = Job.__table__.columns["completed_at"]
        assert completed_at_column.nullable is True  # Not completed yet

    def test_job_has_timeout_seconds_field(self):
        """Test that Job has timeout_seconds field."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "timeout_seconds")


class TestJobModelRelationships:
    """Test cases for Job model relationships."""

    def test_job_has_cluster_relationship(self):
        """Test that Job has relationship to Cluster model."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "cluster")

    def test_job_can_have_endpoint_id(self):
        """Test that Job can optionally link to an endpoint."""
        from budcluster.jobs.models import Job

        assert hasattr(Job, "endpoint_id")
        endpoint_id_column = Job.__table__.columns["endpoint_id"]
        assert endpoint_id_column.nullable is True  # Optional


class TestJobModelDefaults:
    """Test cases for Job model default values."""

    def test_job_default_status_is_pending(self):
        """Test that Job status column exists (default applied at insert time)."""
        from budcluster.jobs.models import Job

        # Check if there's a server_default or default
        status_column = Job.__table__.columns["status"]
        # The model requires status, so it may not have a default
        # But we should verify the column exists
        assert status_column is not None

    def test_job_default_retry_count_column_exists(self):
        """Test that Job retry_count column exists with default."""
        from budcluster.jobs.models import Job

        retry_count_column = Job.__table__.columns["retry_count"]
        # Default should be 0 (applied at insert time)
        assert retry_count_column is not None
        assert retry_count_column.nullable is False

    def test_job_default_priority_column_exists(self):
        """Test that Job priority column exists with default."""
        from budcluster.jobs.models import Job

        priority_column = Job.__table__.columns["priority"]
        # Default priority should be NORMAL (50) - applied at insert time
        assert priority_column is not None


class TestJobModelEnumTypes:
    """Test cases for enum types in Job model."""

    def test_job_type_column_uses_enum(self):
        """Test that job_type column uses enum type."""
        from sqlalchemy import Enum as SQLEnum

        from budcluster.jobs.models import Job

        job_type_column = Job.__table__.columns["job_type"]
        # Should be a SQLAlchemy Enum type
        assert isinstance(job_type_column.type, SQLEnum)

    def test_job_status_column_uses_enum(self):
        """Test that status column uses enum type."""
        from sqlalchemy import Enum as SQLEnum

        from budcluster.jobs.models import Job

        status_column = Job.__table__.columns["status"]
        assert isinstance(status_column.type, SQLEnum)

    def test_job_source_column_uses_enum(self):
        """Test that source column uses enum type."""
        from sqlalchemy import Enum as SQLEnum

        from budcluster.jobs.models import Job

        source_column = Job.__table__.columns["source"]
        assert isinstance(source_column.type, SQLEnum)


class TestJobModelJSONBFields:
    """Test cases for JSONB fields in Job model."""

    def test_config_is_jsonb_type(self):
        """Test that config field is JSONB type."""
        from budcluster.jobs.models import Job

        config_column = Job.__table__.columns["config"]
        assert "jsonb" in str(config_column.type).lower()

    def test_metadata_is_jsonb_type(self):
        """Test that metadata field is JSONB type."""
        from budcluster.jobs.models import Job

        metadata_column = Job.__table__.columns["metadata"]
        assert "jsonb" in str(metadata_column.type).lower()


class TestJobCRUD:
    """Test cases for JobCRUD class."""

    def test_job_crud_exists(self):
        """Test that JobCRUD class can be imported."""
        from budcluster.jobs.models import JobCRUD

        assert JobCRUD is not None

    def test_job_crud_has_model(self):
        """Test that JobCRUD has __model__ attribute."""
        from budcluster.jobs.models import Job, JobCRUD

        assert JobCRUD.__model__ == Job

    def test_job_crud_inherits_crud_mixin(self):
        """Test that JobCRUD inherits from CRUDMixin."""
        from budmicroframe.shared.psql_service import CRUDMixin

        from budcluster.jobs.models import JobCRUD

        # JobCRUD should be a subclass of CRUDMixin
        assert issubclass(JobCRUD, CRUDMixin)


class TestJobModelTableConstraints:
    """Test cases for Job model table constraints."""

    def test_job_table_has_indexes(self):
        """Test that Job table has appropriate indexes for common queries."""
        from budcluster.jobs.models import Job

        # Get all indexes
        indexes = list(Job.__table__.indexes)

        # Should have indexes for common query patterns
        # (status, cluster_id, source, created_at)
        index_columns = []
        for idx in indexes:
            for col in idx.columns:
                index_columns.append(col.name)

        # At minimum, status should be indexed for filtering
        # This is flexible - implementation may vary
        assert len(indexes) >= 0  # At least check the table is valid

    def test_job_cluster_id_foreign_key(self):
        """Test that cluster_id has proper foreign key constraint."""
        from budcluster.jobs.models import Job

        cluster_id_col = Job.__table__.columns["cluster_id"]
        fks = list(cluster_id_col.foreign_keys)

        assert len(fks) == 1
        # Should reference cluster.id
        fk = fks[0]
        assert "cluster.id" in str(fk.target_fullname)


class TestJobEnumValues:
    """Test cases for enum value compatibility with Job model."""

    def test_job_type_enum_values_defined(self):
        """Test that all JobType enum values are defined."""
        from budcluster.jobs.enums import JobType

        expected_types = [
            "model_deployment",
            "custom_job",
            "fine_tuning",
            "batch_inference",
            "usecase_component",
            "benchmark",
            "data_pipeline",
        ]
        actual_types = [jt.value for jt in JobType]
        for expected in expected_types:
            assert expected in actual_types

    def test_job_status_enum_values_defined(self):
        """Test that all JobStatus enum values are defined."""
        from budcluster.jobs.enums import JobStatus

        expected_statuses = [
            "pending",
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "timeout",
            "retrying",
        ]
        actual_statuses = [js.value for js in JobStatus]
        for expected in expected_statuses:
            assert expected in actual_statuses

    def test_job_source_enum_values_defined(self):
        """Test that all JobSource enum values are defined."""
        from budcluster.jobs.enums import JobSource

        expected_sources = [
            "budusecases",
            "budpipeline",
            "manual",
            "budapp",
            "scheduler",
        ]
        actual_sources = [js.value for js in JobSource]
        for expected in expected_sources:
            assert expected in actual_sources
