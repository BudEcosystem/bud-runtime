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
from pydantic import DirectoryPath

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    # Dataset Configuration
    opencompass_dataset_url: str = (
        "https://github.com/open-compass/opencompass/releases/download/0.2.2.rc1/OpenCompassData-complete-20240207.zip"
    )

    # Eval Sync Configuration
    eval_sync_enabled: bool = True
    eval_sync_local_mode: bool = True  # Default to cloud mode like budapp
    eval_manifest_url: str = "https://eval-datasets.bud.eco/v2/eval_manifest.json"
    eval_sync_batch_size: int = 50  # Number of datasets to process per batch
    eval_manifest_local_path: str = "budeval/data/eval_manifest_test.json"
    eval_sync_interval_seconds: int = 3600  # Sync interval in seconds (default 1 hour like budapp)


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # ClickHouse Configuration
    clickhouse_host: str = "okb80nfy88.ap-southeast-1.aws.clickhouse.cloud"
    clickhouse_port: int = 9440  # Secure native TCP port for ClickHouse Cloud
    clickhouse_database: str = "budeval"
    clickhouse_user: str = "default"
    clickhouse_password: str = "N_8Bq67UGItUD"

    # ClickHouse Performance Settings
    clickhouse_batch_size: int = 1000
    clickhouse_pool_min_size: int = 1
    clickhouse_pool_max_size: int = 10
    clickhouse_async_insert: bool = True
    clickhouse_compression: str = "zstd"
    clickhouse_secure: bool = True  # Use SSL for ClickHouse Cloud

    # Storage Backend Selection
    storage_backend: str = "clickhouse"  # "filesystem" or "clickhouse"


app_settings = AppConfig()  # type: ignore[reportCallIssue]
secrets_settings = SecretsConfig()  # type: ignore[reportCallIssue]

register_settings(app_settings, secrets_settings)
