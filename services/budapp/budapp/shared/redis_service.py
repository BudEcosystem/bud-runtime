import json
from typing import Any, Callable, Optional, Union

import redis.asyncio as aioredis
from redis.typing import AbsExpiryT, EncodableT, ExpiryT, KeyT, PatternT, ResponseT

from ..commons import logging
from ..commons.config import secrets_settings
from ..commons.exceptions import RedisException
from .singleton import SingletonMeta


logger = logging.get_logger(__name__)


class RedisSingleton(metaclass=SingletonMeta):
    """Redis singleton class."""

    _redis_client: Optional[aioredis.Redis] = None

    def __init__(self):
        """Initialize the Redis singleton."""
        if not self._redis_client:
            pool = aioredis.ConnectionPool.from_url("redis://localhost:6379")
            self._redis_client = aioredis.Redis.from_pool(pool)

    async def __aenter__(self):
        """Enter the context manager."""
        return self._redis_client

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Exit the context manager."""
        if self._redis_client:
            await self._redis_client.aclose()


class RedisService:
    """Redis service class."""

    def __init__(self):
        """Initialize the Redis service."""
        self.redis_singleton = RedisSingleton()

    async def set(
        self,
        name: KeyT,
        value: EncodableT,
        ex: Union[ExpiryT, None] = None,
        px: Union[ExpiryT, None] = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False,
        get: bool = False,
        exat: Union[AbsExpiryT, None] = None,
        pxat: Union[AbsExpiryT, None] = None,
    ) -> ResponseT:
        """Set a key-value pair in Redis."""
        async with self.redis_singleton as redis:
            try:
                return await redis.set(name, value, ex, px, nx, xx, keepttl, get, exat, pxat)
            except Exception as e:
                logger.exception(f"Error setting Redis key: {e}")
                raise RedisException(f"Error setting Redis key {name}") from e

    async def get(self, name: KeyT) -> ResponseT:
        """Get a value from Redis."""
        async with self.redis_singleton as redis:
            try:
                return await redis.get(name)
            except Exception as e:
                logger.exception(f"Error getting Redis key: {e}")
                raise RedisException(f"Error getting Redis key {name}") from e

    async def keys(self, pattern: PatternT, **kwargs) -> ResponseT:
        """Get all keys matching the pattern."""
        async with self.redis_singleton as redis:
            try:
                return await redis.keys(pattern, **kwargs)
            except Exception as e:
                logger.exception(f"Error getting Redis keys: {e}")
                raise RedisException("Error getting Redis keys") from e

    async def delete(self, *names: Optional[KeyT]) -> ResponseT:
        """Delete a key from Redis."""
        if not names:
            logger.warning("No keys to delete")
            return 0

        async with self.redis_singleton as redis:
            try:
                return await redis.delete(*names)
            except Exception as e:
                logger.exception(f"Error deleting Redis key: {e}")
                raise RedisException(f"Error deleting Redis key {names}") from e

    async def delete_keys_by_pattern(self, pattern):
        """Delete all keys matching a pattern from Redis."""
        async with self.redis_singleton as redis:
            matching_keys = await redis.keys(pattern)
            if matching_keys:
                await redis.delete(*matching_keys)
                return len(matching_keys)
            return 0

    async def incr(self, name: KeyT) -> ResponseT:
        """Increment a value in Redis."""
        async with self.redis_singleton as redis:
            try:
                return await redis.incr(name)
            except Exception as e:
                logger.exception(f"Error incrementing Redis key: {e}")
                raise RedisException(f"Error incrementing Redis key {name}") from e

    async def ttl(self, name: KeyT) -> ResponseT:
        """Get the TTL of a key in Redis."""
        async with self.redis_singleton as redis:
            try:
                return await redis.ttl(name)
            except Exception as e:
                logger.exception(f"Error getting TTL for Redis key: {e}")
                raise RedisException(f"Error getting TTL for Redis key {name}") from e

    async def invalidate_cache_by_patterns(
        self, specific_keys: Optional[list] = None, patterns: Optional[list] = None, operation_name: str = "cache"
    ) -> None:
        """Generic cache invalidation method.

        Args:
            specific_keys: List of specific cache keys to delete
            patterns: List of patterns to match and delete keys
            operation_name: Name of the operation for logging purposes
        """
        try:
            total_deleted = 0

            # Delete specific keys
            if specific_keys:
                await self.delete(*specific_keys)
                logger.debug(f"Invalidated {len(specific_keys)} specific {operation_name} cache keys: {specific_keys}")
                total_deleted += len(specific_keys)

            # Delete keys matching patterns
            if patterns:
                for pattern in patterns:
                    deleted_count = await self.delete_keys_by_pattern(pattern)
                    total_deleted += deleted_count
                    logger.debug(
                        f"Invalidated {deleted_count} {operation_name} cache entries matching pattern: {pattern}"
                    )

            if total_deleted > 0:
                logger.info(f"Successfully invalidated {total_deleted} {operation_name} cache entries")

        except Exception as e:
            logger.warning(f"Failed to invalidate {operation_name} cache: {e}")
            # Don't raise exception - cache invalidation failure shouldn't break the operation

    async def invalidate_catalog_cache(self, endpoint_id: Optional[str] = None) -> None:
        """Invalidate catalog-related cache entries.

        Args:
            endpoint_id: Optional endpoint ID to invalidate specific model cache.
                        If provided, invalidates model detail cache for that endpoint.
                        Always invalidates catalog list cache patterns.
        """
        specific_keys = []
        patterns = ["catalog:models:*"]

        # Add specific model detail cache key if endpoint_id provided
        if endpoint_id:
            specific_keys.append(f"catalog:model:{endpoint_id}")

        await self.invalidate_cache_by_patterns(
            specific_keys=specific_keys if specific_keys else None, patterns=patterns, operation_name="catalog"
        )


def cache(
    key_func: Callable[[Any, Any], str],
    ttl: Optional[int] = None,
    serializer: Callable = json.dumps,
    deserializer: Callable = json.loads,
):
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs) -> Any:
            redis_service = RedisService()

            key = key_func(*args, **kwargs)
            cached_data = await redis_service.get(key)

            if cached_data:
                return deserializer(cached_data)

            result = await func(*args, **kwargs)

            await redis_service.set(key, serializer(result), ex=ttl)

            return result

        return wrapper

    return decorator
