# RBAC Model

> **Version:** 1.1
> **Last Updated:** 2026-01-25
> **Status:** Current Implementation
> **Audience:** Administrators, security engineers

---

## 1. Overview

Bud AI Foundry implements Role-Based Access Control (RBAC) with:
- Hierarchical user roles (SUPER_ADMIN, ADMIN, DEVELOPER, DEVOPS, TESTER)
- Resource-based permissions using scope format (resource:action)
- Keycloak integration for realm-based role management

---

## 2. Role Hierarchy

```
┌──────────────────────────────────────────────────────────────┐
│                      PLATFORM LEVEL                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    SUPER_ADMIN                         │  │
│  │   • Full platform access                               │  │
│  │   • Manage all tenants                                 │  │
│  │   • System configuration                               │  │
│  └────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│                       TENANT LEVEL                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                      ADMIN                             │  │
│  │   • Tenant settings                                    │  │
│  │   • User management                                    │  │
│  │   • All projects in tenant                             │  │
│  └────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│                     OPERATIONAL LEVEL                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                     DEVOPS                             │  │
│  │   • Cluster management                                 │  │
│  │   • Infrastructure configuration                       │  │
│  │   • Deployment operations                              │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                    DEVELOPER                           │  │
│  │   • Project development                                │  │
│  │   • Model deployment                                   │  │
│  │   • API usage                                          │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                     TESTER                             │  │
│  │   • Testing and QA                                     │  │
│  │   • Benchmark execution                                │  │
│  │   • Model evaluation                                   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Role Definitions

**Location:** `budapp/commons/constants.py` - `UserRoleEnum`

```python
class UserRoleEnum(Enum):
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    DEVELOPER = "developer"
    DEVOPS = "devops"
    TESTER = "tester"
