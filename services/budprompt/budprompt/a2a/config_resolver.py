"""Redis-based prompt configuration resolver for A2A protocol.

Resolves prompt configs from Redis using the same key pattern as ResponsesService.
"""

import json
import logging

from a2a.utils.errors import TaskNotFoundError
from pydantic import ValidationError

from ..prompt.schemas import PromptExecuteData
from ..shared.redis_service import RedisService


logger = logging.getLogger(__name__)


class A2AConfigResolver:
    """Resolves prompt configuration from Redis for A2A requests."""

    def __init__(self) -> None:
        """Initialize with Redis service."""
        self._redis = RedisService()

    async def resolve(self, prompt_id: str, version: int) -> tuple[PromptExecuteData, int]:
        """Resolve prompt config from Redis.

        Args:
            prompt_id: The prompt identifier.
            version: Version number (0 = default version).

        Returns:
            Tuple of (validated PromptExecuteData, resolved version number).

        Raises:
            TaskNotFoundError: If prompt config not found in Redis.
        """
        if version == 0:
            # v0 → resolve default version
            default_key = f"prompt:{prompt_id}:default_version"
            redis_key = await self._redis.get(default_key)
            if not redis_key:
                raise TaskNotFoundError(message=f"Prompt not found: {prompt_id}")
            # Extract actual version from key like "prompt:test_prompt_stream:v1"
            try:
                redis_key_str = redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                resolved_version = redis_key_str.rsplit(":v", 1)[1]
            except (IndexError, ValueError) as e:
                raise TaskNotFoundError(message=f"Invalid default version key for {prompt_id}") from e
        else:
            redis_key = f"prompt:{prompt_id}:v{version}"
            resolved_version = version

        config_json = await self._redis.get(redis_key)
        if not config_json:
            raise TaskNotFoundError(
                message=f"Prompt not found: {prompt_id}" + (f" version {version}" if version else "")
            )

        try:
            config_data = json.loads(config_json)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse prompt config for %s: %s", prompt_id, e)
            raise TaskNotFoundError(message=f"Invalid prompt configuration: {prompt_id}") from e

        try:
            return PromptExecuteData.model_validate(config_data), resolved_version
        except ValidationError as e:
            logger.error("Invalid prompt config schema for %s: %s", prompt_id, e)
            raise TaskNotFoundError(message=f"Invalid prompt configuration for {prompt_id}") from e
