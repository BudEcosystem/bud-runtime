# Encryption Standards

> **Version:** 1.1
> **Last Updated:** 2026-01-25
> **Status:** Current Implementation
> **Audience:** Security engineers, compliance officers, developers

> **Implementation Status:** Core encryption standards are implemented. Note that AES key loading uses HEX encoding (not base64 as previously documented). RSA encryption is functional. See Section 7.2 for recommended improvements.

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

```python
class RSAHandler:
    @staticmethod
    async def encrypt(message: str, public_key: PublicKeyTypes) -> str:
        encoded_message = message.encode("utf-8")
        encrypted_message = public_key.encrypt(
            encoded_message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return encrypted_message.hex()

    @staticmethod
    async def decrypt(message_encrypted: str, private_key: PrivateKeyTypes) -> str:
        message_encrypted_bytes = bytes.fromhex(message_encrypted)
        message_decrypted = private_key.decrypt(
            message_encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return message_decrypted.decode("utf-8")
```

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

```python
class AESHandler:
    def __init__(self, key: bytes = secrets_settings.aes_key):
        self.fernet = Fernet(key)

    async def encrypt(self, message: str) -> str:
        encoded_message = message.encode("utf-8")
        encrypted_message = self.fernet.encrypt(encoded_message)
        return encrypted_message.hex()

    async def decrypt(self, encrypted_message: str) -> str:
        encrypted_message_bytes = bytes.fromhex(encrypted_message)
        decrypted_message = self.fernet.decrypt(encrypted_message_bytes)
        return decrypted_message.decode("utf-8")
```

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

```python
# budcluster/cluster_ops/services.py
configuration_encrypted = dapr_service.encrypt_data(
    json.dumps(configure_cluster_request.config_dict)
)

# Store encrypted blob in PostgreSQL
cluster = Cluster(
    configuration=configuration_encrypted,
    ...
)
```

### 2.3 Database Encryption

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

```yaml
# kube-apiserver configuration
--encryption-provider-config=/etc/kubernetes/encryption-config.yaml

# encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded-key>
      - identity: {}
```

---

## 3. Encryption in Transit

### 3.1 TLS Configuration

| Property | Value |
|----------|-------|
| Minimum Version | TLS 1.2 |
| Preferred Version | TLS 1.3 |
| Certificate Type | RSA 2048 or ECDSA P-256 |
| Certificate Authority | Let's Encrypt or Enterprise CA |

#### Supported Cipher Suites (TLS 1.2)

```
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256
TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
```

#### Supported Cipher Suites (TLS 1.3)

```
TLS_AES_256_GCM_SHA384
TLS_AES_128_GCM_SHA256
TLS_CHACHA20_POLY1305_SHA256
```

### 3.2 Service-to-Service mTLS

**Provider:** Dapr Sidecar

| Property | Value |
|----------|-------|
| Certificate Lifetime | 24 hours |
| Auto-Rotation | Yes |
| Trust Domain | Configurable |
| Clock Skew Allowance | 15 minutes |

**Configuration:**

```yaml
apiVersion: dapr.io/v1alpha1
kind: Configuration
metadata:
  name: budconfig
spec:
  mtls:
    enabled: true
    workloadCertTTL: "24h"
    allowedClockSkew: "15m"
```

### 3.3 Database Connections

| Database | Protocol | Certificate Verification |
|----------|----------|-------------------------|
| PostgreSQL | TLS | Required in production |
| ClickHouse | TLS | Required in production |
| Redis | TLS | Recommended |
| MongoDB | TLS | Required in production |

**Connection String Example (Recommended):**

```
postgresql://user:pass@host:5432/db?sslmode=verify-full&sslrootcert=/path/to/ca.crt
```

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

```python
class HashManager:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def get_hash(self, plain_string: str) -> str:
        return self.pwd_context.hash(plain_string)

    async def verify_hash(self, plain_string: str, hashed_string: str) -> bool:
        return self.pwd_context.verify(plain_string, hashed_string)
```

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

```python
@staticmethod
async def create_sha_256_hash(input_string: str) -> str:
    input_bytes = input_string.encode("utf-8")
    sha_256_hash = hashlib.sha256(input_bytes)
    return sha_256_hash.hexdigest()
```

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

```bash
# Generate 4096-bit RSA private key
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 \
  -out crypto-keys/rsa-private-key.pem

# Extract public key
openssl rsa -in crypto-keys/rsa-private-key.pem -pubout \
  -out crypto-keys/rsa-public-key.pem

# Set permissions
chmod 600 crypto-keys/rsa-private-key.pem
chmod 644 crypto-keys/rsa-public-key.pem
```

**AES Key:**

```bash
# Generate 256-bit random key
openssl rand -out crypto-keys/symmetric-key-256 32

# Set permissions
chmod 600 crypto-keys/symmetric-key-256
```

### 5.3 Key Loading

**Location:** `budapp/commons/config.py`

```python
# RSA keys loaded from PEM files
@property
def private_key(self) -> PrivateKeyTypes:
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

@property
def public_key(self) -> PublicKeyTypes:
    with open(PUBLIC_KEY_PATH, "rb") as f:
        return serialization.load_pem_public_key(f.read())

# AES key loaded from HEX format (NOT base64)
@property
def aes_key(self) -> bytes:
    """Return AES key loaded from HEX format."""
    if not self.aes_key_hex:
        raise RuntimeError("AES key is not set")
    return bytes.fromhex(self.aes_key_hex)
```

> **Important:** The AES key is loaded from HEX encoding via the `AES_KEY_HEX` environment variable, not from a base64-encoded file. Ensure keys are stored in HEX format.

### 5.4 Key Rotation (Manual Process)

1. **Generate new keys:**
   ```bash
   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 \
     -out crypto-keys/rsa-private-key-new.pem
   ```

2. **Re-encrypt existing data:**
   ```python
   # Decrypt with old key, encrypt with new key
   for credential in credentials:
       plaintext = await old_handler.decrypt(credential.encrypted_key)
       credential.encrypted_key = await new_handler.encrypt(plaintext)
       await session.commit()
   ```

3. **Swap keys:**
   ```bash
   mv crypto-keys/rsa-private-key.pem crypto-keys/rsa-private-key-old.pem
   mv crypto-keys/rsa-private-key-new.pem crypto-keys/rsa-private-key.pem
   ```

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

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated AES key loading (HEX format, not base64), clarified RSA key size is configurable, added TLS verification note for database connections |
