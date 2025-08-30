# 🚀 OAuth Integration Deployment Guide

This document provides comprehensive step-by-step instructions for deploying the OAuth SSO integration in the Bud Runtime platform.

## Table of Contents
1. [Database Migration](#1-📊-database-migration)
2. [Environment Configuration](#2-🔧-environment-configuration)
3. [OAuth Provider Setup](#3-🔐-oauth-provider-setup)
4. [Configure OAuth Providers via API](#4-🏗️-configure-oauth-providers-via-api)
5. [Testing Strategy](#5-🧪-testing-strategy)
6. [Production Deployment Checklist](#6-🎯-production-deployment-checklist)
7. [Post-Deployment Validation](#7-🔄-post-deployment-validation)
8. [Rollback Plan](#8-📋-rollback-plan)
9. [Documentation and Training](#9-📚-documentation-and-training)
10. [Future Enhancements](#10-🔮-future-enhancements)

## 1. 📊 Database Migration

### Run the Migration
```bash
# Navigate to the budapp service directory
cd services/budapp

# Run the OAuth migration
alembic -c ./budapp/alembic.ini upgrade head

# Verify migration success
alembic -c ./budapp/alembic.ini current
```

### Verify Database Schema
```sql
-- Connect to your PostgreSQL database and verify tables were created
\dt oauth_sessions
\dt tenant_oauth_configs
\dt user_oauth_providers

-- Check the new column was added to users table
\d users
-- Should show auth_providers JSONB column

-- Verify indexes were created
\di idx_users_auth_providers
\di idx_user_oauth_providers_user_provider
```

### Rollback Plan (if needed)
```bash
# If migration fails, rollback
alembic -c ./budapp/alembic.ini downgrade -1

# Check current revision
alembic -c ./budapp/alembic.ini current
```

## 2. 🔧 Environment Configuration

### Required Environment Variables
Add these to your `.env` file:

```bash
# OAuth Security - Generate a new Fernet key
# Run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
OAUTH_ENCRYPTION_KEY=your-base64-fernet-key-here

# Optional: OAuth debug logging
OAUTH_DEBUG=false
LOG_LEVEL=INFO

# Existing Keycloak settings (verify these are correct)
KEYCLOAK_SERVER_URL=https://your-keycloak.com/auth
KEYCLOAK_ADMIN_USERNAME=admin
KEYCLOAK_ADMIN_PASSWORD=your-admin-password
KEYCLOAK_REALM_NAME=master
KEYCLOAK_VERIFY_SSL=true

# Default realm for OAuth (usually matches your main tenant)
DEFAULT_REALM_NAME=your-default-realm
```

### Generate Encryption Key
```python
# Run this script to generate a secure encryption key
from cryptography.fernet import Fernet
import base64

key = Fernet.generate_key()
print(f"OAUTH_ENCRYPTION_KEY={key.decode()}")
```

### Validate Configuration
```bash
# Test that all environment variables are accessible
python -c "
from budapp.commons.config import app_settings
print('Keycloak URL:', app_settings.keycloak_server_url)
print('Default Realm:', app_settings.default_realm_name)
print('OAuth Encryption Key configured:', hasattr(app_settings, 'oauth_encryption_key'))
"
```

## 3. 🔐 OAuth Provider Setup

### Google OAuth 2.0 Setup

1. **Google Cloud Console Configuration**:
   ```bash
   # Go to: https://console.cloud.google.com/
   # 1. Create project or select existing
   # 2. Enable Google+ API and Google Identity API
   # 3. Go to Credentials > Create Credentials > OAuth 2.0 Client ID
   ```

2. **Configure Redirect URIs**:
   ```
   https://your-keycloak.com/auth/realms/{realm-name}/broker/google/endpoint
   ```

3. **Note Client Credentials**:
   ```bash
   GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   ```

### LinkedIn OAuth 2.0 Setup

1. **LinkedIn Developer Portal**:
   ```bash
   # Go to: https://developer.linkedin.com/
   # 1. Create new app
   # 2. Request "Sign In with LinkedIn using OpenID Connect" product
   # 3. Add redirect URLs in Auth section
   ```

2. **Configure Redirect URL**:
   ```
   https://your-keycloak.com/auth/realms/{realm-name}/broker/linkedin/endpoint
   ```

### GitHub OAuth 2.0 Setup

1. **GitHub Settings**:
   ```bash
   # Go to: Settings > Developer settings > OAuth Apps > New OAuth App
   # Application name: Your App Name
   # Homepage URL: https://your-app.com
   # Authorization callback URL: (see below)
   ```

2. **Callback URL**:
   ```
   https://your-keycloak.com/auth/realms/{realm-name}/broker/github/endpoint
   ```

### Microsoft Entra (Azure AD) Setup

1. **Azure Portal Configuration**:
   ```bash
   # Go to: https://portal.azure.com/
   # 1. Azure Active Directory > App registrations > New registration
   # 2. Name: Your App Name
   # 3. Supported account types: Choose based on requirements
   # 4. Redirect URI: Web platform (see below)
   ```

2. **Redirect URI**:
   ```
   https://your-keycloak.com/auth/realms/{realm-name}/broker/microsoft/endpoint
   ```

3. **Generate Client Secret**:
   ```bash
   # In your app registration:
   # Certificates & secrets > New client secret
   # Copy the VALUE (not the Secret ID)
   ```

## 4. 🏗️ Configure OAuth Providers via API

### Create Admin Authentication
```bash
# First, get an admin JWT token
curl -X POST "https://your-api.com/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{
  "email": "admin@yourcompany.com",
  "password": "admin-password"
}'

# Extract the access token from response
ADMIN_TOKEN="your-jwt-token-here"
```

### Configure Google OAuth
```bash
curl -X POST "https://your-api.com/api/v1/auth/admin/oauth/configure" \
-H "Authorization: Bearer $ADMIN_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "tenantId": "your-tenant-uuid",
  "provider": "google",
  "clientId": "your-google-client-id.apps.googleusercontent.com",
  "clientSecret": "your-google-client-secret",
  "enabled": true,
  "allowedDomains": ["yourcompany.com", "partner.com"],
  "autoCreateUsers": false,
  "configData": {
    "hostedDomain": "yourcompany.com"
  }
}'
```

### Configure LinkedIn OAuth
```bash
curl -X POST "https://your-api.com/api/v1/auth/admin/oauth/configure" \
-H "Authorization: Bearer $ADMIN_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "tenantId": "your-tenant-uuid",
  "provider": "linkedin",
  "clientId": "your-linkedin-client-id",
  "clientSecret": "your-linkedin-client-secret",
  "enabled": true,
  "allowedDomains": null,
  "autoCreateUsers": true
}'
```

### Configure GitHub OAuth
```bash
curl -X POST "https://your-api.com/api/v1/auth/admin/oauth/configure" \
-H "Authorization: Bearer $ADMIN_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "tenantId": "your-tenant-uuid",
  "provider": "github",
  "clientId": "your-github-client-id",
  "clientSecret": "your-github-client-secret",
  "enabled": true,
  "allowedDomains": null,
  "autoCreateUsers": true
}'
```

### Configure Microsoft OAuth
```bash
curl -X POST "https://your-api.com/api/v1/auth/admin/oauth/configure" \
-H "Authorization: Bearer $ADMIN_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "tenantId": "your-tenant-uuid",
  "provider": "microsoft",
  "clientId": "your-azure-app-id",
  "clientSecret": "your-azure-client-secret",
  "enabled": true,
  "allowedDomains": ["yourcompany.com"],
  "autoCreateUsers": false,
  "configData": {
    "tenant": "your-azure-tenant-id"
  }
}'
```

### Verify Configuration
```bash
# Get all configured providers
curl -X GET "https://your-api.com/api/v1/auth/admin/oauth/configurations/your-tenant-uuid" \
-H "Authorization: Bearer $ADMIN_TOKEN"

# Get public provider list (what users see)
curl -X GET "https://your-api.com/api/v1/auth/oauth/providers?tenant_id=your-tenant-uuid"
```

## 5. 🧪 Testing Strategy

### Unit Tests
```bash
# Run OAuth-specific tests
cd services/budapp
pytest tests/test_oauth_integration.py -v
pytest tests/test_oauth_routes.py -v

# Run with coverage report
pytest tests/test_oauth_*.py --cov=budapp.auth.oauth_services --cov=budapp.auth.oauth_error_handler --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Integration Testing
```bash
# Test with real Keycloak instance (if available)
pytest tests/test_oauth_integration.py::TestOAuthLoginInitiation::test_initiate_oauth_login_success -v --dapr-http-port 3510

# Test error scenarios
pytest tests/test_oauth_integration.py::TestOAuthCallback -v
```

### Manual API Testing
```bash
# Test OAuth flow initiation
curl -X POST "https://your-api.com/api/v1/auth/oauth/login" \
-H "Content-Type: application/json" \
-d '{
  "provider": "google",
  "tenantId": "your-tenant-uuid"
}'

# Expected response: auth URL and state parameter
# Visit the auth URL in browser to test full flow
```

### Frontend Integration Testing
```javascript
// Test OAuth initiation from frontend
const testOAuthFlow = async () => {
  try {
    const response = await fetch('/api/v1/auth/oauth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: 'google',
        tenantId: 'your-tenant-uuid'
      })
    });

    const data = await response.json();
    console.log('OAuth URL generated:', data.data.authUrl);

    // Open in new window for testing
    window.open(data.data.authUrl, '_blank');
  } catch (error) {
    console.error('OAuth flow failed:', error);
  }
};
```

## 6. 🎯 Production Deployment Checklist

### Pre-Deployment
- [ ] Database migration completed successfully
- [ ] All environment variables configured
- [ ] OAuth providers configured in external services
- [ ] OAuth providers configured via admin API
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Security review completed

### Security Checklist
- [ ] OAuth encryption key is secure and backed up
- [ ] Keycloak admin credentials are secure
- [ ] Provider client secrets are stored encrypted
- [ ] Domain restrictions configured appropriately
- [ ] Rate limiting is active on OAuth endpoints
- [ ] HTTPS is enforced for all OAuth callbacks

### Monitoring Setup
```python
# Add OAuth metrics monitoring
import structlog

logger = structlog.get_logger(__name__)

# Example metrics to track
oauth_metrics = {
    'oauth_login_attempts': 0,
    'oauth_login_successes': 0,
    'oauth_login_failures': 0,
    'oauth_providers_configured': 0,
    'oauth_account_links': 0
}
```

### Health Checks
```bash
# Add OAuth health check endpoint
curl -X GET "https://your-api.com/api/v1/health/oauth"

# Expected response:
{
  "status": "healthy",
  "providers_configured": 4,
  "keycloak_connection": "ok",
  "encryption_key_configured": true
}
```

## 7. 🔄 Post-Deployment Validation

### Functional Testing
1. **Test each OAuth provider**:
   ```bash
   # For each provider, test:
   # 1. Login initiation
   # 2. Provider redirect
   # 3. Callback handling
   # 4. User creation/authentication
   # 5. Token generation
   ```

2. **Test error scenarios**:
   ```bash
   # Test with:
   # - Disabled providers
   # - Invalid client credentials
   # - Expired sessions
   # - Domain restrictions
   # - Account conflicts
   ```

### User Acceptance Testing
1. **Create test accounts** in each OAuth provider
2. **Test complete user journeys**:
   - New user registration via OAuth
   - Existing user login via OAuth
   - Account linking for existing users
   - Multi-provider account linking

### Performance Testing
```bash
# Load test OAuth endpoints
ab -n 100 -c 10 -T 'application/json' -p oauth_payload.json \
https://your-api.com/api/v1/auth/oauth/login
```

## 8. 📋 Rollback Plan

### If Issues Occur
1. **Disable OAuth providers**:
   ```bash
   # Disable all OAuth providers quickly
   curl -X PUT "https://your-api.com/api/v1/auth/admin/oauth/disable/tenant-uuid/google" \
   -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

2. **Database rollback**:
   ```bash
   # Rollback migration if needed
   alembic -c ./budapp/alembic.ini downgrade oauth_support_20250731
   ```

3. **Revert environment changes**:
   ```bash
   # Remove OAuth environment variables
   # Restart services with previous configuration
   ```

## 9. 📚 Documentation and Training

### Update Documentation
- [ ] Update API documentation with OAuth endpoints
- [ ] Create user guides for OAuth login
- [ ] Document admin procedures for OAuth management
- [ ] Update troubleshooting guides

### Team Training
- [ ] Train support team on OAuth error scenarios
- [ ] Train DevOps team on OAuth deployment procedures
- [ ] Train development team on OAuth integration patterns

## 10. 🔮 Future Enhancements

### Short-term (Next Sprint)
- Monitor OAuth usage patterns
- Collect user feedback on OAuth experience
- Optimize OAuth flow performance
- Add more detailed analytics

### Medium-term (Next Quarter)
- Implement Just-in-Time (JIT) user provisioning
- Add support for additional OAuth providers
- Implement OAuth token refresh mechanisms
- Add OAuth session management UI

### Long-term (Next 6 Months)
- SAML 2.0 integration
- Advanced attribute mapping
- Multi-factor authentication integration
- Enterprise SSO features

## Troubleshooting Common Issues

### Provider Connection Errors
```bash
# Check Keycloak logs
kubectl logs -n keycloak keycloak-pod-name | grep -i error

# Verify provider configuration
curl -X GET "https://keycloak.com/auth/admin/realms/{realm}/identity-provider/instances/{provider}" \
-H "Authorization: Bearer admin-token"
```

### Token Encryption Issues
```python
# Test encryption key
from cryptography.fernet import Fernet
key = b'your-encryption-key'
f = Fernet(key)
test = f.encrypt(b"test")
print(f.decrypt(test))
```

### Session State Issues
```sql
-- Check OAuth sessions
SELECT * FROM oauth_sessions
WHERE state = 'problematic-state'
ORDER BY created_at DESC;

-- Clean up expired sessions
DELETE FROM oauth_sessions
WHERE expires_at < NOW() - INTERVAL '1 day';
```

---

This deployment guide ensures a smooth rollout of the OAuth integration while maintaining system security and reliability. Keep this document updated as the system evolves.
