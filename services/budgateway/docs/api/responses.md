# OpenAI-Compatible Responses API

## Overview

The Responses API provides OpenAI's next-generation interface for stateful conversations and advanced AI interactions. This API enables multi-turn conversations, parallel tool calling, reasoning models support, and multimodal interactions.

## Endpoints

### Create Response
```
POST /v1/responses
```

### Retrieve Response
```
GET /v1/responses/{response_id}
```

### Delete Response
```
DELETE /v1/responses/{response_id}
```

### Cancel Response
```
POST /v1/responses/{response_id}/cancel
```

### List Input Items
```
GET /v1/responses/{response_id}/input_items
```

## Authentication

```
Authorization: Bearer <API_KEY>
```

## Create Response

Creates a new response with advanced conversation capabilities.

### Request Body

#### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Model identifier with responses capability |
| `input` | string or array | Input content (text or multimodal array) |

#### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instructions` | string | null | System instructions for the response |
| `previous_response_id` | string | null | ID of previous response for conversation continuity |
| `modalities` | array | ["text"] | Supported modalities (text, image, audio) |
| `tools` | array | null | Available tool definitions |
| `tool_choice` | string/object | "auto" | Tool selection strategy |
| `parallel_tool_calls` | boolean | true | Enable parallel tool calls |
| `temperature` | float | Model default | Sampling temperature (0.0 to 2.0) |
| `max_output_tokens` | integer | Model default | Maximum tokens to generate |
| `top_p` | float | Model default | Nucleus sampling parameter |
| `stream` | boolean | false | Enable streaming response |
| `stream_options` | object | null | Streaming configuration |
| `reasoning` | object | null | Reasoning configuration for o1 models |
| `metadata` | object | null | Custom metadata |
| `user` | string | null | User identifier |

#### Input Format

**Text Input:**
```json
{
  "input": "Hello, how can you help me today?"
}
```

**Multimodal Input:**
```json
{
  "input": [
    {
      "type": "text",
      "text": "What's in this image?"
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/jpeg;base64,..."
      }
    }
  ]
}
```

#### Tool Configuration

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get weather information",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {"type": "string"}
          },
          "required": ["location"]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "parallel_tool_calls": true
}
```

#### Reasoning Configuration

For o1 and reasoning-capable models:

```json
{
  "reasoning": {
    "reasoning_effort": "high"
  }
}
```

### Response Format

#### Standard Response

```json
{
  "id": "resp_abc123",
  "object": "response",
  "created_at": 1750179872,
  "status": "completed",
  "output": [
    {
      "type": "text",
      "text": "Hello! I can help you with various tasks..."
    }
  ],
  "usage": {
    "input_tokens": 15,
    "output_tokens": 42,
    "total_tokens": 57
  },
  "metadata": {},
  "conversation_id": "conv_xyz789"
}
```

#### Streaming Response

When `stream: true`, returns Server-Sent Events (SSE):

```
data: {"id":"resp_abc123","object":"response.stream","event_type":"response.started","response":{"id":"resp_abc123","object":"response","created_at":1750179872,"status":"in_progress"}}

data: {"id":"resp_abc123","object":"response.stream","event_type":"response.output.started","response":{"id":"resp_abc123","output":[{"type":"text","text":""}]}}

data: {"id":"resp_abc123","object":"response.stream","event_type":"response.output.delta","response":{"id":"resp_abc123","output":[{"type":"text","text":"Hello"}]}}

data: {"id":"resp_abc123","object":"response.stream","event_type":"response.output.delta","response":{"id":"resp_abc123","output":[{"type":"text","text":"Hello!"}]}}

data: {"id":"resp_abc123","object":"response.stream","event_type":"response.done","response":{"id":"resp_abc123","status":"completed","usage":{"input_tokens":15,"output_tokens":42,"total_tokens":57}}}

data: [DONE]
```

## Retrieve Response

**Note**: Since the OpenAI API doesn't include a model parameter for retrieval operations, you must specify the model name using the `x-model-name` header. If not provided, it defaults to `gpt-4-responses`.

### Request

```bash
curl -X GET http://localhost:3000/v1/responses/resp_abc123 \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "x-model-name: your-responses-model"
```

### Response

```json
{
  "id": "resp_abc123",
  "object": "response",
  "created_at": 1750179872,
  "status": "completed",
  "output": [...],
  "usage": {...}
}
```

## Delete Response

Deletes a response and its associated data.

### Request

```bash
curl -X DELETE http://localhost:3000/v1/responses/resp_abc123 \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "x-model-name: your-responses-model"
```

### Response

```json
{
  "id": "resp_abc123",
  "object": "response.deleted",
  "deleted": true
}
```

## Cancel Response

Cancels an in-progress response.

### Request

```bash
curl -X POST http://localhost:3000/v1/responses/resp_abc123/cancel \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "x-model-name: your-responses-model"
```

### Response

```json
{
  "id": "resp_abc123",
  "object": "response",
  "status": "cancelled"
}
```

## List Input Items

Lists the input items for a response.

### Request

```bash
curl -X GET http://localhost:3000/v1/responses/resp_abc123/input_items \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "x-model-name: your-responses-model"
```

### Response

```json
{
  "object": "list",
  "data": [
    {
      "id": "item_1_resp_abc123",
      "object": "response.input_item",
      "type": "text",
      "content": "Hello, how can you help me today?"
    }
  ]
}
```

## Usage Examples

### Basic Response

```bash
curl -X POST http://localhost:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4-responses",
    "input": "Hello, world!",
    "instructions": "Be helpful and friendly"
  }'
