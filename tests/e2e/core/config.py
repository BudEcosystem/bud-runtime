"""
E2E test configuration management.

Provides configurable timeouts and settings for different workflow types.
All values can be overridden via environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimeoutConfig:
    """Timeout configuration for different workflow types."""

    # General API timeouts (seconds)
    api_request: int = 30
    api_long_request: int = 120

    # Authentication timeouts
    auth_login: int = 30
    auth_token_refresh: int = 30

    # Model workflow timeouts
    model_cloud_workflow: int = 120
    model_local_workflow: int = 600  # Local model extraction can be slow
    model_download: int = 1800  # 30 minutes for large model downloads

    # Cluster workflow timeouts
    cluster_provision: int = 1800  # 30 minutes for cluster provisioning
    cluster_configure: int = 600  # 10 minutes for cluster configuration
    cluster_delete: int = 600  # 10 minutes for cluster deletion

    # Deployment timeouts
    deployment_create: int = 600  # 10 minutes for deployment
    deployment_scale: int = 300  # 5 minutes for scaling
    deployment_delete: int = 300

    # Simulation timeouts
    simulation_run: int = 300  # 5 minutes for simulation

    # Polling configuration
    poll_interval: int = 5  # Default polling interval
    poll_interval_fast: int = 2  # Fast polling for quick operations
    poll_interval_slow: int = 15  # Slow polling for long operations

    @classmethod
    def from_env(cls) -> "TimeoutConfig":
        """Create config from environment variables."""
        config = cls()

        # Override with environment variables if present
        env_mappings = {
            "E2E_TIMEOUT_API_REQUEST": "api_request",
            "E2E_TIMEOUT_API_LONG_REQUEST": "api_long_request",
            "E2E_TIMEOUT_AUTH_LOGIN": "auth_login",
            "E2E_TIMEOUT_MODEL_CLOUD": "model_cloud_workflow",
            "E2E_TIMEOUT_MODEL_LOCAL": "model_local_workflow",
            "E2E_TIMEOUT_MODEL_DOWNLOAD": "model_download",
            "E2E_TIMEOUT_CLUSTER_PROVISION": "cluster_provision",
            "E2E_TIMEOUT_CLUSTER_CONFIGURE": "cluster_configure",
            "E2E_TIMEOUT_DEPLOYMENT_CREATE": "deployment_create",
            "E2E_TIMEOUT_SIMULATION_RUN": "simulation_run",
            "E2E_POLL_INTERVAL": "poll_interval",
            "E2E_POLL_INTERVAL_FAST": "poll_interval_fast",
            "E2E_POLL_INTERVAL_SLOW": "poll_interval_slow",
        }

        for env_var, attr in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                try:
                    setattr(config, attr, int(value))
                except ValueError:
                    pass  # Keep default if invalid

        return config


@dataclass
class E2EConfig:
    """Main E2E test configuration."""

    # Service URLs
    budapp_url: str = "http://localhost:9081"
    budadmin_url: str = "http://localhost:8007"
    keycloak_url: str = "http://localhost:8080"

    # Database configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "budapp"
    postgres_password: str = "budapp-password"
    postgres_db: str = "budapp"

    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: str = "redis://localhost:6379/2"

    # Test credentials
    test_user_email: str = "test@example.com"
    test_user_password: str = "TestP@ssw0rd123!"
    admin_user_email: str = "admin@bud.studio"
    admin_user_password: str = "admin-password"

    # Test model configuration
    test_model_id: str = "meta-llama/Llama-2-7b-chat-hf"
    test_model_provider: str = "huggingface"

    # Test session configuration
    test_session_id: Optional[str] = None
    test_project_prefix: str = "e2e-test"

    # Feature flags
    debug: bool = False
    cleanup_on_failure: bool = True
    skip_slow_tests: bool = False

    # Timeouts
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)

    @classmethod
    def from_env(cls) -> "E2EConfig":
        """Create config from environment variables."""
        config = cls(
            budapp_url=os.getenv("E2E_BUDAPP_URL", "http://localhost:9081"),
            budadmin_url=os.getenv("E2E_BUDADMIN_URL", "http://localhost:8007"),
            keycloak_url=os.getenv("E2E_KEYCLOAK_URL", "http://localhost:8080"),
            postgres_host=os.getenv("E2E_POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("E2E_POSTGRES_PORT", "5432")),
            postgres_user=os.getenv("E2E_POSTGRES_USER", "budapp"),
            postgres_password=os.getenv("E2E_POSTGRES_PASSWORD", "budapp-password"),
            postgres_db=os.getenv("E2E_POSTGRES_DB", "budapp"),
            redis_host=os.getenv("E2E_REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("E2E_REDIS_PORT", "6379")),
            redis_url=os.getenv("E2E_REDIS_URL", "redis://localhost:6379/2"),
            test_user_email=os.getenv("E2E_TEST_USER_EMAIL", "test@example.com"),
            test_user_password=os.getenv("E2E_TEST_USER_PASSWORD", "TestP@ssw0rd123!"),
            admin_user_email=os.getenv("E2E_ADMIN_USER_EMAIL", "admin@bud.studio"),
            admin_user_password=os.getenv("E2E_ADMIN_USER_PASSWORD", "admin-password"),
            test_model_id=os.getenv(
                "E2E_TEST_MODEL_ID", "meta-llama/Llama-2-7b-chat-hf"
            ),
            test_model_provider=os.getenv("E2E_TEST_MODEL_PROVIDER", "huggingface"),
            test_session_id=os.getenv("E2E_TEST_SESSION_ID"),
            test_project_prefix=os.getenv("E2E_TEST_PROJECT_PREFIX", "e2e-test"),
            debug=os.getenv("E2E_DEBUG", "false").lower() in ("true", "1", "yes"),
            cleanup_on_failure=os.getenv("E2E_CLEANUP_ON_FAILURE", "true").lower()
            in ("true", "1", "yes"),
            skip_slow_tests=os.getenv("E2E_SKIP_SLOW_TESTS", "false").lower()
            in ("true", "1", "yes"),
            timeouts=TimeoutConfig.from_env(),
        )

        return config


# Global config instance (lazy loaded)
_config: Optional[E2EConfig] = None


def get_config() -> E2EConfig:
    """Get the global E2E configuration."""
    global _config
    if _config is None:
        _config = E2EConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global config (useful for testing)."""
    global _config
    _config = None
