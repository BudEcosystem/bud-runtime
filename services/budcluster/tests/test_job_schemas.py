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

"""TDD Tests for Job Pydantic schemas.

These tests are written BEFORE the implementation following TDD methodology.
The implementation should make all these tests pass.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from budcluster.jobs.enums import JobPriority, JobSource, JobStatus, JobType


class TestJobCreateSchema:
    """Test cases for JobCreate schema."""

    def test_job_create_schema_exists(self):
        """Test that JobCreate schema can be imported."""
        from budcluster.jobs.schemas import JobCreate

        assert JobCreate is not None

    def test_job_create_with_minimal_required_fields(self):
        """Test JobCreate with only required fields."""
        from budcluster.jobs.schemas import JobCreate

        cluster_id = uuid4()
        job = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=cluster_id,
        )
        assert job.name == "test-job"
        assert job.job_type == JobType.MODEL_DEPLOYMENT
        assert job.source == JobSource.MANUAL
        assert job.cluster_id == cluster_id

    def test_job_create_with_all_fields(self):
        """Test JobCreate with all fields."""
        from budcluster.jobs.schemas import JobCreate

        cluster_id = uuid4()
        source_id = uuid4()
        endpoint_id = uuid4()

        job = JobCreate(
            name="full-test-job",
            job_type=JobType.FINE_TUNING,
            source=JobSource.BUDUSECASES,
            cluster_id=cluster_id,
            source_id=source_id,
            namespace="production",
            endpoint_id=endpoint_id,
            priority=JobPriority.HIGH.value,
            config={"model": "llama-3", "gpu_count": 4},
            metadata_={"user": "admin", "department": "ml"},
            timeout_seconds=7200,
        )
        assert job.name == "full-test-job"
        assert job.source_id == source_id
        assert job.namespace == "production"
        assert job.endpoint_id == endpoint_id
        assert job.priority == JobPriority.HIGH.value
        assert job.config == {"model": "llama-3", "gpu_count": 4}
        assert job.metadata_ == {"user": "admin", "department": "ml"}
        assert job.timeout_seconds == 7200

    def test_job_create_name_required(self):
        """Test that name is required."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError) as exc_info:
            JobCreate(
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )
        assert "name" in str(exc_info.value)

    def test_job_create_job_type_required(self):
        """Test that job_type is required."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError) as exc_info:
            JobCreate(
                name="test-job",
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )
        assert "job_type" in str(exc_info.value)

    def test_job_create_source_required(self):
        """Test that source is required."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError) as exc_info:
            JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                cluster_id=uuid4(),
            )
        assert "source" in str(exc_info.value)

    def test_job_create_cluster_id_required(self):
        """Test that cluster_id is required."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError) as exc_info:
            JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
            )
        assert "cluster_id" in str(exc_info.value)

    def test_job_create_invalid_job_type(self):
        """Test that invalid job_type raises error."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError):
            JobCreate(
                name="test-job",
                job_type="invalid_type",
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )

    def test_job_create_invalid_source(self):
        """Test that invalid source raises error."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError):
            JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                source="invalid_source",
                cluster_id=uuid4(),
            )

    def test_job_create_default_priority(self):
        """Test that default priority is NORMAL."""
        from budcluster.jobs.schemas import JobCreate

        job = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
        )
        assert job.priority == JobPriority.NORMAL.value

    def test_job_create_name_max_length(self):
        """Test that name has maximum length validation."""
        from budcluster.jobs.schemas import JobCreate

        long_name = "a" * 256
        with pytest.raises(ValidationError):
            JobCreate(
                name=long_name,
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )

    def test_job_create_namespace_max_length(self):
        """Test that namespace has maximum length validation."""
        from budcluster.jobs.schemas import JobCreate

        long_namespace = "a" * 256
        with pytest.raises(ValidationError):
            JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
                namespace=long_namespace,
            )

    def test_job_create_priority_validation(self):
        """Test that priority accepts valid integer values."""
        from budcluster.jobs.schemas import JobCreate

        job = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            priority=100,
        )
        assert job.priority == 100

    def test_job_create_timeout_positive(self):
        """Test that timeout_seconds must be positive."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError):
            JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
                timeout_seconds=-1,
            )

    def test_job_create_accepts_string_enum_values(self):
        """Test that JobCreate accepts string values for enums."""
        from budcluster.jobs.schemas import JobCreate

        job = JobCreate(
            name="test-job",
            job_type="model_deployment",
            source="manual",
            cluster_id=uuid4(),
        )
        assert job.job_type == JobType.MODEL_DEPLOYMENT
        assert job.source == JobSource.MANUAL


