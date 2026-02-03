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
from typing import Annotated, Any, List, Optional

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    enable_periodic_sync_from_store,
    register_settings,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.types import (
    PrivateKeyTypes,
    PublicKeyTypes,
)
from dotenv import load_dotenv
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BeforeValidator,
    DirectoryPath,
    Field,
    computed_field,
)

from budapp.__about__ import __version__

from . import logging


load_dotenv()


def parse_cors(v: Any) -> List[str] | str:
    """Parse CORS_ORIGINS into a list of strings."""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class AppConfig(BaseAppConfig):
    """Manages configuration settings for the microservice.

    This class is used to define and access the configuration settings for the microservice. It supports syncing
    fields from a dapr config store and allows configuration via environment variables.

    Attributes:
        env (str): The environment in which the application is running (e.g., 'development', 'production').
        debug (Optional[bool]): Enable or disable debugging mode.
        Other mandatory fields as required by the application.

    Sync Details:
        Fields annotated with `json_schema_extra` will be synced from the config store. The sync behavior is controlled
        by `sync=True` and additional configurations can be made using `key_prefix` and `alias`.

    Usage:
        Configure the settings via environment variables or sync with a config store. Access settings as attributes of
        an instance of `AppConfig`.

    Example:
        ```python
        from budapp.commons.config import app_settings

        if app_settings.env == "dev":
            # Development-specific logic
            ...
        ```
    """

    # App Info
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent.parent.resolve())

    # Profiling
    profiler_enabled: bool = Field(False, alias="ENABLE_PROFILER")

    # Rate Limiting
    rate_limit_enabled: bool = Field(True, alias="RATE_LIMIT_ENABLED")

    # Superuser
    superuser_email: str = Field(alias="SUPER_USER_EMAIL")
    superuser_password: str = Field(alias="SUPER_USER_PASSWORD")

    # System user for internal service-to-service calls
    system_user_id: Optional[str] = Field(
        default=None,
        alias="SYSTEM_USER_ID",
        description="UUID of system user for internal service calls (optional, uses superuser if not set)",
    )

    # default non master realm name
    default_realm_name: str = Field(alias="DEFAULT_REALM_NAME", default="bud")

    # default client name for bud-stack in shared realm
    default_client_name: str = Field(alias="DEFAULT_CLIENT_NAME", default="default-internal-client")

    # Token
    access_token_expire_minutes: int = Field(30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(60 * 24 * 7, alias="REFRESH_TOKEN_EXPIRE_MINUTES")

    # Static
    static_dir_path: DirectoryPath | None = Field(None, alias="STATIC_DIR")

    # CORS
    cors_origins: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []

    # Bud microservice
    dapr_base_url: AnyHttpUrl = Field(alias="DAPR_BASE_URL")
    bud_cluster_app_id: str = Field(alias="BUD_CLUSTER_APP_ID")
    bud_model_app_id: str = Field(alias="BUD_MODEL_APP_ID")
    bud_simulator_app_id: str = Field(alias="BUD_SIMULATOR_APP_ID")
    bud_metrics_app_id: str = Field(alias="BUD_METRICS_APP_ID")
    bud_notify_app_id: str = Field(alias="BUD_NOTIFY_APP_ID")
    bud_doc_service_url: str = Field(
        default="http://buddoc:9081",
        description="BudDoc service URL for document processing",
        alias="BUD_DOC_SERVICE_URL",
    )
    bud_doc_api_key_location: str = Field(
        default="dynamic::authorization",
        description="API key location for BudDoc provider (e.g., 'dynamic::authorization', 'env::BUDDOC_API_KEY', 'none')",
        alias="BUD_DOC_API_KEY_LOCATION",
    )
    bud_prompt_service_url: str = Field(
        description="BudPrompt service URL for prompt execution",
        alias="BUD_PROMPT_SERVICE_URL",
    )
    bud_eval_app_id: str = Field(alias="BUD_EVAL_APP_ID", default="budeval")
    bud_prompt_app_id: str = Field(alias="BUD_PROMPT_APP_ID")
    bud_pipeline_app_id: str = Field(alias="BUD_PIPELINE_APP_ID", default="budpipeline")
    source_topic: str = Field(alias="SOURCE_TOPIC", default="budAppMessages")

    # Prometheus URL
    prometheus_url: str = Field(alias="PROMETHEUS_URL", default="https://metrics.fmops.in")

    # Metrics backend configuration
    use_budmetrics_backend: bool = Field(alias="USE_BUDMETRICS_BACKEND", default=False)
    budmetrics_app_id: str = Field(alias="BUDMETRICS_APP_ID", default="budmetrics")

    # Add model directory
    add_model_dir: DirectoryPath = Field(os.path.expanduser("~/.cache"), alias="ADD_MODEL_DIR")

    # Bud Proxy
    cache_embedding_model: Optional[str] = Field(alias="CACHE_EMBEDDING_MODEL", default=None)
    cache_eviction_policy: str = Field(alias="CACHE_EVICTION_POLICY", default="LRU")
    cache_max_size: int = Field(alias="CACHE_MAX_SIZE", default=1000)
    cache_ttl: Optional[int] = Field(alias="CACHE_TTL", default=None)
    cache_score_threshold: float = Field(alias="CACHE_SCORE_THRESHOLD", default=0.1)
    prompt_config_redis_ttl: int = Field(alias="PROMPT_CONFIG_REDIS_TTL", default=86400)
    litellm_proxy_master_key: str = Field(alias="LITELLM_PROXY_MASTER_KEY", default="sk-1234")

    # Frontend URL
    frontend_url: AnyUrl = Field(alias="FRONTEND_URL", default="http://localhost:3000")
    admin_frontend_url: AnyUrl = Field(alias="ADMIN_FRONTEND_URL", default="http://localhost:3002")

    # OAuth Settings
    use_http_only_oauth: bool = Field(False, alias="USE_HTTP_ONLY_OAUTH")

    # Keycloak
    keycloak_server_url: str = Field(alias="KEYCLOAK_SERVER_URL")
    keycloak_admin_username: str = Field(alias="KEYCLOAK_ADMIN_USERNAME")
    keycloak_admin_password: str = Field(alias="KEYCLOAK_ADMIN_PASSWORD")
    keycloak_realm_name: str = Field(alias="KEYCLOAK_REALM_NAME")
    keycloak_verify_ssl: bool = Field(True, alias="KEYCLOAK_VERIFY_SSL")
    # Keycloak Token Settings (in seconds)
    keycloak_access_token_lifespan: int = Field(1800, alias="KEYCLOAK_ACCESS_TOKEN_LIFESPAN")  # 30 minutes
    keycloak_sso_session_idle_timeout: int = Field(86400, alias="KEYCLOAK_SSO_SESSION_IDLE_TIMEOUT")  # 24 hours
    keycloak_sso_session_max_lifespan: int = Field(86400, alias="KEYCLOAK_SSO_SESSION_MAX_LIFESPAN")  # 24 hours
    keycloak_offline_session_idle_timeout: int = Field(
        2592000, alias="KEYCLOAK_OFFLINE_SESSION_IDLE_TIMEOUT"
    )  # 30 days
    keycloak_offline_session_max_lifespan: int = Field(
        2592000, alias="KEYCLOAK_OFFLINE_SESSION_MAX_LIFESPAN"
    )  # 30 days
    # Minio store
    minio_endpoint: str = Field("bud-store.bud.studio", alias="MINIO_ENDPOINT")
    minio_secure: bool = Field(True, alias="MINIO_SECURE")
    # Stores actual model files (weights, configs, tokenizers)
    minio_bucket: str = Field("models-registry", alias="MINIO_BUCKET")
    # Stores model metadata and license files only (NOT model files)
    minio_model_bucket: str = Field("model-info", alias="MINIO_MODEL_BUCKET")

    # model download directory
    model_download_dir: str = Field("model_registry", alias="MODEL_DOWNLOAD_DIR")

    # Grafana
    grafana_scheme: str = Field(alias="GRAFANA_SCHEME")
    grafana_url: str = Field(alias="GRAFANA_URL")
    grafana_username: str = Field(alias="GRAFANA_USERNAME")
    grafana_password: str = Field(alias="GRAFANA_PASSWORD")

    # Bud Connect
    cloud_model_seeder_engine: str = Field(alias="CLOUD_MODEL_SEEDER_ENGINE")
    bud_connect_base_url: AnyHttpUrl = Field(alias="BUD_CONNECT_BASE_URL")

    # Evaluation Data Sync
    eval_manifest_url: str = Field(
        default="https://eval-datasets.bud.eco/v2/manifest.json",
        description="URL to the evaluation datasets manifest file",
        alias="EVAL_MANIFEST_URL",
    )
    eval_sync_enabled: bool = Field(
        default=True, description="Enable automatic evaluation data synchronization", alias="EVAL_SYNC_ENABLED"
    )
    eval_sync_use_bundles: bool = Field(
        default=True,
        description="Use bundle downloads when available for evaluation datasets",
        alias="EVAL_SYNC_USE_BUNDLES",
    )
    eval_sync_local_mode: bool = Field(
        default=False, description="Use local mode for evaluation data synchronization", alias="EVAL_SYNC_LOCAL_MODE"
    )

    # Bud Sentinel
    bud_sentinel_base_url: Optional[str] = Field(default=None, alias="BUD_SENTINEL_BASE_URL")
    # MCP Foundry
    mcp_foundry_base_url: AnyHttpUrl = Field(alias="MCP_FOUNDRY_BASE_URL")
    mcp_foundry_api_key: str = Field(alias="MCP_FOUNDRY_API_KEY")

    @computed_field
    def static_dir(self) -> str:
        """Get the static directory."""
        if self.static_dir_path is None:
            return os.path.join(str(self.base_dir), "static")

        return self.static_dir_path

    @computed_field
    def icon_dir(self) -> DirectoryPath:
        """Directory for icon."""
        return os.path.join(self.static_dir, "icons")


# class SecretsConfig(BaseSecretsConfig):
class SecretsConfig(BaseSecretsConfig):
    """Manages secret configurations for the microservice.

    This class handles the configuration of secrets required by the microservice. It supports secret management via
    a Dapr secret store.

    Attributes:
        dapr_api_token (str): The API token required for Dapr interactions (mandatory field).
        Other placeholder fields for secrets which can be removed or customized as needed.

    Configuration:
        Secrets should be defined in a `.env` file located in the project root. Use the prefix `SECRETS_` for syncing them with the secret store.
        For example:

        ```
        DAPR_API_TOKEN = your_api_token_here  # Won't be synced to the secret store
        SECRETS_OPENAI_TOKEN = your_api_token_here  # Will be synced to the secret store
        ```

    Sync Details:
        Similar to `AppConfig`, fields can be synced from the secret store using the `json_schema` settings.

    Usage:
        Configure secrets in `.env` for development. Ensure that the `.env` file is not included in the repository.

    Example:
        ```python
        from budapp.commons.config import secrets_settings

        api_token = secrets_settings.dapr_api_token
        ```
    """

    # App Info
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    dapr_api_token: Optional[str] = Field(None, alias="DAPR_API_TOKEN")

    password_salt: str = Field("bud_password_salt", alias="PASSWORD_SALT")
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    redis_uri: Optional[str] = Field(
        None, alias="TENSORZERO_REDIS_URL", json_schema_extra=enable_periodic_sync_from_store(is_global=True)
    )
    hf_token: Optional[str] = Field(
        None, alias="HF_TOKEN", json_schema_extra=enable_periodic_sync_from_store(is_global=True)
    )

    base_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent.parent.resolve())
    vault_path: DirectoryPath = base_dir

    # Encryption
    private_key_password: str = "bud_encryption_password"
    private_key_path: str = Field(alias="PRIVATE_KEY_PATH", default="private_key.pem")
    public_key_path: str = Field(alias="PUBLIC_KEY_PATH", default="public_key.pem")
    aes_key_hex: str = ""

    # Minio store
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

    @computed_field
    def redis_url(self) -> str:
        """Construct and returns a Redis connection URL."""
        return self.redis_uri

    @property
    def public_key(self) -> PublicKeyTypes:
        """Return Public key loaded from the PEM file."""
        try:
            # Use absolute path if provided, otherwise relative to vault_path
            if os.path.isabs(self.public_key_path):
                public_key_file = Path(self.public_key_path)
            else:
                public_key_file = Path(os.path.join(self.vault_path, self.public_key_path))

            # Read the public key from PEM file
            public_pem_bytes = public_key_file.read_bytes()

            # Load the public key
            public_key_from_pem = serialization.load_pem_public_key(public_pem_bytes)

            return public_key_from_pem
        except (ValueError, UnboundLocalError, FileNotFoundError):
            raise RuntimeError("Could not load public key") from None

    @property
    def private_key(self) -> PrivateKeyTypes:
        """Return Private key loaded from the PEM file."""
        try:
            # Use absolute path if provided, otherwise relative to vault_path
            if os.path.isabs(self.private_key_path):
                private_key_file = Path(self.private_key_path)
            else:
                private_key_file = Path(os.path.join(self.vault_path, self.private_key_path))

            # Read the private key from PEM file
            private_pem_bytes = private_key_file.read_bytes()

            # Load the private key
            private_key_from_pem = serialization.load_pem_private_key(
                private_pem_bytes, password=self.private_key_password.encode("utf-8")
            )

            return private_key_from_pem
        except (ValueError, UnboundLocalError, FileNotFoundError):
            raise RuntimeError("Could not load private key") from None

    @property
    def aes_key(self) -> bytes:
        """Return AES key loaded from the HEX format."""
        if not self.aes_key_hex:
            raise RuntimeError("AES key is not set")

        return bytes.fromhex(self.aes_key_hex)


app_settings = AppConfig()
secrets_settings = SecretsConfig()

logging.configure_logging(app_settings.log_dir, app_settings.log_level)

register_settings(app_settings, secrets_settings)
