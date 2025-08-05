# Model Catalog & Pricing API Documentation

This document describes the Model Catalog and Pricing APIs that allow CLIENT users to browse published models and manage pricing information.

## Overview

The Model Catalog APIs provide a way for authenticated CLIENT users to:
- Browse published models with pricing information
- Filter models by modality and status
- Search models by text
- View detailed model information including capabilities and pricing

The Pricing APIs allow authorized users to:
- Set pricing when publishing models
- Update pricing for published models
- View pricing history

## Authentication

All endpoints require authentication with appropriate permissions:
- **Catalog APIs**: Require `CLIENT_ACCESS` permission
- **Pricing Management APIs**: Require `ENDPOINT_MANAGE` permission

## Endpoints

### Model Catalog Endpoints

#### 1. List Published Models

List all published models available in the catalog with optional filtering and search.

**Endpoint:** `GET /api/v1/models/catalog`

**Permissions:** `CLIENT_ACCESS`

**Query Parameters:**
- `page` (integer, default: 1): Page number for pagination
- `limit` (integer, default: 10, max: 100): Number of items per page
- `modality` (array[string], optional): Filter by model modality (text, image, audio, video)
- `status` (string, optional): Filter by model status
- `order_by` (array[string], optional): Sort order (e.g., ["published_date:desc", "name:asc"])
- `search` (string, optional, min length: 2): Search term for full-text search in model names, descriptions, and use cases

**Response:**
```json
{
  "models": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "GPT-4",
      "modality": ["text"],
      "status": "active",
      "description": "Advanced language model with improved reasoning capabilities",
      "capabilities": ["reasoning", "coding", "analysis", "creative writing"],
      "token_limit": 8192,
      "max_input_tokens": 4096,
      "use_cases": ["chatbot", "code generation", "content creation", "analysis"],
      "author": "OpenAI",
      "model_size": 1760,
      "provider_type": "CLOUD",
      "published_date": "2024-01-15T10:30:00Z",
      "endpoint_id": "660e8400-e29b-41d4-a716-446655440001",
      "supported_endpoints": ["text-generation", "chat-completion"],
      "pricing": {
        "input_cost": 0.03,
        "output_cost": 0.06,
        "currency": "USD",
        "per_tokens": 1000
      }
    }
  ],
  "total_record": 25,
  "page": 1,
  "limit": 10,
  "object": "catalog.models.list",
  "code": 200
}
```

**Example Requests:**

1. Basic listing:
```bash
curl -X GET "https://api.example.com/api/v1/models/catalog?page=1&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

2. With filtering:
```bash
curl -X GET "https://api.example.com/api/v1/models/catalog?modality=text&status=active" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

3. With search:
```bash
curl -X GET "https://api.example.com/api/v1/models/catalog?search=language%20model" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. Combined search and filter:
```bash
curl -X GET "https://api.example.com/api/v1/models/catalog?search=GPT&modality=text&order_by=published_date:desc" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 2. Get Model Details

Get detailed information about a specific published model.

**Endpoint:** `GET /api/v1/models/catalog/{endpoint_id}`

**Permissions:** `CLIENT_ACCESS`

**Path Parameters:**
- `endpoint_id` (UUID): The endpoint ID of the published model

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "GPT-4",
  "modality": ["text"],
  "status": "active",
  "description": "Advanced language model with improved reasoning capabilities",
  "capabilities": ["reasoning", "coding", "analysis", "creative writing"],
  "token_limit": 8192,
  "max_input_tokens": 4096,
  "use_cases": ["chatbot", "code generation", "content creation", "analysis"],
  "author": "OpenAI",
  "model_size": 1760,
  "provider_type": "CLOUD",
  "published_date": "2024-01-15T10:30:00Z",
  "endpoint_id": "660e8400-e29b-41d4-a716-446655440001",
  "supported_endpoints": ["text-generation", "chat-completion"],
  "pricing": {
    "input_cost": 0.03,
    "output_cost": 0.06,
    "currency": "USD",
    "per_tokens": 1000
  },
  "code": 200
}
```

**Error Response (404):**
```json
{
  "message": "Published model not found",
  "code": 404
}
```

### Pricing Management Endpoints

#### 3. Publish Endpoint with Pricing

Publish an endpoint and set its initial pricing (integrated with existing publish endpoint).

**Endpoint:** `PUT /api/v1/endpoints/{endpoint_id}/publication-status`

**Permissions:** `ENDPOINT_MANAGE`

**Request Body:**
```json
{
  "action": "publish",
  "pricing": {
    "input_cost": 0.03,
    "output_cost": 0.06,
    "currency": "USD",
    "per_tokens": 1000
  }
}
```

**Response:**
```json
{
  "message": "Endpoint published successfully",
  "endpoint": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "gpt-4-endpoint",
    "is_published": true,
    "published_date": "2024-01-15T10:30:00Z"
  },
  "code": 200
}
```

**Note:** When action is "publish", pricing information is required. When action is "unpublish", pricing is ignored.

#### 4. Update Pricing

Update pricing for an already published endpoint.

**Endpoint:** `PUT /api/v1/endpoints/{endpoint_id}/pricing`

**Permissions:** `ENDPOINT_MANAGE`

**Request Body:**
```json
{
  "input_cost": 0.05,
  "output_cost": 0.10,
  "currency": "USD",
  "per_tokens": 1000
}
```

**Response:**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "endpoint_id": "660e8400-e29b-41d4-a716-446655440001",
  "input_cost": 0.05,
  "output_cost": 0.10,
  "currency": "USD",
  "per_tokens": 1000,
  "is_current": true,
  "created_at": "2024-01-20T14:00:00Z",
  "created_by": "880e8400-e29b-41d4-a716-446655440003",
  "code": 200
}
```

