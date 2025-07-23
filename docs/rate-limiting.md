# Rate Limiting in TensorZero

TensorZero provides a high-performance, distributed rate limiting system to protect your AI models from abuse and manage resource consumption. The rate limiter is designed to operate with <1ms P99 latency at 1000 requests/second while providing flexible configuration options.

## Overview

The rate limiting system uses a hybrid approach:
- **Local in-memory rate limiting** using the `governor` crate for ultra-low latency
- **Redis coordination** for distributed configuration synchronization
- **Per-model and per-API-key limits** with granular control
- **Multiple algorithms** to suit different use cases

## Configuration

### Global Rate Limits

Configure global rate limits in your `tensorzero.toml`:

```toml
[gateway.rate_limits]
enabled = true                        # Enable/disable rate limiting globally
default_requests_per_minute = 100     # Default limit for models without specific config
default_burst_size = 10               # Default burst capacity
default_algorithm = "sliding_window"  # Default algorithm: fixed_window, sliding_window, token_bucket
```

### Per-Model Rate Limits

Override rate limits for specific models with full configuration control:

```toml
[models.gpt-4.rate_limits]
algorithm = "token_bucket"            # Algorithm: fixed_window, sliding_window, token_bucket
requests_per_second = 10              # Requests allowed per second (optional)
requests_per_minute = 60              # Requests allowed per minute (optional)
requests_per_hour = 1000              # Requests allowed per hour (optional)
burst_size = 15                       # Maximum burst capacity
enabled = true                        # Enable/disable for this model
cache_ttl_ms = 200                    # Local cache TTL in milliseconds
redis_timeout_ms = 1                  # Redis operation timeout in milliseconds
local_allowance = 0.1                 # Local allowance ratio (0.0-1.0)
sync_interval_ms = 100                # Background sync interval in milliseconds
```

## Configuration Parameters

### Rate Limit Algorithms

Choose the algorithm that best fits your use case:

| Algorithm | Description | Use Case | Performance |
|-----------|-------------|----------|-------------|
| `fixed_window` | Simple counter reset at fixed intervals | Basic rate limiting, highest performance | Fastest |
| `sliding_window` | More accurate, prevents burst abuse at boundaries | Better accuracy, moderate performance | Medium |
| `token_bucket` | Smooth rate limiting with burst capacity | API-style limiting, burst handling | Good |

### Time Window Configuration

You can configure multiple time windows simultaneously:

```toml
[models.api-heavy.rate_limits]
requests_per_second = 10    # 10 requests per second
requests_per_minute = 300   # 300 requests per minute (5 per second average)
requests_per_hour = 5000    # 5000 requests per hour (83 per minute average)
```

**Note**: The most restrictive limit applies. In the example above, `requests_per_second = 10` would be the effective limit.

### Performance Tuning Parameters

#### Cache Configuration
- **`cache_ttl_ms`** (default: `200`): How long to cache rate limit state locally
  - Lower values: More accurate distributed limiting
  - Higher values: Better performance, less Redis load

#### Redis Configuration  
- **`redis_timeout_ms`** (default: `1`): Timeout for Redis operations
  - Lower values: Faster fallback to local-only limiting
  - Higher values: More tolerance for Redis latency

#### Local Allowance
- **`local_allowance`** (default: `0.1`): Fraction of rate limit enforced locally
  - `0.0`: Strict distributed enforcement (more Redis calls)
  - `1.0`: Aggressive local allowance (less accurate)
  - `0.1-0.3`: Recommended range for most use cases

#### Background Sync
- **`sync_interval_ms`** (default: `100`): How often to sync with Redis
  - Lower values: More accurate, higher Redis load
  - Higher values: Less accurate, lower Redis load

## Rate Limit Headers

TensorZero returns standard rate limit headers with every response:

- `X-RateLimit-Limit`: The rate limit ceiling for that request
- `X-RateLimit-Remaining`: The number of requests left for the time window
- `X-RateLimit-Reset`: Unix timestamp when the rate limit window resets
- `Retry-After`: (On 429 responses) Number of seconds to wait before retrying

## OpenAI-Compatible Error Responses

When rate limits are exceeded on OpenAI-compatible endpoints, TensorZero returns:

```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error", 
    "code": "rate_limit_exceeded"
  }
}
```

## Architecture

### Local Rate Limiting

Each gateway instance maintains local rate limiters using the `governor` crate. This provides:
- Sub-microsecond latency for rate limit checks
- No network calls in the hot path
- Configurable burst handling

### Distributed Coordination

When Redis is available, the rate limiter provides:
- Shared state across gateway instances
- Dynamic configuration updates (coming soon)
- Consistent rate limiting across your fleet

### Performance Characteristics

Based on our benchmarks:
- **Local rate limit check**: <100μs average latency
- **Header generation**: <10μs average latency
- **Metrics recording**: <50ns average latency
- **P99 latency at 1000 req/s**: <1ms

## Authentication and API Keys

### Anonymous Rate Limiting

When authentication is disabled, rate limits are applied per model:

```toml
[gateway.authentication]
enabled = false

[models.gpt-4.rate_limits]
requests_per_minute = 100  # Applied to all users of this model
```

### Per-API-Key Rate Limiting

When authentication is enabled, rate limits are applied per API key + model combination:

```toml
[gateway.authentication]
enabled = true

[models.gpt-4.rate_limits]
requests_per_minute = 10   # Per API key per model
```

## Environment Variables

Rate limiting requires Redis for distributed coordination:

```bash
# Required for distributed rate limiting
TENSORZERO_REDIS_URL="redis://localhost:6379"

# Optional Redis configuration
REDIS_PASSWORD="your-password"
REDIS_DATABASE="0"
```

