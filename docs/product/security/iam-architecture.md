# IAM Architecture

> **Version:** 1.1
> **Last Updated:** 2026-01-25
> **Status:** Current Implementation
> **Audience:** Security engineers, administrators, integration developers

> **Implementation Status:** Core IAM functionality is implemented. External IdP federation (SAML 2.0/OIDC) is Keycloak capability but not configured. MFA, account lockout, and concurrent session limits are NOT enforced. See Section 10.2 for known limitations.

---

## 1. Overview

Bud AI Foundry uses Keycloak as its identity provider with a multi-tenant architecture supporting:
- JWT-based authentication
- Role-based access control (RBAC)
- OAuth 2.0 / OpenID Connect protocols
- External IdP federation (Keycloak capability, not configured)
- Service-to-service authentication

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL CLIENTS                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │   Browser   │  │  CLI/SDK    │  │  External   │                  │
│  │   (budadmin)│  │  (API)      │  │    App      │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          │ OIDC           │ OAuth 2.0      │ OAuth 2.0
          │                │                │
┌─────────┼────────────────┼────────────────┼─────────────────────────┐
│         │     IDENTITY LAYER              │                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────┐                │
│  │                   KEYCLOAK                      │                │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐   │                │
│  │  │  Master   │  │  Tenant A │  │  Tenant B │   │                │
│  │  │   Realm   │  │   Realm   │  │   Realm   │   │                │
│  │  └───────────┘  └───────────┘  └───────────┘   │                │
│  │        │              │              │          │                │
│  │        │    ┌─────────┴──────────┐   │          │                │
│  │        │    │   External IdP     │   │          │                │
│  │        │    │   (SAML/OIDC)      │   │          │                │
│  │        │    └────────────────────┘   │          │                │
│  └────────┼─────────────────────────────┼──────────┘                │
│           │ JWT Token                   │                           │
└───────────┼─────────────────────────────┼───────────────────────────┘
            │                             │
┌───────────┼─────────────────────────────┼───────────────────────────┐
│           │   APPLICATION LAYER         │                           │
│           ▼                             ▼                           │
│  ┌─────────────────────────────────────────────────┐                │
│  │                   budapp                        │                │
│  │  ┌───────────────┐  ┌───────────────┐          │                │
│  │  │ Token Validation│  │ Permission   │          │                │
│  │  │ (JWT Verify)    │  │ Enforcement  │          │                │
│  │  └───────────────┘  └───────────────┘          │                │
│  │           │                  │                  │                │
│  │           ▼                  ▼                  │                │
│  │  ┌───────────────┐  ┌───────────────┐          │                │
│  │  │ User Context  │  │  Permission   │          │                │
│  │  │   (Claims)    │  │    Store      │          │                │
│  │  └───────────────┘  └───────────────┘          │                │
│  └─────────────────────────────────────────────────┘                │
│                             │                                       │
│                             ▼                                       │
│  ┌─────────────────────────────────────────────────┐                │
│  │                  PostgreSQL                     │                │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────┐       │                │
│  │  │  User   │ │  Tenant │ │ Permission  │       │                │
│  │  │  Table  │ │  Table  │ │   Table     │       │                │
│  │  └─────────┘ └─────────┘ └─────────────┘       │                │
│  └─────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Identity Management

### 3.1 User Model

**Location:** `budapp/user_ops/models.py`

```python
class User(Base):
    id: UUID                    # Internal unique identifier
    auth_id: UUID               # Keycloak user ID (stored in auth_id field)
    email: str                  # Unique email address
    first_name: str             # Display name
    last_name: str              # Display name
    role: UserRoleEnum          # Global role
    status: UserStatusEnum      # ACTIVE, INACTIVE, PENDING
    tenant_client_id: UUID      # FK to TenantClient
    created_at: datetime
    updated_at: datetime
```

> **Note:** The Keycloak user ID is stored in the `auth_id` field (not `keycloak_id`).

### 3.2 Tenant Model

**Multi-tenancy Architecture:**

```python
class Tenant(Base):
    id: UUID
    name: str
    slug: str                   # URL-safe identifier
    realm_name: str             # Keycloak realm name
    created_at: datetime

class TenantClient(Base):
    id: UUID
    tenant_id: UUID             # FK to Tenant
    client_id: str              # Keycloak client ID
    client_named_id: str        # Human-readable name
    client_secret_encrypted: str # Encrypted client secret
    created_at: datetime

class TenantUserMapping(Base):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: UserRoleEnum          # Role within this tenant
```

