# BudGateway Analytics Documentation

## Overview

BudGateway includes comprehensive analytics capabilities for monitoring API usage, collecting request metadata, and enforcing security policies through blocking rules.

## Features

### 1. Request Analytics Collection

The gateway automatically collects detailed metrics for every API request:

- **Request Metadata**: HTTP method, path, headers, query parameters
- **Client Information**: IP address, user agent, API key/token
- **Geographic Data**: Country, region, city, coordinates (via MaxMind GeoIP)
- **Device Information**: Browser, OS, device type (via user agent parsing)
- **Performance Metrics**: Response time, token usage, streaming metrics
- **Response Data**: Status code, error messages, token counts

### 2. Blocking Rules System

Protect your API endpoints with configurable blocking rules:

- **IP Blocking**: Block specific IPs or CIDR ranges
- **Geographic Blocking**: Block requests from specific countries
- **User Agent Blocking**: Block requests matching user agent patterns
- **Rate Limiting**: Block clients exceeding request thresholds

### 3. Real-time Data Pipeline

```
Request → Analytics Middleware → ClickHouse (async write)
        ↓
        → Blocking Middleware → Redis (rule check) → Allow/Block
```

## Configuration

### Basic Setup

Add to your `tensorzero.toml` configuration:

```toml
[gateway.analytics]
enabled = true
geoip_db_path = "/opt/geoip/GeoLite2-City.mmdb"
clickhouse_batch_size = 100
clickhouse_flush_interval = 5  # seconds

[gateway.blocking]
enabled = true
redis_url = "redis://localhost:6379"
cache_ttl = 60  # seconds
```

### GeoIP Database Setup

1. **Download MaxMind GeoLite2 Database**:
   ```bash
   # Sign up for free account at https://www.maxmind.com
   wget -O GeoLite2-City.mmdb.tar.gz "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=YOUR_LICENSE_KEY&suffix=tar.gz"
   tar -xzf GeoLite2-City.mmdb.tar.gz
   cp GeoLite2-City_*/GeoLite2-City.mmdb /opt/geoip/
   ```

2. **Set Permissions**:
   ```bash
   chmod 644 /opt/geoip/GeoLite2-City.mmdb
   ```

3. **Configure Auto-updates** (optional):
   ```bash
   # Add to crontab
   0 0 * * 0 /usr/local/bin/update-geoip.sh
   ```

### Environment Variables

```bash
# Required for analytics
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_DATABASE=budmetrics
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=

# Required for blocking rules
REDIS_URL=redis://localhost:6379
REDIS_BLOCKING_PREFIX=gateway:blocking:

# Optional
ANALYTICS_ENABLED=true
BLOCKING_ENABLED=true
GEOIP_DB_PATH=/opt/geoip/GeoLite2-City.mmdb
```

## Middleware Architecture

### Analytics Middleware

Located in `src/analytics_middleware.rs`:

```rust
pub struct AnalyticsMiddleware {
    clickhouse: ClickHouseClient,
    geoip: Arc<GeoIpService>,
    user_agent_parser: Arc<UserAgentParser>,
}
```

**Key Features**:
- Non-blocking async writes to ClickHouse
- Request/response body sampling (configurable)
- Automatic retry with exponential backoff
- Batch writing for performance

### Blocking Middleware

Located in `src/blocking_middleware.rs`:

```rust
pub struct BlockingMiddleware {
    redis: Arc<RedisClient>,
    rules_cache: Arc<RwLock<HashMap<String, BlockingRule>>>,
    last_sync: Arc<RwLock<Instant>>,
}
```

**Key Features**:
- Local cache with TTL for performance
- Redis sync for distributed updates
- Sub-millisecond evaluation time
- Detailed blocking reason codes

## Data Schema

### ClickHouse Analytics Table

```sql
CREATE TABLE gateway_analytics (
    -- Request identifiers
    request_id UUID,
    inference_id UUID,
    episode_id UUID,

    -- Timestamps
    timestamp DateTime64(3),
    response_time_ms UInt32,

    -- Request details
    method String,
    path String,
    query_params String,
    headers Map(String, String),

    -- Client information
    client_ip String,
    user_agent String,
    api_key_id UUID,

    -- Geographic data
    country_code String,
    country_name String,
    region String,
    city String,
    latitude Float32,
    longitude Float32,

    -- Device information
    device_type String,
    browser String,
    browser_version String,
    os String,
    os_version String,

    -- Response data
    status_code UInt16,
    error_message String,

    -- Token metrics
    input_tokens UInt32,
    output_tokens UInt32,
    total_tokens UInt32,

    -- Blocking information
    is_blocked Bool,
    blocking_rule_id UUID,
    blocking_reason String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (project_id, timestamp, request_id);
```

