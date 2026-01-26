# Encryption Standards

---

## 1. Overview

This document specifies the encryption standards implemented in Bud AI Foundry for protecting data at rest and in transit.

**Summary:**
- **Asymmetric Encryption:** RSA with OAEP padding (key size configurable, typically 2048-4096 bits)
- **Symmetric Encryption:** AES-256 (Fernet implementation)
- **Hashing:** SHA-256, bcrypt for passwords
- **Transport:** TLS 1.2+ for all connections

---

## 2. Encryption at Rest

### 2.1 Credential Encryption

**Location:** `budapp/commons/security.py`

#### RSA Encryption (Asymmetric)

| Property | Value |
|----------|-------|
| Algorithm | RSA |
| Key Size | Configurable (2048-4096 bits, see key generation) |
| Padding | OAEP |
| Mask Generation | MGF1 |
| Hash Function | SHA-256 |
| Standard | PKCS#1 v2.1 |

> **Note:** Key size depends on the generated key. Default generation commands below use 4096 bits, but actual deployments may vary.

**Implementation:**

**Use Cases:**
- Client secrets (Keycloak)
- Short sensitive strings requiring key exchange

#### AES Encryption (Symmetric)

| Property | Value |
|----------|-------|
| Algorithm | AES |
| Key Size | 256 bits |
| Mode | CBC (via Fernet) |
| Authentication | HMAC-SHA256 (via Fernet) |
| Standard | FIPS 197 |

**Implementation:**

**Use Cases:**
- API credentials
- Configuration values
- Large data blobs

### 2.2 Cluster Credentials (budcluster)

**Method:** Dapr Crypto Component

| Property | Value |
|----------|-------|
| Component | Dapr cryptography building block |
| Backend | Local keys or cloud KMS |
| Algorithm | AES-256-GCM |
| Key Storage | File-based or KMS |

**Implementation:**
#### PostgreSQL

| Method | Description | When Used |
|--------|-------------|-----------|
| Column Encryption | Application-level (RSA/AES) | Credentials, secrets |
| TDE (Cloud) | Provider-managed | AWS RDS, Azure PostgreSQL |
| pgcrypto | PostgreSQL extension | Optional for self-managed |

#### ClickHouse

| Method | Description |
|--------|-------------|
| Disk Encryption | At storage layer |
| Network Encryption | TLS for connections |

#### MinIO

| Method | Description |
|--------|-------------|
| SSE-S3 | Server-side encryption with MinIO-managed keys |
| SSE-C | Server-side encryption with customer-provided keys |
| SSE-KMS | Server-side encryption with KMS integration |

### 2.4 Kubernetes Secrets

| Property | Value |
|----------|-------|
| Storage | etcd |
| Encryption | Provider-dependent |
| Access | RBAC controlled |

**Best Practice:** Enable etcd encryption at rest:

---

## 3. Encryption in Transit

### 3.1 TLS Configuration

| Property | Value |
|----------|-------|
| Minimum Version | TLS 1.2 |
| Preferred Version | TLS 1.3 |
| Certificate Type | RSA 2048 or ECDSA P-256 |
| Certificate Authority | Let's Encrypt or Enterprise CA |
#### 3.2 Service-to-Service mTLS

**Provider:** Dapr Sidecar

| Property | Value |
|----------|-------|
| Certificate Lifetime | 24 hours |
| Auto-Rotation | Yes |
| Trust Domain | Configurable |
| Clock Skew Allowance | 15 minutes |

**Configuration:**

### 3.3 Database Connections

| Database | Protocol | Certificate Verification |
|----------|----------|-------------------------|
| PostgreSQL | TLS | Required in production |
| ClickHouse | TLS | Required in production |
| Redis | TLS | Recommended |
| MongoDB | TLS | Required in production |

**Connection String Example (Recommended):**

> **Implementation Note:** Current connection strings may not enforce TLS verification. Verify `sslmode` is set to `require` or `verify-full` in production deployments.

---