### 3.3 Role Definitions

**Location:** `budapp/commons/constants.py` - `UserRoleEnum`

| Role | Scope | Capabilities |
|------|-------|--------------|
| `SUPER_ADMIN` | Platform | Full platform access, tenant management |
| `ADMIN` | Tenant | Tenant settings, user management, all projects |
| `DEVELOPER` | Project | Project development, model deployment, API usage |
| `DEVOPS` | Tenant | Cluster management, infrastructure, deployments |
| `TESTER` | Project | Testing, benchmarks, model evaluation |

```python
class UserRoleEnum(Enum):
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    DEVELOPER = "developer"
    DEVOPS = "devops"
    TESTER = "tester"
```

---

## 4. Authentication Flows

### 4.1 Web UI Authentication (Authorization Code Flow)

```
┌────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐
│Browser │     │budadmin │     │  budapp  │     │Keycloak │
└───┬────┘     └────┬────┘     └────┬─────┘     └────┬────┘
    │               │               │                │
    │ 1. Access     │               │                │
    │──────────────▶│               │                │
    │               │               │                │
    │ 2. Redirect to Keycloak       │                │
    │◀──────────────│               │                │
    │                                                │
    │ 3. Login Page                                  │
    │───────────────────────────────────────────────▶│
    │                                                │
    │ 4. Credentials                                 │
    │───────────────────────────────────────────────▶│
    │                                                │
    │ 5. Auth Code + Redirect                        │
    │◀───────────────────────────────────────────────│
    │                                                │
    │ 6. Auth Code  │               │                │
    │──────────────▶│               │                │
    │               │ 7. Exchange   │                │
    │               │──────────────▶│                │
    │               │               │ 8. Token       │
    │               │               │───────────────▶│
    │               │               │ 9. JWT         │
    │               │               │◀───────────────│
    │               │ 10. Set Cookie│                │
    │               │◀──────────────│                │
    │ 11. Redirect  │               │                │
    │◀──────────────│               │                │
```

### 4.2 API Authentication (Direct Grant / Client Credentials)

```
┌────────┐     ┌─────────┐     ┌──────────┐
│  CLI   │     │ budapp  │     │ Keycloak │
└───┬────┘     └────┬────┘     └────┬─────┘
    │               │               │
    │ 1. POST /auth/login           │
    │   (email, password)           │
    │──────────────▶│               │
    │               │ 2. Validate   │
    │               │──────────────▶│
    │               │ 3. Token      │
    │               │◀──────────────│
    │ 4. JWT Token  │               │
    │◀──────────────│               │
    │                               │
    │ 5. API Request + JWT          │
    │──────────────▶│               │
    │               │ 6. Validate   │
    │               │   (signature, │
    │               │    claims)    │
    │ 7. Response   │               │
    │◀──────────────│               │
```

### 4.3 Token Exchange (Cross-Tenant)

**Implementation:** `budapp/auth/token_exchange_service.py`

Used when a user needs to access resources in a different tenant:

```python
async def exchange_token(
    self,
    source_token: str,
    target_tenant: str,
) -> TokenExchangeResponse:
    """Exchange token for different tenant access."""
    # Validate source token
    # Check cross-tenant permission
    # Request new token from Keycloak
    # Return token for target tenant
```

---

## 5. Token Management

