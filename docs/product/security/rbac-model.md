# RBAC Model

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Current Implementation
> **Audience:** Administrators, security engineers

---

## 1. Overview

Bud AI Foundry implements Role-Based Access Control (RBAC) with:
- Hierarchical roles at platform, tenant, and project levels
- Fine-grained permissions on individual resources
- Permission inheritance within resource hierarchies

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
│                      PROJECT LEVEL                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  PROJECT_ADMIN                         │  │
│  │   • Project configuration                              │  │
│  │   • Deploy/manage models                               │  │
│  │   • Manage project users                               │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                      USER                              │  │
│  │   • Use deployed models                                │  │
│  │   • View project resources                             │  │
│  │   • Create credentials                                 │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                     VIEWER                             │  │
│  │   • Read-only access                                   │  │
│  │   • View configurations                                │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Role Definitions

### 3.1 SUPER_ADMIN

**Scope:** Platform-wide

| Resource | Create | Read | Update | Delete | Special |
|----------|--------|------|--------|--------|---------|
| Tenants | Yes | Yes | Yes | Yes | - |
| Users (all) | Yes | Yes | Yes | Yes | Force password reset |
| Projects (all) | Yes | Yes | Yes | Yes | - |
| Clusters (all) | Yes | Yes | Yes | Yes | - |
| Models (all) | Yes | Yes | Yes | Yes | - |
| Endpoints (all) | Yes | Yes | Yes | Yes | - |
| System Config | - | Yes | Yes | - | - |
| Audit Logs | - | Yes | - | - | Export |

**Assignment:** Manual, by existing SUPER_ADMIN only

### 3.2 ADMIN

**Scope:** Single tenant

| Resource | Create | Read | Update | Delete | Special |
|----------|--------|------|--------|--------|---------|
| Tenant Settings | - | Yes | Yes | - | - |
| Users (tenant) | Yes | Yes | Yes | Yes | Invite, deactivate |
| Projects (tenant) | Yes | Yes | Yes | Yes | - |
| Clusters (tenant) | Yes | Yes | Yes | Yes | - |
| Models (tenant) | Yes | Yes | Yes | Yes | - |
| Endpoints (tenant) | Yes | Yes | Yes | Yes | - |
| Billing (tenant) | - | Yes | Yes | - | - |
| Audit Logs (tenant) | - | Yes | - | - | Export |

**Assignment:** By SUPER_ADMIN or existing tenant ADMIN

### 3.3 PROJECT_ADMIN

**Scope:** Single project

| Resource | Create | Read | Update | Delete | Special |
|----------|--------|------|--------|--------|---------|
| Project Settings | - | Yes | Yes | - | - |
| Project Users | - | Yes | Yes | - | Grant/revoke permissions |
| Credentials | Yes | Yes | Yes | Yes | - |
| Endpoints | Yes | Yes | Yes | Yes | Deploy, undeploy |
| Routers | Yes | Yes | Yes | Yes | - |
| Prompts | Yes | Yes | Yes | Yes | - |
| Guardrails | Yes | Yes | Yes | Yes | - |
| Models (project) | Yes | Yes | Yes | Yes | - |

**Assignment:** By ADMIN or existing PROJECT_ADMIN

### 3.4 USER

**Scope:** Single project

| Resource | Create | Read | Update | Delete | Special |
|----------|--------|------|--------|--------|---------|
| Project Settings | - | Yes | - | - | - |
| Credentials (own) | Yes | Yes | Yes | Yes | - |
| Endpoints | - | Yes | - | - | Invoke |
| Routers | - | Yes | - | - | Invoke |
| Prompts | - | Yes | - | - | Use |
| Guardrails | - | Yes | - | - | - |
| Models | - | Yes | - | - | - |
| Playground | - | Yes | - | - | Use |

**Assignment:** By PROJECT_ADMIN or ADMIN

### 3.5 VIEWER

**Scope:** Single project

| Resource | Create | Read | Update | Delete | Special |
|----------|--------|------|--------|--------|---------|
| All project resources | - | Yes | - | - | - |

**Assignment:** By PROJECT_ADMIN or ADMIN

---

## 4. Permission Levels

### 4.1 Permission Enum

