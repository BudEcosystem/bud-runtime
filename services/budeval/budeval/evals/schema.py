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

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase
from pydantic import BaseModel, Field


# --- Evaluation Engine --- #
class EvaluationEngine(str, Enum):
    """Supported evaluation engines."""

    OPENCOMPASS = "opencompass"


class EvalMode(str, Enum):
    """Supported evaluation modes."""

    GEN = "gen"
    PPL = "ppl"


# --- Evaluation Job Info --- #
class EvalModelInfo(BaseModel):
    """Model information for evaluation."""

    model_name: str = Field(..., description="Name of the model to be evaluated")
    endpoint: str = Field(..., description="Endpoint of the model to be evaluated")
    api_key: str = Field(..., description="API key for authentication")
    extra_args: Dict[str, Any] = Field(default_factory=dict, description="Extra arguments for the model")


class EvalDataset(BaseModel):
    """Dataset information for evaluation."""

    dataset_id: str = Field(..., description="ID of the dataset to be evaluated")
    run_id: str = Field(..., description="ID of the run to be evaluated")
    eval_mode: Optional[EvalMode] = Field(
        default=None,
        description=(
            "Evaluation mode for the dataset (generation or perplexity); defaults to the request mode when omitted"
        ),
    )


class EvalConfig(BaseModel):
    """Configuration for evaluation."""

    config_name: str = Field(..., description="Name of the evaluation configuration")
    config_value: Dict[str, Any] = Field(..., description="Value of the evaluation configuration")


class EvaluationRequest(CloudEventBase):
    """Schema for evaluation request with nested structure."""

    eval_id: UUID = Field(..., description="Unique identifier for the evaluation request")

    # Experiment ID to track evaluation back to experiment
    experiment_id: UUID = Field(..., description="The experiment ID this evaluation belongs to")

    # Nested model info structure
    eval_model_info: EvalModelInfo = Field(..., description="Model information for evaluation")

    # Evaluation mode
    eval_mode: EvalMode = Field(
        default=EvalMode.GEN,
        description="Evaluation mode (e.g., generation or perplexity)",
    )

    # Structured datasets instead of simple strings
    eval_datasets: List[EvalDataset] = Field(..., description="Evaluation datasets")

    # New field for evaluation configurations
    eval_configs: List[EvalConfig] = Field(default_factory=list, description="Evaluation configurations")

    # Keep engine field for compatibility
    engine: EvaluationEngine = Field(
        default=EvaluationEngine.OPENCOMPASS,
        description="Evaluation engine to use",
    )

    # Kubeconfig remains optional
    kubeconfig: Optional[str] = Field(
        None,
        description="Kubernetes configuration JSON content (optional, uses local config if not provided)",
    )
