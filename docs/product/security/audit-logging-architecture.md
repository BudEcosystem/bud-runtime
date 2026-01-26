# Audit Logging Architecture

---

## 1. Overview

Bud AI Foundry implements comprehensive audit logging with cryptographic integrity protection through individual record hashing. Each audit record includes a SHA-256 hash for tamper detection. This document describes what is logged, where logs are stored, and how to extract audit evidence.

> **Note:** Hash chain mechanism (linking records via `previous_hash`) is planned but not yet implemented. See TECH_DEBT.md SEC-016 for status.

---

---

## 3. Audit Trail (budapp)

### 3.1 Data Model

**Location:** `budapp/audit_ops/models.py`

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

### 4.3 Integrity Verification

**Location:** `budapp/audit_ops/services.py`

---

## 5. Immutability Protection

### 5.1 SQLAlchemy Event Listener

**Location:** `budapp/audit_ops/models.py`

Currently, only UPDATE prevention is implemented via SQLAlchemy event listener:

> **Note:** DELETE prevention via event listener is not yet implemented. See TECH_DEBT.md SEC-017. Currently, deletion is only prevented via application-level controls.

### 5.2 Database Constraints (Recommended)

For production environments, the following database constraints should be applied:

> **Note:** Database-level constraints are not automatically applied by the application. They must be configured by the DBA during deployment.

---

## 6. Logging Implementation

### 6.1 Creating Audit Records

**Location:** `budapp/audit_ops/audit_logger.py`

---

## 7. Application Logging

### 7.1 Structured Logging Configuration

**Location:** `budapp/commons/logging.py`

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

---

## 9. Retention and Archival

### 9.1 Retention Policy

| Log Type | Hot Storage | Archive | Total Retention |
|----------|-------------|---------|-----------------|
| Audit Trail | Indefinite (PostgreSQL) | - | Indefinite |
| Application Logs | 30 days (Loki) | 1 year (S3) | 1 year |
| Security Events | 90 days (Loki) | 7 years (S3) | 7 years |
| Debug Logs | 7 days | - | 7 days |

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
