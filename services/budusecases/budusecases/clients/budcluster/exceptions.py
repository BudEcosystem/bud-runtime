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

"""Exceptions for BudCluster client."""


class BudClusterError(Exception):
    """Base exception for BudCluster client errors."""

    pass


class BudClusterConnectionError(BudClusterError):
    """Raised when connection to BudCluster fails."""

    pass


class BudClusterTimeoutError(BudClusterError):
    """Raised when a request to BudCluster times out."""

    pass


class BudClusterValidationError(BudClusterError):
    """Raised when BudCluster returns a validation error."""

    pass


class JobNotFoundError(BudClusterError):
    """Raised when a job is not found."""

    pass


class ClusterNotFoundError(BudClusterError):
    """Raised when a cluster is not found."""

    pass
