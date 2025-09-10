# OAuth Integration Guide

This document provides comprehensive guidance for implementing and using the OAuth SSO integration in the Bud Runtime platform.

## Overview

The OAuth integration enables Single Sign-On (SSO) authentication with multiple external providers:
- Google OAuth 2.0
- LinkedIn OAuth 2.0
- GitHub OAuth 2.0
- Microsoft Entra (Azure AD) OAuth 2.0

The implementation leverages Keycloak's identity brokering capabilities while maintaining the existing multi-tenant architecture.

## Architecture

### Components

1. **Keycloak Identity Brokering**: Handles OAuth flows and user attribute mapping
2. **Database Models**: Track OAuth sessions, provider configurations, and user links
3. **API Endpoints**: Public OAuth flow endpoints and admin configuration endpoints
4. **Security Layer**: PKCE implementation, state validation, and domain restrictions

### Database Schema

```sql
-- OAuth session tracking
CREATE TABLE oauth_sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    provider VARCHAR(50) NOT NULL,
    state VARCHAR(255) UNIQUE NOT NULL,
    code_verifier VARCHAR(128), -- For PKCE
    redirect_uri TEXT,
    tenant_id UUID REFERENCES tenants(id),
    expires_at TIMESTAMP NOT NULL,
    completed BOOLEAN DEFAULT false
);

-- Tenant OAuth configuration
CREATE TABLE tenant_oauth_configs (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    client_secret_encrypted TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    allowed_domains TEXT[],
    auto_create_users BOOLEAN DEFAULT false,
    config_data JSONB
);

-- User OAuth provider links
CREATE TABLE user_oauth_providers (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP,
    provider_data JSONB,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add OAuth providers to users table
ALTER TABLE users ADD COLUMN auth_providers JSONB DEFAULT '[]';
```

## API Endpoints

### Public OAuth Endpoints

#### Initiate OAuth Login
```http
POST /api/v1/auth/oauth/login
```

**Request:**
```json
{
  "provider": "google",
  "tenantId": "uuid-optional",
  "redirectUri": "https://app.example.com/callback"
}
```

**Response:**
```json
{
  "code": 200,
  "message": "OAuth login initiated successfully",
  "data": {
    "authUrl": "https://keycloak.example.com/auth/broker/google/login?state=...",
    "state": "secure-state-parameter",
    "expiresAt": "2024-01-01T12:00:00Z"
  }
}
```

#### Handle OAuth Callback
```http
GET /api/v1/auth/oauth/callback?code=...&state=...
```

**Response (Success):**
```json
{
  "code": 200,
  "message": "OAuth authentication successful",
  "data": {
    "accessToken": "jwt-token",
    "refreshToken": "refresh-token",
    "expiresIn": 3600,
    "tokenType": "Bearer",
    "userInfo": {
      "provider": "google",
      "externalId": "google-user-id",
      "email": "user@example.com",
      "name": "User Name",
      "emailVerified": true
    },
    "isNewUser": false,
    "requiresLinking": false
  }
}
```

**Response (Account Linking Required):**
```json
{
  "code": 200,
  "message": "Account linking required",
  "data": {
    "requiresLinking": true,
    "userInfo": { ... }
  }
}
```

#### Get Available Providers
```http
GET /api/v1/auth/oauth/providers?tenant_id=uuid
```

**Response:**
```json
{
  "code": 200,
  "message": "OAuth providers retrieved successfully",
  "data": {
    "providers": [
      {
        "provider": "google",
        "enabled": true,
        "allowedDomains": ["company.com"],
        "autoCreateUsers": true,
        "iconUrl": "https://www.google.com/favicon.ico",
        "displayName": "Google"
      }
    ],
    "tenantId": "tenant-uuid"
  }
}
```

### Admin Configuration Endpoints

#### Configure OAuth Provider
```http
POST /api/v1/auth/admin/oauth/configure
```

**Headers:**
```
Authorization: Bearer admin-jwt-token
```

**Request:**
```json
{
  "tenantId": "tenant-uuid",
  "provider": "google",
  "clientId": "google-client-id",
  "clientSecret": "google-client-secret",
  "enabled": true,
  "allowedDomains": ["company.com", "partner.org"],
  "autoCreateUsers": false,
  "configData": {
    "hostedDomain": "company.com"
  }
}
```

#### Microsoft OAuth Configuration Example
```json
POST /api/v1/auth/admin/oauth/configure

{
  "tenantId": "your-tenant-id",
  "provider": "microsoft",
  "clientId": "azure-app-client-id",
  "clientSecret": "azure-app-client-secret",
  "enabled": true,
  "allowedDomains": ["company.com"],
  "autoCreateUsers": true,
  "configData": {
    "tenantId": "azure-tenant-id"  // Microsoft Azure AD tenant ID
  }
}
```

