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

"""Defines custom exceptions to handle specific error cases gracefully."""

from budmicroframe.commons import logging


logger = logging.get_logger(__name__)


class KubernetesException(Exception):
    """Base exception for kubernetes handler errors."""

    def __init__(self, message="Kubernetes error occurred"):
        """Initialize KubernetesException."""
        self.message = message
        super().__init__(self.message)


class OpenshiftException(Exception):
    """Base exception for Openshift handler errors."""

    def __init__(self, message="Openshift error occurred"):
        """Initialize OpenshiftException."""
        self.message = message
        super().__init__(self.message)


class ClusterDecryptionException(Exception):
    """Raise when the cluster config cannot be decrypted."""

    def __init__(self, message="An error occurred during cluster configuration decryption"):
        """Initialize ClusterDecryptionException."""
        self.message = message
        super().__init__(message)


class DaprJobsException(Exception):
    """Raise when a Dapr Jobs error occurs."""

    def __init__(self, message="An error occurred during Dapr Jobs"):
        """Initialize DaprJobsException."""
        self.message = message
        super().__init__(message)


class ClientException(Exception):
    """A custom exception class for client-related errors.

    This exception can be raised when client requests fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the database error.

    Args:
        message (str): The error message describing the database issue.
    """

    def __init__(self, message: str, status_code: int = 400):
        """Initialize the ClientException with a message."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the database exception."""
        return f"ClientException: {self.message}"


class BenchmarkResultSaveError(Exception):
    """Exception raised when saving a benchmark result fails."""

    def __init__(self, message: str, status_code: int = 400):
        """Initialize the BenchmarkResultSaveError with a message."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the database exception."""
        return f"BenchmarkResultSaveError: {self.message}"
