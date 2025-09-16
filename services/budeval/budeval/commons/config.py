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

from budmicroframe.commons.config import BaseAppConfig, BaseSecretsConfig, register_settings
from pydantic import Field

from budeval.__about__ import __version__


class AppConfig(BaseAppConfig):
    """Application configuration."""

    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = "BudEval - LLM Evaluation Platform"

    # Kubernetes
    namespace: str = Field(default="budeval", alias="NAMESPACE")

    # OpenCompass Configuration
    opencompass_image: str = Field(default="ghcr.io/rahulvramesh/opencompass:latest", alias="OPENCOMPASS_IMAGE")
    opencompass_dataset_path: str = Field(default="bud-dev-budeval-dataset", alias="OPENCOMPASS_DATASET_PATH")

    # ClickHouse Configuration
    clickhouse_host: str = Field(default="localhost", alias="CLICKHOUSE_HOST")
    clickhouse_port: int = Field(default=9000, alias="CLICKHOUSE_PORT")
    clickhouse_database: str = Field(default="budeval", alias="CLICKHOUSE_DATABASE")
    clickhouse_user: str = Field(default="default", alias="CLICKHOUSE_USER")
    clickhouse_password: str = Field(default="", alias="CLICKHOUSE_PASSWORD")
    clickhouse_secure: bool = Field(default=False, alias="CLICKHOUSE_SECURE")
    clickhouse_batch_size: int = Field(default=1000, alias="CLICKHOUSE_BATCH_SIZE")
    clickhouse_pool_min_size: int = Field(default=1, alias="CLICKHOUSE_POOL_MIN_SIZE")
    clickhouse_pool_max_size: int = Field(default=10, alias="CLICKHOUSE_POOL_MAX_SIZE")

    # Storage Backend (only ClickHouse now)
    storage_backend: str = Field(default="clickhouse", alias="STORAGE_BACKEND")

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent.resolve()
    extraction_base_path: Path = Field(default=Path("/tmp/eval_results"), alias="EXTRACTION_BASE_PATH")

    @property
    def ansible_playbooks_dir(self) -> Path:
        """Get the Ansible playbooks directory."""
        return self.base_dir / "budeval" / "ansible" / "playbooks"

    @classmethod
    def get_current_namespace(cls) -> str:
        """Get the current Kubernetes namespace."""
        # First try environment variable
        namespace = os.environ.get("NAMESPACE")
        if namespace:
            return namespace.lower()

        # Try reading from serviceaccount if running in cluster
        namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        try:
            with open(namespace_file, "r") as f:
                return f.read().strip().lower()
        except FileNotFoundError:
            pass

        # Default fallback
        return "budeval"


class SecretsConfig(BaseSecretsConfig):
    """Secrets configuration."""

    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # PostgreSQL (if still needed for some features)
    psql_user: str | None = Field(default="postgres", alias="PSQL_USER")
    psql_password: str | None = Field(default="", alias="PSQL_PASSWORD")
    psql_db_name: str | None = Field(default="budeval", alias="PSQL_DB_NAME")
    psql_port: int | None = Field(default=5432, alias="PSQL_PORT")
    psql_host: str | None = Field(default="localhost", alias="PSQL_HOST")


# Global configuration instances
app_settings = AppConfig()  # type: ignore[reportCallIssue]
secrets_settings = SecretsConfig()  # type: ignore[reportCallIssue]

# Register Config
register_settings(app_settings, secrets_settings)
