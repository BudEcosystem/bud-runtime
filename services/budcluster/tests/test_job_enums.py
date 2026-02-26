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

"""TDD Tests for Job enums and constants.

These tests are written BEFORE the implementation following TDD methodology.
The implementation should make all these tests pass.
"""

import pytest


class TestJobTypeEnum:
    """Test cases for JobType enum."""

    def test_job_type_enum_exists(self):
        """Test that JobType enum can be imported."""
        from budcluster.jobs.enums import JobType

        assert JobType is not None

    def test_job_type_has_model_deployment(self):
        """Test JobType has MODEL_DEPLOYMENT value for vLLM/model serving deployments."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "MODEL_DEPLOYMENT")
        assert JobType.MODEL_DEPLOYMENT.value == "model_deployment"

    def test_job_type_has_custom_job(self):
        """Test JobType has CUSTOM_JOB value for user-defined K8s jobs."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "CUSTOM_JOB")
        assert JobType.CUSTOM_JOB.value == "custom_job"

    def test_job_type_has_fine_tuning(self):
        """Test JobType has FINE_TUNING value for model fine-tuning jobs."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "FINE_TUNING")
        assert JobType.FINE_TUNING.value == "fine_tuning"

    def test_job_type_has_batch_inference(self):
        """Test JobType has BATCH_INFERENCE value for batch processing jobs."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "BATCH_INFERENCE")
        assert JobType.BATCH_INFERENCE.value == "batch_inference"

    def test_job_type_has_usecase_component(self):
        """Test JobType has USECASE_COMPONENT value for UseCase deployments (RAG, Chatbot, etc)."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "USECASE_COMPONENT")
        assert JobType.USECASE_COMPONENT.value == "usecase_component"

    def test_job_type_has_benchmark(self):
        """Test JobType has BENCHMARK value for performance benchmark jobs."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "BENCHMARK")
        assert JobType.BENCHMARK.value == "benchmark"

    def test_job_type_has_data_pipeline(self):
        """Test JobType has DATA_PIPELINE value for data processing pipelines."""
        from budcluster.jobs.enums import JobType

        assert hasattr(JobType, "DATA_PIPELINE")
        assert JobType.DATA_PIPELINE.value == "data_pipeline"

    def test_job_type_is_string_enum(self):
        """Test JobType is a string-based enum for easy serialization."""
        from budcluster.jobs.enums import JobType

        # Should be usable as string
        assert str(JobType.MODEL_DEPLOYMENT) == "model_deployment"
        assert JobType.MODEL_DEPLOYMENT == "model_deployment"

    def test_job_type_iteration(self):
        """Test JobType can be iterated to get all values."""
        from budcluster.jobs.enums import JobType

        job_types = list(JobType)
        assert len(job_types) >= 7  # At least 7 job types
        assert JobType.MODEL_DEPLOYMENT in job_types
        assert JobType.CUSTOM_JOB in job_types

    def test_job_type_from_value(self):
        """Test JobType can be constructed from string value."""
        from budcluster.jobs.enums import JobType

        assert JobType("model_deployment") == JobType.MODEL_DEPLOYMENT
        assert JobType("fine_tuning") == JobType.FINE_TUNING