## Blocking Rules Management

### Rule Types

1. **IP Blocking**:
   ```json
   {
     "rule_type": "ip_blocking",
     "rule_config": {
       "ip_addresses": ["192.168.1.1", "10.0.0.0/8"],
       "action": "block"
     }
   }
   ```

2. **Geographic Blocking**:
   ```json
   {
     "rule_type": "country_blocking",
     "rule_config": {
       "countries": ["CN", "RU", "KP"],
       "action": "block"
     }
   }
   ```

3. **User Agent Blocking**:
   ```json
   {
     "rule_type": "user_agent_blocking",
     "rule_config": {
       "patterns": ["bot", "crawler", "spider"],
       "action": "block"
     }
   }
   ```

4. **Rate Limiting**:
   ```json
   {
     "rule_type": "rate_based_blocking",
     "rule_config": {
       "threshold": 100,
       "window_seconds": 60,
       "action": "block"
     }
   }
   ```

### Redis Storage Format

Rules are stored in Redis with the following structure:

```
Key: gateway:blocking:rules
Value: JSON array of rules

Key: gateway:blocking:ip:{ip_address}
Value: Block reason

Key: gateway:blocking:rate:{client_id}
Value: Request count
TTL: window_seconds
```

## Performance Considerations

### Optimization Strategies

1. **Batch Writing**: Analytics data is batched before writing to ClickHouse
2. **Local Caching**: Blocking rules are cached locally with TTL
3. **Async Processing**: All analytics operations are non-blocking
4. **Connection Pooling**: Reuse database and Redis connections

### Benchmarks

- Analytics middleware overhead: < 1ms
- Blocking evaluation time: < 0.5ms
- GeoIP lookup: < 0.1ms (with caching)
- ClickHouse write: Async (no request blocking)

## Monitoring

### Key Metrics

Monitor these metrics for system health:

1. **Analytics Pipeline**:
   - `gateway_analytics_writes_total`: Total writes to ClickHouse
   - `gateway_analytics_write_errors`: Failed write attempts
   - `gateway_analytics_batch_size`: Average batch size

2. **Blocking System**:
   - `gateway_blocks_total`: Total blocked requests
   - `gateway_blocking_rule_matches`: Matches per rule
   - `gateway_blocking_cache_hits`: Cache hit rate

3. **Performance**:
   - `gateway_middleware_duration`: Middleware processing time
   - `gateway_geoip_lookup_duration`: GeoIP lookup time

### Debugging

Enable debug logging:

```toml
[logging]
level = "debug"
analytics_debug = true
blocking_debug = true
```

Check logs for:
- Analytics write failures
- GeoIP lookup errors
- Redis connection issues
- Rule evaluation details

## Troubleshooting

### Common Issues

1. **GeoIP Database Not Found**:
   ```
   Error: Failed to load GeoIP database
   Solution: Verify path and permissions for GeoLite2-City.mmdb
   ```

2. **ClickHouse Connection Failed**:
   ```
   Error: Failed to write analytics data
   Solution: Check CLICKHOUSE_URL and network connectivity
   ```

3. **Redis Sync Failed**:
   ```
   Error: Failed to sync blocking rules
   Solution: Verify Redis connection and REDIS_URL
   ```

4. **High Memory Usage**:
   ```
   Issue: Gateway using excessive memory
   Solution: Reduce batch sizes and cache TTLs
   ```

## Security Considerations

1. **Data Privacy**:
   - IP addresses are stored but can be anonymized
   - Sensitive headers are filtered before storage
   - Request/response bodies are sampled, not fully stored

2. **Access Control**:
   - Analytics data access requires authentication
   - Blocking rules management requires admin privileges
   - API keys are hashed before storage

3. **Rate Limiting**:
   - Implement distributed rate limiting with Redis
   - Use sliding window algorithm for accuracy
   - Configure separate limits per endpoint

## Future Enhancements

- [ ] Machine learning-based anomaly detection
- [ ] Real-time streaming analytics
- [ ] Advanced pattern matching for blocking rules
- [ ] Automatic rule generation based on traffic patterns
- [ ] GraphQL API for analytics queries
