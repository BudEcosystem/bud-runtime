"""Tests for Redis cache invalidation functionality."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from budapp.shared.redis_service import RedisService


class TestRedisServiceCacheInvalidation:
    """Test cases for Redis cache invalidation methods."""

    @pytest.mark.asyncio
    async def test_invalidate_cache_by_patterns_with_specific_keys(self):
        """Test generic cache invalidation with specific keys."""
        # Arrange
        redis_service = RedisService()
        specific_keys = ["cache:key1", "cache:key2"]
        patterns = ["cache:pattern:*"]

        with patch.object(RedisService, 'delete', new_callable=AsyncMock) as mock_delete:
            with patch.object(RedisService, 'delete_keys_by_pattern', new_callable=AsyncMock) as mock_delete_pattern:
                mock_delete_pattern.return_value = 5  # Mock 5 keys deleted by pattern

                # Act
                await redis_service.invalidate_cache_by_patterns(
                    specific_keys=specific_keys,
                    patterns=patterns,
                    operation_name="test"
                )

                # Assert
                mock_delete.assert_called_once_with(*specific_keys)
                mock_delete_pattern.assert_called_once_with("cache:pattern:*")

    @pytest.mark.asyncio
    async def test_invalidate_cache_by_patterns_patterns_only(self):
        """Test generic cache invalidation with patterns only."""
        # Arrange
        redis_service = RedisService()
        patterns = ["pattern1:*", "pattern2:*"]

        with patch.object(RedisService, 'delete', new_callable=AsyncMock) as mock_delete:
            with patch.object(RedisService, 'delete_keys_by_pattern', new_callable=AsyncMock) as mock_delete_pattern:
                mock_delete_pattern.side_effect = [3, 2]  # Mock different counts for each pattern

                # Act
                await redis_service.invalidate_cache_by_patterns(
                    patterns=patterns,
                    operation_name="test"
                )

                # Assert
                mock_delete.assert_not_called()
                assert mock_delete_pattern.call_count == 2
                mock_delete_pattern.assert_any_call("pattern1:*")
                mock_delete_pattern.assert_any_call("pattern2:*")

    @pytest.mark.asyncio
    async def test_invalidate_cache_by_patterns_exception_handling(self):
        """Test that cache invalidation handles exceptions gracefully."""
        # Arrange
        redis_service = RedisService()
        specific_keys = ["cache:key1"]

        with patch.object(RedisService, 'delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = Exception("Redis connection error")

            # Act - should not raise exception
            await redis_service.invalidate_cache_by_patterns(
                specific_keys=specific_keys,
                operation_name="test"
            )

            # Assert
            mock_delete.assert_called_once_with(*specific_keys)

    @pytest.mark.asyncio
    async def test_invalidate_catalog_cache_with_endpoint_id(self):
        """Test catalog cache invalidation with endpoint ID."""
        # Arrange
        redis_service = RedisService()
        endpoint_id = str(uuid4())

        with patch.object(RedisService, 'invalidate_cache_by_patterns', new_callable=AsyncMock) as mock_invalidate:
            # Act
            await redis_service.invalidate_catalog_cache(endpoint_id=endpoint_id)

            # Assert
            mock_invalidate.assert_called_once_with(
                specific_keys=[f"catalog:model:{endpoint_id}"],
                patterns=["catalog:models:*"],
                operation_name="catalog"
            )

    @pytest.mark.asyncio
    async def test_invalidate_catalog_cache_without_endpoint_id(self):
        """Test catalog cache invalidation without endpoint ID."""
        # Arrange
        redis_service = RedisService()

        with patch.object(RedisService, 'invalidate_cache_by_patterns', new_callable=AsyncMock) as mock_invalidate:
            # Act
            await redis_service.invalidate_catalog_cache()

            # Assert
            mock_invalidate.assert_called_once_with(
                specific_keys=None,
                patterns=["catalog:models:*"],
                operation_name="catalog"
            )

    @pytest.mark.asyncio
    async def test_invalidate_cache_with_empty_inputs(self):
        """Test cache invalidation with empty inputs."""
        # Arrange
        redis_service = RedisService()

        with patch.object(RedisService, 'delete', new_callable=AsyncMock) as mock_delete:
            with patch.object(RedisService, 'delete_keys_by_pattern', new_callable=AsyncMock) as mock_delete_pattern:
                # Act
                await redis_service.invalidate_cache_by_patterns(
                    specific_keys=None,
                    patterns=None,
                    operation_name="test"
                )

                # Assert
                mock_delete.assert_not_called()
                mock_delete_pattern.assert_not_called()
