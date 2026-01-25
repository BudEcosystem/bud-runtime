# Audit Logging Architecture

> **Version:** 1.1
> **Last Updated:** 2026-01-25
> **Status:** Current Implementation
> **Audience:** Security engineers, compliance officers, auditors

---

## 1. Overview

Bud AI Foundry implements comprehensive audit logging with cryptographic integrity protection through individual record hashing. Each audit record includes a SHA-256 hash for tamper detection. This document describes what is logged, where logs are stored, and how to extract audit evidence.

> **Note:** Hash chain mechanism (linking records via `previous_hash`) is planned but not yet implemented. See TECH_DEBT.md SEC-016 for status.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   budapp    │  │ budcluster  │  │   budsim    │              │
│  │  audit_ops  │  │   logging   │  │   logging   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LOGGING LAYER                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Structured Logging (structlog)             │    │
│  │   • JSON format                                         │    │
│  │   • Request ID correlation                              │    │
│  │   • User context                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │                                │
          ▼                                ▼
┌─────────────────────┐        ┌─────────────────────┐
│    PostgreSQL       │        │       Loki          │
│   (Audit Trail)     │        │  (Application Logs) │
│  • Hash chain       │        │  • Aggregation      │
│  • Immutable        │        │  • Search           │
│  • Structured       │        │  • Retention        │
└─────────────────────┘        └─────────────────────┘
```

---

## 3. Audit Trail (budapp)

### 3.1 Data Model

**Location:** `budapp/audit_ops/models.py`

```python
class AuditTrail(Base, TimestampMixin):
    __tablename__ = "audit_trail"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=True)
    actioned_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=True)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    previous_state: Mapped[dict] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict] = mapped_column(JSONB, nullable=True)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Note: created_at and modified_at provided by TimestampMixin
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier for the audit record |
| `user_id` | ID of the user who performed the action (nullable for system actions) |
| `actioned_by` | ID of the admin who performed action on behalf of another user |
| `action` | Type of action performed (CREATE, UPDATE, DELETE, etc.) |
| `resource_type` | Type of resource affected (PROJECT, MODEL, ENDPOINT, etc.) |
| `resource_id` | ID of the affected resource |
| `resource_name` | Name of the affected resource for display and search |
| `timestamp` | When the action occurred |
| `ip_address` | IP address from which the action was performed |
| `details` | Additional context about the action in JSON format |
| `previous_state` | State of the resource before the action (for updates) |
| `new_state` | State of the resource after the action (for creates/updates) |
| `record_hash` | SHA-256 hash of record data for integrity verification |

### 3.2 Audited Actions

| Category | Actions |
|----------|---------|
| Authentication | `LOGIN`, `LOGOUT`, `LOGIN_FAILED`, `TOKEN_REFRESH`, `PASSWORD_CHANGE`, `PASSWORD_RESET` |
| User Management | `CREATE_USER`, `UPDATE_USER`, `DELETE_USER`, `ACTIVATE_USER`, `DEACTIVATE_USER` |
| Tenant | `CREATE_TENANT`, `UPDATE_TENANT`, `DELETE_TENANT` |
| Project | `CREATE_PROJECT`, `UPDATE_PROJECT`, `DELETE_PROJECT` |
| Endpoint | `CREATE_ENDPOINT`, `UPDATE_ENDPOINT`, `DELETE_ENDPOINT`, `DEPLOY_ENDPOINT`, `UNDEPLOY_ENDPOINT` |
| Cluster | `REGISTER_CLUSTER`, `UPDATE_CLUSTER`, `DELETE_CLUSTER` |
| Model | `ADD_MODEL`, `UPDATE_MODEL`, `DELETE_MODEL`, `DEPLOY_MODEL` |
| Credential | `CREATE_CREDENTIAL`, `UPDATE_CREDENTIAL`, `DELETE_CREDENTIAL`, `ROTATE_CREDENTIAL` |
| Permission | `GRANT_PERMISSION`, `REVOKE_PERMISSION`, `UPDATE_PERMISSION` |
| Billing | `UPDATE_BILLING`, `QUOTA_EXCEEDED` |

### 3.3 Resource Types