```

### 3.1 SUPER_ADMIN

**Scope:** Platform-wide

| Resource | View | Manage | Special |
|----------|------|--------|---------|
| Tenants | Yes | Yes | - |
| Users (all) | Yes | Yes | Force password reset |
| Projects (all) | Yes | Yes | - |
| Clusters (all) | Yes | Yes | - |
| Models (all) | Yes | Yes | - |
| Endpoints (all) | Yes | Yes | - |
| System Config | Yes | Yes | - |
| Audit Logs | Yes | - | Export |

**Assignment:** Manual, by existing SUPER_ADMIN only

### 3.2 ADMIN

**Scope:** Single tenant (Keycloak realm)

| Resource | View | Manage | Special |
|----------|------|--------|---------|
| Tenant Settings | Yes | Yes | - |
| Users (tenant) | Yes | Yes | Invite, deactivate |
| Projects (tenant) | Yes | Yes | - |
| Clusters (tenant) | Yes | Yes | - |
| Models (tenant) | Yes | Yes | - |
| Endpoints (tenant) | Yes | Yes | - |
| Billing (tenant) | Yes | Yes | - |
| Audit Logs (tenant) | Yes | - | Export |

**Assignment:** By SUPER_ADMIN or existing tenant ADMIN

### 3.3 DEVOPS

**Scope:** Tenant infrastructure

| Resource | View | Manage | Special |
|----------|------|--------|---------|
| Clusters | Yes | Yes | Register, delete |
| Endpoints | Yes | Yes | Deploy, undeploy |
| Infrastructure | Yes | Yes | - |
| Projects | Yes | Limited | - |
| Models | Yes | - | - |

**Assignment:** By ADMIN

### 3.4 DEVELOPER

**Scope:** Project development

| Resource | View | Manage | Special |
|----------|------|--------|---------|
| Projects | Yes | Yes | Create, update |
| Credentials | Yes | Yes | Create, rotate |
| Endpoints | Yes | Yes | Deploy |
| Models | Yes | Limited | - |
| Playground | Yes | Yes | Use |
| Routers | Yes | Yes | - |

**Assignment:** By ADMIN (default role for new users)

### 3.5 TESTER

**Scope:** Testing and benchmarks

| Resource | View | Manage | Special |
|----------|------|--------|---------|
| Projects | Yes | - | - |
| Models | Yes | - | - |
| Benchmarks | Yes | Yes | Execute |
| Endpoints | Yes | - | Invoke |
| Playground | Yes | Yes | Use |

**Assignment:** By ADMIN

---

## 4. Permission Levels

### 4.1 Permission Enum

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

### 4.2 Permission Scopes

| Scope | Description |
|-------|-------------|
| `view` | Read-only access to the resource |
| `manage` | Full control (create, update, delete) |
| `benchmark` | Execute benchmarks (model-specific) |
| `access` | Client API access |

### 4.3 Resource Type Matrix

| Resource Type | view | manage | Notes |
|---------------|------|--------|-------|
| `model` | View model details | Add, update, delete models | `benchmark` scope for evaluation |
| `project` | View project | Create, update, delete projects | - |
| `endpoint` | View endpoints | Deploy, undeploy, configure | - |
| `cluster` | View clusters | Register, update, delete | - |
| `user` | View users | Create, update, deactivate | - |
| `benchmark` | View benchmarks | Run, manage benchmarks | - |

---

## 5. Access Control Matrix

### 5.1 API Endpoint Permissions

| Endpoint | Method | Required Role/Permission |
|----------|--------|--------------------------|
| `/projects` | GET | Any authenticated |
| `/projects` | POST | ADMIN, DEVELOPER |
| `/projects/{id}` | GET | project:view |
| `/projects/{id}` | PUT | project:manage |
| `/projects/{id}` | DELETE | ADMIN |
| `/projects/{id}/endpoints` | GET | project:view |
| `/projects/{id}/endpoints` | POST | endpoint:manage |
| `/endpoints/{id}` | GET | endpoint:view |
| `/endpoints/{id}/deploy` | POST | endpoint:manage |
| `/endpoints/{id}/undeploy` | POST | endpoint:manage |
| `/endpoints/{id}` | DELETE | endpoint:manage |
| `/credentials` | GET | project:view |
| `/credentials` | POST | project:manage |
| `/credentials/{id}` | DELETE | project:manage |
| `/users` | GET | ADMIN |
| `/users` | POST | ADMIN |
| `/clusters` | GET | cluster:view |
| `/clusters` | POST | cluster:manage (ADMIN, DEVOPS) |
| `/models` | GET | model:view |
| `/models` | POST | model:manage |

### 5.2 UI Feature Access

| Feature | SUPER_ADMIN | ADMIN | DEVOPS | DEVELOPER | TESTER |
|---------|-------------|-------|--------|-----------|--------|
| Tenant Settings | Yes | Yes | - | - | - |
| User Management | Yes | Yes | - | - | - |
| Project Creation | Yes | Yes | - | Yes | - |
| Project Settings | Yes | Yes | - | Yes | - |
| Cluster Management | Yes | Yes | Yes | - | - |
| Endpoint Deployment | Yes | Yes | Yes | Yes | - |
| Model Testing (Playground) | Yes | Yes | Yes | Yes | Yes |
| API Key Creation | Yes | Yes | Yes | Yes | - |
| View Dashboards | Yes | Yes | Yes | Yes | Yes |
| View Audit Logs | Yes | Yes | - | - | - |
| Run Benchmarks | Yes | Yes | - | - | Yes |

---

## 6. Permission Assignment

### 6.1 Role Assignment via Keycloak

User roles are managed through Keycloak realm roles. When a user is created or updated, their role is synced with Keycloak:

```python
# Role assignment happens via Keycloak API
keycloak.assign_realm_role(user_id, realm_name, role_name)
```

**Requirements:**
- Caller must be ADMIN or SUPER_ADMIN
- Role must be a valid UserRoleEnum value
- SUPER_ADMIN role can only be assigned by existing SUPER_ADMIN

### 6.2 Permission Check

**Location:** `budapp/commons/permission_handler.py`

```python
@require_permissions(roles=UserRoleEnum.ADMIN)
async def admin_only_route():
    pass

@require_permissions(permissions=[PermissionEnum.PROJECT_MANAGE])
async def project_manage_route():
    pass