class TestJobUpdateSchema:
    """Test cases for JobUpdate schema."""

    def test_job_update_schema_exists(self):
        """Test that JobUpdate schema can be imported."""
        from budcluster.jobs.schemas import JobUpdate

        assert JobUpdate is not None

    def test_job_update_all_fields_optional(self):
        """Test that all JobUpdate fields are optional."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate()
        assert job_update.status is None
        assert job_update.namespace is None
        assert job_update.error_message is None

    def test_job_update_status_field(self):
        """Test updating status field."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate(status=JobStatus.RUNNING)
        assert job_update.status == JobStatus.RUNNING

    def test_job_update_namespace_field(self):
        """Test updating namespace field."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate(namespace="new-namespace")
        assert job_update.namespace == "new-namespace"

    def test_job_update_error_message_field(self):
        """Test updating error_message field."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate(error_message="Job failed due to OOM")
        assert job_update.error_message == "Job failed due to OOM"

    def test_job_update_retry_count_field(self):
        """Test updating retry_count field."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate(retry_count=2)
        assert job_update.retry_count == 2

    def test_job_update_config_field(self):
        """Test updating config field."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate(config={"new_setting": "value"})
        assert job_update.config == {"new_setting": "value"}

    def test_job_update_metadata_field(self):
        """Test updating metadata field."""
        from budcluster.jobs.schemas import JobUpdate

        job_update = JobUpdate(metadata_={"updated": True})
        assert job_update.metadata_ == {"updated": True}

    def test_job_update_started_at_field(self):
        """Test updating started_at field."""
        from budcluster.jobs.schemas import JobUpdate

        now = datetime.now(timezone.utc)
        job_update = JobUpdate(started_at=now)
        assert job_update.started_at == now

    def test_job_update_completed_at_field(self):
        """Test updating completed_at field."""
        from budcluster.jobs.schemas import JobUpdate

        now = datetime.now(timezone.utc)
        job_update = JobUpdate(completed_at=now)
        assert job_update.completed_at == now

    def test_job_update_invalid_status(self):
        """Test that invalid status raises error."""
        from budcluster.jobs.schemas import JobUpdate

        with pytest.raises(ValidationError):
            JobUpdate(status="invalid_status")

    def test_job_update_retry_count_non_negative(self):
        """Test that retry_count must be non-negative."""
        from budcluster.jobs.schemas import JobUpdate

        with pytest.raises(ValidationError):
            JobUpdate(retry_count=-1)

    def test_job_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        from budcluster.jobs.schemas import JobUpdate

        now = datetime.now(timezone.utc)
        job_update = JobUpdate(
            status=JobStatus.SUCCEEDED,
            completed_at=now,
            retry_count=1,
        )
        assert job_update.status == JobStatus.SUCCEEDED
        assert job_update.completed_at == now
        assert job_update.retry_count == 1


