# Rate Limiting Performance Guide

## Architecture Overview

The rate limiting system uses a hybrid architecture with:
- **Local rate limiting** using the governor crate for fast, in-process decisions
- **Redis coordination** for distributed rate limiting across multiple instances
- **Caching layer** using Moka to reduce Redis calls

## Performance Optimizations

### 1. Early Model Extraction

The key optimization is extracting the model name BEFORE the request body is consumed by the handlers. This is achieved through:

- **Early extraction middleware** that runs before rate limiting
- **Request extensions** to pass the model name without re-parsing
- **Header-based fallback** using `X-Model-Name` header

### 2. Optimized Middleware Order

The middleware stack is ordered for optimal performance:

```
1. Early Model Extraction (extracts model from body once)
2. Rate Limiting (uses pre-extracted model)
3. Authentication
4. Route Handlers (body is still intact)
```

### 3. Configuration Tuning

For optimal performance, tune these parameters:

```toml
[models."model-name".rate_limits]
# Algorithm choice
algorithm = "fixed_window"    # Fastest algorithm

# Local caching
cache_ttl_ms = 500           # Balance between accuracy and performance
local_allowance = 0.2        # 20% of decisions made locally

# Redis settings
redis_timeout_ms = 10        # Fail fast on Redis issues
sync_interval_ms = 200       # Sync every 200ms
```

### 4. Best Practices

1. **Use Fixed Window algorithm** for best performance
2. **Set appropriate cache TTL** - longer TTL reduces Redis calls but may be less accurate
3. **Tune local allowance** - higher values mean more local decisions
4. **Configure reasonable timeouts** - too short causes unnecessary failures
5. **Consider using headers** - clients can pass `X-Model-Name` header to skip body parsing

## Performance Targets

With proper configuration, the system should achieve:
- **P99 latency**: <2ms overhead for rate limiting
- **Throughput**: 1000+ req/s per instance
- **Redis calls**: <20% of requests (with 80%+ cache hit rate)

## Monitoring

Monitor these metrics for performance:
- Rate limiter cache hit rate
- Redis operation latency
- Local vs distributed decisions ratio
- Request latency by percentile

## Troubleshooting High Latency

If experiencing high latency:

1. **Check cache hit rate** - Low hit rate means too many Redis calls
2. **Monitor Redis latency** - High Redis latency impacts all operations
3. **Review body size** - Large request bodies take longer to parse
4. **Verify middleware order** - Ensure early extraction runs first
5. **Consider header approach** - Use `X-Model-Name` header for best performance