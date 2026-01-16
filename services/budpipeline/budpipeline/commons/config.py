"""Configuration settings for budpipeline service."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service
    service_name: str = Field(default="budpipeline", description="Service name")
    service_port: int = Field(default=8010, description="Service port")
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Debug mode")

    # Dapr
    dapr_http_port: int = Field(default=3510, description="Dapr HTTP port")
    dapr_grpc_port: int = Field(default=50010, description="Dapr gRPC port")
    dapr_api_token: str | None = Field(default=None, description="Dapr API token")
    app_api_token: str | None = Field(default=None, description="App API token for internal auth")

    # State Store
    state_store_name: str = Field(default="statestore", description="Dapr state store name")

    # Pub/Sub
    pubsub_name: str = Field(default="pubsub", description="Dapr pub/sub name")

    # Service Discovery (Dapr App IDs)
    budapp_app_id: str = Field(default="budapp", description="budapp Dapr app ID")
    budcluster_app_id: str = Field(default="budcluster", description="budcluster Dapr app ID")
    budmodel_app_id: str = Field(default="budmodel", description="budmodel Dapr app ID")
    budsim_app_id: str = Field(default="budsim", description="budsim Dapr app ID")
    budnotify_app_id: str = Field(default="budnotify", description="budnotify Dapr app ID")
    budmetrics_app_id: str = Field(default="budmetrics", description="budmetrics Dapr app ID")

    # Workflow Settings
    workflow_default_timeout: int = Field(
        default=7200, description="Default workflow timeout in seconds"
    )
    workflow_max_parallel_steps: int = Field(
        default=10, description="Maximum parallel steps in a workflow"
    )
    step_default_timeout: int = Field(default=300, description="Default step timeout in seconds")

    # Retry Settings
    retry_max_attempts: int = Field(default=3, description="Default max retry attempts")
    retry_backoff_seconds: int = Field(default=60, description="Default retry backoff in seconds")
    retry_backoff_multiplier: float = Field(default=2.0, description="Retry backoff multiplier")
    retry_max_backoff_seconds: int = Field(
        default=3600, description="Maximum retry backoff in seconds"
    )

    # Scheduler Settings
    scheduler_poll_interval: int = Field(
        default=60, description="Scheduler poll interval in seconds"
    )
    scheduler_max_concurrent_jobs: int = Field(
        default=100, description="Maximum concurrent scheduled jobs"
    )

    # K8s Job Settings
    k8s_job_default_namespace: str = Field(
        default="bud-jobs", description="Default namespace for K8s jobs"
    )
    k8s_job_ttl_after_finished: int = Field(
        default=86400, description="TTL for completed K8s jobs in seconds"
    )

    # System User
    system_user_id: str | None = Field(
        default=None,
        description="System user ID for internal workflow operations",
    )

    # Monitoring
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    log_streaming_enabled: bool = Field(default=True, description="Enable log streaming")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v

    @property
    def dapr_http_endpoint(self) -> str:
        """Get Dapr HTTP endpoint."""
        return f"http://localhost:{self.dapr_http_port}"

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