class TestJobResponseSchema:
    """Test cases for JobResponse schema."""

    def test_job_response_schema_exists(self):
        """Test that JobResponse schema can be imported."""
        from budcluster.jobs.schemas import JobResponse

        assert JobResponse is not None

    def test_job_response_has_id(self):
        """Test that JobResponse has id field."""
        from budcluster.jobs.schemas import JobResponse

        job_id = uuid4()
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        job = JobResponse(
            id=job_id,
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            status=JobStatus.PENDING,
            source=JobSource.MANUAL,
            cluster_id=cluster_id,
            priority=50,
            retry_count=0,
            created_at=now,
            modified_at=now,
        )
        assert job.id == job_id

    def test_job_response_has_timestamps(self):
        """Test that JobResponse has created_at and modified_at."""
        from budcluster.jobs.schemas import JobResponse

        now = datetime.now(timezone.utc)
        job = JobResponse(
            id=uuid4(),
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            status=JobStatus.PENDING,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            priority=50,
            retry_count=0,
            created_at=now,
            modified_at=now,
        )
        assert job.created_at == now
        assert job.modified_at == now

    def test_job_response_has_execution_timestamps(self):
        """Test that JobResponse has started_at and completed_at."""
        from budcluster.jobs.schemas import JobResponse

        now = datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        job = JobResponse(
            id=uuid4(),
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            status=JobStatus.SUCCEEDED,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            priority=50,
            retry_count=0,
            created_at=now,
            modified_at=now,
            started_at=started,
            completed_at=completed,
        )
        assert job.started_at == started
        assert job.completed_at == completed

    def test_job_response_has_all_core_fields(self):
        """Test that JobResponse has all core fields."""
        from budcluster.jobs.schemas import JobResponse

        job_id = uuid4()
        cluster_id = uuid4()
        source_id = uuid4()
        endpoint_id = uuid4()
        now = datetime.now(timezone.utc)

        job = JobResponse(
            id=job_id,
            name="complete-job",
            job_type=JobType.FINE_TUNING,
            status=JobStatus.RUNNING,
            source=JobSource.BUDPIPELINE,
            source_id=source_id,
            cluster_id=cluster_id,
            namespace="ml-jobs",
            endpoint_id=endpoint_id,
            priority=75,
            config={"epochs": 10},
            metadata_={"team": "ai"},
            error_message=None,
            retry_count=1,
            timeout_seconds=3600,
            started_at=now,
            completed_at=None,
            created_at=now,
            modified_at=now,
        )

        assert job.id == job_id
        assert job.name == "complete-job"
        assert job.job_type == JobType.FINE_TUNING
        assert job.status == JobStatus.RUNNING
        assert job.source == JobSource.BUDPIPELINE
        assert job.source_id == source_id
        assert job.cluster_id == cluster_id
        assert job.namespace == "ml-jobs"
        assert job.endpoint_id == endpoint_id
        assert job.priority == 75
        assert job.config == {"epochs": 10}
        assert job.metadata_ == {"team": "ai"}
        assert job.retry_count == 1
        assert job.timeout_seconds == 3600

    def test_job_response_from_attributes(self):
        """Test that JobResponse has from_attributes config for ORM."""
        from budcluster.jobs.schemas import JobResponse

        # Check that ConfigDict has from_attributes=True
        assert hasattr(JobResponse, "model_config")
        config = JobResponse.model_config
        assert config.get("from_attributes") is True

    def test_job_response_optional_fields_can_be_none(self):
        """Test that optional fields can be None."""
        from budcluster.jobs.schemas import JobResponse

        now = datetime.now(timezone.utc)
        job = JobResponse(
            id=uuid4(),
            name="minimal-job",
            job_type=JobType.CUSTOM_JOB,
            status=JobStatus.PENDING,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            priority=50,
            retry_count=0,
            created_at=now,
            modified_at=now,
            source_id=None,
            namespace=None,
            endpoint_id=None,
            config=None,
            metadata_=None,
            error_message=None,
            timeout_seconds=None,
            started_at=None,
            completed_at=None,
        )

        assert job.source_id is None
        assert job.namespace is None
        assert job.endpoint_id is None
        assert job.config is None


class TestJobFilterSchema:
    """Test cases for JobFilter schema for list filtering."""

    def test_job_filter_schema_exists(self):
        """Test that JobFilter schema can be imported."""
        from budcluster.jobs.schemas import JobFilter

        assert JobFilter is not None

    def test_job_filter_all_fields_optional(self):
        """Test that all JobFilter fields are optional."""
        from budcluster.jobs.schemas import JobFilter

        job_filter = JobFilter()
        # Should not raise

    def test_job_filter_by_status(self):
        """Test filtering by status."""
        from budcluster.jobs.schemas import JobFilter

        job_filter = JobFilter(status=JobStatus.RUNNING)
        assert job_filter.status == JobStatus.RUNNING

    def test_job_filter_by_job_type(self):
        """Test filtering by job_type."""
        from budcluster.jobs.schemas import JobFilter

        job_filter = JobFilter(job_type=JobType.FINE_TUNING)
        assert job_filter.job_type == JobType.FINE_TUNING

    def test_job_filter_by_source(self):
        """Test filtering by source."""
        from budcluster.jobs.schemas import JobFilter

        job_filter = JobFilter(source=JobSource.BUDUSECASES)
        assert job_filter.source == JobSource.BUDUSECASES

    def test_job_filter_by_cluster_id(self):
        """Test filtering by cluster_id."""
        from budcluster.jobs.schemas import JobFilter

        cluster_id = uuid4()
        job_filter = JobFilter(cluster_id=cluster_id)
        assert job_filter.cluster_id == cluster_id

    def test_job_filter_by_source_id(self):
        """Test filtering by source_id."""
        from budcluster.jobs.schemas import JobFilter

        source_id = uuid4()
        job_filter = JobFilter(source_id=source_id)
        assert job_filter.source_id == source_id

    def test_job_filter_multiple_criteria(self):
        """Test filtering with multiple criteria."""
        from budcluster.jobs.schemas import JobFilter

        cluster_id = uuid4()
        job_filter = JobFilter(
            status=JobStatus.RUNNING,
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.BUDAPP,
            cluster_id=cluster_id,
        )
        assert job_filter.status == JobStatus.RUNNING
        assert job_filter.job_type == JobType.MODEL_DEPLOYMENT
        assert job_filter.source == JobSource.BUDAPP
        assert job_filter.cluster_id == cluster_id

    def test_job_filter_by_priority_range(self):
        """Test filtering by priority range."""
        from budcluster.jobs.schemas import JobFilter

        job_filter = JobFilter(
            priority_min=50,
            priority_max=100,
        )
        assert job_filter.priority_min == 50
        assert job_filter.priority_max == 100


