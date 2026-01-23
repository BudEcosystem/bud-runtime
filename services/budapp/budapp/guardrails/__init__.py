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

"""Guardrails module for managing guardrail probes, rules, profiles, and deployments."""

from budapp.guardrails.crud import GuardrailsDeploymentDataManager, GuardrailsProbeRulesDataManager
from budapp.guardrails.models import (
    GuardrailDeployment,
    GuardrailProbe,
    GuardrailProfile,
    GuardrailProfileProbe,
    GuardrailProfileRule,
    GuardrailRule,
    GuardrailRuleDeployment,
)


# Note: Services and pipeline_actions are NOT imported here to avoid circular imports.
# Import them directly where needed:
#   from budapp.guardrails.services import GuardrailProbeRuleService, ...
#   from budapp.guardrails.pipeline_actions import GuardrailPipelineActions


__all__ = [
    # Data Managers
    "GuardrailsProbeRulesDataManager",
    "GuardrailsDeploymentDataManager",
    # Models
    "GuardrailProbe",
    "GuardrailRule",
    "GuardrailProfile",
    "GuardrailProfileProbe",
    "GuardrailProfileRule",
    "GuardrailDeployment",
    "GuardrailRuleDeployment",
]
