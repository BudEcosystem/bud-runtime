"""Configuration settings for budpipeline service.

Uses budmicroframe's BaseAppConfig and BaseSecretsConfig for consistent
configuration patterns across bud-stack services.
"""

from pathlib import Path

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    register_settings,
)
from dotenv import load_dotenv
from pydantic import AnyHttpUrl, DirectoryPath, Field

from budpipeline.__about__ import __version__

load_dotenv()


class AppConfig(BaseAppConfig):
    """Application configuration for budpipeline service.

    Inherits PostgreSQL connection settings from BaseAppConfig:
    - psql_host, psql_port, psql_dbname
    - psql_pool_size, psql_max_overflow, psql_pool_timeout, etc.
    """

    # App Info
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = "Pipeline orchestration service for Bud Runtime"
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.resolve()
    )

    # PostgreSQL overrides with defaults for local development
    # These are inherited from BaseAppConfig but we provide defaults
    psql_host: str = Field(default="localhost", alias="PSQL_HOST")
    psql_port: int = Field(default=5432, alias="PSQL_PORT")
    psql_dbname: str = Field(default="budpipeline", alias="PSQL_DB_NAME")

    # Dapr
    dapr_base_url: AnyHttpUrl = Field(default="http://localhost:3500", alias="DAPR_BASE_URL")

    # State Store
    state_store_name: str = Field(default="statestore", alias="STATE_STORE_NAME")

    # Pub/Sub
    pubsub_name: str = Field(default="pubsub", alias="PUBSUB_NAME")

    # Service Discovery (Dapr App IDs)
    budapp_app_id: str = Field(default="budapp", alias="BUDAPP_APP_ID")
    budcluster_app_id: str = Field(default="budcluster", alias="BUDCLUSTER_APP_ID")
    budmodel_app_id: str = Field(default="budmodel", alias="BUDMODEL_APP_ID")
    budsim_app_id: str = Field(default="budsim", alias="BUDSIM_APP_ID")
    budnotify_app_id: str = Field(default="budnotify", alias="BUDNOTIFY_APP_ID")
    budmetrics_app_id: str = Field(default="budmetrics", alias="BUDMETRICS_APP_ID")

    # Workflow Settings
    workflow_default_timeout: int = Field(
        default=7200,
        alias="WORKFLOW_DEFAULT_TIMEOUT",
        description="Default workflow timeout in seconds",
    )
    workflow_max_parallel_steps: int = Field(
        default=10,
        alias="WORKFLOW_MAX_PARALLEL_STEPS",
        description="Maximum parallel steps in a workflow",
    )
    step_default_timeout: int = Field(
        default=300, alias="STEP_DEFAULT_TIMEOUT", description="Default step timeout in seconds"
    )

    # Retry Settings
    retry_max_attempts: int = Field(
        default=3, alias="RETRY_MAX_ATTEMPTS", description="Default max retry attempts"
    )
    retry_backoff_seconds: int = Field(
        default=60, alias="RETRY_BACKOFF_SECONDS", description="Default retry backoff in seconds"
    )
    retry_backoff_multiplier: float = Field(
        default=2.0, alias="RETRY_BACKOFF_MULTIPLIER", description="Retry backoff multiplier"
    )
    retry_max_backoff_seconds: int = Field(
        default=3600,
        alias="RETRY_MAX_BACKOFF_SECONDS",
        description="Maximum retry backoff in seconds",
    )

    # Scheduler Settings
    scheduler_poll_interval: int = Field(
        default=60,
        alias="SCHEDULER_POLL_INTERVAL",
        description="Scheduler poll interval in seconds",
    )
    scheduler_max_concurrent_jobs: int = Field(
        default=100,
        alias="SCHEDULER_MAX_CONCURRENT_JOBS",
        description="Maximum concurrent scheduled jobs",
    )

    # K8s Job Settings
    k8s_job_default_namespace: str = Field(
        default="bud-jobs",
        alias="K8S_JOB_DEFAULT_NAMESPACE",
        description="Default namespace for K8s jobs",
    )
    k8s_job_ttl_after_finished: int = Field(
        default=86400,
        alias="K8S_JOB_TTL_AFTER_FINISHED",
        description="TTL for completed K8s jobs in seconds",
    )

    # System User
    system_user_id: str | None = Field(
        default=None,
        alias="SYSTEM_USER_ID",
        description="System user ID for internal workflow operations",
    )

    # Monitoring
    metrics_enabled: bool = Field(
        default=True, alias="METRICS_ENABLED", description="Enable metrics collection"
    )
    log_streaming_enabled: bool = Field(
        default=True, alias="LOG_STREAMING_ENABLED", description="Enable log streaming"
    )

    # Pipeline Persistence & Retention (002-pipeline-event-persistence)
    pipeline_retention_days: int = Field(
        default=30,
        alias="PIPELINE_RETENTION_DAYS",
        description="Number of days to retain pipeline execution history (FR-005, FR-049)",
    )
    pipeline_cleanup_schedule: str = Field(
        default="0 3 * * *",
        alias="PIPELINE_CLEANUP_SCHEDULE",
        description="Cron schedule for retention cleanup job (FR-050, default: 3 AM daily)",
    )

    # Resilience Settings (002-pipeline-event-persistence)
    db_retry_max_attempts: int = Field(
        default=3,
        alias="DB_RETRY_MAX_ATTEMPTS",
        description="Maximum retry attempts for database operations (FR-043)",
    )
    db_retry_exponential_base: float = Field(
        default=2.0,
        alias="DB_RETRY_EXPONENTIAL_BASE",
        description="Exponential backoff base for database retries",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        description="Number of failures before circuit breaker opens",
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=30,
        alias="CIRCUIT_BREAKER_RECOVERY_TIMEOUT",
        description="Seconds to wait before attempting recovery",
    )

    # Event-Driven Completion Settings (event-driven-completion architecture)
    default_async_step_timeout: int = Field(
        default=1800,
        alias="DEFAULT_ASYNC_STEP_TIMEOUT",
        description="Default timeout in seconds for async steps waiting for events (30 minutes)",
    )
    step_timeout_check_interval: int = Field(
        default=60,
        alias="STEP_TIMEOUT_CHECK_INTERVAL",
        description="Interval in seconds for checking timed-out steps",
    )

    @property
    def dapr_http_endpoint(self) -> str:
        """Get Dapr HTTP endpoint."""
        return str(self.dapr_base_url)

    @property
    def database_url(self) -> str:
        """Get async PostgreSQL database URL for Alembic migrations.

        Constructs the URL from individual config components.
        Uses asyncpg driver for async support.
        """
        # Import here to avoid circular imports
        from budpipeline.commons.config import secrets_settings

        return (
            f"postgresql+asyncpg://{secrets_settings.psql_user}:{secrets_settings.psql_password}"
            f"@{self.psql_host}:{self.psql_port}/{self.psql_dbname}"
        )

    def get_service_app_id(self, service_name: str) -> str:
        """Get Dapr app ID for a service."""
        app_id_map = {
            "budapp": self.budapp_app_id,
            "budcluster": self.budcluster_app_id,
            "budmodel": self.budmodel_app_id,
            "budsim": self.budsim_app_id,
            "budnotify": self.budnotify_app_id,
            "budmetrics": self.budmetrics_app_id,
        }
        return app_id_map.get(service_name, service_name)


class SecretsConfig(BaseSecretsConfig):
    """Secrets configuration for budpipeline service.

    Inherits PostgreSQL credentials from BaseSecretsConfig:
    - psql_user, psql_password
    """

    # App Info
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # Dapr API Token
    dapr_api_token: str | None = Field(None, alias="DAPR_API_TOKEN")

    # App API Token for internal auth
    app_api_token: str | None = Field(None, alias="APP_API_TOKEN")


# Global settings instances
app_settings = AppConfig()
secrets_settings = SecretsConfig()

# Register settings for Dapr config store sync
register_settings(app_settings, secrets_settings)

# Backward compatibility alias
settings = app_settings