### 5.1 JWT Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "<key-id>"
  },
  "payload": {
    "exp": 1700000300,
    "iat": 1700000000,
    "jti": "<unique-token-id>",
    "iss": "https://keycloak.example.com/realms/{realm}",
    "aud": "bud-client",
    "sub": "<keycloak-user-id>",
    "typ": "Bearer",
    "azp": "bud-client",
    "session_state": "<session-id>",
    "scope": "openid email profile",
    "email_verified": true,
    "name": "John Doe",
    "preferred_username": "john@example.com",
    "email": "john@example.com",
    "realm_access": {
      "roles": ["user"]
    },
    "resource_access": {
      "bud-client": {
        "roles": ["project-admin"]
      }
    }
  }
}
```

### 5.2 Token Validation

**Location:** `budapp/commons/dependencies.py`

```python
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract and validate JWT, return user object."""

    # 1. Extract token from Authorization header
    token = extract_token(request.headers.get("Authorization"))

    # 2. Verify signature using Keycloak public key
    payload = jwt.decode(
        token,
        key=keycloak_public_key,
        algorithms=["RS256"],
        audience="bud-client"
    )

    # 3. Check blacklist
    if await jwt_blacklist.is_blacklisted(payload["jti"]):
        raise HTTPException(401, "Token revoked")

    # 4. Load user from database
    user = await user_manager.get_by_keycloak_id(payload["sub"])

    # 5. Verify user status
    if user.status != UserStatusEnum.ACTIVE:
        raise HTTPException(403, "User inactive")

    return user
```

### 5.3 Token Blacklisting

**Location:** `budapp/shared/jwt_blacklist_service.py`

```python
class JWTBlacklistService:
    """Manage token revocation via Dapr state store."""

    STATE_STORE = "statestore"
    KEY_PREFIX = "jwt_blacklist:"

    async def blacklist_token(self, jti: str, exp: int) -> None:
        """Add token to blacklist until expiration."""
        ttl = exp - int(time.time())
        if ttl > 0:
            await self.dapr.save_state(
                self.STATE_STORE,
                f"{self.KEY_PREFIX}{jti}",
                "revoked",
                metadata={"ttlInSeconds": str(ttl)}
            )

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if token is revoked."""
        result = await self.dapr.get_state(
            self.STATE_STORE,
            f"{self.KEY_PREFIX}{jti}"
        )
        return result.data is not None
```

### 5.4 Token Lifecycle

| Event | Access Token | Refresh Token | Blacklist |
|-------|--------------|---------------|-----------|
| Login | Created (5 min) | Created (30 min) | - |
| API Request | Validated | - | Checked |
| Refresh | New token | Rotated | Old added |
| Logout | - | - | Both added |
| Password Change | - | - | All user tokens |

---

## 6. Authorization

### 6.1 Permission Model

**Location:** `budapp/commons/constants.py` - `PermissionEnum`

The permission system uses a `resource:action` format with two primary scopes:

```python
class PermissionEnum(Enum):
    # Model permissions
    MODEL_VIEW = "model:view"
    MODEL_MANAGE = "model:manage"
    MODEL_BENCHMARK = "model:benchmark"

    # Project permissions
    PROJECT_VIEW = "project:view"
    PROJECT_MANAGE = "project:manage"

    # Endpoint permissions
    ENDPOINT_VIEW = "endpoint:view"
    ENDPOINT_MANAGE = "endpoint:manage"

    # Cluster permissions
    CLUSTER_VIEW = "cluster:view"
    CLUSTER_MANAGE = "cluster:manage"

    # User permissions
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"

    # Benchmark permissions
    BENCHMARK_VIEW = "benchmark:view"
    BENCHMARK_MANAGE = "benchmark:manage"

    # Client access
    CLIENT_ACCESS = "client:access"
```

**Permission Scopes:**

| Scope | Description |
|-------|-------------|
| `view` | Read-only access to the resource |
| `manage` | Full control (create, update, delete) |
| `benchmark` | Execute benchmarks (model-specific) |
| `access` | Client API access |

### 6.2 Permission Enforcement

**Location:** `budapp/commons/permission_handler.py`

```python
async def check_permission(
    session: AsyncSession,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    required_level: PermissionEnum
) -> bool:
    """Check if user has required permission on resource."""

    # Check global role first
    user = await get_user(session, user_id)
    if user.role == UserRoleEnum.SUPER_ADMIN:
        return True

    # Check specific permission
    permission = await get_permission(
        session, user_id, resource_type, resource_id
    )

    if not permission:
        return False

    return permission.level >= required_level
