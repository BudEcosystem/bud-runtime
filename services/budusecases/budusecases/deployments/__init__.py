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

"""Deployment Orchestration Module for BudUseCases.

This module handles deployment lifecycle management including
creating, starting, stopping, and monitoring GenAI deployments.
"""

from .crud import DeploymentDataManager
from .enums import ComponentDeploymentStatus, DeploymentStatus
from .exceptions import (
    AccessConfigValidationError,
    DeploymentNotFoundError,
    IncompatibleComponentError,
    InvalidDeploymentStateError,
    MissingRequiredComponentError,
    TemplateNotFoundError,
)
from .models import ComponentDeployment, UseCaseDeployment
from .schemas import (
    ComponentDeploymentResponseSchema,
    DeploymentCreateSchema,
    DeploymentResponseSchema,
)
from .services import DeploymentOrchestrationService

__all__ = [
    "UseCaseDeployment",
    "ComponentDeployment",
    "DeploymentStatus",
    "ComponentDeploymentStatus",
    "DeploymentDataManager",
    "DeploymentOrchestrationService",
    "DeploymentCreateSchema",
    "DeploymentResponseSchema",
    "ComponentDeploymentResponseSchema",
    "AccessConfigValidationError",
    "DeploymentNotFoundError",
    "TemplateNotFoundError",
    "InvalidDeploymentStateError",
    "MissingRequiredComponentError",
    "IncompatibleComponentError",
]
