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

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    # BudServe Gateway Configuration
    bud_gateway_base_url: str = Field(..., alias="BUD_GATEWAY_BASE_URL")
    bud_default_model_name: str = Field(..., alias="BUD_DEFAULT_MODEL_NAME")


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    bud_redis_uri: str = Field(
        ..., alias="BUD_REDIS_URI", json_schema_extra=enable_periodic_sync_from_store(is_global=True)
    )
    bud_redis_password: str = Field(
        ..., alias="BUD_REDIS_PASSWORD", json_schema_extra=enable_periodic_sync_from_store(is_global=True)
    )

    @property
    def redis_url(self) -> str:
        """Construct the complete Redis URL with password.

        Returns:
            Complete Redis connection URL with authentication
        """
        # If URI already contains authentication, return as-is
        if "@" in self.bud_redis_uri:
            return self.bud_redis_uri

        # Parse the URI to insert password
        if self.bud_redis_uri.startswith("redis://") or self.bud_redis_uri.startswith("rediss://"):
            # Extract protocol and the rest
            protocol = "rediss://" if self.bud_redis_uri.startswith("rediss://") else "redis://"
            uri_without_protocol = self.bud_redis_uri[len(protocol) :]

            # Construct URL with password
            if self.bud_redis_password:
                return f"{protocol}:{self.bud_redis_password}@{uri_without_protocol}"
            else:
                return self.bud_redis_uri
        else:
            # Assume it's just host:port, add redis:// protocol
            if self.bud_redis_password:
                return f"redis://:{self.bud_redis_password}@{self.bud_redis_uri}"
            else:
                return f"redis://{self.bud_redis_uri}"


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
