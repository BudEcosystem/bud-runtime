# API Key Management Security Enhancements

This document describes the enhanced security features added to the API key management system in budapp.

## Overview

The API key management system has been extended with the following security enhancements:

1. **Secure Key Generation** - Cryptographically secure API keys using Python's `secrets` module
2. **Credential Types** - Support for different credential types (client_app, admin_app)
3. **IP Whitelisting** - Optional IP address restrictions per credential
4. **Enhanced Validation** - Comprehensive validation in service layer with security checks

## Database Schema Changes

### New Fields in `credential` Table

- `credential_type` (enum) - Type of credential: client_app or admin_app
- `ip_whitelist` (JSONB) - List of allowed IP addresses (optional)

## API Endpoints

### Existing Endpoints Enhanced

#### POST /credentials/
- Added `credential_type` parameter (default: client_app)
- Added `ip_whitelist` parameter for IP restrictions
- Uses secure key generation

#### GET /credentials/
- Returns credential type
- Shows IP whitelist if configured

#### DELETE /credentials/{id}
- Deletes the credential from the system

## Security Features

### Automatic Credential Type Mapping

Based on user type, the system automatically enforces appropriate credential types:

- **Client Users** (`user_type: CLIENT`): Always create `client_app` credentials regardless of request
- **Admin Users** (`user_type: ADMIN`): Can create any credential type (`client_app`, `admin_app`)

This ensures that client users cannot create admin credentials, maintaining proper access control.

### Secure Key Generation

API keys are now generated using cryptographically secure methods:

```python
# Format: bud_<type>_<base64_encoded_random>
# Example: bud_client_KJ8sN3mP9qR2tV5wX7yA1bC4dF6gH0jL
```

- 32 bytes (256 bits) of random data
- URL-safe base64 encoding
- Type prefix for easy identification

### IP Whitelisting

- Optional per-credential IP restrictions
- Supports multiple IPs per credential
- Validates client IP on each request
- Logs unauthorized access attempts

### Enhanced Validation

The service layer performs comprehensive checks:

1. Database validation
2. Expiry date validation
3. IP whitelist validation (if configured)
4. Credential type validation (if required)

## Usage Examples

### Creating a Credential with Security Features

```bash
curl -X POST "http://localhost:8000/credentials/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "project_id": "project-uuid",
    "credential_type": "client_app",
    "ip_whitelist": ["203.0.113.0", "203.0.113.1"],
    "expiry": 30
  }'
```


## Migration Notes

- Existing credentials are assigned `client_app` type by default
- No breaking changes to existing API
- Backward compatible with existing keys
- Gradual migration path available

## Performance Considerations

- Redis caching for fast validation
- Database indexes on key fields
- Asynchronous last_used_at updates

## Security Best Practices

1. **Key Storage**: Never store API keys in plain text
2. **Key Transmission**: Always use HTTPS
3. **Key Rotation**: Regularly rotate keys (future feature)
4. **IP Restrictions**: Use IP whitelisting for production keys
5. **Monitoring**: Monitor key usage and failed attempts
6. **Deletion**: Immediately delete compromised keys
