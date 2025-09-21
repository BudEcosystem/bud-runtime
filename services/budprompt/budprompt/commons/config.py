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

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    register_settings,
)
from pydantic import DirectoryPath, Field

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    # BudServe Gateway Configuration
    bud_gateway_base_url: str = Field(..., alias="BUD_GATEWAY_BASE_URL")
    bud_default_model_name: str = Field(..., alias="BUD_DEFAULT_MODEL_NAME")

    # Redis Configuration
    redis_host: str = Field(..., alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db_index: int = Field(default=0, alias="REDIS_DB_INDEX")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # Redis TTL Configuration
    prompt_config_redis_ttl: int = Field(default=86400, alias="PROMPT_CONFIG_REDIS_TTL")

    @property
    def redis_url(self) -> str:
        """Construct the complete Redis URL from individual components.

        Returns:
            Complete Redis connection URL with authentication if password is provided
        """
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db_index}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_index}"


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # Add any other secrets here that are not Redis-related
    # For now, this class can remain empty or contain other secrets


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