Note: For Microsoft provider, the `configData.tenantId` field specifies the Azure AD tenant ID. Use "common" to allow users from any Azure AD tenant.

#### Get OAuth Configurations
```http
GET /api/v1/auth/admin/oauth/configurations/{tenant_id}?enabled_only=true
```

#### Disable OAuth Provider
```http
PUT /api/v1/auth/admin/oauth/disable/{tenant_id}/{provider}
```

## Setup Guide

### 1. Provider Configuration

#### Google OAuth 2.0
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   ```
   https://your-keycloak.com/auth/realms/{realm}/broker/google/endpoint
   ```

#### LinkedIn OAuth 2.0
1. Go to [LinkedIn Developer Portal](https://developer.linkedin.com/)
2. Create a new app
3. Request "Sign In with LinkedIn" permissions
4. Configure redirect URLs:
   ```
   https://your-keycloak.com/auth/realms/{realm}/broker/linkedin/endpoint
   ```

#### GitHub OAuth 2.0
1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Create a new OAuth app
3. Set Authorization callback URL:
   ```
   https://your-keycloak.com/auth/realms/{realm}/broker/github/endpoint
   ```

#### Microsoft Entra (Azure AD)
1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to Azure Active Directory > App registrations
3. Create new registration
4. Configure redirect URI:
   ```
   https://your-keycloak.com/auth/realms/{realm}/broker/microsoft/endpoint
   ```

### 2. Keycloak Configuration

The system automatically configures Keycloak identity providers when you use the admin API. Manual configuration steps:

1. **Create Identity Provider:**
   ```bash
   # Example for Google
   curl -X POST "https://keycloak.example.com/auth/admin/realms/{realm}/identity-provider/instances" \
   -H "Authorization: Bearer admin-token" \
   -H "Content-Type: application/json" \
   -d '{
     "alias": "google",
     "providerId": "google",
     "enabled": true,
     "config": {
       "clientId": "your-google-client-id",
       "clientSecret": "your-google-client-secret"
     }
   }'
   ```

2. **Configure Attribute Mappers:**
   - Email mapper: `email` → `email`
   - First name mapper: `given_name` → `firstName`
   - Last name mapper: `family_name` → `lastName`
   - Username mapper: `${CLAIM.email}` → `username`

### 3. Environment Configuration

Add OAuth-related environment variables:

```bash
# OAuth encryption key for storing provider secrets
OAUTH_ENCRYPTION_KEY=base64-encoded-fernet-key

# Keycloak configuration (existing)
KEYCLOAK_SERVER_URL=https://your-keycloak.com/auth
KEYCLOAK_ADMIN_USERNAME=admin
KEYCLOAK_ADMIN_PASSWORD=admin-password
KEYCLOAK_REALM_NAME=master
```

### 4. Database Migration

Run the OAuth migration:

```bash
alembic -c ./budapp/alembic.ini upgrade head
```

## Usage Examples

### Frontend Integration

#### React/JavaScript Example
```javascript
// Initiate OAuth login
const initiateOAuthLogin = async (provider) => {
  const response = await fetch('/api/v1/auth/oauth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider })
  });

  const data = await response.json();

  // Redirect to OAuth provider
  window.location.href = data.data.authUrl;
};

// Handle OAuth callback (on callback page)
const handleOAuthCallback = async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const state = urlParams.get('state');

  if (code && state) {
    const response = await fetch(`/api/v1/auth/oauth/callback?code=${code}&state=${state}`);
    const data = await response.json();

    if (data.data.requiresLinking) {
      // Show account linking UI
      showAccountLinkingModal(data.data.userInfo);
    } else {
      // Store tokens and redirect to app
      localStorage.setItem('accessToken', data.data.accessToken);
      localStorage.setItem('refreshToken', data.data.refreshToken);
      window.location.href = '/dashboard';
    }
  }
};
```

### Admin Configuration

#### Configure OAuth Provider
```python
import requests

# Configure Google OAuth for a tenant
response = requests.post(
    'https://api.example.com/api/v1/auth/admin/oauth/configure',
    headers={'Authorization': 'Bearer admin-token'},
    json={
        'tenantId': 'tenant-uuid',
        'provider': 'google',
        'clientId': 'google-client-id',
        'clientSecret': 'google-client-secret',
        'enabled': True,
        'allowedDomains': ['company.com'],
        'autoCreateUsers': False,
        'configData': {
            'hostedDomain': 'company.com'
        }
    }
)
```

## Security Features

### PKCE (Proof Key for Code Exchange)
- Code verifier and challenge generated for each OAuth session
- Prevents authorization code interception attacks
- Stored securely in database with session state

### State Parameter Validation
- Cryptographically secure state generation
- Prevents CSRF attacks
- Session expiration (15 minutes default)
- One-time use validation

### Domain Restrictions
- Configure allowed email domains per tenant per provider
- Prevents unauthorized access from external domains
- Supports multiple domains per configuration

### Token Security
- Provider tokens encrypted before storage
- Separate encryption key for OAuth secrets
- Token refresh handling for supported providers

### Redirect URI Validation
- Whitelist allowed redirect URIs
- Prevent open redirect vulnerabilities
- Sanitization of callback URLs

## Error Handling

### Error Codes
```typescript
enum OAuthErrorCode {
  PROVIDER_ERROR = "provider_error",
  PROVIDER_NOT_CONFIGURED = "provider_not_configured",
  PROVIDER_DISABLED = "provider_disabled",
  INVALID_STATE = "invalid_state",
  STATE_EXPIRED = "state_expired",
  INVALID_CODE = "invalid_code",
  ACCOUNT_EXISTS = "account_exists",
  ACCOUNT_NOT_FOUND = "account_not_found",
  ACCOUNT_ALREADY_LINKED = "account_already_linked",
  EMAIL_NOT_VERIFIED = "email_not_verified",
  DOMAIN_NOT_ALLOWED = "domain_not_allowed",
  CONFIG_ERROR = "configuration_error",
  INTERNAL_ERROR = "internal_error"
}
```

### User-Friendly Messages
```javascript
const errorMessages = {
  'provider_error': 'We couldn\'t connect to the provider. Please try again later.',
  'provider_not_configured': 'This login method is not configured for your organization.',
  'invalid_state': 'Your login session has expired. Please try logging in again.',
  'domain_not_allowed': 'Your email domain is not allowed. Please use an authorized email address.',
  // ... more messages
};
```

## Testing

### Unit Tests
```bash
# Run OAuth-specific tests
pytest tests/test_oauth_integration.py -v
pytest tests/test_oauth_routes.py -v

# Run with coverage
pytest tests/test_oauth_*.py --cov=budapp.auth.oauth_services --cov-report=html
```

### Integration Testing
```python
# Example test case
async def test_complete_oauth_flow():
    # 1. Initiate OAuth login
    response = await client.post("/api/v1/auth/oauth/login", json={
        "provider": "google",
        "tenantId": str(tenant.id)
    })

    # 2. Simulate OAuth callback
    state = response.json()["data"]["state"]
    callback_response = await client.get(
        f"/api/v1/auth/oauth/callback?code=test-code&state={state}"
    )

    # 3. Verify user creation and tokens
    assert callback_response.status_code == 200
    assert "accessToken" in callback_response.json()["data"]
```

## Monitoring and Analytics

### Metrics to Track
- OAuth login attempts by provider
- Success/failure rates per provider
- Account linking requests
- Domain restriction blocks
- Session expiration rates

### Logging
```python
# OAuth events are logged with structured data
logger.info("OAuth login initiated", extra={
    "provider": "google",
    "tenant_id": tenant_id,
    "user_id": user_id,
    "event": "oauth_login_initiated"
})
```

## Troubleshooting

### Common Issues

#### Provider Configuration
- **Issue**: "Provider not configured" error
- **Solution**: Verify OAuth provider is configured for the tenant via admin API

#### Token Issues
- **Issue**: Invalid or expired tokens
- **Solution**: Check provider token expiration, implement refresh logic

#### Domain Restrictions
- **Issue**: "Domain not allowed" error
- **Solution**: Add user's email domain to allowed domains list

#### Keycloak Integration
- **Issue**: Identity provider not found in Keycloak
- **Solution**: Verify Keycloak realm configuration and provider setup

### Debug Mode
```bash
# Enable OAuth debug logging
export LOG_LEVEL=DEBUG
export OAUTH_DEBUG=true
```

## Future Enhancements

### Planned Features
1. **SAML Integration**: Support for SAML 2.0 providers
2. **Just-in-Time Provisioning**: Advanced user attribute mapping
3. **Multi-Factor Authentication**: Integration with provider MFA
4. **Audit Logging**: Comprehensive OAuth event tracking
5. **Provider Health Monitoring**: Real-time provider status checks

### API Versioning
- Current version: `v1`
- Backward compatibility maintained for 2 major versions
- Migration guides provided for breaking changes

## Support

For issues and questions:
1. Check the troubleshooting guide above
2. Review server logs for detailed error information
3. Verify provider and Keycloak configurations
4. Contact platform administrators for tenant-specific issues

---

This integration provides enterprise-grade OAuth SSO capabilities while maintaining security best practices and multi-tenant architecture requirements.