```

### 6.3 Role Hierarchy Check

```python
# Super admin bypasses all permission checks
if current_user.role == UserRoleEnum.SUPER_ADMIN:
    return True

# Admin has tenant-wide access
if current_user.role == UserRoleEnum.ADMIN:
    return is_same_tenant(current_user, resource)
```

---

## 7. Special Access Patterns

### 7.1 Project Owner

The user who creates a project automatically receives ADMIN permission:

```python
async def create_project(self, request: ProjectCreate, user: User):
    project = await self._create_project(request)

    # Auto-grant admin to creator
    await permission_service.grant(
        user_id=user.id,
        resource_type="project",
        resource_id=project.id,
        level=PermissionEnum.ADMIN
    )

    return project
```

### 7.2 Inherited Access

When a user has permission on a parent resource, they inherit access to children:

```python
async def check_permission(
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    required: PermissionEnum
) -> bool:
    # Check direct permission
    if await has_direct_permission(user_id, resource_type, resource_id, required):
        return True

    # Check parent permission (e.g., project for endpoint)
    parent = await get_parent_resource(resource_type, resource_id)
    if parent:
        return await check_permission(user_id, parent.type, parent.id, required)

    return False
```

### 7.3 System Resources

Some resources are system-owned and have special access rules:

| Resource | Access Rule |
|----------|-------------|
| System models | Read access for all authenticated users |
| Public endpoints | Invoke access based on API key |
| Shared prompts | Read access for all project members |

---

## 8. Audit Trail

All permission changes are logged:

```python
{
    "action": "GRANT_PERMISSION",
    "resource_type": "permission",
    "resource_id": "permission-uuid",
    "user_id": "granter-uuid",
    "details": {
        "target_user": "grantee-uuid",
        "resource_type": "project",
        "resource_id": "project-uuid",
        "permission_level": "edit"
    },
    "timestamp": "2026-01-23T10:00:00Z"
}
```

---

## 9. Best Practices

### 9.1 Role Assignment Guidelines

| Scenario | Recommended Role |
|----------|------------------|
| Platform administrator | SUPER_ADMIN |
| Organization administrator | ADMIN |
| Infrastructure engineer | DEVOPS |
| Software developer | DEVELOPER |
| QA engineer | TESTER |
| External auditor | TESTER (time-limited, read-only)

### 9.2 Principle of Least Privilege

1. Start with VIEWER and upgrade as needed
2. Use project-level permissions, not tenant-level
3. Grant time-limited access when possible
4. Regular access reviews (quarterly recommended)

### 9.3 Access Review Checklist

- [ ] Review all ADMIN role assignments
- [ ] Verify PROJECT_ADMIN assignments are current
- [ ] Remove access for departed users
- [ ] Check for over-privileged service accounts
- [ ] Audit permission grant/revoke history

---

## 10. Implementation Details

### 10.1 Permission Check Flow

```python
# budapp/commons/permission_handler.py

async def require_permission(
    resource_type: str,
    resource_id: UUID,
    required: PermissionEnum
):
    """Decorator for permission-protected routes."""

    async def dependency(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
    ):
        # Super admin bypass
        if current_user.role == UserRoleEnum.SUPER_ADMIN:
            return True

        # Check permission
        has_perm = await check_permission(
            session, current_user.id,
            resource_type, resource_id, required
        )

        if not has_perm:
            raise HTTPException(403, "Permission denied")

        return True

    return dependency
```

### 10.2 Permission Query

```python
# budapp/permissions/crud.py

async def get_user_permissions(
    session: AsyncSession,
    user_id: UUID,
    resource_type: Optional[str] = None
) -> List[Permission]:
    """Get all permissions for a user."""

    query = select(Permission).where(Permission.user_id == user_id)

    if resource_type:
        query = query.where(Permission.resource_type == resource_type)

    result = await session.execute(query)
    return result.scalars().all()
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated to reflect actual implementation - corrected roles (SUPER_ADMIN, ADMIN, DEVELOPER, DEVOPS, TESTER), permission format (resource:action with view/manage scopes) |