class TestJobListResponseSchema:
    """Test cases for JobListResponse schema."""

    def test_job_list_response_schema_exists(self):
        """Test that JobListResponse schema can be imported."""
        from budcluster.jobs.schemas import JobListResponse

        assert JobListResponse is not None

    def test_job_list_response_has_jobs_field(self):
        """Test that JobListResponse has jobs list."""
        from budcluster.jobs.schemas import JobListResponse, JobResponse

        now = datetime.now(timezone.utc)
        jobs = [
            JobResponse(
                id=uuid4(),
                name="job-1",
                job_type=JobType.MODEL_DEPLOYMENT,
                status=JobStatus.PENDING,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
                priority=50,
                retry_count=0,
                created_at=now,
                modified_at=now,
            ),
            JobResponse(
                id=uuid4(),
                name="job-2",
                job_type=JobType.FINE_TUNING,
                status=JobStatus.RUNNING,
                source=JobSource.BUDUSECASES,
                cluster_id=uuid4(),
                priority=75,
                retry_count=0,
                created_at=now,
                modified_at=now,
            ),
        ]

        response = JobListResponse(jobs=jobs, total=2, page=1, page_size=10)
        assert len(response.jobs) == 2
        assert response.total == 2

    def test_job_list_response_pagination(self):
        """Test that JobListResponse has pagination fields."""
        from budcluster.jobs.schemas import JobListResponse

        response = JobListResponse(jobs=[], total=100, page=2, page_size=20)
        assert response.total == 100
        assert response.page == 2
        assert response.page_size == 20


class TestJobStatusTransitionSchema:
    """Test cases for JobStatusTransition schema."""

    def test_job_status_transition_schema_exists(self):
        """Test that JobStatusTransition schema can be imported."""
        from budcluster.jobs.schemas import JobStatusTransition

        assert JobStatusTransition is not None

    def test_job_status_transition_fields(self):
        """Test JobStatusTransition fields."""
        from budcluster.jobs.schemas import JobStatusTransition

        transition = JobStatusTransition(
            status=JobStatus.RUNNING,
        )
        assert transition.status == JobStatus.RUNNING

    def test_job_status_transition_to_failed_with_error(self):
        """Test transitioning to FAILED with error message."""
        from budcluster.jobs.schemas import JobStatusTransition

        transition = JobStatusTransition(
            status=JobStatus.FAILED,
            error_message="OOM Error: Insufficient GPU memory",
        )
        assert transition.status == JobStatus.FAILED
        assert transition.error_message == "OOM Error: Insufficient GPU memory"


