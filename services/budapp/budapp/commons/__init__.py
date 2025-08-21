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

"""Initialization module for the `commons` subpackage. Contains common utilities, configurations, constants, and helper functions that are shared across the project."""

from budapp.auth.models import Token as Token
from budapp.cluster_ops.models import Cluster as Cluster
from budapp.core.models import Icon as Icon
from budapp.core.models import ModelTemplate as ModelTemplate
from budapp.credential_ops.models import Credential as Credential
from budapp.credential_ops.models import ProprietaryCredential as ProprietaryCredential
from budapp.endpoint_ops.models import Endpoint as Endpoint
from budapp.eval_ops.models import (  # noqa: F401
    EvalSyncState,
    ExpDataset,
    ExpDatasetVersion,
    Experiment,
    ExpModel,
    ExpTrait,
    ExpTraitsDatasetPivot,
)
from budapp.model_ops.models import CloudModel as CloudModel
from budapp.model_ops.models import Model as Model
from budapp.model_ops.models import Provider as Provider
from budapp.permissions.models import Permission as Permission
from budapp.permissions.models import ProjectPermission as ProjectPermission
from budapp.project_ops.models import Project as Project
from budapp.router_ops.models import Router as Router
from budapp.router_ops.models import RouterEndpoint as RouterEndpoint
from budapp.user_ops.models import User as User
from budapp.workflow_ops.models import Workflow as Workflow
from budapp.workflow_ops.models import WorkflowStep as WorkflowStep

from ..benchmark_ops.models import BenchmarkRequestMetricsSchema as BenchmarkRequestMetricsSchema
from ..benchmark_ops.models import BenchmarkSchema as BenchmarkSchema
from ..cluster_ops.models import ModelClusterRecommended as ModelClusterRecommended
from ..dataset_ops.models import DatasetSchema as DatasetSchema
from ..playground_ops.models import ChatSession as ChatSession
from ..playground_ops.models import Message as Message
from ..playground_ops.models import Note as Note
from ..guardrails.models import GuardrailProbe as GuardrailProbe
from ..guardrails.models import GuardrailRule as GuardrailRule
from ..guardrails.models import GuardrailDeployment as GuardrailDeployment
from ..guardrails.models import GuardrailDeploymentProbe as GuardrailDeploymentProbe
from ..guardrails.models import GuardrailDeploymentRule as GuardrailDeploymentRule
from .database import Base as Base
