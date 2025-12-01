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

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    # Dataset Configuration
    opencompass_dataset_url: str = Field(
        default="https://github.com/open-compass/opencompass/releases/download/0.2.2.rc1/OpenCompassData-complete-20240207.zip",
        alias="OPENCOMPASS_DATASET_URL",
    )
    eval_datasets_pvc_name: str = Field(default="eval-datasets-pvc", alias="EVAL_DATASETS_PATH")
    skip_volume_check: bool = Field(default=False, alias="SKIP_VOLUME_CHECK")

    # Eval Sync Configuration
    eval_sync_enabled: bool = Field(default=True, alias="EVAL_SYNC_ENABLED")
    eval_sync_local_mode: bool = Field(default=True, alias="EVAL_SYNC_LOCAL_MODE")
    eval_manifest_url: str = Field(
        default="https://eval-datasets.bud.eco/v2/eval_manifest.json", alias="EVAL_MANIFEST_URL"
    )
    eval_sync_batch_size: int = Field(default=50, alias="EVAL_SYNC_BATCH_SIZE")
    eval_manifest_local_path: str = Field(
        default="budeval/data/eval_manifest_test.json", alias="EVAL_MANIFEST_LOCAL_PATH"
    )
    eval_sync_interval_seconds: int = Field(default=3600, alias="EVAL_SYNC_INTERVAL_SECONDS")
    eval_sync_use_bundles: bool = Field(default=False, alias="EVAL_SYNC_USE_BUNDLES")
    eval_datasets_path: str = Field(default="bud-dev-budeval-dataset", alias="EVAL_DATASETS_PATH")

    # ClickHouse Configuration (moved from SecretsConfig)
    clickhouse_host: str = Field(default="okb80nfy88.ap-southeast-1.aws.clickhouse.cloud", alias="CLICKHOUSE_HOST")
    clickhouse_port: int = Field(default=9000, alias="CLICKHOUSE_PORT")  # Native protocol port
    clickhouse_http_port: int = Field(default=8123, alias="CLICKHOUSE_HTTP_PORT")  # HTTP port for clickhouse-connect
    clickhouse_database: str = Field(default="budeval", alias="CLICKHOUSE_DATABASE")
    clickhouse_user: str = Field(default="default", alias="CLICKHOUSE_USER")
    clickhouse_password: str = Field(default="N_8Bq67UGItUD", alias="CLICKHOUSE_PASSWORD")

    # ClickHouse Performance Settings
    clickhouse_batch_size: int = Field(default=1000, alias="CLICKHOUSE_BATCH_SIZE")
    clickhouse_pool_min_size: int = Field(default=1, alias="CLICKHOUSE_POOL_MIN_SIZE")
    clickhouse_pool_max_size: int = Field(default=10, alias="CLICKHOUSE_POOL_MAX_SIZE")
    clickhouse_async_insert: bool = Field(default=True, alias="CLICKHOUSE_ASYNC_INSERT")
    clickhouse_compression: str = Field(default="zstd", alias="CLICKHOUSE_COMPRESSION")
    clickhouse_secure: bool = Field(default=False, alias="CLICKHOUSE_SECURE")

    # Storage Backend Selection
    storage_backend: str = Field(default="clickhouse", alias="STORAGE_BACKEND")

    # OpenCompass Docker Image Configuration
    opencompass_docker_image: str = Field(
        default="docker.io/budstudio/opencompass:latest",
        alias="OPENCOMPASS_DOCKER_IMAGE",
    )

    # Budapp Service Configuration for Dapr Invocation
    bud_app_id: str = Field(default="budapp", alias="BUD_APP_ID")
    dapr_http_port: int = Field(default=3500, alias="DAPR_HTTP_PORT")


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # PostgreSQL Configuration
    psql_user: str = Field(alias="PSQL_USER")
    psql_password: str = Field(alias="PSQL_PASSWORD")
    psql_db_name: str = Field(alias="PSQL_DB_NAME")
    psql_port: int = Field(default=5432, alias="PSQL_PORT")
    psql_host: str = Field(alias="PSQL_HOST")

    # (ClickHouse settings moved to AppConfig)


app_settings = AppConfig()  # type: ignore[reportCallIssue]
secrets_settings = SecretsConfig()  # type: ignore[reportCallIssue]

register_settings(app_settings, secrets_settings)