```

### Conversation with Previous Response

```bash
curl -X POST http://localhost:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4-responses",
    "input": "Continue our conversation",
    "previous_response_id": "resp_previous_123"
  }'
```

### With Tool Calls

```bash
curl -X POST http://localhost:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4-responses",
    "input": "What is the weather like in New York?",
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get weather information",
          "parameters": {
            "type": "object",
            "properties": {
              "location": {"type": "string"}
            },
            "required": ["location"]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "parallel_tool_calls": true
  }'
```

### Multimodal Response

```bash
curl -X POST http://localhost:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4o-responses",
    "input": [
      {
        "type": "text",
        "text": "What is in this image?"
      },
      {
        "type": "image_url",
        "image_url": {
          "url": "data:image/png;base64,iVBORw0KGgo..."
        }
      }
    ],
    "modalities": ["text", "image"]
  }'
```

### Reasoning Model

```bash
curl -X POST http://localhost:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "o1-responses",
    "input": "Solve this complex problem step by step",
    "reasoning": {
      "reasoning_effort": "high"
    },
    "temperature": 0.7,
    "max_output_tokens": 2000
  }'
```

### Streaming Response

```javascript
const response = await fetch('http://localhost:3000/v1/responses', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_API_KEY'
  },
  body: JSON.stringify({
    model: 'gpt-4-responses',
    input: 'Tell me a story',
    stream: true,
    stream_options: {include_usage: true}
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6);
      if (data === '[DONE]') break;
      
      const event = JSON.parse(data);
      if (event.event_type === 'response.output.delta') {
        const output = event.response.output[0];
        if (output.type === 'text') {
          process.stdout.write(output.text);
        }
      }
    }
  }
}
```

### With Metadata

```bash
curl -X POST http://localhost:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4-responses",
    "input": "Hello",
    "metadata": {
      "user_id": "user_123",
      "session_id": "session_456",
      "custom_field": {"nested": "value"}
    },
    "user": "user_123"
  }'
```

## Response Status Values

| Status | Description |
|--------|-------------|
| `in_progress` | Response is being generated |
| `completed` | Response generation completed successfully |
| `failed` | Response generation failed |
| `cancelled` | Response was cancelled |

## Event Types (Streaming)

| Event Type | Description |
|------------|-------------|
| `response.started` | Response generation started |
| `response.output.started` | Output generation started |
| `response.output.delta` | Incremental output content |
| `response.done` | Response generation completed |
| `response.failed` | Response generation failed |
| `response.cancelled` | Response was cancelled |

## Model Configuration

To use the Responses API, configure your models with the `responses` endpoint capability:

```toml
[models."gpt-4-responses"]
routing = ["openai"]
endpoints = ["responses"]

[models."gpt-4-responses".providers.openai]
type = "openai"
model_name = "gpt-4"
api_key_location = { env = "OPENAI_API_KEY" }

# For reasoning models
[models."o1-responses"]
routing = ["openai"]
endpoints = ["responses"]

[models."o1-responses".providers.openai]
type = "openai"
model_name = "o1"
```

## Error Responses

```json
{
  "error": {
    "message": "Error description",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

Common error codes:
- `400` - Invalid request format or parameters
- `401` - Authentication failed
- `404` - Response, model, or function not found
- `429` - Rate limit exceeded
- `500` - Internal server error

## Limitations

- Response retrieval, deletion, cancellation, and input item listing are currently not supported by TensorZero's implementation
- These operations will return appropriate error messages indicating the feature is not yet available
- Only response creation is fully functional in the current implementation

## Key Differences from Chat Completions

1. **Stateful**: Responses maintain conversation state via `previous_response_id`
2. **Advanced Tools**: Enhanced tool calling with parallel execution
3. **Multimodal**: Native support for multiple input modalities
4. **Reasoning**: Special support for reasoning models like o1
5. **Metadata**: Rich metadata and user tracking capabilities
6. **Background Processing**: Support for async response generation