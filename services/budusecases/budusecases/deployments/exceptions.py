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

"""Exceptions for Deployment module."""


class DeploymentError(Exception):
    """Base exception for deployment-related errors."""

    pass


class DeploymentNotFoundError(DeploymentError):
    """Raised when a deployment is not found."""

    pass


class TemplateNotFoundError(DeploymentError):
    """Raised when a template is not found."""

    pass


class InvalidDeploymentStateError(DeploymentError):
    """Raised when an operation is invalid for the current deployment state."""

    pass


class MissingRequiredComponentError(DeploymentError):
    """Raised when a required component is missing."""

    pass


class IncompatibleComponentError(DeploymentError):
    """Raised when a component is not compatible with the template."""

    pass


class AccessConfigValidationError(DeploymentError):
    """Raised when access config validation fails (e.g., missing project_id for API access)."""

    pass
