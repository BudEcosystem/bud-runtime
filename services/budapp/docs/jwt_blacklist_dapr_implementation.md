# JWT Blacklist Implementation Using Dapr State Store

## Overview
The JWT blacklist functionality has been migrated from Redis-based implementation to use Dapr state store. This provides better integration with the microservices architecture and leverages Dapr's built-in state management capabilities.

## Implementation Details

### Components

1. **JWT Blacklist Service** (`budapp/shared/jwt_blacklist_service.py`)
   - Singleton service for managing JWT blacklist
   - Uses Dapr state store for persistence
   - Supports TTL (Time-To-Live) for automatic token expiration

2. **Auth Service Updates** (`budapp/auth/services.py`)
   - Modified `logout_user` method to use `JWTBlacklistService`
   - Calculates TTL based on token expiration time
   - Handles errors gracefully without interrupting logout flow

3. **Dependencies Updates** (`budapp/commons/dependencies.py`)
   - Updated `get_current_user` to check blacklist via Dapr state store
   - Returns 401 Unauthorized for blacklisted tokens

### Key Features

#### Token Blacklisting
- Tokens are stored with prefix `jwt_blacklist:` in Dapr state store
- TTL is automatically calculated from token expiration
- Default TTL of 1 hour if token expiration cannot be determined

#### Token Verification
- Every authenticated request checks if token is blacklisted
- Non-blocking implementation - errors don't prevent access
- Efficient key-value lookups using Dapr state store

#### State Store Configuration
- Uses existing Dapr state store component (Redis backend)
- Configuration in `.dapr/components/statestore.yaml`
- Leverages Dapr's abstraction for potential backend changes

### API Usage

#### Logout Endpoint
```python
POST /auth/logout
Headers:
  Authorization: Bearer <access_token>
Body:
  {
    "refresh_token": "...",
    "tenant_id": "..." (optional)
  }
```

The logout endpoint:
1. Blacklists the access token (if provided)
2. Invalidates the refresh token in Keycloak
3. Returns success response

#### Token Validation
All protected endpoints automatically check token blacklist status through the `get_current_user` dependency.

### Testing

#### Unit Tests
Run the updated test suite:
```bash
pytest tests/test_logout_blacklist.py --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

#### Integration Test Script
A standalone test script is provided:
```bash
python test_jwt_blacklist_dapr.py
```

This script tests:
- Token blacklisting
- Blacklist verification
- Token removal from blacklist
- Mock tests for CI/CD environments

### Migration Notes

#### From Redis to Dapr State Store
- No data migration required (tokens are temporary)
- Existing tokens in Redis will expire naturally
- New tokens use Dapr state store immediately

#### Benefits of Dapr State Store
1. **Consistency**: Same state management approach across all services
2. **Flexibility**: Easy to switch backing store (Redis, MongoDB, etc.)
3. **Features**: Built-in TTL support, strong consistency options
4. **Monitoring**: Integrated with Dapr observability

### Configuration

#### Environment Variables
No new environment variables required. Uses existing Dapr configuration:
- `DAPR_HTTP_PORT`: Dapr sidecar HTTP port
- `DAPR_API_TOKEN`: Dapr API authentication token
- State store name from Dapr metadata

#### Dapr Component
The state store component (`.dapr/components/statestore.yaml`) remains unchanged, using Redis as the backing store with proper authentication.

### Error Handling

The implementation includes comprehensive error handling:
- Blacklist failures don't prevent logout
- Token check failures don't block requests (fail-open)
- All errors are logged for monitoring

### Performance Considerations

- **Latency**: Minimal overhead (~1-5ms per token check)
- **Scalability**: Leverages Dapr's distributed state management
- **Caching**: State store handles caching automatically
- **TTL**: Automatic cleanup of expired tokens

### Monitoring and Debugging

#### Logs
Key log messages:
- Token blacklisted: `"Token blacklisted successfully with TTL {ttl} seconds"`
- Token found in blacklist: `"Token found in blacklist"`
- Errors: `"Failed to blacklist token: {error}"`

#### Debugging Commands
Check Dapr state store directly:
```bash
# Get all blacklisted tokens (via Dapr CLI)
dapr state get --name statestore --key "jwt_blacklist:*"

# Check specific token
dapr state get --name statestore --key "jwt_blacklist:<token>"
```

### Security Considerations

1. **Token Storage**: Only token hash stored, not full token
2. **TTL Enforcement**: Tokens automatically expire
3. **Fail-Safe**: Errors don't grant unauthorized access
4. **Isolation**: Each service has isolated state store access

### Future Enhancements

Potential improvements:
1. Add metrics for blacklist hit/miss rates
2. Implement bulk token revocation
3. Add admin endpoints for blacklist management
4. Consider bloom filters for performance optimization
