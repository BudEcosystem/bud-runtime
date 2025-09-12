# Billing Cycle Reset Implementation

## Overview

The billing cycle reset feature provides automatic and manual mechanisms to reset user usage when billing cycles change. This ensures accurate tracking and proper quota enforcement across billing periods.

## Architecture

### Components

1. **BudApp Service (Python)**
   - `reset_usage.py`: Core reset logic and API endpoints
   - `usage_sync.py`: Background task for periodic Redis sync
   - `services.py`: Enhanced billing service with cycle tracking

2. **BudGateway Service (Rust)**
   - `usage_limit/limiter.rs`: Local cache with cycle detection
   - `usage_limit/middleware.rs`: Request interception
   - Automatic reset detection based on `billing_cycle_start` changes

3. **Redis**
   - Central storage for usage limits
   - Cache clear signals for immediate updates
   - TTL-based expiration for temporary data

## Key Features

### 1. Automatic Cycle Detection

The gateway automatically detects when a billing cycle has been reset by comparing the `billing_cycle_start` timestamp:

```rust
if cached.billing_cycle_start != info.billing_cycle_start {
    // Billing cycle has reset - use new values directly
    cached.tokens_used = info.tokens_used;
    cached.cost_used = info.cost_used;
}
```

### 2. Delta Tracking

Usage is tracked using delta calculations to handle concurrent updates:

```python
# In services.py
"tokens_used": tokens_used,
"prev_tokens_used": prev_tokens_used,
"cost_used": cost_used,
"prev_cost_used": prev_cost_used,
```

Gateway calculates deltas:
```rust
let token_delta = info.tokens_used - info.prev_tokens_used;
cached.tokens_used = (cached.tokens_used + token_delta).max(info.tokens_used);
```

### 3. Manual Reset API

Admin endpoints for manual usage reset:

- `POST /billing/reset/{user_id}` - Reset specific user
- `POST /billing/reset-all` - Reset all users
- `POST /billing/reset-expired` - Reset expired cycles

### 4. Cache Invalidation

Immediate cache clearing across all gateways:

```python
# Send clear signal
clear_key = f"usage_limit_clear:{user_id}"
await redis_client.setex(clear_key, 10, "1")
```

Gateway monitors for clear signals:
```rust
if redis_client.exists(&clear_key).await.unwrap_or(0) > 0 {
    cache.invalidate(&user_id).await;
    redis_client.del(&clear_key).await.ok();
}
```

### 5. Background Tasks

Two background tasks ensure system consistency:

1. **Usage Sync Task** (every 5 seconds)
   - Syncs usage limits from database to Redis
   - Ensures all active users have current limits

2. **Billing Reset Task** (every hour)
   - Checks for expired billing cycles
   - Automatically resets usage for new cycles

## Data Flow

1. **Normal Operation**
   ```
   Request → Gateway → Check Local Cache → Allow/Deny
                ↓ (periodic)
           Redis Sync → Update Cache
   ```

2. **Billing Cycle Reset**
   ```
   New Cycle → BudApp Reset → Redis Update → Clear Signal
                                    ↓
                          Gateway Detects → Cache Reset
   ```

## Usage Patterns

### Automatic Reset on Cycle Change

When a user's billing cycle expires:
1. Background task detects expiration
2. Calls `reset_user_usage()`
3. Updates Redis with new cycle dates
4. Sends cache clear signal
5. Gateway invalidates cache and reloads

### Manual Admin Reset

```bash
# Reset specific user
curl -X POST http://localhost:8000/billing/reset/{user_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"reason": "Manual adjustment"}'

# Reset all users
curl -X POST http://localhost:8000/billing/reset-all \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Testing Reset Functionality

Run the test script:
```bash
python test_billing_cycle_reset.py
```

This tests:
- Basic cycle reset simulation
- Delta tracking after reset
- API endpoint functionality
- Cache invalidation

## Configuration

### Environment Variables

```bash
# Redis configuration
REDIS_URL=redis://localhost:6379

# Sync intervals
USAGE_SYNC_INTERVAL=5  # seconds
BILLING_RESET_CHECK_INTERVAL=3600  # seconds (1 hour)
```

### Cache Settings

Gateway cache configuration:
```rust
UsageLimiterConfig {
    cache_size: 10000,  // Maximum cached users
    cache_ttl_secs: 300,  // 5 minute TTL
    redis_refresh_interval_secs: 60,  // Redis check interval
}
```

## Monitoring

### Key Metrics

1. **Reset Operations**
   - Count of automatic resets
   - Count of manual resets
   - Reset failures

2. **Cache Performance**
   - Cache hit rate
   - Clear signal processing time
   - Sync lag between Redis and cache

3. **Usage Tracking**
   - Delta calculation accuracy
   - Reconciliation frequency
   - Drift detection

### Logging

Important log messages:
```
INFO: Reset usage for user {user_id}: {reason}
INFO: Billing cycle reset detected for user {user_id}
INFO: Cache clear signal processed for user {user_id}
WARN: Failed to reset usage for user {user_id}: {error}
```

## Troubleshooting

### Common Issues

1. **Usage not resetting**
   - Check Redis connectivity
   - Verify background tasks are running
   - Check billing_cycle_start dates

2. **Cache not clearing**
   - Ensure clear signals are being sent
   - Check gateway Redis connection
   - Verify cache TTL settings

3. **Delta tracking drift**
   - Monitor reconciliation logic
   - Check for concurrent updates
   - Verify prev_* fields are updating

### Verification Script

Run verification:
```bash
./verify_billing_reset.sh
```

This checks:
- All implementation files exist
- API endpoints are registered
- Background tasks are integrated
- Gateway compilation succeeds

## Security Considerations

1. **Admin-Only Reset**: Manual reset endpoints require admin authentication
2. **Audit Logging**: All reset operations are logged with user and reason
3. **Data Integrity**: Delta tracking prevents data loss during resets
4. **Fail-Open**: System allows requests if unable to verify limits

## Future Enhancements

1. **Webhook Notifications**: Notify users when cycles reset
2. **Grace Period**: Allow temporary over-quota usage at cycle end
3. **Prorated Resets**: Support mid-cycle plan changes
4. **Usage Reports**: Generate cycle-end usage summaries
5. **Distributed Locking**: Prevent concurrent reset operations
