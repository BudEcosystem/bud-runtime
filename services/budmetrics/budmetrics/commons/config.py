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

from typing import Optional

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    register_settings,
)
from pydantic import Field

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""
    scoring_tool: str = Field("LLMGuardScorer", alias="SCORING_TOOL")

    # DB
    psql_host: Optional[str] = Field(None, alias="PSQL_HOST")
    psql_port: Optional[int] = Field(None, alias="PSQL_PORT")
    psql_dbname: Optional[str] = Field(None, alias="PSQL_DB_NAME")

    clickhouse_host: str = Field(..., alias="CLICKHOUSE_HOST")
    clickhouse_port: int = Field(..., alias="CLICKHOUSE_PORT")
    clickhouse_dbname: str = Field("bud", alias="CLICKHOUSE_DB_NAME")

    clickhouse_enable_query_cache: bool = Field(False, alias="CLICKHOUSE_ENABLE_QUERY_CACHE")
    clickhouse_enable_connection_warmup: bool = Field(False, alias="CLICKHOUSE_ENABLE_CONNECTION_WARMUP")
    clickhouse_ttl_inference_fact: int = Field(90, alias="CLICKHOUSE_TTL_INFERENCE_FACT")


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    clickhouse_user: Optional[str] = Field(None, alias="CLICKHOUSE_USER")
    clickhouse_password: Optional[str] = Field(None, alias="CLICKHOUSE_PASSWORD")


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
