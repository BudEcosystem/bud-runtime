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

import os
from pathlib import Path
from typing import Optional

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    enable_periodic_sync_from_store,
    register_settings,
)
from pydantic import DirectoryPath, Field

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # huggingface hub directory
    hf_home_dir: str = Field(os.path.expanduser("~/.cache/huggingface/hub"), alias="HF_HOME_DIR")

    # model download directory
    model_download_dir: DirectoryPath = Field(os.path.expanduser("~/.cache"), alias="MODEL_DOWNLOAD_DIR")

    # model download directory max size in GB
    model_download_dir_max_size: int = Field(300, alias="MODEL_DOWNLOAD_DIR_MAX_SIZE")

    # Add model directory
    add_model_dir: DirectoryPath = Field(os.path.expanduser("~/.cache"), alias="ADD_MODEL_DIR")

    # PerplexityAI model name
    model: str = Field("llama-3.1-sonar-small-128k-online", alias="PERPLEXITYAI_MODEL_NAME")

    # minio
    minio_endpoint: str = Field("bud-store.bud.studio", alias="MINIO_ENDPOINT")
    minio_secure: bool = Field(True, alias="MINIO_SECURE")
    minio_bucket: str = Field("models-registry", alias="MINIO_BUCKET")
    minio_model_bucket: str = Field("model-info", alias="MINIO_MODEL_BUCKET")

    # max thread workers
    max_thread_workers: int = Field(10, alias="MAX_THREAD_WORKERS")

    # Base Directory
    base_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent.parent.resolve())

    # Aria2p Config
    Aria2p_host: str = Field("http://localhost", alias="ARIA2P_HOST")
    Aria2p_port: int = Field(6800, alias="ARIA2P_PORT")

    # Bud LLM Base URL
    bud_llm_base_url: Optional[str] = Field(None, alias="BUD_LLM_BASE_URL")
    bud_llm_model: str = Field("Qwen/QwQ-32B", alias="BUD_LLM_MODEL")

    # clamav config
    clamd_port: int = Field(3310, alias="CLAMD_PORT")
    clamd_host: str = Field("0.0.0.0", alias="CLAMD_HOST")

    # seeder config
    enable_seeder: bool = Field(True, alias="ENABLE_SEEDER")

    # budconnect config
    budconnect_url: str = Field("https://budconnect.bud.studio", alias="BUDCONNECT_URL")
    budconnect_timeout: int = Field(30, alias="BUDCONNECT_TIMEOUT")


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # External Services
    openai_api_key: Optional[str] = Field(
        None, alias="OPENAI_API_KEY", json_schema_extra=enable_periodic_sync_from_store(is_global=True)
    )
    perplexity_api_key: Optional[str] = Field(
        None, alias="PERPLEXITY_API_KEY", json_schema_extra=enable_periodic_sync_from_store(is_global=True)
    )

    minio_access_key: Optional[str] = Field(
        None,
        alias="MINIO_ACCESS_KEY",
        json_schema_extra=enable_periodic_sync_from_store(is_global=True),
    )
    minio_secret_key: Optional[str] = Field(
        None,
        alias="MINIO_SECRET_KEY",
        json_schema_extra=enable_periodic_sync_from_store(is_global=True),
    )

    bud_llm_api_key: Optional[str] = Field(
        "sk-xxx",
        alias="BUD_LLM_API_KEY",
        json_schema_extra=enable_periodic_sync_from_store(is_global=True),
    )


app_settings = AppConfig()
secrets_settings = SecretsConfig()


register_settings(app_settings, secrets_settings)
