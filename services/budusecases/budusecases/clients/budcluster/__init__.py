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

"""BudCluster Client for Dapr service invocation."""

from .client import BudClusterClient
from .exceptions import (
    BudClusterConnectionError,
    BudClusterError,
    BudClusterTimeoutError,
    BudClusterValidationError,
    ClusterNotFoundError,
    JobNotFoundError,
)
from .schemas import (
    ClusterCapacityResponse,
    ClusterInfoResponse,
    ClusterStatus,
    JobCreateRequest,
    JobListResponse,
    JobResponse,
    JobSource,
    JobStatus,
    JobStatusUpdateRequest,
    JobType,
)

__all__ = [
    "BudClusterClient",
    "BudClusterError",
    "BudClusterConnectionError",
    "BudClusterTimeoutError",
    "BudClusterValidationError",
    "JobNotFoundError",
    "ClusterNotFoundError",
    "JobCreateRequest",
    "JobResponse",
    "JobListResponse",
    "JobStatusUpdateRequest",
    "JobType",
    "JobStatus",
    "JobSource",
    "ClusterInfoResponse",
    "ClusterCapacityResponse",
    "ClusterStatus",
]