| Resource Type | Description |
|---------------|-------------|
| `USER` | User accounts |
| `TENANT` | Tenant organizations |
| `PROJECT` | Projects within tenants |
| `ENDPOINT` | Model deployment endpoints |
| `CLUSTER` | Kubernetes clusters |
| `MODEL` | ML models |
| `CREDENTIAL` | API credentials |
| `PERMISSION` | Access permissions |
| `BILLING` | Billing records |
| `ROUTER` | Request routers |
| `PROMPT` | Prompt templates |
| `GUARDRAIL` | Guardrail configurations |

---

## 4. Record Integrity Verification

### 4.1 Hash Mechanism

Each audit record includes a `record_hash` field containing a SHA-256 hash of the record's key fields. This enables detection of any tampering with audit data.

> **Note:** Hash chain mechanism (linking records via `previous_hash`) is planned but not yet implemented. Current implementation verifies individual records only. See TECH_DEBT.md SEC-016.

### 4.2 Hash Calculation

**Location:** `budapp/audit_ops/hash_utils.py`

The hash is calculated from the following fields:
- `action`
- `resource_type`
- `resource_id`
- `user_id`
- `timestamp`
- `details`

```python
def calculate_audit_hash(
    action: str,
    resource_type: str,
    resource_id: Optional[UUID],
    user_id: Optional[UUID],
    timestamp: datetime,
    details: Optional[dict],
) -> str:
    """Calculate SHA-256 hash of audit record fields."""

    # Serialize deterministically
    hash_input = json.dumps({
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "user_id": str(user_id) if user_id else None,
        "timestamp": timestamp.isoformat(),
        "details": details,
    }, sort_keys=True, separators=(',', ':'))

    return hashlib.sha256(hash_input.encode()).hexdigest()
```

### 4.3 Integrity Verification

**Location:** `budapp/audit_ops/services.py`

```python
def verify_audit_record_integrity(self, audit_id: UUID) -> Tuple[bool, str]:
    """Verify the integrity of an audit record using its hash.

    Args:
        audit_id: ID of the audit record to verify

    Returns:
        Tuple of (is_valid, message) indicating verification status
    """
    record = self.data_manager.get_audit_record_by_id(audit_id)
    if not record:
        return False, f"Audit record with ID {audit_id} not found"

    return verify_audit_integrity(record)

def find_tampered_records(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Find audit records that may have been tampered with.

    Returns list of records where stored hash doesn't match recalculated hash.
    """
```

---

## 5. Immutability Protection

### 5.1 SQLAlchemy Event Listener

**Location:** `budapp/audit_ops/models.py`

Currently, only UPDATE prevention is implemented via SQLAlchemy event listener:

```python
@event.listens_for(AuditTrail, "before_update", propagate=True)
def receive_before_update(mapper, connection, target):
    """Prevent updates to audit trail records.

    Audit trail records should be immutable. This event listener
    raises an exception if an update is attempted.
    """
    raise ValueError("Audit trail records cannot be updated. They are immutable.")
```

> **Note:** DELETE prevention via event listener is not yet implemented. See TECH_DEBT.md SEC-017. Currently, deletion is only prevented via application-level controls.

### 5.2 Database Constraints (Recommended)

For production environments, the following database constraints should be applied:

```sql
-- Prevent direct modification (additional layer)
REVOKE UPDATE, DELETE ON audit_trail FROM app_user;

-- Only allow INSERT
GRANT INSERT ON audit_trail TO app_user;
GRANT SELECT ON audit_trail TO app_user;
```

> **Note:** Database-level constraints are not automatically applied by the application. They must be configured by the DBA during deployment.

---

## 6. Logging Implementation

### 6.1 Creating Audit Records

**Location:** `budapp/audit_ops/audit_logger.py`

```python
def log_audit(
    session: AsyncSession,
    action: AuditActionEnum,
    resource_type: AuditResourceTypeEnum,
    resource_id: Optional[UUID] = None,
    resource_name: Optional[str] = None,
    user_id: Optional[UUID] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
    success: bool = True
) -> None:
    """Log an audit event."""

    # Extract context from request
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    # Queue audit record creation
    audit_service = AuditService(session)
    asyncio.create_task(
        audit_service.create_audit_record(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            user_id=user_id,
            details={**(details or {}), "success": success},
            ip_address=ip_address,
            user_agent=user_agent
        )
    )
```

### 6.2 Usage in Routes

```python
@router.post("/projects")
async def create_project(
    request: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    http_request: Request = None
):
    project = await project_service.create(request, current_user)

    log_audit(
        session=session,
        action=AuditActionEnum.CREATE_PROJECT,
        resource_type=AuditResourceTypeEnum.PROJECT,
        resource_id=project.id,
        resource_name=project.name,
        user_id=current_user.id,
        details={"project_type": request.project_type},
        request=http_request
    )

    return project
```

