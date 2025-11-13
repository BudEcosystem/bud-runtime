from pathlib import Path
from typing import Optional

from budmicroframe.commons.config import (
    BaseAppConfig,
    BaseSecretsConfig,
    enable_periodic_sync_from_store,
    register_settings,
)
from dotenv import load_dotenv
from pydantic import AnyHttpUrl, DirectoryPath, Field

from budcluster.__about__ import __version__


load_dotenv()


class AppConfig(BaseAppConfig):
    # App Info
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Crypto
    crypto_name: Optional[str] = None
    rsa_key_name: Optional[str] = Field(None, json_schema_extra=enable_periodic_sync_from_store())
    aes_symmetric_key_name: Optional[str] = Field(None, json_schema_extra=enable_periodic_sync_from_store())

    # Base Directory
    base_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent.parent.resolve())

    # Cluster
    validate_certs: bool = Field(True, alias="VALIDATE_CERTS")
    # Node-info-collector removed - NFD is now the only method for hardware detection
    quantization_job_image: Optional[str] = Field(None, alias="QUANTIZATION_JOB_IMAGE")
    engine_container_port: int = Field(..., alias="ENGINE_CONTAINER_PORT")

    # NFD Configuration (Node Feature Discovery - required for hardware detection)
    enable_nfd_detection: bool = Field(True, alias="ENABLE_NFD_DETECTION")
    # nfd_fallback_to_configmap deprecated - NFD is now the only method
    nfd_detection_timeout: int = Field(30, alias="NFD_DETECTION_TIMEOUT")
    nfd_namespace: str = Field("node-feature-discovery", alias="NFD_NAMESPACE")

    # Endpoint validation configuration
    max_endpoint_retry_attempts: int = Field(15, alias="MAX_ENDPOINT_RETRY_ATTEMPTS")
    endpoint_retry_interval: int = Field(20, alias="ENDPOINT_RETRY_INTERVAL")

    # Microservice
    notify_service_name: str = Field("notify", alias="NOTIFY_SERVICE_NAME")
    notify_service_topic: Optional[str] = Field(None, alias="NOTIFY_SERVICE_TOPIC")
    dapr_base_url: AnyHttpUrl = Field(alias="DAPR_BASE_URL")

    # Litellm
    litellm_proxy_server_image: str = Field(..., alias="LITELLM_PROXY_SERVER_IMAGE")
    litellm_server_port: int = Field(4000, alias="LITELLM_SERVER_PORT")

    # Tensorzero
    tensorzero_image: str = Field("budstudio/budproxy:nightly", alias="TENSORZERO_IMAGE")

    # Model registry volume
    volume_type: str = Field("local", alias="VOLUME_TYPE")
    model_registry_path: str = Field("/data/models-registry/", alias="MODEL_REGISTRY_PATH")

    # minio
    minio_endpoint: str = Field("bud-store.bud.studio", alias="MINIO_ENDPOINT")
    minio_secure: bool = Field(True, alias="MINIO_SECURE")
    minio_bucket: str = Field("models-registry", alias="MINIO_BUCKET")

    # Prometheus Primary Cluster Write URL
    prometheus_url: str = Field(..., alias="PROMETHEUS_URL")

    # Metrics Collection Configuration
    metrics_collection_enabled: bool = Field(True, alias="METRICS_COLLECTION_ENABLED")
    metrics_collection_timeout: int = Field(30, alias="METRICS_COLLECTION_TIMEOUT")
    metrics_batch_size: int = Field(20000, alias="METRICS_BATCH_SIZE")

    # OpenTelemetry Collector Configuration
    otel_collector_endpoint: Optional[str] = Field("http://localhost:4318", alias="OTEL_COLLECTOR_ENDPOINT")
    otel_config_path: Optional[str] = Field("/etc/otel/config.yaml", alias="OTEL_CONFIG_PATH")

    # Prometheus configuration
    prometheus_service_name: str = Field("bud-metrics-kube-prometheu-prometheus", alias="PROMETHEUS_SERVICE_NAME")
    prometheus_namespace: str = Field("bud-system", alias="PROMETHEUS_NAMESPACE")
    prometheus_port: int = Field(9090, alias="PROMETHEUS_PORT")

    # Bud Services
    bud_app_id: str = Field("budapp", alias="BUD_APP_ID")


class SecretsConfig(BaseSecretsConfig):
    # App Info
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    litellm_master_key: Optional[str] = Field(
        None,
        alias="LITELLM_PROXY_MASTER_KEY",
        json_schema_extra=enable_periodic_sync_from_store(is_global=True),
    )
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


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
