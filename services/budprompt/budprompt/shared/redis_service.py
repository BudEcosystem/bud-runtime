import logging
from typing import Optional, Union

import redis.asyncio as aioredis
from redis.typing import AbsExpiryT, EncodableT, ExpiryT, KeyT, PatternT, ResponseT

from ..commons.config import app_settings
from ..commons.exceptions import RedisException
from .singleton import SingletonMeta


logger = logging.getLogger(__name__)


class RedisSingleton(metaclass=SingletonMeta):
    """Redis singleton class."""

    _redis_client: Optional[aioredis.Redis] = None

    def __init__(self):
        """Initialize the Redis singleton."""
        if not self._redis_client:
            pool = aioredis.ConnectionPool.from_url(app_settings.redis_url)
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

    async def hset(self, name: KeyT, key: str, value: EncodableT) -> ResponseT:
        """Set a hash field value (atomic operation).

        Args:
            name: The Redis hash key
            key: The field name within the hash
            value: The value to set

        Returns:
            Number of fields that were added (0 if field existed and was updated, 1 if new field)

        Raises:
            RedisException: If the operation fails
        """
        async with self.redis_singleton as redis:
            try:
                return await redis.hset(name, key, value)
            except Exception as e:
                logger.exception(f"Error setting Redis hash field: {e}")
                raise RedisException(f"Error setting hash field {key} in {name}") from e

    async def hget(self, name: KeyT, key: str) -> ResponseT:
        """Get a hash field value.

        Args:
            name: The Redis hash key
            key: The field name within the hash

        Returns:
            The value of the field, or None if field doesn't exist

        Raises:
            RedisException: If the operation fails
        """
        async with self.redis_singleton as redis:
            try:
                return await redis.hget(name, key)
            except Exception as e:
                logger.exception(f"Error getting Redis hash field: {e}")
                raise RedisException(f"Error getting hash field {key} from {name}") from e

    async def hgetall(self, name: KeyT) -> ResponseT:
        """Get all hash fields and values (atomic snapshot).

        Args:
            name: The Redis hash key

        Returns:
            Dictionary of all fields and values in the hash

        Raises:
            RedisException: If the operation fails
        """
        async with self.redis_singleton as redis:
            try:
                return await redis.hgetall(name)
            except Exception as e:
                logger.exception(f"Error getting all Redis hash fields: {e}")
                raise RedisException(f"Error getting all hash fields from {name}") from e

    async def hdel(self, name: KeyT, *keys: str) -> ResponseT:
        """Delete one or more hash fields (atomic operation).

        Args:
            name: The Redis hash key
            *keys: One or more field names to delete

        Returns:
            Number of fields that were removed

        Raises:
            RedisException: If the operation fails
        """
        async with self.redis_singleton as redis:
            try:
                return await redis.hdel(name, *keys)
            except Exception as e:
                logger.exception(f"Error deleting Redis hash fields: {e}")
                raise RedisException(f"Error deleting hash fields from {name}") from e

    async def hexists(self, name: KeyT, key: str) -> ResponseT:
        """Check if a hash field exists.

        Args:
            name: The Redis hash key
            key: The field name to check

        Returns:
            1 if field exists, 0 if it doesn't

        Raises:
            RedisException: If the operation fails
        """
        async with self.redis_singleton as redis:
            try:
                return await redis.hexists(name, key)
            except Exception as e:
                logger.exception(f"Error checking Redis hash field existence: {e}")
                raise RedisException(f"Error checking hash field {key} in {name}") from e
