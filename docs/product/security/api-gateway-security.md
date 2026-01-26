# API Gateway Security

---

## 1. Overview

This document describes the security architecture and controls implemented in the budgateway service, which handles all inference API traffic for Bud AI Foundry.

---

## 2. Authentication

### 2.1 API Key Authentication

**API Key Format:**
- Prefix: `bud_client_` (client credentials) or `bud_admin_` (admin credentials)
- Random portion: 32 bytes (256 bits) of cryptographically secure random data
- Encoding: URL-safe base64 (padding removed)
- Storage: RSA-encrypted at rest in PostgreSQL

**Header Format:**

### 2.2 Key Validation Process

The validation process involves coordination between budgateway (Rust) and budapp (Python):

**budgateway (Rust) - Request Time:**

**budapp (Python) - Cache Population:**

**Expiry Enforcement:**
- Redis TTL automatically removes keys when expiry time is reached
- budgateway listens for Redis `expired` keyspace events
- Expired keys are removed from in-memory cache immediately
- budapp also validates expiry explicitly when checking credential validity

### 2.3 Permission Scopes

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `inference:read` | Execute inference requests | `/v1/chat/completions`, `/v1/completions` |
| `inference:stream` | Use streaming responses | All inference with `stream: true` |
| `models:read` | List available models | `/v1/models` |
| `usage:read` | View usage statistics | `/v1/usage` |

---

## 3. Transport Security

### 3.1 TLS Configuration

| Setting | Value |
|---------|-------|
| Minimum TLS Version | TLS 1.2 |
| Preferred TLS Version | TLS 1.3 |
| Certificate Type | RSA 2048 or ECDSA P-256 |
| HSTS | Enabled, max-age=31536000 |

**Cipher Suites (TLS 1.3):**
- TLS_AES_256_GCM_SHA384
- TLS_CHACHA20_POLY1305_SHA256
- TLS_AES_128_GCM_SHA256

### 3.2 Certificate Management

- Certificates issued by Let's Encrypt or enterprise CA
- Auto-renewal via cert-manager
- Certificate pinning optional for enterprise clients

---

## 4. Request Validation

### 4.1 Input Validation

| Field | Validation | Limit |
|-------|------------|-------|
| `model` | Must exist in allowed models | - |
| `messages` | Array of valid message objects | 100 messages |
| `max_tokens` | Positive integer | 128,000 |
| `temperature` | Float 0.0-2.0 | - |
| `stream` | Boolean | - |
| Request body | JSON schema validation | 10 MB |

### 4.3 Prompt Injection Mitigations

| Control | Description |
|---------|-------------|
| System prompt isolation | System prompts marked and protected |
| Input length limits | Prevents resource exhaustion |
| Rate limiting | Limits abuse attempts |
| Logging | All requests logged for audit |

---

## 5. Rate Limiting

### 5.1 Rate Limit Tiers

| Tier | Requests/min | Tokens/min | Concurrent |
|------|--------------|------------|------------|
| Free | 20 | 40,000 | 2 |
| Standard | 100 | 200,000 | 10 |
| Pro | 500 | 1,000,000 | 50 |
| Enterprise | Custom | Custom | Custom |

### 5.3 Rate Limit Algorithm

- Configurable algorithm: Token Bucket (default), Sliding Window, or Fixed Window
- Request-based limits: per-second, per-minute, per-hour
- Burst size configurable for token bucket algorithm
- Redis-based distributed rate limiting with local caching
- Local allowance ratio for reduced Redis round-trips

### 5.4 Usage Limits (Token Quota)

In addition to request rate limiting, budgateway enforces usage limits:
- Token quota tracking per user/project
- Cost-based limiting (optional)
- Billing cycle tracking with automatic reset
- Real-time usage increments via Redis pub/sub

---

## 6. Logging and Audit

### 6.1 Request Logging

| Field | Logged | PII Handling |
|-------|--------|--------------|
| Timestamp | Yes | - |
| API Key ID | Yes (not full key) | Hashed |
| Model | Yes | - |
| Token counts | Yes | - |
| Latency | Yes | - |
| Status code | Yes | - |
| Request body | Optional | Redacted |
| Response body | No | - |
| Client IP | Yes | Anonymized after 30 days |

### 6.2 Security Events

| Event | Severity | Alert |
|-------|----------|-------|
| Invalid API key | Low | After 10/min |
| Revoked key used | Medium | Immediate |
| Rate limit exceeded | Low | After 100/hour |
| Request validation failed | Low | After 50/min |
| TLS downgrade attempt | High | Immediate |

---

## 7. Network Security

### 7.2 Service Mesh Security

- mTLS between all services via Dapr
- Service-to-service authentication
- Traffic encryption in transit

---

## 8. Secrets Management

### 8.1 API Key Encryption

| Layer | Method |
|-------|--------|
| Storage | RSA with OAEP padding (SHA256) |
| Key Size | Configurable (RSA-4096 recommended) |
| Transit | TLS 1.3 |
| Hashing | SHA256 with `bud-` prefix for lookups |

### 8.2 Key Rotation

- Customer keys: User-initiated or 90-day recommendation
- Internal keys: Automatic 30-day rotation
- Encryption keys: Annual rotation with re-encryption