## 4. Password Hashing

### 4.1 bcrypt Configuration

| Property | Value |
|----------|-------|
| Algorithm | bcrypt |
| Work Factor | 12 (default) |
| Salt | Auto-generated |
| Standard | bcrypt (OpenBSD) |

**Implementation:**

### 4.2 Integrity Hashing (SHA-256)

| Property | Value |
|----------|-------|
| Algorithm | SHA-256 |
| Output | 64 hex characters (256 bits) |
| Standard | FIPS 180-4 |

**Use Cases:**
- Audit log hash chain
- Data integrity verification
- Token hashing

**Implementation:**

---

## 5. Key Management

### 5.1 Key Types and Storage

| Key Type | Algorithm | Size | Storage | Rotation |
|----------|-----------|------|---------|----------|
| RSA Private | RSA | 4096-bit | File system | Manual |
| RSA Public | RSA | 4096-bit | File system | With private |
| AES Key | AES | 256-bit | File system | Manual |
| Dapr Crypto | AES-GCM | 256-bit | Dapr component | Manual |
| TLS Cert | RSA/ECDSA | 2048/256-bit | Kubernetes Secret | Auto (cert-manager) |
| JWT Signing | RS256 | 2048-bit | Keycloak | Per realm config |

### 5.2 Key Generation

**RSA Key Pair:**

**AES Key:**

### 5.3 Key Loading

**Location:** `budapp/commons/config.py`

> **Important:** The AES key is loaded from HEX encoding via the `AES_KEY_HEX` environment variable, not from a base64-encoded file. Ensure keys are stored in HEX format.

### 5.4 Key Rotation (Manual Process)

1. **Generate new keys:**

2. **Re-encrypt existing data:**

3. **Swap keys:**

4. **Restart services**

5. **Delete old key after verification**

---

## 6. Compliance Standards

### 6.1 Standards Compliance

| Standard | Requirement | Status |
|----------|-------------|--------|
| FIPS 140-2 | Validated crypto modules | Partial (uses OpenSSL) |
| FIPS 197 | AES | Compliant |
| FIPS 180-4 | SHA-256 | Compliant |
| PCI DSS 4.0 | Strong cryptography | Compliant |
| NIST SP 800-57 | Key management | Partial |

### 6.2 Algorithm Deprecation

| Algorithm | Status | Replacement |
|-----------|--------|-------------|
| MD5 | Deprecated | SHA-256 |
| SHA-1 | Deprecated | SHA-256 |
| DES | Deprecated | AES-256 |
| 3DES | Deprecated | AES-256 |
| RC4 | Deprecated | AES-GCM |
| RSA-1024 | Deprecated | RSA-2048+ |
| TLS 1.0/1.1 | Deprecated | TLS 1.2+ |

---

## 7. Security Recommendations

### 7.1 Implemented

- [x] AES-256 for symmetric encryption
- [x] RSA-4096 for asymmetric encryption
- [x] TLS 1.2+ for all connections
- [x] bcrypt for password hashing
- [x] SHA-256 for integrity
- [x] mTLS for service-to-service

### 7.2 Recommended Improvements

| Improvement | Priority | Reference |
|-------------|----------|-----------|
| Automated key rotation | Critical | SEC-003 |
| HSM integration | High | SEC-010 |
| FIPS 140-2 validated module | Medium | - |
| Key backup to KMS | Critical | SEC-010 |
| Certificate automation (cert-manager) | High | OPS-010 |

---

## 8. Data Classification and Handling

| Classification | Encryption at Rest | Encryption in Transit | Key Access |
|----------------|-------------------|----------------------|------------|
| Public | Optional | TLS | Any |
| Internal | Required (AES) | TLS | Service accounts |
| Confidential | Required (AES) | mTLS | Restricted |
| Restricted | Required (RSA+AES) | mTLS | Named individuals |

---

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated AES key loading (HEX format, not base64), clarified RSA key size is configurable, added TLS verification note for database connections |
