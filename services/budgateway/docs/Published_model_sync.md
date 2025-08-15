# Published Model Info Sync Implementation

## Overview
This implementation adds synchronization support for the `published_model_info` Redis key to the budgateway service, enabling dynamic updates to published model information that can be used in the authentication system.

## Changes Made

### 1. Auth Module (`auth.rs`)
- Added `PublishedModelInfo` type alias: `HashMap<String, ApiKeyMetadata>`
  - Uses the same structure as `APIConfig` for consistency
  - Each key is a model identifier
  - Each value contains `ApiKeyMetadata` with:
    - `endpoint_id`: Endpoint identifier
    - `model_id`: Model identifier
    - `project_id`: Associated project ID

- Updated `Auth` struct to include:
  - `published_model_info: Arc<RwLock<PublishedModelInfo>>` field
  - Methods for managing published model info:
    - `update_published_model_info()`: Replace entire published model info
    - `clear_published_model_info()`: Clear all published model info
    - `get_published_model_info()`: Get all published model info

### 2. Redis Client Module (`redis_client.rs`)
- Added constant: `PUBLISHED_MODEL_INFO_KEY = "published_model_info"`

- Added parsing function:
  - `parse_published_model_info()`: Deserializes JSON to `PublishedModelInfo` (HashMap)

- Updated event handlers:
  - **SET events**: Parse and store published model info when the key is created/updated
  - **DEL/EXPIRED events**: Clear published model info when the key is deleted

- Added initial fetch logic:
  - On startup, fetches the `published_model_info` key from Redis if it exists
  - Populates the Auth struct with initial published model data

## Redis Key Format
The Redis key is a single key: `published_model_info`

Example JSON structure stored in Redis (same format as APIConfig):
```json
{
  "gpt-4-custom": {
    "endpoint_id": "endpoint-789",
    "model_id": "model-123",
    "project_id": "proj-456"
  },
  "claude-3-sonnet": {
    "endpoint_id": "endpoint-790",
    "model_id": "model-124",
    "project_id": "proj-457"
  }
}
```

## Usage
Once deployed, the system will:
1. Automatically sync published model info from Redis on startup
2. Listen for real-time updates via Redis keyspace events
3. Maintain an in-memory cache of all published models
4. Provide thread-safe access to published model information

## Future Integration
The published model info can be used in authentication middleware to:
- Validate model access based on project associations
- Apply model-specific rate limiting
- Route requests based on model capabilities
- Track model usage for billing/analytics

## Testing
To test the implementation:
1. Set the published model info key in Redis:
   ```bash
   redis-cli SET "published_model_info" '{"test-model":{"endpoint_id":"e1","model_id":"m1","project_id":"p1"},"another-model":{"endpoint_id":"e2","model_id":"m2","project_id":"p2"}}'
   ```

2. Verify the models are loaded in the gateway logs

3. Update or delete the key and verify the changes are reflected:
   ```bash
   # Update
   redis-cli SET "published_model_info" '{"updated-model":{"endpoint_id":"e3","model_id":"m3","project_id":"p3"}}'

   # Delete
   redis-cli DEL "published_model_info"
   ```

## Benefits
- **Dynamic Updates**: No gateway restart required for model configuration changes
- **Centralized Management**: Model info managed externally (e.g., by budapp)
- **Scalability**: Supports multiple gateway instances with shared state
- **Security**: Integrates with existing authentication and access control