```

### 6.3 Route Protection

```python
# Example protected route
@router.post("/projects/{project_id}/endpoints")
async def create_endpoint(
    project_id: UUID,
    request: EndpointCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Check permission
    if not await check_permission(
        session, current_user.id, "project", project_id, PermissionEnum.EDIT
    ):
        raise HTTPException(403, "Permission denied")

    # Proceed with creation
    return await endpoint_service.create(project_id, request)
```

---

## 7. Service-to-Service Authentication

### 7.1 Dapr Service Invocation

```yaml
# Dapr configuration for service auth
apiVersion: dapr.io/v1alpha1
kind: Configuration
metadata:
  name: budconfig
spec:
  mtls:
    enabled: true
    workloadCertTTL: "24h"
  accessControl:
    defaultAction: deny
    trustDomain: "bud.local"
    policies:
      - appId: budapp
        defaultAction: allow
        trustDomain: "bud.local"
        operations:
          - name: /invoke/*
            httpVerb: ["*"]
            action: allow
```

### 7.2 Internal API Token

**Location:** `budapp/commons/internal_auth.py`

```python
async def verify_internal_token(request: Request) -> bool:
    """Verify request is from internal service."""
    token = request.headers.get("X-Internal-Token")
    if not token:
        return False
    return token == app_settings.internal_api_token
```

---

## 8. External IdP Integration

> **Implementation Status:** SAML 2.0 and OIDC federation are Keycloak capabilities but NOT currently configured in the platform. The configurations below are reference architecture for customer IdP integration.

### 8.1 SAML 2.0 (NOT CONFIGURED)

Keycloak supports SAML 2.0 identity provider federation:

| Setting | Value |
|---------|-------|
| Entity ID | `https://keycloak.example.com/realms/{realm}` |
| SSO URL | `https://keycloak.example.com/realms/{realm}/protocol/saml` |
| SLO URL | `https://keycloak.example.com/realms/{realm}/protocol/saml` |
| Certificate | Download from Keycloak admin |

### 8.2 OIDC Federation (NOT CONFIGURED)

For OIDC IdP integration:

```
Keycloak Admin → Identity Providers → Add Provider → OpenID Connect

- Alias: corporate-idp
- Authorization URL: https://idp.example.com/authorize
- Token URL: https://idp.example.com/token
- Client ID: keycloak-client
- Client Secret: <secret>
- Default Scopes: openid email profile
```

### 8.3 User Attribute Mapping

| IdP Claim | Keycloak Attribute | User Field |
|-----------|-------------------|------------|
| email | email | email |
| given_name | firstName | first_name |
| family_name | lastName | last_name |
| groups | groups | role (mapped) |

---

## 9. Session Management

### 9.1 Session Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| SSO Session Idle | 30 minutes | Idle timeout |
| SSO Session Max | 10 hours | Maximum session |
| Access Token Lifespan | 5 minutes | JWT validity |
| Refresh Token Lifespan | 30 minutes | Refresh validity |

### 9.2 Session Events

| Event | Action |
|-------|--------|
| Login | Create session, issue tokens |
| Idle Timeout | Require re-authentication |
| Max Lifetime | Force logout |
| Password Change | Invalidate all sessions |
| Admin Logout | Invalidate specific session |

---

## 10. Security Considerations

### 10.1 Implemented Controls

| Control | Implementation |
|---------|----------------|
| Token signature | RS256 with Keycloak keys |
| Token expiration | Short-lived access tokens |
| Token revocation | Blacklist via Dapr state |
| Credential encryption | AES-256 for client secrets |
| Session binding | JWT bound to session |

### 10.2 Known Limitations

| Gap | Risk | Mitigation |
|-----|------|------------|
| No MFA enforcement | Weak authentication | Enable MFA in Keycloak |
| No account lockout | Brute force | Configure in Keycloak |
| No session limits | Session hijacking | Add concurrent session limit |
| No IP binding | Token theft | Implement IP validation |

See `TECH_DEBT.md` for detailed tracking.

---

## 11. API Reference

### 11.1 Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Login with email/password |
| `/auth/logout` | POST | Logout and revoke tokens |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/me` | GET | Get current user info |
| `/auth/password/reset` | POST | Initiate password reset |
| `/auth/password/change` | POST | Change password |

### 11.2 User Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users` | GET | List users (admin) |
| `/users` | POST | Create user (admin) |
| `/users/{id}` | GET | Get user details |
| `/users/{id}` | PUT | Update user |
| `/users/{id}` | DELETE | Deactivate user |

### 11.3 Permission Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/permissions` | GET | List permissions |
| `/permissions` | POST | Grant permission |
| `/permissions/{id}` | DELETE | Revoke permission |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated to reflect actual implementation - corrected field name (auth_id not keycloak_id), role names, permission format (resource:action), noted IdP federation not configured |
