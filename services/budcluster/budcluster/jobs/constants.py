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

"""Constants for job management in BudCluster.

This module defines constants used for job timeouts, retries, polling,
and other job-related configurations.
"""

from .enums import JobType


# Default timeout for jobs in seconds (1 hour)
DEFAULT_JOB_TIMEOUT: int = 3600

# Maximum number of retry attempts for failed jobs
MAX_JOB_RETRIES: int = 3

# Delay between retry attempts in seconds
JOB_RETRY_DELAY: int = 30

# Polling interval for checking job status in seconds
JOB_POLL_INTERVAL: int = 5

# Prefix for job-related Kubernetes namespaces
JOB_NAMESPACE_PREFIX: str = "bud-job"

# Type-specific timeout overrides in seconds
JOB_TYPE_TIMEOUTS: dict[JobType, int] = {
    JobType.MODEL_DEPLOYMENT: 7200,  # 2 hours - model downloads can be slow
    JobType.CUSTOM_JOB: 3600,  # 1 hour - default
    JobType.FINE_TUNING: 86400,  # 24 hours - fine-tuning can take long
    JobType.BATCH_INFERENCE: 14400,  # 4 hours - batch jobs can be large
    JobType.USECASE_COMPONENT: 3600,  # 1 hour - component deployments
    JobType.BENCHMARK: 7200,  # 2 hours - benchmarks need time
    JobType.DATA_PIPELINE: 21600,  # 6 hours - data processing
    JobType.HELM_DEPLOY: 3600,  # 1 hour - Helm deployments
}

# Exponential backoff configuration for retries
RETRY_BACKOFF_BASE: int = 2  # Base for exponential backoff
RETRY_BACKOFF_MAX: int = 300  # Maximum backoff delay in seconds (5 minutes)

# Job cleanup configuration
JOB_RETENTION_DAYS: int = 30  # Days to keep completed job records
FAILED_JOB_RETENTION_DAYS: int = 90  # Days to keep failed job records for debugging

# Resource limits for job pods (defaults)
DEFAULT_JOB_MEMORY_LIMIT: str = "4Gi"
DEFAULT_JOB_CPU_LIMIT: str = "2"
DEFAULT_JOB_MEMORY_REQUEST: str = "1Gi"
DEFAULT_JOB_CPU_REQUEST: str = "500m"
