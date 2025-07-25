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
    node_info_collector_image_cpu: str = Field(..., alias="NODE_INFO_COLLECTOR_IMAGE_CPU")
    node_info_collector_image_cuda: str = Field(..., alias="NODE_INFO_COLLECTOR_IMAGE_CUDA")
    node_info_collector_image_hpu: str = Field(..., alias="NODE_INFO_COLLECTOR_IMAGE_HPU")
    node_info_labeler_image: str = Field(..., alias="NODE_INFO_LABELER_IMAGE")
    quantization_job_image: Optional[str] = Field(None, alias="QUANTIZATION_JOB_IMAGE")
    engine_container_port: int = Field(..., alias="ENGINE_CONTAINER_PORT")

    registry_server: str = Field(..., alias="REGISTRY_SERVER")
    registry_username: str = Field(..., alias="REGISTRY_USERNAME")
    registry_password: str = Field(..., alias="REGISTRY_PASSWORD")

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