class TestJobSchemaEnumCompatibility:
    """Test cases for enum compatibility in schemas."""

    def test_job_create_accepts_all_job_types(self):
        """Test that JobCreate accepts all JobType values."""
        from budcluster.jobs.schemas import JobCreate

        for job_type in JobType:
            job = JobCreate(
                name=f"test-{job_type.value}",
                job_type=job_type,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )
            assert job.job_type == job_type

    def test_job_create_accepts_all_sources(self):
        """Test that JobCreate accepts all JobSource values."""
        from budcluster.jobs.schemas import JobCreate

        for source in JobSource:
            job = JobCreate(
                name=f"test-{source.value}",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=source,
                cluster_id=uuid4(),
            )
            assert job.source == source

    def test_job_update_accepts_all_statuses(self):
        """Test that JobUpdate accepts all JobStatus values."""
        from budcluster.jobs.schemas import JobUpdate

        for status in JobStatus:
            update = JobUpdate(status=status)
            assert update.status == status

    def test_job_filter_accepts_all_enums(self):
        """Test that JobFilter accepts all enum values."""
        from budcluster.jobs.schemas import JobFilter

        for job_type in JobType:
            job_filter = JobFilter(job_type=job_type)
            assert job_filter.job_type == job_type

        for status in JobStatus:
            job_filter = JobFilter(status=status)
            assert job_filter.status == status

        for source in JobSource:
            job_filter = JobFilter(source=source)
            assert job_filter.source == source


class TestJobSchemaJsonSerialization:
    """Test cases for JSON serialization of schemas."""

    def test_job_create_json_serializable(self):
        """Test that JobCreate can be serialized to JSON."""
        from budcluster.jobs.schemas import JobCreate

        job = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
        )
        json_dict = job.model_dump(mode="json")
        assert "name" in json_dict
        assert json_dict["job_type"] == "model_deployment"
        assert json_dict["source"] == "manual"

    def test_job_response_json_serializable(self):
        """Test that JobResponse can be serialized to JSON."""
        from budcluster.jobs.schemas import JobResponse

        now = datetime.now(timezone.utc)
        job = JobResponse(
            id=uuid4(),
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            status=JobStatus.RUNNING,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            priority=50,
            retry_count=0,
            created_at=now,
            modified_at=now,
        )
        json_dict = job.model_dump(mode="json")
        assert "id" in json_dict
        assert "created_at" in json_dict
        assert json_dict["status"] == "running"

    def test_job_update_json_serializable(self):
        """Test that JobUpdate can be serialized to JSON."""
        from budcluster.jobs.schemas import JobUpdate

        update = JobUpdate(status=JobStatus.SUCCEEDED)
        json_dict = update.model_dump(mode="json", exclude_none=True)
        assert json_dict["status"] == "succeeded"


class TestJobSchemaValidationEdgeCases:
    """Test cases for edge case validations."""

    def test_job_create_empty_name_rejected(self):
        """Test that empty name is rejected."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError):
            JobCreate(
                name="",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )

    def test_job_create_whitespace_name_rejected(self):
        """Test that whitespace-only name is rejected."""
        from budcluster.jobs.schemas import JobCreate

        with pytest.raises(ValidationError):
            JobCreate(
                name="   ",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )

    def test_job_create_config_accepts_nested_dict(self):
        """Test that config accepts nested dictionaries."""
        from budcluster.jobs.schemas import JobCreate

        job = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            config={
                "model": "llama-3",
                "settings": {
                    "gpu": {"count": 4, "type": "A100"},
                    "memory": "32Gi",
                },
            },
        )
        assert job.config["settings"]["gpu"]["count"] == 4

    def test_job_create_metadata_accepts_nested_dict(self):
        """Test that metadata accepts nested dictionaries."""
        from budcluster.jobs.schemas import JobCreate

        job = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
            metadata_={
                "labels": {"env": "production", "team": "ml"},
                "annotations": {"version": "1.0"},
            },
        )
        assert job.metadata_["labels"]["env"] == "production"

    def test_job_update_empty_dict_config(self):
        """Test that empty dict is valid for config update."""
        from budcluster.jobs.schemas import JobUpdate

        update = JobUpdate(config={})
        assert update.config == {}

    def test_job_response_with_error_message(self):
        """Test JobResponse with error message for failed job."""
        from budcluster.jobs.schemas import JobResponse

        now = datetime.now(timezone.utc)
        job = JobResponse(
            id=uuid4(),
            name="failed-job",
            job_type=JobType.FINE_TUNING,
            status=JobStatus.FAILED,
            source=JobSource.BUDUSECASES,
            cluster_id=uuid4(),
            priority=50,
            retry_count=3,
            error_message="CUDA out of memory. Tried to allocate 20.00 GiB",
            created_at=now,
            modified_at=now,
        )
        assert job.status == JobStatus.FAILED
        assert "CUDA out of memory" in job.error_message
