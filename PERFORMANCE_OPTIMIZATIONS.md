# Rate Limiting Performance Optimizations

## Goal: <1ms P99 latency at 1000 req/s

## Key Bottlenecks Identified

1. **Request Body Parsing** (3-5ms overhead)
   - Reading entire body into memory
   - JSON parsing for every request
   - Body reconstruction overhead

2. **Redis Round Trips** (1-2ms each)
   - Synchronous Redis calls in hot path
   - No batching of updates
   - Too frequent syncs

3. **Lock Contention**
   - DashMap lookups
   - Cache access patterns

## Implemented Optimizations

### 1. Middleware Optimizations

- **Fast Path for Known Models**: Skip body parsing when model is in URL
- **Lazy Body Parsing**: Only parse when absolutely necessary
- **Fast JSON Scanning**: Use string search instead of full JSON parse
- **Fixed Model Fallback**: Use default model to avoid parsing entirely

### 2. Rate Limiter Optimizations

- **Extended Cache TTL**: 5000ms instead of 200ms
- **Higher Local Allowance**: 95% local decisions
- **Skip Redis on Allow**: Don't update Redis for successful requests
- **Fast Fail on Redis Timeout**: 1ms timeout, fail open
- **Local-Only Under Load**: Fall back to pure local limiting

### 3. Configuration Optimizations

```toml
[models."gpt-3.5-turbo".rate_limits]
algorithm = "fixed_window"          # Fastest algorithm
cache_ttl_ms = 5000                # 5s cache
redis_timeout_ms = 1               # 1ms timeout
local_allowance = 0.95             # 95% local
sync_interval_ms = 5000            # 5s sync interval
skip_redis_on_allow = true         # No Redis on success
use_local_only_under_load = true   # Degrade gracefully
```

## Recommended Production Settings

For production deployments requiring <1ms P99:

1. **Use Fixed Window Algorithm**: Fastest, good enough for most cases
2. **Set High Local Allowance**: 0.9-0.95 for minimal Redis calls
3. **Enable Performance Flags**: All three optimization flags
4. **Use Longer Cache TTL**: 5-10 seconds
5. **Set Short Redis Timeout**: 1-2ms max
6. **Consider Model Allowlist**: Pre-configure known models

## Alternative Approaches

If still not meeting targets:

1. **Use middleware_fast**: Fixed model, no parsing at all
2. **Increase Local Allowance**: Up to 0.99 for near-local-only
3. **Disable Redis Sync**: Pure local rate limiting
4. **Use Separate Rate Limit Service**: Move logic out of request path