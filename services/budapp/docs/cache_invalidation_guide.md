# Cache Invalidation Guide

This document explains how to use the common cache invalidation functions in the RedisService class.

## Overview

The RedisService class provides two main methods for cache invalidation:

1. **`invalidate_cache_by_patterns()`** - Generic method for any cache type
2. **`invalidate_catalog_cache()`** - Specific method for catalog cache

## Generic Cache Invalidation

### Method Signature

```python
async def invalidate_cache_by_patterns(
    self,
    specific_keys: Optional[list] = None,
    patterns: Optional[list] = None,
    operation_name: str = "cache"
) -> None
```

### Parameters

- `specific_keys`: List of exact cache keys to delete
- `patterns`: List of Redis patterns to match and delete keys (e.g., "user:*", "session:123:*")
- `operation_name`: Name for logging purposes (helps identify what type of cache is being invalidated)

### Usage Examples

#### Example 1: Invalidating User Session Cache

```python
from budapp.shared.redis_service import RedisService

async def logout_user(user_id: str):
    # ... logout logic ...

    # Invalidate user's session cache
    redis_service = RedisService()
    await redis_service.invalidate_cache_by_patterns(
        specific_keys=[f"user:session:{user_id}"],
        patterns=[f"user:{user_id}:*"],
        operation_name="user_session"
    )
```

#### Example 2: Invalidating Project Cache

```python
async def update_project(project_id: str):
    # ... update project logic ...

    # Invalidate project-related cache
    redis_service = RedisService()
    await redis_service.invalidate_cache_by_patterns(
        specific_keys=[f"project:{project_id}"],
        patterns=[f"project:{project_id}:*", "projects:list:*"],
        operation_name="project"
    )
```

#### Example 3: Invalidating Only Pattern-Based Cache

```python
async def bulk_update_models():
    # ... bulk update logic ...

    # Invalidate all model list caches
    redis_service = RedisService()
    await redis_service.invalidate_cache_by_patterns(
        patterns=["models:list:*", "models:search:*"],
        operation_name="models_bulk"
    )
```

## Catalog-Specific Cache Invalidation

### Method Signature

```python
async def invalidate_catalog_cache(self, endpoint_id: Optional[str] = None) -> None
```

### Parameters

- `endpoint_id`: Optional endpoint ID. If provided, also invalidates the specific model detail cache.

### Usage Examples

#### Example 1: Invalidating After Model Publication

```python
from budapp.shared.redis_service import RedisService

async def publish_model(endpoint_id: UUID):
    # ... publication logic ...

    # Invalidate catalog cache
    redis_service = RedisService()
    await redis_service.invalidate_catalog_cache(endpoint_id=str(endpoint_id))
```

#### Example 2: Invalidating All Catalog Cache

```python
async def bulk_update_published_models():
    # ... bulk update logic ...

    # Invalidate all catalog cache (no specific endpoint)
    redis_service = RedisService()
    await redis_service.invalidate_catalog_cache()
```

## Best Practices

### 1. Use Descriptive Operation Names

```python
# Good
await redis_service.invalidate_cache_by_patterns(
    patterns=["clusters:*"],
    operation_name="cluster_management"
)

# Bad
await redis_service.invalidate_cache_by_patterns(
    patterns=["clusters:*"],
    operation_name="cache"
)
```

### 2. Group Related Cache Keys

```python
# Good - group related cache keys
await redis_service.invalidate_cache_by_patterns(
    specific_keys=[
        f"endpoint:{endpoint_id}",
        f"endpoint:{endpoint_id}:status",
        f"endpoint:{endpoint_id}:metrics"
    ],
    patterns=[f"endpoint:{endpoint_id}:workers:*"],
    operation_name="endpoint_update"
)

# Less efficient - multiple calls
await redis_service.invalidate_cache_by_patterns(
    specific_keys=[f"endpoint:{endpoint_id}"],
    operation_name="endpoint"
)
await redis_service.invalidate_cache_by_patterns(
    specific_keys=[f"endpoint:{endpoint_id}:status"],
    operation_name="endpoint"
)
```

### 3. Handle Cache Invalidation After Successful Operations

```python
async def update_model_pricing(endpoint_id: UUID, pricing_data: dict):
    try:
        # Update pricing in database
        new_pricing = await create_deployment_pricing(endpoint_id, pricing_data)

        # Only invalidate cache after successful database update
        redis_service = RedisService()
        await redis_service.invalidate_catalog_cache(endpoint_id=str(endpoint_id))

        return new_pricing
    except Exception as e:
        # Don't invalidate cache if operation failed
        logger.error(f"Failed to update pricing: {e}")
        raise
```

### 4. Use Specific Cache Invalidation for Domain-Specific Operations

```python
# Good - use specific method for catalog operations
await redis_service.invalidate_catalog_cache(endpoint_id=str(endpoint_id))

# Less preferred - use generic method for well-known patterns
await redis_service.invalidate_cache_by_patterns(
    specific_keys=[f"catalog:model:{endpoint_id}"],
    patterns=["catalog:models:*"],
    operation_name="catalog"
)
```

## Creating Custom Cache Invalidation Methods

For frequently used cache patterns, consider adding specific methods to RedisService:

```python
async def invalidate_user_cache(self, user_id: str) -> None:
    """Invalidate user-related cache entries."""
    await self.invalidate_cache_by_patterns(
        specific_keys=[f"user:{user_id}", f"user:{user_id}:profile"],
        patterns=[f"user:{user_id}:sessions:*", f"user:{user_id}:projects:*"],
        operation_name="user"
    )

async def invalidate_cluster_cache(self, cluster_id: Optional[str] = None) -> None:
    """Invalidate cluster-related cache entries."""
    specific_keys = []
    patterns = ["clusters:list:*"]

    if cluster_id:
        specific_keys.extend([
            f"cluster:{cluster_id}",
            f"cluster:{cluster_id}:status",
            f"cluster:{cluster_id}:metrics"
        ])
        patterns.append(f"cluster:{cluster_id}:*")

    await self.invalidate_cache_by_patterns(
        specific_keys=specific_keys if specific_keys else None,
        patterns=patterns,
        operation_name="cluster"
    )
```

## Error Handling

The cache invalidation methods are designed to be fault-tolerant:

- Exceptions are caught and logged but not re-raised
- Operations continue even if cache invalidation fails
- Detailed logging helps with debugging cache issues

This ensures that cache invalidation failures don't break the primary business logic.

## Logging

Cache invalidation operations are logged at different levels:

- `DEBUG`: Individual cache key deletions
- `INFO`: Summary of successful invalidations
- `WARNING`: Cache invalidation failures

Example log messages:
```
DEBUG - Invalidated 2 specific catalog cache keys: ['catalog:model:abc-123', 'catalog:model:def-456']
DEBUG - Invalidated 15 catalog cache entries matching pattern: catalog:models:*
INFO - Successfully invalidated 17 catalog cache entries
WARNING - Failed to invalidate user cache: Redis connection timeout
```
