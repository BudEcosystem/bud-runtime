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

## Best Practices

1. **Encryption**: In production, encrypt API keys before storing in Redis
2. **Key Rotation**: Implement regular key rotation policies
3. **Audit Logging**: Log key usage for security auditing
4. **Access Control**: Restrict Redis access to authorized services
5. **Monitoring**: Monitor for unauthorized key access attempts

## Testing

Use the provided test script `test_model_credentials.py` to verify functionality:
```bash
python test_model_credentials.py
```

This will demonstrate:
- Adding models with API keys
- Updating API keys
- Deleting models and their keys