class TestJobStatusEnum:
    """Test cases for JobStatus enum."""

    def test_job_status_enum_exists(self):
        """Test that JobStatus enum can be imported."""
        from budcluster.jobs.enums import JobStatus

        assert JobStatus is not None

    def test_job_status_has_pending(self):
        """Test JobStatus has PENDING value for jobs waiting to be scheduled."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "PENDING")
        assert JobStatus.PENDING.value == "pending"

    def test_job_status_has_queued(self):
        """Test JobStatus has QUEUED value for jobs in scheduler queue."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "QUEUED")
        assert JobStatus.QUEUED.value == "queued"

    def test_job_status_has_running(self):
        """Test JobStatus has RUNNING value for actively executing jobs."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "RUNNING")
        assert JobStatus.RUNNING.value == "running"

    def test_job_status_has_succeeded(self):
        """Test JobStatus has SUCCEEDED value for successfully completed jobs."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "SUCCEEDED")
        assert JobStatus.SUCCEEDED.value == "succeeded"

    def test_job_status_has_failed(self):
        """Test JobStatus has FAILED value for jobs that encountered errors."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "FAILED")
        assert JobStatus.FAILED.value == "failed"

    def test_job_status_has_cancelled(self):
        """Test JobStatus has CANCELLED value for user-cancelled jobs."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "CANCELLED")
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_job_status_has_timeout(self):
        """Test JobStatus has TIMEOUT value for jobs that exceeded time limit."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "TIMEOUT")
        assert JobStatus.TIMEOUT.value == "timeout"

    def test_job_status_has_retrying(self):
        """Test JobStatus has RETRYING value for jobs being retried after failure."""
        from budcluster.jobs.enums import JobStatus

        assert hasattr(JobStatus, "RETRYING")
        assert JobStatus.RETRYING.value == "retrying"

    def test_job_status_is_string_enum(self):
        """Test JobStatus is a string-based enum for easy serialization."""
        from budcluster.jobs.enums import JobStatus

        assert str(JobStatus.RUNNING) == "running"
        assert JobStatus.RUNNING == "running"

    def test_job_status_iteration(self):
        """Test JobStatus can be iterated to get all values."""
        from budcluster.jobs.enums import JobStatus

        statuses = list(JobStatus)
        assert len(statuses) >= 8  # At least 8 statuses
        assert JobStatus.PENDING in statuses
        assert JobStatus.SUCCEEDED in statuses

    def test_job_status_terminal_states(self):
        """Test that terminal states are correctly identified."""
        from budcluster.jobs.enums import JobStatus, TERMINAL_JOB_STATUSES

        # Terminal states - jobs that won't change status anymore
        assert JobStatus.SUCCEEDED in TERMINAL_JOB_STATUSES
        assert JobStatus.FAILED in TERMINAL_JOB_STATUSES
        assert JobStatus.CANCELLED in TERMINAL_JOB_STATUSES
        assert JobStatus.TIMEOUT in TERMINAL_JOB_STATUSES

        # Non-terminal states
        assert JobStatus.PENDING not in TERMINAL_JOB_STATUSES
        assert JobStatus.RUNNING not in TERMINAL_JOB_STATUSES

    def test_job_status_active_states(self):
        """Test that active states are correctly identified."""
        from budcluster.jobs.enums import JobStatus, ACTIVE_JOB_STATUSES

        # Active states - jobs currently consuming resources
        assert JobStatus.RUNNING in ACTIVE_JOB_STATUSES
        assert JobStatus.RETRYING in ACTIVE_JOB_STATUSES

        # Non-active states
        assert JobStatus.PENDING not in ACTIVE_JOB_STATUSES
        assert JobStatus.SUCCEEDED not in ACTIVE_JOB_STATUSES


class TestJobSourceEnum:
    """Test cases for JobSource enum."""

    def test_job_source_enum_exists(self):
        """Test that JobSource enum can be imported."""
        from budcluster.jobs.enums import JobSource

        assert JobSource is not None

    def test_job_source_has_budusecases(self):
        """Test JobSource has BUDUSECASES value for UseCase-created jobs."""
        from budcluster.jobs.enums import JobSource

        assert hasattr(JobSource, "BUDUSECASES")
        assert JobSource.BUDUSECASES.value == "budusecases"

    def test_job_source_has_budpipeline(self):
        """Test JobSource has BUDPIPELINE value for pipeline-created jobs."""
        from budcluster.jobs.enums import JobSource

        assert hasattr(JobSource, "BUDPIPELINE")
        assert JobSource.BUDPIPELINE.value == "budpipeline"

    def test_job_source_has_manual(self):
        """Test JobSource has MANUAL value for manually created jobs."""
        from budcluster.jobs.enums import JobSource

        assert hasattr(JobSource, "MANUAL")
        assert JobSource.MANUAL.value == "manual"

    def test_job_source_has_budapp(self):
        """Test JobSource has BUDAPP value for BudApp-created jobs (legacy endpoints)."""
        from budcluster.jobs.enums import JobSource

        assert hasattr(JobSource, "BUDAPP")
        assert JobSource.BUDAPP.value == "budapp"

    def test_job_source_has_scheduler(self):
        """Test JobSource has SCHEDULER value for scheduled/cron jobs."""
        from budcluster.jobs.enums import JobSource

        assert hasattr(JobSource, "SCHEDULER")
        assert JobSource.SCHEDULER.value == "scheduler"

    def test_job_source_is_string_enum(self):
        """Test JobSource is a string-based enum for easy serialization."""
        from budcluster.jobs.enums import JobSource

        assert str(JobSource.BUDUSECASES) == "budusecases"
        assert JobSource.BUDUSECASES == "budusecases"

    def test_job_source_iteration(self):
        """Test JobSource can be iterated to get all values."""
        from budcluster.jobs.enums import JobSource

        sources = list(JobSource)
        assert len(sources) >= 5  # At least 5 sources
        assert JobSource.BUDUSECASES in sources
        assert JobSource.MANUAL in sources


class TestJobPriorityEnum:
    """Test cases for JobPriority enum."""

    def test_job_priority_enum_exists(self):
        """Test that JobPriority enum can be imported."""
        from budcluster.jobs.enums import JobPriority

        assert JobPriority is not None

    def test_job_priority_has_low(self):
        """Test JobPriority has LOW value."""
        from budcluster.jobs.enums import JobPriority

        assert hasattr(JobPriority, "LOW")
        assert JobPriority.LOW.value == 0

    def test_job_priority_has_normal(self):
        """Test JobPriority has NORMAL value (default)."""
        from budcluster.jobs.enums import JobPriority

        assert hasattr(JobPriority, "NORMAL")
        assert JobPriority.NORMAL.value == 50

    def test_job_priority_has_high(self):
        """Test JobPriority has HIGH value."""
        from budcluster.jobs.enums import JobPriority

        assert hasattr(JobPriority, "HIGH")
        assert JobPriority.HIGH.value == 75

    def test_job_priority_has_critical(self):
        """Test JobPriority has CRITICAL value for urgent jobs."""
        from budcluster.jobs.enums import JobPriority

        assert hasattr(JobPriority, "CRITICAL")
        assert JobPriority.CRITICAL.value == 100

    def test_job_priority_ordering(self):
        """Test that priorities are properly ordered."""
        from budcluster.jobs.enums import JobPriority

        assert JobPriority.LOW.value < JobPriority.NORMAL.value
        assert JobPriority.NORMAL.value < JobPriority.HIGH.value
        assert JobPriority.HIGH.value < JobPriority.CRITICAL.value

    def test_job_priority_is_int_enum(self):
        """Test JobPriority is an integer-based enum for comparison."""
        from budcluster.jobs.enums import JobPriority

        # Should be usable as integer
        assert int(JobPriority.NORMAL) == 50
        # Should be comparable
        assert JobPriority.HIGH > JobPriority.NORMAL


class TestJobConstants:
    """Test cases for Job-related constants."""

    def test_default_job_timeout_exists(self):
        """Test that DEFAULT_JOB_TIMEOUT constant exists."""
        from budcluster.jobs.constants import DEFAULT_JOB_TIMEOUT

        assert DEFAULT_JOB_TIMEOUT is not None
        assert isinstance(DEFAULT_JOB_TIMEOUT, int)
        assert DEFAULT_JOB_TIMEOUT > 0

    def test_default_job_timeout_value(self):
        """Test DEFAULT_JOB_TIMEOUT is reasonable (1 hour in seconds)."""
        from budcluster.jobs.constants import DEFAULT_JOB_TIMEOUT

        # Default timeout should be 1 hour (3600 seconds)
        assert DEFAULT_JOB_TIMEOUT == 3600

    def test_max_job_retries_exists(self):
        """Test that MAX_JOB_RETRIES constant exists."""
        from budcluster.jobs.constants import MAX_JOB_RETRIES

        assert MAX_JOB_RETRIES is not None
        assert isinstance(MAX_JOB_RETRIES, int)
        assert MAX_JOB_RETRIES >= 0

    def test_max_job_retries_value(self):
        """Test MAX_JOB_RETRIES is reasonable (3 retries)."""
        from budcluster.jobs.constants import MAX_JOB_RETRIES

        assert MAX_JOB_RETRIES == 3

    def test_job_retry_delay_exists(self):
        """Test that JOB_RETRY_DELAY constant exists."""
        from budcluster.jobs.constants import JOB_RETRY_DELAY

        assert JOB_RETRY_DELAY is not None
        assert isinstance(JOB_RETRY_DELAY, int)
        assert JOB_RETRY_DELAY > 0

    def test_job_retry_delay_value(self):
        """Test JOB_RETRY_DELAY is reasonable (30 seconds)."""
        from budcluster.jobs.constants import JOB_RETRY_DELAY

        assert JOB_RETRY_DELAY == 30

    def test_job_poll_interval_exists(self):
        """Test that JOB_POLL_INTERVAL constant exists."""
        from budcluster.jobs.constants import JOB_POLL_INTERVAL

        assert JOB_POLL_INTERVAL is not None
        assert isinstance(JOB_POLL_INTERVAL, int)
        assert JOB_POLL_INTERVAL > 0

    def test_job_poll_interval_value(self):
        """Test JOB_POLL_INTERVAL is reasonable (5 seconds)."""
        from budcluster.jobs.constants import JOB_POLL_INTERVAL

        assert JOB_POLL_INTERVAL == 5

    def test_job_type_timeouts_mapping(self):
        """Test that JOB_TYPE_TIMEOUTS mapping exists for type-specific timeouts."""
        from budcluster.jobs.constants import JOB_TYPE_TIMEOUTS
        from budcluster.jobs.enums import JobType

        assert JOB_TYPE_TIMEOUTS is not None
        assert isinstance(JOB_TYPE_TIMEOUTS, dict)

        # Fine-tuning jobs should have longer timeout
        assert JobType.FINE_TUNING in JOB_TYPE_TIMEOUTS
        assert JOB_TYPE_TIMEOUTS[JobType.FINE_TUNING] > 3600  # > 1 hour

        # Batch inference may have longer timeout
        assert JobType.BATCH_INFERENCE in JOB_TYPE_TIMEOUTS

    def test_job_namespace_prefix(self):
        """Test that JOB_NAMESPACE_PREFIX constant exists."""
        from budcluster.jobs.constants import JOB_NAMESPACE_PREFIX

        assert JOB_NAMESPACE_PREFIX is not None
        assert isinstance(JOB_NAMESPACE_PREFIX, str)
        assert JOB_NAMESPACE_PREFIX == "bud-job"


class TestEnumInteroperability:
    """Test cases for enum interoperability with other systems."""

    def test_job_type_json_serializable(self):
        """Test JobType can be serialized to JSON."""
        import json

        from budcluster.jobs.enums import JobType

        # Should be directly JSON serializable as string
        result = json.dumps({"type": JobType.MODEL_DEPLOYMENT.value})
        assert '"model_deployment"' in result

    def test_job_status_json_serializable(self):
        """Test JobStatus can be serialized to JSON."""
        import json

        from budcluster.jobs.enums import JobStatus

        result = json.dumps({"status": JobStatus.RUNNING.value})
        assert '"running"' in result

    def test_job_enums_sqlalchemy_compatible(self):
        """Test that enums can be used with SQLAlchemy Enum type."""
        from budcluster.jobs.enums import JobSource, JobStatus, JobType

        # SQLAlchemy expects enums to have .value attribute and be iterable
        for enum_class in [JobType, JobStatus, JobSource]:
            for member in enum_class:
                assert hasattr(member, "value")
                assert hasattr(member, "name")

    def test_job_status_pydantic_compatible(self):
        """Test JobStatus works with Pydantic validation."""
        from pydantic import BaseModel

        from budcluster.jobs.enums import JobStatus

        class TestModel(BaseModel):
            status: JobStatus

        # Should validate correctly
        model = TestModel(status=JobStatus.RUNNING)
        assert model.status == JobStatus.RUNNING

        # Should accept string value
        model2 = TestModel(status="running")
        assert model2.status == JobStatus.RUNNING

    def test_job_type_pydantic_compatible(self):
        """Test JobType works with Pydantic validation."""
        from pydantic import BaseModel

        from budcluster.jobs.enums import JobType

        class TestModel(BaseModel):
            job_type: JobType

        model = TestModel(job_type=JobType.FINE_TUNING)
        assert model.job_type == JobType.FINE_TUNING

        model2 = TestModel(job_type="fine_tuning")
        assert model2.job_type == JobType.FINE_TUNING


class TestEnumEdgeCases:
    """Test edge cases and error handling for enums."""

    def test_invalid_job_type_raises_error(self):
        """Test that invalid JobType value raises ValueError."""
        from budcluster.jobs.enums import JobType

        with pytest.raises(ValueError):
            JobType("invalid_type")

    def test_invalid_job_status_raises_error(self):
        """Test that invalid JobStatus value raises ValueError."""
        from budcluster.jobs.enums import JobStatus

        with pytest.raises(ValueError):
            JobStatus("invalid_status")

    def test_invalid_job_source_raises_error(self):
        """Test that invalid JobSource value raises ValueError."""
        from budcluster.jobs.enums import JobSource

        with pytest.raises(ValueError):
            JobSource("invalid_source")

    def test_job_type_case_sensitive(self):
        """Test that JobType values are case-sensitive."""
        from budcluster.jobs.enums import JobType

        # Lowercase should work (our values are lowercase)
        assert JobType("model_deployment") == JobType.MODEL_DEPLOYMENT

        # Uppercase should fail
        with pytest.raises(ValueError):
            JobType("MODEL_DEPLOYMENT")

    def test_enum_equality_by_value(self):
        """Test enum equality comparisons work with string values."""
        from budcluster.jobs.enums import JobStatus

        # Should be equal to its string value
        assert JobStatus.RUNNING == "running"
        assert "running" == JobStatus.RUNNING

        # Should not be equal to other values
        assert JobStatus.RUNNING != "pending"
        assert JobStatus.RUNNING != JobStatus.PENDING

    def test_enum_hash_consistency(self):
        """Test that enum members have consistent hash values."""
        from budcluster.jobs.enums import JobStatus

        # Same enum should hash to same value
        assert hash(JobStatus.RUNNING) == hash(JobStatus.RUNNING)

        # Should be usable in sets and dicts
        status_set = {JobStatus.RUNNING, JobStatus.PENDING, JobStatus.RUNNING}
        assert len(status_set) == 2  # RUNNING should deduplicate

        status_dict = {JobStatus.RUNNING: "active"}
        assert status_dict[JobStatus.RUNNING] == "active"
