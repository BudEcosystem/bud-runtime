# Published Model Info Implementation for BudGateway

## Overview
This implementation adds support for dynamically extending API configurations with published model information for client API keys (those starting with `bud_client`). This allows external services to manage and publish model access permissions that are automatically synchronized to the gateway.

## Implementation Details

### 1. Data Structure
- `PublishedModelInfo` is defined as `HashMap<String, ApiKeyMetadata>` - same structure as `APIConfig`
- Each entry maps a model name to its metadata containing:
  - `endpoint_id`: The endpoint identifier
  - `model_id`: The model identifier
  - `project_id`: The project identifier

### 2. Redis Synchronization
- **Key**: Single Redis key `published_model_info` (not a prefix)
- **Initial Load**: On startup, the gateway fetches the key if it exists
- **Real-time Updates**: Subscribes to Redis keyspace events for SET/DEL/EXPIRED operations
- **Data Flow**: Redis → RedisClient → Auth struct

### 3. Authentication Flow
When an API request is received:
1. Extract and validate the API key
2. Get the base `api_config` for the key
3. **NEW**: If the key starts with `bud_client`:
   - Fetch the current `published_model_info`
   - Extend the `api_config` with all published models
   - This gives client keys access to all published models
4. Validate the requested model exists in the (potentially extended) config
5. Add metadata headers for downstream processing

## Usage Example

### 1. Set Published Model Info in Redis
```bash
redis-cli SET "published_model_info" '{
  "gpt-4-custom": {
    "endpoint_id": "endpoint-123",
    "model_id": "model-456",
    "project_id": "project-789"
  },
  "claude-3-sonnet": {
    "endpoint_id": "endpoint-124",
    "model_id": "model-457",
    "project_id": "project-790"
  }
}'
```

### 2. Client API Key Behavior
When a request is made with a `bud_client_*` API key:
```bash
curl -X POST http://gateway/v1/chat/completions \
  -H "Authorization: Bearer bud_client_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4-custom",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

The gateway will:
1. Validate the `bud_client_abc123` key
2. Get its base configuration
3. Automatically add access to all models in `published_model_info`
4. Process the request for `gpt-4-custom` model

### 3. Non-Client API Key Behavior
Regular API keys (not starting with `bud_client`) only have access to models explicitly configured for them - they do NOT get the published models.

## Benefits

1. **Dynamic Model Access**: Client keys automatically get access to newly published models without configuration changes
2. **Centralized Management**: Model publishing can be managed by external services (e.g., budapp)
3. **Granular Control**: Non-client keys maintain strict access control
4. **Real-time Updates**: Changes propagate immediately without gateway restart
5. **Scalability**: Multiple gateway instances share the same published model state via Redis

## Security Considerations

1. **Client Key Distinction**: Only keys starting with `bud_client` get extended access
2. **Project Isolation**: Each model still maintains its `project_id` for row-level security
3. **Audit Trail**: All model access includes metadata headers for tracking
4. **Controlled Publishing**: Only authorized services should write to the `published_model_info` key

## Testing

### Test Client Key with Published Models
```bash
# 1. Set up published models
redis-cli SET "published_model_info" '{"test-model":{"endpoint_id":"e1","model_id":"m1","project_id":"p1"}}'

# 2. Create a client API key configuration
redis-cli SET "api_key:client_keys" '{"bud_client_test":{"base-model":{"endpoint_id":"e0","model_id":"m0","project_id":"p0"}}}'

# 3. Test access to published model (should work)
curl -X POST http://gateway/v1/chat/completions \
  -H "Authorization: Bearer bud_client_test" \
  -d '{"model": "test-model", "messages": []}'

# 4. Test with non-client key (should fail for published models)
curl -X POST http://gateway/v1/chat/completions \
  -H "Authorization: Bearer regular_key_123" \
  -d '{"model": "test-model", "messages": []}'
```

## Integration Points

This feature integrates with:
- **budapp**: Can publish model configurations based on user permissions
- **budmodel**: Can publish newly registered models
- **budmetrics**: Tracks usage of published models
- **Authentication Middleware**: Seamlessly extends existing auth flow
