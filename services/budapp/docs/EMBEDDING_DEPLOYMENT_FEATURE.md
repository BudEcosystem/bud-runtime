# Embedding Deployment Feature Documentation

## Overview

This feature introduces support for specifying and tracking which API endpoints are enabled for deployed models. Previously, all endpoints were implicitly available for every model deployment. With this change, endpoints can now be selectively enabled based on the model's capabilities and deployment configuration.

## Key Changes

### 1. Database Schema Updates

#### Migration: `c301ac188f1b_supported_endpoints_in_endpoint_table.py`
- **Added**: `supported_endpoints` column to the `endpoint` table
- **Type**: PostgreSQL ARRAY of `model_endpoint_enum` values
- **Purpose**: Tracks which API endpoints are enabled for each deployment

The migration also makes several existing columns non-nullable:
- `cloud_model.modality`
- `cloud_model.supported_endpoints`
- `model.modality`
- `model.supported_endpoints`

### 2. Data Model Changes

#### `budapp/endpoint_ops/models.py`
Added a new field to the `Endpoint` model:
```python
supported_endpoints: Mapped[List[str]] = mapped_column(
    PG_ARRAY(
        PG_ENUM(
            ModelEndpointEnum,
            name="model_endpoint_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
    ),
    nullable=False,
)
```

### 3. API Schema Updates

#### `budapp/endpoint_ops/schemas.py`
- **EndpointCreate**: Added `supported_endpoints: list[ModelEndpointEnum]` field
- **ProxyModelConfig**: Added `endpoints: list[str]` field for proxy configuration

### 4. Service Layer Enhancements

#### `budapp/endpoint_ops/services.py`

**Endpoint Creation Flow**:
1. Extracts `supported_endpoints` from deployment status
2. Handles both dictionary format (endpoint: enabled) and list format (legacy)
3. Filters only enabled endpoints when dictionary format is used
4. Stores enabled endpoints in the database

**Proxy Cache Integration**:
- Enhanced `add_model_to_proxy_cache` method to include supported endpoints
- Converts endpoint paths to lowercase names (e.g., "/v1/chat/completions" → "chat")
- Updates proxy configuration with specific endpoints for routing

## Supported Endpoint Types

The system supports 16 different endpoint types via `ModelEndpointEnum`:

### Currently Supported
1. **CHAT** (`/v1/chat/completions`) - Chat completions
2. **EMBEDDING** (`/v1/embeddings`) - Vector embeddings

### Available Endpoints
1. ~~COMPLETION (`/v1/completions`) - Text completions~~ (removed)
2. **IMAGE_GENERATION** (`/v1/images/generations`) - Image generation
3. **IMAGE_EDIT** (`/v1/images/edits`) - Image editing
4. **IMAGE_VARIATION** (`/v1/images/variations`) - Image variations
5. **AUDIO_TRANSCRIPTION** (`/v1/audio/transcriptions`) - Speech-to-text
6. **AUDIO_TRANSLATION** (`/v1/audio/translations`) - Audio translation to English
7. **TEXT_TO_SPEECH** (`/v1/audio/speech`) - Text-to-speech
8. **REALTIME_SESSION** (`/v1/realtime/sessions`) - Real-time bidirectional conversation
9. **REALTIME_TRANSCRIPTION** (`/v1/realtime/transcription_sessions`) - Real-time audio transcription
10. **BATCH** (`/v1/batch`) - Batch processing
11. **RESPONSES** (`/v1/responses`) - Async response retrieval
12. **RERANK** (`/v1/rerank`) - Reranking functionality
13. **MODERATION** (`/v1/moderations`) - Content moderation
14. **CLASSIFY** (`/v1/classify`) - Classification

## Benefits

1. **Granular Control**: Administrators can enable only the endpoints relevant to each model
2. **Security**: Reduces attack surface by disabling unused endpoints
3. **Performance**: Proxy can optimize routing based on available endpoints
4. **Clarity**: Clear visibility into what capabilities each deployment provides

## Implementation Details

### Backward Compatibility
The service layer handles both legacy list format and new dictionary format for `supported_endpoints`, ensuring smooth migration.

### Proxy Integration
The proxy cache now includes endpoint information, allowing the proxy layer to:
- Route requests only to deployments that support specific endpoints
- Return appropriate errors for unsupported endpoints
- Optimize load balancing based on endpoint availability


The system will:
1. Store the enabled endpoints in the database
2. Update the proxy cache with endpoint routing information
3. Make only the specified endpoints available for this deployment
