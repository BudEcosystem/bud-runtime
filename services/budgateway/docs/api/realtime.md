# Realtime API

The TensorZero Realtime API provides OpenAI-compatible endpoints for creating and managing realtime audio and text interaction sessions. This API enables real-time conversation capabilities with support for voice interaction, transcription, and function calling.

## Overview

The Realtime API consists of two main endpoints:

- **Realtime Sessions** (`/v1/realtime/sessions`) - Full realtime audio/text interaction
- **Transcription Sessions** (`/v1/realtime/transcription_sessions`) - Audio transcription only

All endpoints require authentication and return OpenAI-compatible response formats.

## Authentication

All Realtime API endpoints require authentication via API key:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     https://your-tensorzero-endpoint.com/v1/realtime/sessions
```

## Endpoints

### Create Realtime Session

Creates a new realtime session for full audio and text interaction.

```http
POST /v1/realtime/sessions
```

#### Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | The model to use for the session (e.g., "gpt-4o-realtime-preview") |
| `voice` | string | No | Voice to use for audio output. Options: "alloy", "echo", "fable", "onyx", "nova", "shimmer" |
| `input_audio_format` | string | No | Format for input audio. Options: "pcm16", "g711_ulaw", "g711_alaw" |
| `output_audio_format` | string | No | Format for output audio. Options: "pcm16", "g711_ulaw", "g711_alaw" |
| `input_audio_noise_reduction` | boolean | No | Whether to enable noise reduction for input audio |
| `temperature` | number | No | Sampling temperature (0.0 to 1.0) |
| `max_response_output_tokens` | number\|string | No | Maximum tokens in response. Use "inf" for unlimited |
| `modalities` | array[string] | No | Supported modalities. Options: ["text"], ["audio"], ["text", "audio"] |
| `instructions` | string | No | System instructions for the assistant |
| `turn_detection` | object | No | Turn detection configuration |
| `tools` | array[object] | No | Available function tools |
| `tool_choice` | string | No | Tool choice strategy. Options: "auto", "required", "none" |
| `speed` | number | No | Audio playback speed (0.25 to 4.0) |

#### Turn Detection Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | Yes | Detection type. Currently only "server_vad" supported |
| `threshold` | number | No | Voice activity detection threshold (0.0 to 1.0) |
| `prefix_padding_ms` | integer | No | Padding before speech in milliseconds |
| `silence_duration_ms` | integer | No | Silence duration to detect end of speech |
| `create_response` | boolean | No | Whether to automatically create responses |
| `interrupt_response` | boolean | No | Whether responses can be interrupted |

#### Example Request

```bash
curl -X POST https://your-tensorzero-endpoint.com/v1/realtime/sessions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-realtime-preview",
    "voice": "alloy",
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "temperature": 0.8,
    "modalities": ["text", "audio"],
    "instructions": "You are a helpful assistant.",
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 200,
      "create_response": true,
      "interrupt_response": true
    },
    "tools": [],
    "tool_choice": "auto",
    "speed": 1.0
  }'
```

#### Response

```json
{
  "id": "sess_abc123def456ghi789",
  "object": "realtime.session",
  "model": "gpt-4o-realtime-preview",
  "expires_at": 0,
  "client_secret": {
    "value": "eph_xyz789abc123def456",
    "expires_at": 1703123456
  },
  "voice": "alloy",
  "input_audio_format": "pcm16",
  "output_audio_format": "pcm16",
  "input_audio_noise_reduction": false,
  "temperature": 0.8,
  "max_response_output_tokens": "inf",
  "modalities": ["text", "audio"],
  "instructions": "You are a helpful assistant.",
  "turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 200,
    "create_response": true,
    "interrupt_response": true
  },
  "tools": [],
  "tool_choice": "auto",
  "speed": 1.0
}
```

### Create Transcription Session

Creates a new session specifically for audio transcription.

```http
POST /v1/realtime/transcription_sessions
```

#### Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | The model to use for transcription |
| `input_audio_format` | string | No | Format for input audio. Options: "pcm16", "g711_ulaw", "g711_alaw" |
| `input_audio_transcription` | object | No | Transcription configuration |
| `turn_detection` | object | No | Turn detection configuration |
| `modalities` | array[string] | No | Always ["text"] for transcription sessions |

#### Input Audio Transcription Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Transcription model (e.g., "whisper-1") |
| `language` | string | No | Input audio language (ISO 639-1 code) |
| `prompt` | string | No | Transcription prompt for context |

#### Example Request

```bash
curl -X POST https://your-tensorzero-endpoint.com/v1/realtime/transcription_sessions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini-transcribe",
    "input_audio_format": "pcm16",
    "input_audio_transcription": {
      "model": "whisper-1",
      "language": "en",
      "prompt": "Transcribe this conversation"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 200
    },
    "modalities": ["text"]
  }'