## Monitoring

Rate limiter metrics are exposed via the `/metrics` endpoint:

- `rate_limit_requests_total`: Total requests checked
- `rate_limit_requests_allowed`: Requests allowed
- `rate_limit_requests_denied`: Requests denied
- `rate_limit_cache_hits`: Local cache hits
- `rate_limit_cache_misses`: Local cache misses
- `rate_limit_redis_timeouts`: Redis operation timeouts

## Configuration Examples

### Basic Setup

```toml
[gateway.rate_limits]
enabled = true
default_requests_per_minute = 100
default_algorithm = "sliding_window"

[models.gpt-4.rate_limits]
requests_per_minute = 60
burst_size = 10
enabled = true
```

### High-Performance Setup

```toml
[gateway.rate_limits]
enabled = true
default_algorithm = "fixed_window"  # Fastest algorithm

[models.gpt-3.5-turbo.rate_limits]
algorithm = "fixed_window"
requests_per_second = 50
burst_size = 100
cache_ttl_ms = 1000                 # Longer cache
local_allowance = 0.3               # More local allowance
redis_timeout_ms = 5                # Higher Redis timeout
```

### Strict Enforcement Setup

```toml
[gateway.rate_limits]
enabled = true
default_algorithm = "sliding_window"  # Most accurate

[models.premium-model.rate_limits]
algorithm = "sliding_window"
requests_per_minute = 10
burst_size = 2
cache_ttl_ms = 100                  # Shorter cache
local_allowance = 0.05              # Minimal local allowance
redis_timeout_ms = 1                # Quick Redis timeout
sync_interval_ms = 50               # Frequent sync
```

### Multi-Tier Service

```toml
[gateway.rate_limits]
enabled = true
default_requests_per_minute = 60
default_algorithm = "token_bucket"

# Free tier
[models.gpt-3.5-turbo.rate_limits]
requests_per_minute = 20
burst_size = 5
enabled = true

# Premium tier  
[models.gpt-4.rate_limits]
requests_per_minute = 100
burst_size = 20
enabled = true

# Enterprise tier
[models.gpt-4-32k.rate_limits]
requests_per_second = 10
requests_per_minute = 500
burst_size = 50
enabled = true
```

## Best Practices

### Choosing Rate Limits

1. **Start conservative**: Begin with lower limits and increase based on usage patterns
2. **Monitor usage**: Track rate limit hits to identify bottlenecks
3. **Consider cost**: Higher limits may increase provider costs
4. **Plan for peaks**: Use burst capacity for legitimate traffic spikes

### Algorithm Selection

1. **Fixed Window**: Choose for highest performance, simple use cases
2. **Sliding Window**: Choose for better accuracy, preventing boundary abuse
3. **Token Bucket**: Choose for smooth rate limiting, API-style behavior

### Performance Optimization

1. **Cache TTL**: 
   - Start with 200ms default
   - Increase to 500-1000ms for better performance
   - Decrease to 50-100ms for stricter enforcement

2. **Local Allowance**:
   - Use 0.1-0.2 for balanced performance/accuracy
   - Use 0.05-0.1 for strict enforcement
   - Use 0.3-0.5 for performance-critical applications

3. **Redis Timeout**:
   - Use 1-5ms for fast failover
   - Use 10-50ms for tolerating Redis latency

### Multi-Window Configuration

When using multiple time windows, ensure they make sense together:

```toml
# Good: Consistent rates
[models.example.rate_limits]
requests_per_second = 10    # 10/s
requests_per_minute = 600   # 10/s average
requests_per_hour = 36000   # 10/s average

# Bad: Conflicting rates
[models.example.rate_limits] 
requests_per_second = 100   # 100/s
requests_per_minute = 60    # 1/s average - this will be the effective limit!
```

## Troubleshooting

### Rate Limits Not Working

1. **Check Redis connectivity**:
   ```bash
   redis-cli -u $TENSORZERO_REDIS_URL ping
   ```

2. **Verify configuration**:
   - Ensure `gateway.rate_limits.enabled = true`
   - Check model has rate limits configured
   - Verify algorithm names use snake_case: `fixed_window`, not `FixedWindow`

3. **Check logs**:
   ```
   INFO gateway: Applying rate limiting middleware to OpenAI routes
   INFO tensorzero_internal::gateway_util: Distributed rate limiter initialized successfully
   ```

### Performance Issues

1. **High Redis latency**:
   - Increase `redis_timeout_ms`
   - Increase `local_allowance`
   - Increase `cache_ttl_ms`

2. **Inaccurate rate limiting**:
   - Decrease `cache_ttl_ms`
   - Decrease `local_allowance`
   - Use `sliding_window` algorithm

3. **High CPU usage**:
   - Use `fixed_window` algorithm
   - Increase `cache_ttl_ms`
   - Increase `sync_interval_ms`

### Common Configuration Errors

1. **Algorithm naming**: Use `snake_case` (`fixed_window`), not `PascalCase` (`FixedWindow`)
2. **Missing Redis**: Rate limiting requires `TENSORZERO_REDIS_URL` to be set
3. **Conflicting limits**: When using multiple time windows, the most restrictive applies
4. **Float precision**: `local_allowance` must be between 0.0 and 1.0

## Future Enhancements

- Dynamic configuration updates via Redis pub/sub
- Per-endpoint rate limiting (separate limits for chat vs embeddings)
- Cost-based rate limiting (tokens/credits instead of requests)
- Rate limit inheritance and groups
- WebSocket support for real-time configuration updates
- Integration with external rate limiting services