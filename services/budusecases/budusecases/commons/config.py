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

"""Configuration management for BudUseCases service."""

from pathlib import Path

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    register_settings,
)
from dotenv import load_dotenv
from pydantic import AnyHttpUrl, DirectoryPath, Field

from budusecases.__about__ import __version__

load_dotenv()


class AppConfig(BaseAppConfig):
    """Application configuration for BudUseCases service."""

    # App Info
    name: str = "budusecases"
    version: str = __version__
    description: str = "Pre-configured GenAI deployment templates and orchestration"
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent.parent.resolve())

    # Template configuration
    templates_path: str = Field("templates", alias="TEMPLATES_PATH")
    templates_sync_on_startup: bool = Field(True, alias="TEMPLATES_SYNC_ON_STARTUP")

    # BudCluster integration
    budcluster_app_id: str = Field("budcluster", alias="BUDCLUSTER_APP_ID")

    # BudPipeline integration
    budpipeline_app_id: str = Field("budpipeline", alias="BUDPIPELINE_APP_ID")

    # Orchestration
    use_pipeline_orchestration: bool = Field(True, alias="USE_PIPELINE_ORCHESTRATION")

    # Callback topic for budapp notifications
    budapp_callback_topic: str = Field("budAppMessages", alias="BUDAPP_CALLBACK_TOPIC")

    # Dapr configuration
    dapr_base_url: AnyHttpUrl | None = Field(None, alias="DAPR_BASE_URL")


class SecretsConfig(BaseSecretsConfig):
    """Secrets configuration for BudUseCases service."""

    # App Info
    name: str = "budusecases"
    version: str = __version__


# Singleton instances
app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