**Error Response (400):**
```json
{
  "message": "Cannot update pricing for unpublished endpoint",
  "code": 400
}
```

#### 5. Get Current Pricing

Get the current pricing for an endpoint.

**Endpoint:** `GET /api/v1/endpoints/{endpoint_id}/pricing`

**Permissions:** `ENDPOINT_MANAGE`

**Response:**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "endpoint_id": "660e8400-e29b-41d4-a716-446655440001",
  "input_cost": 0.05,
  "output_cost": 0.10,
  "currency": "USD",
  "per_tokens": 1000,
  "is_current": true,
  "created_at": "2024-01-20T14:00:00Z",
  "created_by": "880e8400-e29b-41d4-a716-446655440003",
  "code": 200
}
```

#### 6. Get Pricing History

Get the pricing history for an endpoint.

**Endpoint:** `GET /api/v1/endpoints/{endpoint_id}/pricing/history`

**Permissions:** `ENDPOINT_MANAGE`

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 10): Items per page

**Response:**
```json
{
  "pricing_history": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "endpoint_id": "660e8400-e29b-41d4-a716-446655440001",
      "input_cost": 0.05,
      "output_cost": 0.10,
      "currency": "USD",
      "per_tokens": 1000,
      "is_current": true,
      "created_at": "2024-01-20T14:00:00Z",
      "created_by": "880e8400-e29b-41d4-a716-446655440003"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "endpoint_id": "660e8400-e29b-41d4-a716-446655440001",
      "input_cost": 0.03,
      "output_cost": 0.06,
      "currency": "USD",
      "per_tokens": 1000,
      "is_current": false,
      "created_at": "2024-01-15T10:30:00Z",
      "created_by": "880e8400-e29b-41d4-a716-446655440003"
    }
  ],
  "total_record": 2,
  "page": 1,
  "limit": 10,
  "object": "pricing.history",
  "code": 200
}
```

## Data Models

### ModelCatalogItem

Represents a model in the catalog with its pricing information.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Model ID |
| name | string | Model name |
| modality | array[string] | Supported modalities |
| status | string | Model status |
| description | string | Model description |
| capabilities | array[string] | Model capabilities (from strengths + tags) |
| token_limit | integer | Maximum token limit |
| max_input_tokens | integer | Maximum input tokens |
| use_cases | array[string] | Suggested use cases |
| author | string | Model author/creator |
| model_size | number | Model size in parameters |
| provider_type | string | Provider type (CLOUD, LOCAL) |
| published_date | datetime | When the model was published |
| endpoint_id | UUID | Associated endpoint ID |
| supported_endpoints | array[string] | Supported endpoint types |
| pricing | DeploymentPricingInfo | Pricing information |

### DeploymentPricingInfo

Pricing information for a model.

| Field | Type | Description |
|-------|------|-------------|
| input_cost | number | Cost per input tokens |
| output_cost | number | Cost per output tokens |
| currency | string | Currency code (default: USD) |
| per_tokens | integer | Token unit for pricing (default: 1000) |

### DeploymentPricing

Complete pricing record with metadata.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Pricing record ID |
| endpoint_id | UUID | Associated endpoint ID |
| input_cost | decimal | Cost per input tokens |
| output_cost | decimal | Cost per output tokens |
| currency | string | Currency code |
| per_tokens | integer | Token unit for pricing |
| is_current | boolean | Whether this is the current pricing |
| created_at | datetime | When the pricing was created |
| created_by | UUID | User who created the pricing |

## Caching

The catalog APIs implement Redis caching with a 5-minute TTL to improve performance:

- Model catalog lists are cached with a key based on filter parameters
- Individual model details are cached by endpoint ID
- Cache is automatically invalidated when:
  - An endpoint is published/unpublished
  - Pricing is updated

## Performance Considerations

1. **Response Times**: All catalog endpoints are optimized to respond in < 200ms
2. **Database Indexes**: The following indexes are created for performance:
   - GIN index on model name and description for full-text search
   - B-tree index on endpoint publication status
   - Composite index on endpoint status and publication date
3. **Pagination**: Use appropriate page sizes (10-50 items) for optimal performance
4. **Caching**: Frequently accessed data is cached in Redis with 5-minute TTL

## Error Handling

All endpoints follow a consistent error response format:

```json
{
  "message": "Error description",
  "code": 400,
  "details": {}  // Optional additional error details
}
```

Common error codes:
- `400`: Bad request (invalid parameters, missing required fields)
- `401`: Unauthorized (missing or invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Resource not found
- `500`: Internal server error

## Migration Notes

When implementing these APIs:

1. Run the database migration to create the `deployment_pricing` table and indexes
2. Ensure Redis is configured for caching
3. Update existing published endpoints to have pricing information
4. Configure appropriate permissions for CLIENT users

## Example Use Cases

### 1. Browse Available Models
A CLIENT user wants to see all available text generation models:

```bash
GET /api/v1/models/catalog?modality=text&order_by=published_date:desc
```

### 2. Search for Specific Capabilities
Find models that support code generation:

```bash
GET /api/v1/models/catalog?search=code%20generation
```

### 3. Update Model Pricing
Admin updates pricing for a published model:

```bash
PUT /api/v1/endpoints/{endpoint_id}/pricing
{
  "input_cost": 0.04,
  "output_cost": 0.08,
  "currency": "USD",
  "per_tokens": 1000
}
```
