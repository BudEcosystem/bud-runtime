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

"""Manages application and secret configurations, utilizing environment variables and Dapr's configuration store for syncing."""

from pathlib import Path

from budmicroframe.commons.config import BaseAppConfig, BaseSecretsConfig, register_settings
from pydantic import DirectoryPath, Field

from budsim.__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    # Runtime
    vllm_cpu_image: str = Field("budecosystem/bud-runtime-cpu:latest", alias="VLLM_CPU_IMAGE")
    vllm_cuda_image: str = Field("budecosystem/bud-runtime-cuda:latest", alias="VLLM_CUDA_IMAGE")
    vllm_hpu_image: str = Field("budecosystem/bud-runtime-hpu:latest", alias="VLLM_HPU_IMAGE")
    sglang_cuda_image: str = Field("budecosystem/bud-runtime-cuda:latest", alias="SGLANG_CUDA_IMAGE")
    litellm_image: str = Field("ghcr.io/berriai/litellm:main-latest", alias="LITELLM_IMAGE")
    quantization_cpu_image: str = Field("budecosystem/bud-quantization-cpu:latest", alias="QUANTIZATION_CPU_IMAGE")
    quantization_cuda_image: str = Field("budecosystem/bud-quantization-cuda:latest", alias="QUANTIZATION_CUDA_IMAGE")

    # Regressor
    benchmark_predictor_models_dir: str = Field(
        Path(base_dir, "cache/pretrained_models").resolve().as_posix(),
        alias="BENCHMARK_PREDICTOR_MODELS_DIR",
    )

    # Evolution
    population_size: int = Field(10, alias="POPULATION_SIZE")
    generation_count: int = Field(50, alias="GENERATION_COUNT")

    model_registry_dir: str = Field(..., alias="MODEL_REGISTRY_DIR")

    # Simulation method
    default_simulation_method: str = Field("heuristic", alias="DEFAULT_SIMULATION_METHOD")

    # CPU optimization: skip master/control-plane nodes for CPU deployments
    skip_master_node_for_cpu: bool = Field(True, alias="SKIP_MASTER_NODE_FOR_CPU")

    # Bud Connect
    bud_connect_url: str = Field(..., alias="BUD_CONNECT_URL")


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
