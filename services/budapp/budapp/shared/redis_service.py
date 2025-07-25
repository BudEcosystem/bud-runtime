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
            pool = aioredis.ConnectionPool.from_url(secrets_settings.redis_url)
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
