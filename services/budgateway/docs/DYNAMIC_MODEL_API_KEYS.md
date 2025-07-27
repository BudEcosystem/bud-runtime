# Dynamic Model API Key Management

This document describes how TensorZero manages API keys for dynamically added models via Redis.

## Overview

When models are added dynamically via Redis pub/sub, they can include API keys that are securely stored in memory and automatically used for authentication with providers.

## Architecture

### 1. Storage
- API keys are stored in a secure in-memory store: `AppStateData.model_credential_store`
- Keys are stored as `SecretString` which provides automatic memory zeroization
- The store is a thread-safe `Arc<RwLock<HashMap<String, SecretString>>>`

### 2. Key Flow
1. Model configuration is sent to Redis with an `api_key` field
2. Redis client extracts the API key and stores it with key `store_{model_id}`
3. Model's provider configuration uses `api_key_location = "dynamic::store_{model_id}"`
4. During inference, credentials from the store are merged with request credentials
5. Providers automatically use the correct API key

### 3. Security Features
- API keys are never stored in model configurations
- Keys are removed from Redis payloads before processing
- User-provided credentials take precedence over stored credentials
- Keys are automatically cleaned up when models are deleted
- All keys use `SecretString` for secure memory handling

## Usage

### Adding a Model with API Key

```json
{
  "gpt-4-customer-x": {
    "routing": ["openai"],
    "endpoints": ["chat"],
    "providers": {
      "openai": {
        "type": "openai",
        "model_name": "gpt-4",
        "api_key_location": "dynamic::store_gpt-4-customer-x"
      }
    },
    "api_key": "sk-proj-..."
  }
}
```

Set this in Redis:
```bash
redis-cli SET model_table:customer_x_models '{"gpt-4-customer-x": {...}}'
```

### Key Rotation

To rotate an API key, simply update the model with a new `api_key`:
```bash
redis-cli SET model_table:customer_x_models '{"gpt-4-customer-x": {..., "api_key": "sk-proj-new-key"}}'
```

### Deletion

When a model is deleted, its API key is automatically removed:
```bash
redis-cli DEL model_table:customer_x_models
```

## Implementation Details

### Redis Client (redis_client.rs)
- Parses model configurations from Redis
- Extracts `api_key` field before model parsing
- Stores keys in `app_state.model_credential_store`

### Inference Endpoint (endpoints/inference.rs)
- Merges stored credentials with request credentials
- User-provided credentials take precedence
- Passes merged credentials to providers

### Providers (e.g., openai.rs)
- Use standard dynamic credential resolution
- No provider-specific changes needed
- Keys are resolved from the merged credentials map

## RSA Encryption Support

TensorZero supports RSA encryption for API keys stored in Redis. When enabled, API keys are automatically decrypted when loading models from Redis.

### Configuration

Set one of these environment variables to enable RSA decryption:
- `TENSORZERO_RSA_PRIVATE_KEY`: Inline PEM-formatted private key
- `TENSORZERO_RSA_PRIVATE_KEY_PATH`: Path to PEM file containing private key
- `TENSORZERO_RSA_PRIVATE_KEY_PASSWORD`: Password for encrypted PKCS#8 private keys (optional)

### Encryption Details
- Algorithm: RSA with PKCS#1 v1.5 padding
- Key Format: Supports both PKCS#1 and PKCS#8 PEM formats
- Password Protection: Supports password-protected PKCS#8 keys (PBES2 with AES)
- Encoding: Base64-encoded encrypted data

### Troubleshooting Key Loading Issues

If you encounter "PKCS#5 encryption failed" or similar errors:

1. **Check your key format**:
```bash
# First line should be one of:
# -----BEGIN RSA PRIVATE KEY-----  (PKCS#1)
# -----BEGIN PRIVATE KEY-----      (PKCS#8 unencrypted)
# -----BEGIN ENCRYPTED PRIVATE KEY----- (PKCS#8 encrypted)
head -1 /path/to/your/key.pem
```

2. **Debug your key** (requires Python with cryptography):
```bash
python debug_key.py /path/to/your/key.pem yourpassword
```

3. **Convert to compatible format** if needed:
```bash
# Convert to unencrypted PKCS#8 (simplest option)
python convert_key.py old_key.pem new_key.pem oldpassword

# Or use OpenSSL
openssl pkcs8 -topk8 -inform PEM -outform PEM \
  -in old_key.pem -out new_key.pem -nocrypt
```

4. **Common issues**:
- Legacy OpenSSL format: Convert to PKCS#8
- Unsupported encryption: Try converting with the provided script
- Password encoding: Ensure no special characters or use base64 encoding

### Usage with Encrypted Keys

The Python service encrypts API keys before storing them in Redis:
```json
{
  "gpt-4-customer-x": {
    "routing": ["openai"],
    "endpoints": ["chat"],
    "providers": {
      "openai": {
        "type": "openai",
        "model_name": "gpt-4",
        "api_key_location": "dynamic::store_gpt-4-customer-x"
      }
    },
    "api_key": "base64_encoded_encrypted_api_key_here..."
  }
}
```

The Rust proxy automatically decrypts the API key when loading the model configuration.

### Kubernetes Deployment

For Kubernetes deployments:
1. Create a Secret containing the private key:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rsa-private-key
type: Opaque
data:
  private-key.pem: <base64-encoded-pem-content>
```

2. Mount as environment variable or file:
```yaml
# Option 1: Environment variable
env:
- name: TENSORZERO_RSA_PRIVATE_KEY
  valueFrom:
    secretKeyRef:
      name: rsa-private-key
      key: private-key.pem

# Option 2: File mount
volumeMounts:
- name: rsa-key
  mountPath: /etc/keys
  readOnly: true
env:
- name: TENSORZERO_RSA_PRIVATE_KEY_PATH
  value: /etc/keys/private-key.pem

# For password-protected keys, add:
- name: TENSORZERO_RSA_PRIVATE_KEY_PASSWORD
  valueFrom:
    secretKeyRef:
      name: rsa-private-key
      key: password
```

## Best Practices

1. **Encryption**: Always use RSA encryption for API keys in production
2. **Key Management**: Store private keys securely (Kubernetes Secrets, AWS Secrets Manager, etc.)
3. **Key Rotation**: Implement regular key rotation for both RSA keys and API keys
4. **Audit Logging**: Log key usage for security auditing
5. **Access Control**: Restrict Redis access to authorized services
6. **Monitoring**: Monitor for decryption failures and unauthorized access attempts

## Testing

Use the provided test script `test_model_credentials.py` to verify functionality:
```bash
python test_model_credentials.py
```

This will demonstrate:
- Adding models with API keys
- Updating API keys
- Deleting models and their keys
