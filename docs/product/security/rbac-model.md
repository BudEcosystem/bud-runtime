# RBAC Model

---

## 1. Overview

Bud AI Foundry implements Role-Based Access Control (RBAC) with:
- Hierarchical user roles (SUPER_ADMIN, ADMIN, DEVELOPER, DEVOPS, TESTER)
- Resource-based permissions using scope format (resource:action)
- Keycloak integration for realm-based role management

---

---

## 3. Role Definitions

**Location:** `budapp/commons/constants.py` - `UserRoleEnum`

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

**Requirements:**
- Caller must be ADMIN or SUPER_ADMIN
- Role must be a valid UserRoleEnum value
- SUPER_ADMIN role can only be assigned by existing SUPER_ADMIN

### 6.2 Permission Check

**Location:** `budapp/commons/permission_handler.py`

---

## 7. Special Access Patterns

### 7.1 Project Owner

The user who creates a project automatically receives ADMIN permission:

### 7.2 Inherited Access

When a user has permission on a parent resource, they inherit access to children:

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
