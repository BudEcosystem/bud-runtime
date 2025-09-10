from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from budeval.commons.storage_config import StorageConfig


class Job(BaseModel):
    # General info
    uuid: str
    runner_type: Literal["kubernetes", "docker"] = Field(..., description="Which runner type to use")
    namespace: str = Field(default_factory=StorageConfig.get_current_namespace)

    # Engine config
    docker_image: str = Field(..., description="Docker image used to run the engine")
    engine_args: Dict[str, Any] = Field(..., description="Args passed to the engine as JSON")

    # Kubernetes-specific config
    kubeconfig: Optional[str] = Field(None, description="Base64 or raw kubeconfig for Kubernetes jobs")
    ttl_seconds_after_finish: int = Field(default=600)

    # TODO: Add Docker-specific fields here if needed

    class Config:
        """Pydantic configuration with example schema."""

        schema_extra = {
            "example": {
                "uuid": "run-123",
                "runner_type": "kubernetes",
                "namespace": "budeval",
                "docker_image": "ghcr.io/open-compass/opencompass:0.4.2",
                "engine_args": {"model_path": "meta-llama/Llama-3.2-3B-Instruct", "datasets": ["gsm8k"]},
                "kubeconfig": "apiVersion: v1\nclusters:\n  - cluster:...",
                "ttl_seconds_after_finish": 600,
            }
        }
