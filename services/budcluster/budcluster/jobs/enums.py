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

"""Job enums for the unified job tracking layer in BudCluster.

This module defines enums for job types, statuses, sources, and priorities
used to track all workloads running on clusters managed by BudCluster.
"""

from enum import IntEnum, StrEnum


class JobType(StrEnum):
    """Types of jobs that can be tracked by BudCluster.

    This enum categorizes all workloads that run on managed clusters,
    enabling unified tracking regardless of how or why the job was created.

    Attributes:
        MODEL_DEPLOYMENT: vLLM/model serving deployments (long-running).
        CUSTOM_JOB: User-defined Kubernetes jobs.
        FINE_TUNING: Model fine-tuning jobs.
        BATCH_INFERENCE: Batch processing inference jobs.
        USECASE_COMPONENT: Components deployed as part of a UseCase (RAG, Chatbot, etc).
        BENCHMARK: Performance benchmark jobs.
        DATA_PIPELINE: Data processing pipeline jobs.
    """

    MODEL_DEPLOYMENT = "model_deployment"
    CUSTOM_JOB = "custom_job"
    FINE_TUNING = "fine_tuning"
    BATCH_INFERENCE = "batch_inference"
    USECASE_COMPONENT = "usecase_component"
    BENCHMARK = "benchmark"
    DATA_PIPELINE = "data_pipeline"
    HELM_DEPLOY = "helm_deploy"


class JobStatus(StrEnum):
    """Status of a job in the BudCluster job tracking system.

    Jobs progress through various states from creation to completion.
    Terminal states indicate the job has finished and won't change further.

    Attributes:
        PENDING: Job created but not yet scheduled.
        QUEUED: Job in scheduler queue waiting for resources.
        RUNNING: Job actively executing.
        SUCCEEDED: Job completed successfully (terminal).
        FAILED: Job encountered an error (terminal).
        CANCELLED: Job was cancelled by user (terminal).
        TIMEOUT: Job exceeded its time limit (terminal).
        RETRYING: Job failed and is being retried.
    """

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class JobSource(StrEnum):
    """Source system that created the job.

    Tracks which service or method was used to create a job,
    enabling proper attribution and source-specific handling.

    Attributes:
        BUDUSECASES: Job created by BudUseCases service (UseCase deployments).
        BUDPIPELINE: Job created by BudPipeline service (DAG execution).
        MANUAL: Job created manually via API or CLI.
        BUDAPP: Job created by BudApp service (legacy endpoint deployments).
        SCHEDULER: Job created by a scheduler (cron/scheduled jobs).
    """

    BUDUSECASES = "budusecases"
    BUDPIPELINE = "budpipeline"
    MANUAL = "manual"
    BUDAPP = "budapp"
    SCHEDULER = "scheduler"


class JobPriority(IntEnum):
    """Priority levels for job scheduling.

    Higher priority jobs are scheduled before lower priority ones
    when resources are constrained. Used with Kueue for fair scheduling.

    Attributes:
        LOW: Low priority, scheduled last (value: 0).
        NORMAL: Default priority for most jobs (value: 50).
        HIGH: High priority, scheduled preferentially (value: 75).
        CRITICAL: Highest priority, for urgent jobs (value: 100).
    """

    LOW = 0
    NORMAL = 50
    HIGH = 75
    CRITICAL = 100


# Status sets for convenient filtering
TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.TIMEOUT,
    }
)
"""Set of terminal job statuses - jobs that have finished and won't change."""

ACTIVE_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.RUNNING,
        JobStatus.RETRYING,
    }
)
"""Set of active job statuses - jobs currently consuming cluster resources."""

PENDING_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.PENDING,
        JobStatus.QUEUED,
    }
)
"""Set of pending job statuses - jobs waiting to be scheduled or run."""
