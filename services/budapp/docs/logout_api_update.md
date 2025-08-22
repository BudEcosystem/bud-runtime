# Logout API Update - Token Blacklisting

## Overview
The logout functionality has been enhanced to properly invalidate access tokens by implementing a Redis-based token blacklist. This ensures that access tokens cannot be used after a user logs out, addressing the security issue where tokens remained valid post-logout.

## Changes Made

### 1. Authentication Header Support
**File**: `budapp/auth/auth_routes.py`
- Updated logout endpoint to accept access token from Authorization header
- Uses FastAPI's `HTTPBearer` security scheme for proper Swagger documentation
- Follows standard Bearer token format
- More secure than sending token in request body
- Shows lock icon in Swagger UI indicating authentication support

### 2. Logout Service Enhancement
**File**: `budapp/auth/services.py`
- Updated `logout_user` method to blacklist access tokens in Redis
- Calculates appropriate TTL based on token expiration
- Continues with logout even if blacklisting fails (graceful degradation)

### 3. Token Validation Update
**File**: `budapp/commons/dependencies.py`
- Modified `get_current_user` to check Redis blacklist before validating tokens
- Returns 401 Unauthorized if token is blacklisted

## API Changes

### Logout Endpoint
**Endpoint**: `POST /auth/logout`

**Headers**:
```
Authorization: Bearer <access_token>  (optional but recommended)
```

**Request Body**:
```json
{
  "refresh_token": "string",
  "tenant_id": "uuid (optional)"
}
```

## Client Implementation Guide

### Frontend/Client Updates
To take advantage of the enhanced security, update your logout implementation:

```javascript
// Example JavaScript implementation
async function logout() {
  const accessToken = localStorage.getItem('access_token');
  const refreshToken = localStorage.getItem('refresh_token');

  try {
    await fetch('/auth/logout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`  // Send token in header
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });

    // Clear local storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');

    // Redirect to login
    window.location.href = '/login';
  } catch (error) {
    console.error('Logout failed:', error);
  }
}
```

## Backward Compatibility
- The Authorization header is optional
- Existing clients that don't send the Authorization header will continue to work
- However, without the Authorization header, only the refresh token is invalidated in Keycloak
- Access tokens will remain valid until their natural expiration
- Clients should be updated to include the Authorization header for immediate token invalidation

## Security Benefits
1. **Immediate Invalidation**: Access tokens are immediately invalidated upon logout
2. **Defense in Depth**: Combines Keycloak refresh token invalidation with access token blacklisting
3. **Token Leak Mitigation**: Reduces the window of vulnerability if tokens are compromised
4. **Session Management**: Better control over user sessions

## Technical Implementation Details

### Redis Storage
- **Key Format**: `token_blacklist:{access_token}`
- **Value**: "1" (simple flag)
- **TTL**: Set to match token's remaining lifetime (exp - current_time)
- **Auto-cleanup**: Redis automatically removes entries after TTL expires

### Performance Considerations
- Minimal overhead: Single Redis GET operation per authenticated request
- Efficient storage: Only stores blacklisted tokens, not all tokens
- Auto-expiry: No manual cleanup needed

## Testing

### Manual Testing
Run the provided test script:
```bash
python test_logout.py http://localhost:8080
```

### Unit Tests
Run the new unit tests:
```bash
pytest tests/test_logout_blacklist.py --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

## Monitoring
Monitor Redis for blacklist entries:
```bash
redis-cli
> KEYS token_blacklist:*
> TTL token_blacklist:<token>
```

## Migration Checklist
- [ ] Update frontend/clients to send Authorization header in logout requests
- [ ] Deploy backend changes
- [ ] Test logout functionality
- [ ] Monitor Redis memory usage
- [ ] Update API documentation
- [ ] Notify API consumers of the enhancement

## Rollback Plan
If issues arise:
1. The feature is backward compatible - old clients will continue to work
2. To fully disable blacklist checking, comment out the Redis check in `get_current_user`
3. No database migrations are required, so no rollback needed there