```

#### Response

```json
{
  "id": "sess_def456ghi789jkl012",
  "object": "realtime.transcription_session",
  "model": "gpt-4o-mini-transcribe",
  "expires_at": 0,
  "client_secret": {
    "value": "eph_transcribe_mno345pqr678stu901",
    "expires_at": 1703123456
  },
  "input_audio_format": "pcm16",
  "input_audio_transcription": {
    "model": "whisper-1",
    "language": "en",
    "prompt": "Transcribe this conversation"
  },
  "turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 200,
    "create_response": null,
    "interrupt_response": null
  },
  "modalities": ["text"]
}
```

## Response Objects

### Session Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique session identifier |
| `object` | string | Object type ("realtime.session" or "realtime.transcription_session") |
| `model` | string | Model used for the session |
| `expires_at` | integer | Session expiration timestamp (0 = no expiration) |
| `client_secret` | object | Ephemeral credentials for WebSocket connection |

### Client Secret Object

| Field | Type | Description |
|-------|------|-------------|
| `value` | string | Ephemeral token for authentication |
| `expires_at` | integer | Token expiration timestamp |

## Error Responses

The API returns standard HTTP status codes and error objects:

### 400 Bad Request

```json
{
  "error": {
    "message": "Model 'invalid-model' not found or does not support realtime sessions",
    "type": "invalid_request_error",
    "code": "model_not_found"
  }
}
```

### 401 Unauthorized

```json
{
  "error": {
    "message": "Invalid API key",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}
```

### 429 Rate Limit Exceeded

```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

## Model Configuration

To use the Realtime API, models must be configured with the appropriate endpoint capabilities in your TensorZero configuration:

```toml
# Full realtime session model
[models."gpt-4o-realtime-preview"]
routing = ["openai"]
endpoints = ["realtime_session"]

[models."gpt-4o-realtime-preview".providers.openai]
type = "openai"
model_name = "gpt-4o-realtime-preview-2024-10-01"

# Transcription session model
[models."gpt-4o-mini-transcribe"]
routing = ["openai"]
endpoints = ["realtime_transcription"]

[models."gpt-4o-mini-transcribe".providers.openai]
type = "openai"
model_name = "gpt-4o-mini"
```

## Usage with WebSocket

After creating a session, use the returned `client_secret.value` to establish a WebSocket connection:

```javascript
const websocket = new WebSocket(
  `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01`,
  [],
  {
    headers: {
      "Authorization": `Bearer ${clientSecret}`,
      "OpenAI-Beta": "realtime=v1"
    }
  }
);
```

## Rate Limits

- Session creation: 100 requests per minute per API key
- Concurrent sessions: 10 active sessions per API key
- Session duration: 60 minutes maximum

## Best Practices

1. **Session Management**: Always store session IDs and client secrets securely
2. **Error Handling**: Implement retry logic for transient failures
3. **Audio Quality**: Use PCM16 format for best audio quality
4. **Turn Detection**: Tune thresholds based on your audio environment
5. **Token Management**: Monitor token usage with `max_response_output_tokens`

## Examples

### Python with OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-tensorzero-endpoint.com/v1",
    api_key="your-api-key"
)

# Create a realtime session
session = client.realtime.sessions.create(
    model="gpt-4o-realtime-preview",
    voice="alloy",
    modalities=["text", "audio"],
    instructions="You are a helpful assistant."
)

print(f"Session ID: {session.id}")
print(f"Client Secret: {session.client_secret.value}")
```

### JavaScript/Node.js

```javascript
import OpenAI from 'openai';

const openai = new OpenAI({
  baseURL: 'https://your-tensorzero-endpoint.com/v1',
  apiKey: 'your-api-key'
});

async function createSession() {
  const session = await openai.realtime.sessions.create({
    model: 'gpt-4o-realtime-preview',
    voice: 'alloy',
    modalities: ['text', 'audio'],
    instructions: 'You are a helpful assistant.'
  });
  
  console.log('Session ID:', session.id);
  console.log('Client Secret:', session.client_secret.value);
  
  return session;
}
```

### cURL

```bash
# Create session and extract client secret
RESPONSE=$(curl -s -X POST https://your-tensorzero-endpoint.com/v1/realtime/sessions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-realtime-preview",
    "voice": "alloy",
    "modalities": ["text", "audio"]
  }')

SESSION_ID=$(echo $RESPONSE | jq -r '.id')
CLIENT_SECRET=$(echo $RESPONSE | jq -r '.client_secret.value')

echo "Session ID: $SESSION_ID"
echo "Client Secret: $CLIENT_SECRET"
```

## Troubleshooting

### Common Issues

1. **Model Not Found**: Ensure the model is configured with the correct endpoint capability
2. **Authentication Errors**: Verify API key is valid and has proper permissions
3. **WebSocket Connection Fails**: Check that client secret hasn't expired (60-second lifetime)
4. **Audio Quality Issues**: Verify audio format compatibility and sampling rates

### Debug Mode

Enable debug logging in your TensorZero configuration:

```toml
[gateway]
debug = true
```

This will provide detailed request/response logging for troubleshooting.