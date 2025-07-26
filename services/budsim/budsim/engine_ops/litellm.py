from typing import Any, Dict, Optional

from pydantic import Field

from ..commons.config import app_settings
from .base import BaseEngineArgs, BaseEngineCompatibility


class EngineArgs(BaseEngineArgs):
    num_cpus: int = Field(
        description="The number of CPUs.",
        alias="env_NUM_CPUS",
        default=1,
    )

    @staticmethod
    def get_max_concurrency() -> int:
        """Determine the maximum concurrency the engine can handle without degrading performance."""
        return 100


class EngineCompatibility(BaseEngineCompatibility):
    """Implements engine compatibility checks for sglang."""

    def check_args_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check the compatibility of the engine args/envs combinations."""
        return True

    def check_model_compatibility(self, model: str) -> bool:
        """Check if the model is compatible with the LiteLLM scheduler based on its architecture."""
        return True

    def check_device_compatibility(self, device: str) -> Optional[str]:
        """Check if the device is compatible with LiteLLM scheduler."""
        return app_settings.litellm_image if device == "cpu" else None