---

## 7. Application Logging

### 7.1 Structured Logging Configuration

**Location:** `budapp/commons/logging.py`

```python
import structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

def get_logger(name: str):
    return structlog.get_logger(name)
```

### 7.2 Log Format

```json
{
  "timestamp": "2026-01-23T10:30:00.000Z",
  "level": "info",
  "logger": "budapp.auth.services",
  "event": "user_login",
  "user_id": "uuid",
  "email": "user@example.com",
  "ip_address": "192.168.1.1",
  "request_id": "req-uuid",
  "duration_ms": 150
}
```

### 7.3 Log Levels

| Level | Use Case |
|-------|----------|
| DEBUG | Detailed debugging information |
| INFO | Normal operations, significant events |
| WARNING | Unexpected but handled conditions |
| ERROR | Error conditions requiring attention |
| CRITICAL | System-level failures |

---

## 8. Log Aggregation (Loki)

### 8.1 Log Shipping

Services ship logs to Loki via:
- Stdout/stderr → Kubernetes log driver → Promtail → Loki

### 8.2 Label Strategy

```yaml
labels:
  app: budapp
  namespace: bud-system
  pod: budapp-xxx
  container: budapp
  environment: production
```

### 8.3 Query Examples

```logql
# Find all login failures
{app="budapp"} |= "LOGIN_FAILED"

# Find errors for specific user
{app="budapp"} | json | user_id="uuid" level="error"

# Count requests by endpoint
sum by (endpoint) (
  count_over_time({app="budapp"} | json | endpoint != "" [1h])
)
```

---

## 9. Retention and Archival

### 9.1 Retention Policy

| Log Type | Hot Storage | Archive | Total Retention |
|----------|-------------|---------|-----------------|
| Audit Trail | Indefinite (PostgreSQL) | - | Indefinite |
| Application Logs | 30 days (Loki) | 1 year (S3) | 1 year |
| Security Events | 90 days (Loki) | 7 years (S3) | 7 years |
| Debug Logs | 7 days | - | 7 days |

### 9.2 Audit Export

```python
# Export audit records
@router.get("/audit/export")
async def export_audit(
    start_date: datetime,
    end_date: datetime,
    format: str = "json",  # json, csv
    current_user: User = Depends(get_current_user),
):
    # Requires ADMIN role
    if current_user.role not in [UserRoleEnum.SUPER_ADMIN, UserRoleEnum.ADMIN]:
        raise HTTPException(403, "Admin access required")

    records = await audit_service.get_records(start_date, end_date)

    if format == "csv":
        return StreamingResponse(
            generate_csv(records),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit.csv"}
        )

    return records
```

---

## 10. Compliance Requirements

### 10.1 What Must Be Logged

| Requirement | Logged Data |
|-------------|-------------|
| Who | user_id, email (from JWT) |
| What | action, resource_type |
| When | timestamp (UTC) |
| Where | ip_address, user_agent |
| How | details (context) |
| Outcome | success flag |

### 10.2 Framework Requirements

| Framework | Requirement | Status |
|-----------|-------------|--------|
| SOC 2 CC7.2 | Audit events captured | Implemented |
| ISO 27001 A.12.4.1 | Event logging | Implemented |
| PCI DSS 10.2 | Audit trails | Implemented |
| GDPR Art. 30 | Processing records | Partial |
| HIPAA 164.312(b) | Audit controls | Implemented |

---

## 11. API Reference

### 11.1 Audit Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/audit` | GET | List audit records (paginated) |
| `/audit/{id}` | GET | Get specific audit record |
| `/audit/export` | GET | Export audit records |
| `/audit/verify/{id}` | POST | Verify individual record integrity |
| `/audit/verify/batch` | POST | Verify multiple records integrity |
| `/audit/stats` | GET | Get audit statistics |

### 11.2 Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | datetime | Filter from date |
| `end_date` | datetime | Filter to date |
| `action` | string | Filter by action type |
| `resource_type` | string | Filter by resource type |
| `resource_id` | UUID | Filter by resource |
| `user_id` | UUID | Filter by user |
| `page` | int | Page number |
| `page_size` | int | Records per page |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated to reflect actual implementation - hash chain not implemented, only individual record hashing; delete prevention not implemented; corrected data model fields |