```python
class PermissionEnum(str, Enum):
    VIEW = "view"       # Read-only access
    EDIT = "edit"       # Read + modify
    ADMIN = "admin"     # Full control including permission management
```

### 4.2 Permission Inheritance

```
Project ADMIN
    │
    ├── Endpoint ADMIN (inherited)
    │   └── Can manage all endpoints
    │
    ├── Credential ADMIN (inherited)
    │   └── Can manage all credentials
    │
    ├── Router ADMIN (inherited)
    │   └── Can manage all routers
    │
    └── Prompt ADMIN (inherited)
        └── Can manage all prompts
```

### 4.3 Resource Type Matrix

| Resource Type | VIEW | EDIT | ADMIN |
|---------------|------|------|-------|
| `project` | View project | Modify settings | Full control, grant permissions |
| `endpoint` | View endpoint | Deploy/undeploy | Delete, configure |
| `cluster` | View cluster | Update config | Register/delete |
| `credential` | View (masked) | Update | Delete |
| `router` | View routes | Modify routing | Delete |
| `prompt` | View prompts | Edit versions | Delete |
| `guardrail` | View config | Modify rules | Delete profiles |

---

## 5. Access Control Matrix

### 5.1 API Endpoint Permissions

| Endpoint | Method | Required Role/Permission |
|----------|--------|--------------------------|
| `/projects` | GET | Any authenticated |
| `/projects` | POST | ADMIN |
| `/projects/{id}` | GET | project:VIEW |
| `/projects/{id}` | PUT | project:EDIT |
| `/projects/{id}` | DELETE | ADMIN |
| `/projects/{id}/endpoints` | GET | project:VIEW |
| `/projects/{id}/endpoints` | POST | project:EDIT |
| `/endpoints/{id}` | GET | endpoint:VIEW |
| `/endpoints/{id}/deploy` | POST | endpoint:EDIT |
| `/endpoints/{id}/undeploy` | POST | endpoint:EDIT |
| `/endpoints/{id}` | DELETE | endpoint:ADMIN |
| `/credentials` | GET | project:VIEW |
| `/credentials` | POST | project:EDIT |
| `/credentials/{id}` | DELETE | credential:ADMIN |
| `/users` | GET | ADMIN |
| `/users` | POST | ADMIN |
| `/permissions` | POST | resource:ADMIN |
| `/permissions/{id}` | DELETE | resource:ADMIN |

### 5.2 UI Feature Access

| Feature | SUPER_ADMIN | ADMIN | PROJECT_ADMIN | USER | VIEWER |
|---------|-------------|-------|---------------|------|--------|
| Tenant Settings | Yes | Yes | - | - | - |
| User Management | Yes | Yes | - | - | - |
| Project Creation | Yes | Yes | - | - | - |
| Project Settings | Yes | Yes | Yes | - | - |
| Endpoint Deployment | Yes | Yes | Yes | - | - |
| Model Testing (Playground) | Yes | Yes | Yes | Yes | - |
| API Key Creation | Yes | Yes | Yes | Yes | - |
| View Dashboards | Yes | Yes | Yes | Yes | Yes |
| View Audit Logs | Yes | Yes | Yes | - | - |

---

## 6. Permission Assignment

### 6.1 Grant Permission

```python
# POST /permissions
{
    "user_id": "uuid",
    "resource_type": "project",
    "resource_id": "project-uuid",
    "permission_level": "edit"
}
```

**Requirements:**
- Caller must have ADMIN permission on the resource
- Cannot grant higher permission than caller has
- User must belong to same tenant

### 6.2 Revoke Permission

```python
# DELETE /permissions/{permission_id}
```

**Requirements:**
- Caller must have ADMIN permission on the resource
- Cannot revoke own permission (prevents lockout)

### 6.3 Bulk Permission Update

```python
# PUT /projects/{id}/permissions
{
    "permissions": [
        {"user_id": "uuid1", "level": "edit"},
        {"user_id": "uuid2", "level": "view"},
        {"user_id": "uuid3", "level": null}  # revoke
    ]
}
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
| Team lead / project owner | PROJECT_ADMIN |
| Developer using APIs | USER |
| Stakeholder needing visibility | VIEWER |
| External auditor | VIEWER (time-limited) |

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
