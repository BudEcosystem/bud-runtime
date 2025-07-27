# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

### Building
```bash
cargo build                     # Development build
cargo build --release          # Production build
cargo build --workspace        # Build all workspace members
```

### Testing
```bash
cargo test                     # Run all tests
cargo test --workspace         # Run tests for all workspace members
cargo test test_name           # Run specific test
cargo test --lib              # Run only library tests
cargo test --package tensorzero-internal  # Test specific package
```

### Running the Gateway
```bash
# Development mode with custom config
cargo run --bin gateway -- --config-file test_tensorzero.toml

# Production mode
cargo run --release --bin gateway -- --config-file tensorzero.toml

# With environment variables
TENSORZERO_CLICKHOUSE_URL=... cargo run --bin gateway -- --config-file tensorzero.toml
```

### Code Quality
```bash
cargo fmt                      # Format code
cargo clippy -- -D warnings    # Lint with all warnings as errors
cargo check                    # Quick compilation check
```

## Architecture Overview

### Unified Model System

TensorZero uses a unified model configuration system where all models (chat, embedding, moderation) are configured in a single `models` table with endpoint capabilities:

```toml
[models."gpt-4"]
routing = ["primary_provider", "fallback_provider"]
endpoints = ["chat"]  # Capabilities: chat, embedding, moderation

[models."gpt-4".providers.primary_provider]
type = "openai"
model_name = "gpt-4"
api_key_location = { env = "OPENAI_API_KEY" }

[models."text-embedding-ada-002"]
routing = ["openai"]
endpoints = ["embedding"]

[models."omni-moderation-latest"]
routing = ["openai"]
endpoints = ["moderation"]
```

### Endpoint Structure

All OpenAI-compatible endpoints are implemented in `tensorzero-internal/src/endpoints/openai_compatible.rs`:

1. **Handler Function**: Processes the HTTP request
2. **Parameter Conversion**: Converts OpenAI format to internal format
3. **Model Resolution**: Resolves model name based on authentication
4. **Capability Check**: Verifies model supports the required endpoint
5. **Provider Routing**: Routes to appropriate provider based on model config
6. **Response Formatting**: Converts internal response to OpenAI format

### Adding New Endpoints (e.g., Audio)

To add new endpoints like `/v1/audio/transcriptions` or `/v1/audio/speech`:

1. **Define Capability** in `tensorzero-internal/src/endpoints/capability.rs`:
```rust
pub enum EndpointCapability {
    Chat,
    Embedding,
    Moderation,
    AudioTranscription,  // New
    AudioSpeech,         // New
}
```

2. **Add Route** in `gateway/src/main.rs`:
```rust
let openai_routes = Router::new()
    .route("/v1/chat/completions", post(endpoints::openai_compatible::inference_handler))
    .route("/v1/audio/transcriptions", post(endpoints::openai_compatible::audio_transcription_handler))  // New
    .route("/v1/audio/speech", post(endpoints::openai_compatible::audio_speech_handler));  // New
```

3. **Implement Handler** in `tensorzero-internal/src/endpoints/openai_compatible.rs`:
```rust
pub async fn audio_transcription_handler(
    State(app_state): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<OpenAIAudioTranscriptionParams>,
) -> Result<Response<Body>, Error> {
    // 1. Resolve model name
    // 2. Check model has AudioTranscription capability
    // 3. Route to provider
    // 4. Return OpenAI-compatible response
}
```

4. **Add Provider Support**:
   - Add trait method to provider (e.g., `transcribe()` for OpenAI provider)
   - Implement for each supporting provider
   - Handle provider-specific request/response formats

5. **Update Model Config**:
```toml
[models."whisper-1"]
routing = ["openai"]
endpoints = ["audio_transcription"]
```

### Provider Integration Pattern

Providers follow a consistent pattern:

1. **Trait Definition**: Define capability trait (e.g., `AudioTranscriptionProvider`)
2. **Implementation**: Provider-specific implementation in `inference/providers/`
3. **Request/Response Types**: Provider-specific types with conversion to/from internal types
4. **Error Handling**: Convert provider errors to internal error types
5. **Authentication**: Handle API keys via `InferenceCredentials`

### Authentication System

- Controlled by `gateway.authentication` in config
- When enabled, requires API key validation via Redis
- OpenAI routes use authentication middleware
- Internal routes remain public

### Caching Considerations

- Chat/embedding requests support caching via ClickHouse
- Moderation explicitly disables caching (see `cache_options` in moderation handler)
- Audio endpoints should consider whether caching makes sense

### Error Handling

All errors flow through the unified `Error` type with `ErrorDetails` enum. New endpoint-specific errors should be added to `ErrorDetails`.

### Testing Strategy

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test endpoint handlers with mock providers
3. **E2E Tests**: Full request/response cycle with test configs
4. **Provider Tests**: Mock provider responses for consistent testing

### Recent Changes

The moderation system was recently unified under the model system:
- Removed separate `moderation_models` configuration
- Moderation is now an endpoint capability like chat/embedding
- Models declare moderation support via `endpoints = ["moderation"]`
- Simplified configuration and reduced code duplication

Audio endpoints have been added following the same unified model pattern:
- Audio capabilities: `audio_transcription`, `audio_translation`, `text_to_speech`
- Multipart form data handling for file uploads using `axum::extract::Multipart`
- Binary response handling for TTS endpoints
- No caching for audio endpoints (similar to moderation)

## Key Principles

1. **Type Safety**: Use Rust's type system to prevent errors at compile time
2. **Unified Configuration**: All models use the same configuration structure
3. **Provider Abstraction**: Providers implement traits for capabilities they support
4. **OpenAI Compatibility**: Maintain API compatibility while using internal types
5. **Performance**: Keep latency <1ms P99 for gateway operations
6. **Observability**: Comprehensive logging, metrics, and tracing

## Common Patterns

### Adding a New Model Type
1. Add endpoint capability
2. Define request/response types
3. Implement handler
4. Add provider trait and implementations
5. Update router
6. Add tests

### Debugging
- Enable debug mode: `gateway.debug = true` in config
- Check logs for request/response details
- Use `tracing::debug!` for development logging
- Verify model capabilities match endpoint requirements

### Performance Considerations
- Minimize allocations in hot paths
- Use `Arc` for shared immutable data
- Stream responses when possible
- Cache expensive computations

## Audio Implementation Details

### Audio Endpoints Overview

TensorZero implements three OpenAI-compatible audio endpoints:
- `/v1/audio/transcriptions` - Convert audio to text (speech-to-text)
- `/v1/audio/translations` - Convert audio to English text
- `/v1/audio/speech` - Generate audio from text (text-to-speech)

### Key Implementation Patterns

1. **Multipart Form Data**: Transcription/translation endpoints use `axum::extract::Multipart` for file uploads
2. **Binary Responses**: TTS endpoint returns raw audio bytes with appropriate content-type headers
3. **File Validation**: 25MB size limit, supported audio format validation
4. **Response Formats**: Support for json, text, srt, verbose_json, vtt (though srt/vtt not yet implemented)

### Audio-Specific Types

Located in `tensorzero-internal/src/audio.rs`:
- Request types: `AudioTranscriptionRequest`, `AudioTranslationRequest`, `TextToSpeechRequest`
- Response types: `AudioTranscriptionResponse`, `AudioTranslationResponse`, `TextToSpeechResponse`
- Provider traits: `AudioTranscriptionProvider`, `AudioTranslationProvider`, `TextToSpeechProvider`
- Enums: `AudioTranscriptionResponseFormat`, `AudioVoice`, `AudioOutputFormat`, `TimestampGranularity`

## RSA Encryption for API Keys

TensorZero supports RSA decryption for API keys stored in Redis by external services:

### Configuration

Set environment variables to enable RSA decryption:
```bash
# Option 1: Private key file path
TENSORZERO_RSA_PRIVATE_KEY_PATH=/path/to/private_key.pem
TENSORZERO_RSA_PRIVATE_KEY_PASSWORD=your_password

# Option 2: Inline private key
TENSORZERO_RSA_PRIVATE_KEY="-----BEGIN ENCRYPTED PRIVATE KEY-----..."
TENSORZERO_RSA_PRIVATE_KEY_PASSWORD=your_password
```

### Encryption Details

- **Algorithm**: RSA with OAEP padding (SHA256)
- **Key Format**: PEM format (PKCS#1 or PKCS#8, with optional password protection)
- **Encoding**: Encrypted API keys are hex-encoded in Redis
- **Fallback**: Also supports PKCS#1 v1.5 padding and base64 encoding

### Implementation

The encryption module (`tensorzero-internal/src/encryption.rs`) provides:
- `load_private_key()`: Loads RSA private key from environment
- `decrypt_api_key()`: Decrypts hex or base64 encoded API keys
- `is_decryption_enabled()`: Checks if decryption is configured

When Redis data contains encrypted API keys, they are automatically decrypted before being stored in the credential store.

### Model Configuration for Audio

```toml
# Speech-to-text model
[models."whisper-1"]
routing = ["openai"]
endpoints = ["audio_transcription", "audio_translation"]

[models."whisper-1".providers.openai]
type = "openai"
model_name = "whisper-1"

# Text-to-speech model
[models."tts-1"]
routing = ["openai"]
endpoints = ["text_to_speech"]

[models."tts-1".providers.openai]
type = "openai"
model_name = "tts-1"
```

### Provider Implementation

The OpenAI provider implements all three audio traits in `inference/providers/openai.rs`:
- Uses multipart form requests for transcription/translation
- Handles JSON and text response formats
- Returns binary audio data for TTS
- Proper error handling for audio-specific failures

### Testing Audio Endpoints

1. **Unit Tests**: Test request/response type conversions
2. **Integration Tests**: Test with mock audio files and responses
3. **E2E Tests**: Full cycle with actual file uploads/downloads
4. **Manual Testing**: Use curl or API clients with real audio files

Example test command:
```bash
curl -X POST http://localhost:3000/v1/audio/transcriptions \
  -H "Authorization: Bearer test-key" \
  -F "file=@test.mp3" \
  -F "model=whisper-1"
```

### Future Enhancements

- Streaming support for real-time transcription
- SRT/VTT subtitle format generation
- Additional audio format support
- WebSocket support for bidirectional audio streaming
- Audio file validation beyond size checks

## Responses API Implementation Details

### Responses API Overview

TensorZero implements OpenAI's next-generation Responses API endpoints:
- `/v1/responses` - Create a new response (POST)
- `/v1/responses/{response_id}` - Retrieve a response (GET)
- `/v1/responses/{response_id}` - Delete a response (DELETE)
- `/v1/responses/{response_id}/cancel` - Cancel a response (POST)
- `/v1/responses/{response_id}/input_items` - List input items (GET)

### Key Features

1. **Stateful Conversations**: Support for multi-turn conversations with `previous_response_id`
2. **Advanced Tool Calling**: Parallel tool calls, MCP tools support, tool choice control
3. **Reasoning Models**: Special support for o1 and reasoning-capable models
4. **Multimodal Support**: Text, images, audio, and other modalities
5. **Streaming**: Server-Sent Events (SSE) for real-time responses
6. **Metadata**: Custom metadata and user tracking
7. **Background Processing**: Async response generation

### Implementation Architecture

The gateway acts as a routing layer:
- No state management in the gateway
- Providers handle all complex logic
- Simple pass-through with format conversion
- Streaming handled similarly to chat completions

### Responses-Specific Types

Located in `tensorzero-internal/src/responses.rs`:
- Request types: `OpenAIResponseCreateParams`
- Response types: `OpenAIResponse`, `ResponseStatus`, `ResponseUsage`, `ResponseError`
- Streaming types: `ResponseStreamEvent`, `ResponseEventType`
- Provider trait: `ResponseProvider`

### Model Configuration for Responses

```toml
# Standard responses model
[models."gpt-4-responses"]
routing = ["openai"]
endpoints = ["responses"]

[models."gpt-4-responses".providers.openai]
type = "openai"
model_name = "gpt-4"

# Reasoning model with responses support
[models."o1-responses"]
routing = ["openai"]
endpoints = ["responses"]

[models."o1-responses".providers.openai]
type = "openai"
model_name = "o1"
```

### Provider Implementation

The ResponseProvider trait requires:
```rust
async fn create_response(...) -> Result<OpenAIResponse, Error>;
async fn stream_response(...) -> Result<Box<dyn Stream<...>>, Error>;
```

Implemented by:
- OpenAI provider (full implementation)
- Dummy provider (for testing)

### Key Implementation Decisions

1. **No Gateway State**: All state management delegated to providers
2. **Streaming Reuse**: Uses existing streaming infrastructure from chat completions
3. **Error Handling**: Non-supported operations return clear error messages
4. **Unknown Fields**: Accepted with warnings for forward compatibility
5. **Model Resolution for Non-Create Operations**: Since OpenAI's API doesn't include a model parameter for retrieve/delete/cancel/list operations, TensorZero requires the model name to be specified via the `x-model-name` header. If not provided, it defaults to `gpt-4-responses`.

### Testing Responses API

1. **Unit Tests**: Type serialization/deserialization tests
2. **Integration Tests**: Handler logic and model resolution
3. **E2E Tests**: Full request/response cycle (in `tests/e2e/responses.rs`)

Example test requests:
```bash
# Create a response
curl -X POST http://localhost:3000/v1/responses \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4-responses",
    "input": "Hello, world!",
    "instructions": "Be helpful",
    "stream": true
  }'

# Retrieve a response (note the x-model-name header)
curl -X GET http://localhost:3000/v1/responses/resp_123 \
  -H "Authorization: Bearer test-key" \
  -H "x-model-name: gpt-4-responses"

# Delete a response
curl -X DELETE http://localhost:3000/v1/responses/resp_123 \
  -H "Authorization: Bearer test-key" \
  -H "x-model-name: gpt-4-responses"

# Cancel a response
curl -X POST http://localhost:3000/v1/responses/resp_123/cancel \
  -H "Authorization: Bearer test-key" \
  -H "x-model-name: gpt-4-responses"

# List input items
curl -X GET http://localhost:3000/v1/responses/resp_123/input_items \
  -H "Authorization: Bearer test-key" \
  -H "x-model-name: gpt-4-responses"
```

### Future Considerations

- State persistence for conversation management
- Integration with existing inference pipeline
- Caching strategy for responses
- Metrics and observability for response lifecycle
- Provider-specific optimizations

## Together Provider Image Generation

### Overview

The Together provider now supports image generation through OpenAI-compatible endpoints, enabling access to FLUX.1 image generation models:
- **FLUX.1 [schnell]** - Fast open-source model with free tier
- **FLUX1.1 [pro]** - Premium model
- **FLUX.1 [pro]** - High-performance production model

### Configuration

```toml
# Image generation model configuration
[models."flux-schnell"]
routing = ["together"]
endpoints = ["image_generation"]

[models."flux-schnell".providers.together]
type = "together"
model_name = "black-forest-labs/FLUX.1-schnell"

# For premium models
[models."flux-1-1-pro"]
routing = ["together"]
endpoints = ["image_generation"]

[models."flux-1-1-pro".providers.together]
type = "together"
model_name = "black-forest-labs/FLUX1.1-pro"
```

### API Usage

Together's image generation follows the OpenAI-compatible format:

```bash
# Generate an image
curl -X POST http://localhost:3000/v1/images/generations \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "flux-schnell",
    "prompt": "A beautiful sunset over mountains",
    "n": 1,
    "size": "1024x1024",
    "response_format": "url"
  }'
```

### Implementation Details

1. **Provider Implementation**: `TogetherProvider` implements the `ImageGenerationProvider` trait
2. **Endpoint**: Uses Together's OpenAI-compatible endpoint: `https://api.together.xyz/v1/images/generations`
3. **Authentication**: Uses the same API key configuration as chat completions
4. **Response Format**: Returns standard OpenAI image response format with URLs or base64 data

### Together-Specific Parameters

While the implementation uses OpenAI-compatible format, Together supports additional parameters:
- `steps`: Number of inference steps (currently set to default)
- `disable_safety_checker`: Boolean flag for safety filter (currently set to default)

These can be added in future enhancements if needed.

### Limitations

- Only image generation is supported (no image editing or variations)
- Together-specific parameters are not yet exposed through the API
- No caching support for image generation responses

### Testing

```bash
# Run unit tests
cargo test --package tensorzero-internal test_together_image

# Run integration tests (requires test configuration)
cargo test --package tensorzero-internal test_openai_compatible_image_generation
```

## xAI Provider Image Generation

### Overview

The xAI provider now supports image generation through OpenAI-compatible endpoints, enabling access to xAI's `grok-2-image` model:
- **grok-2-image** - xAI's high-quality image generation model
- **Pricing**: $0.07 per image
- **Rate Limits**: 5 requests/second, up to 10 images per request
## Together Provider Text-to-Speech

### Overview

The Together provider now supports text-to-speech (TTS) through OpenAI-compatible endpoints, enabling access to Cartesia's Sonic model:
- **Cartesia Sonic** - High-quality text-to-speech model with 100+ available voices
- **Real-time generation** - Fast synthesis suitable for interactive applications
- **Multiple output formats** - Support for MP3 and raw PCM audio

### Configuration

```toml
# Image generation model configuration
[models."grok-2-image"]
routing = ["xai"]
endpoints = ["image_generation"]

[models."grok-2-image".providers.xai]
type = "xai"
model_name = "grok-2-image"
api_key_location = { env = "XAI_API_KEY" }
# Text-to-speech model configuration
[models."together-tts"]
routing = ["together"]
endpoints = ["text_to_speech"]

[models."together-tts".providers.together]
type = "together"
model_name = "cartesia/sonic"
```

### API Usage

xAI's image generation follows the OpenAI-compatible format:

```bash
# Generate an image
curl -X POST http://localhost:3000/v1/images/generations \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-2-image",
    "prompt": "A futuristic city at sunset",
    "n": 1,
    "response_format": "url"
  }'
```

### Implementation Details

1. **Provider Implementation**: `XAIProvider` implements the `ImageGenerationProvider` trait
2. **Endpoint**: Uses xAI's OpenAI-compatible endpoint: `https://api.x.ai/v1/images/generations`
3. **Authentication**: Uses the same API key configuration as chat completions
4. **Response Format**: Returns standard OpenAI image response format with URLs or base64 data

### Supported Parameters

xAI supports a subset of OpenAI's image generation parameters:
- `model`: Always "grok-2-image"
- `prompt`: Required string describing the image to generate
- `n`: Number of images to generate (1-10, default: 1)
- `response_format`: "url" or "b64_json" (default: "url")
- `user`: Optional string for abuse monitoring

### Limitations

Unlike OpenAI's DALL-E models, xAI currently doesn't support:
- `quality`: Not supported by xAI API
- `size`: Not supported by xAI API
- `style`: Not supported by xAI API

These parameters are ignored gracefully if provided.

### Error Handling

The xAI provider includes comprehensive error handling for:
- Rate limiting (5 requests/second)
- Invalid prompts or content policy violations
- Network timeouts and connection issues
- Authentication failures
Together's TTS follows the OpenAI-compatible format:

```bash
# Generate speech from text
curl -X POST http://localhost:3000/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "together-tts",
    "input": "Hello, this is a test of Together AI text-to-speech.",
    "voice": "alloy",
    "response_format": "mp3"
  }'
```

### Voice Support

TensorZero supports **all of Together AI's 100+ voices** through flexible voice handling:

#### Standard Voice Mapping
TensorZero's standardized voice names are mapped to Together's descriptive voice names:

| TensorZero Voice | Together Voice Name         | Description                    |
|------------------|----------------------------|--------------------------------|
| `alloy`          | `helpful woman`            | Clear, professional female     |
| `echo`           | `laidback woman`           | Relaxed, casual female         |
| `fable`          | `meditation lady`          | Calm, soothing female          |
| `onyx`           | `newsman`                  | Authoritative male narrator    |
| `nova`           | `friendly sidekick`        | Enthusiastic, supportive       |
| `shimmer`        | `british reading lady`     | British accent, clear diction  |
| `ash`            | `barbershop man`           | Warm, conversational male      |
| `ballad`         | `indian lady`              | Indian accent female           |
| `coral`          | `german conversational woman` | German accent female        |
| `sage`           | `pilot over intercom`      | Clear, professional male       |
| `verse`          | `australian customer support man` | Australian accent male  |

#### Full Voice Catalog Support
You can use **any of Together AI's voices directly** by specifying the exact voice name:

**Popular Together Voices:**
- `german conversational woman`
- `french narrator lady`
- `japanese woman conversational`
- `british narration lady`
- `spanish narrator man`
- `meditation lady`
- `helpful woman`
- `newsman`
- `1920's radioman`
- `calm lady`
- `wise man`
- `customer support lady`
- `announcer man`
- `asmr lady`
- `storyteller lady`
- `princess`
- `doctor mischief`
- And 80+ more voices!

### Implementation Details

1. **Provider Implementation**: `TogetherProvider` implements the `TextToSpeechProvider` trait
2. **Endpoint**: Uses Together's audio endpoint: `https://api.together.xyz/v1/audio/generations`
3. **Model**: Always uses `cartesia/sonic` (Together's only TTS model)
4. **Authentication**: Uses the same API key configuration as chat completions
5. **Sample Rate**: Automatically set to 44.1kHz for optimal quality

### Supported Output Formats

- **MP3** - Compressed audio format (default)
- **Raw PCM** - Uncompressed audio for processing

### Usage Examples

```bash
# Standard OpenAI voice (mapped to Together voice)
curl -X POST http://localhost:3000/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "together-tts",
    "input": "The weather today is sunny and warm.",
    "voice": "nova"
  }'

# Together-specific voice (used directly)
curl -X POST http://localhost:3000/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "together-tts",
    "input": "Bonjour! Comment allez-vous?",
    "voice": "french narrator lady",
    "response_format": "mp3"
  }'

# Another Together-specific voice example
curl -X POST http://localhost:3000/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "together-tts",
    "input": "Guten Tag! Wie geht es Ihnen?",
    "voice": "german conversational woman"
  }'

# Creative voice example
curl -X POST http://localhost:3000/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "together-tts",
    "input": "Welcome to the magical realm!",
    "voice": "princess"
  }'
```

### Limitations

- Only text-to-speech is supported (no speech-to-text or translation)
- Limited to Cartesia Sonic model (no model selection)
- No streaming support (planned for future enhancement)
- No caching support for audio responses

### Error Handling

Common error scenarios:
- **Unsupported Format**: Returns error for formats other than MP3 or raw PCM
- **Authentication**: Returns API key missing error without valid Together API key
- **Rate Limits**: Subject to Together AI's rate limiting policies

### Testing

```bash
# Run unit tests for xAI image generation
cargo test --package tensorzero-internal test_xai_image

# Run all xAI provider tests
cargo test --package tensorzero-internal --lib xai
```

### Future Enhancements

Potential improvements that could be added when xAI expands their API:
- Image size control
- Quality settings
- Style parameters
- Batch processing optimizations
# Run unit tests for voice mapping and serialization
cargo test --package tensorzero-internal test_map_audio_voice_to_together
cargo test --package tensorzero-internal test_together_tts_request_serialization

# Run integration tests (requires test configuration and gateway)
cargo test --test e2e --features e2e_tests test_openai_compatible_audio_speech_with_together
```

### Pricing

Text-to-speech with Cartesia Sonic is priced at $65 per 1 million characters. For current pricing details, refer to [Together AI's pricing page](https://www.together.ai/pricing).

## Fireworks Provider Multimodal Support

### Overview

The Fireworks provider now supports multiple capabilities beyond chat completions:
- **Embeddings** - Text embeddings with models like Nomic Embed
- **Image Generation** - Limited support (Fireworks uses async workflow API, not fully compatible)
- **Audio Transcription** - Speech-to-text with Whisper v3 models
- **Audio Translation** - Audio to English text translation with Whisper v3 models

### Configuration

#### Embeddings
```toml
[models."nomic-embed"]
routing = ["fireworks"]
endpoints = ["embedding"]

[models."nomic-embed".providers.fireworks]
type = "fireworks"
model_name = "nomic-ai/nomic-embed-text-v1.5"
```

#### Image Generation (Limited Support)
```toml
# NOTE: Fireworks uses an async workflow API for image generation
# that returns a request_id instead of images directly.
# This is not currently compatible with TensorZero's synchronous interface.
# The provider will return an error explaining this limitation.

[models."stable-diffusion-xl"]
routing = ["fireworks"]
endpoints = ["image_generation"]

[models."stable-diffusion-xl".providers.fireworks]
type = "fireworks"
model_name = "stable-diffusion-xl"

# FLUX models
[models."flux-schnell"]
routing = ["fireworks"]
endpoints = ["image_generation"]

[models."flux-schnell".providers.fireworks]
type = "fireworks"
model_name = "flux-schnell"
```

#### Audio Transcription & Translation
```toml
[models."whisper-v3"]
routing = ["fireworks"]
endpoints = ["audio_transcription", "audio_translation"]

[models."whisper-v3".providers.fireworks]
type = "fireworks"
model_name = "whisper-v3"

# Whisper v3 turbo for faster transcription/translation
[models."whisper-v3-turbo"]
routing = ["fireworks"]
endpoints = ["audio_transcription", "audio_translation"]

[models."whisper-v3-turbo".providers.fireworks]
type = "fireworks"
model_name = "whisper-v3-turbo"
```

### API Usage

#### Embeddings
```bash
curl -X POST http://localhost:3000/v1/embeddings \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed",
    "input": "Your text to embed"
  }'
```

#### Image Generation
```bash
curl -X POST http://localhost:3000/v1/images/generations \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "stable-diffusion-xl",
    "prompt": "A beautiful sunset over mountains",
    "n": 1,
    "size": "1024x1024",
    "response_format": "url"
  }'
```

#### Audio Transcription
```bash
curl -X POST http://localhost:3000/v1/audio/transcriptions \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@audio.mp3" \
  -F "model=whisper-v3" \
  -F "response_format=json"
```

#### Audio Translation
```bash
curl -X POST http://localhost:3000/v1/audio/translations \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@audio.mp3" \
  -F "model=whisper-v3" \
  -F "response_format=json"
```

### Implementation Details

1. **Provider Implementation**: `FireworksProvider` implements:
   - `EmbeddingProvider` trait for embeddings
   - `ImageGenerationProvider` trait for image generation
   - `AudioTranscriptionProvider` trait for audio transcription
   - `AudioTranslationProvider` trait for audio translation

2. **API Endpoints**: All endpoints use Fireworks' OpenAI-compatible API:
   - Base URL: `https://api.fireworks.ai/inference/v1/`
   - Embeddings: `/embeddings`
   - Images: `/images/generations`
   - Audio Transcription: `/audio/transcriptions`
   - Audio Translation: `/audio/translations`

3. **Authentication**: Uses the same API key configuration as chat completions:
   - Environment variable: `FIREWORKS_API_KEY`
   - Or configured via `api_key_location` in the model config

### Supported Features

#### Embeddings
- Single and batch text embedding
- Optional encoding format (base64)
- Dimension parameter support (model-dependent)
- Models: Nomic Embed v1.5 and others

#### Image Generation
- Multiple image generation (n parameter)
- Size control
- Response format: URL or base64
- Models: Stable Diffusion XL, SSD-1B, Playground v2, FLUX models

#### Audio Transcription & Translation
- File upload via multipart form data
- Response formats: json, text (srt/vtt planned)
- Language detection and specification
- Temperature control for transcription
- Translation to English from any source language
- Models: Whisper v3, Whisper v3 turbo

### Limitations

- Audio endpoints may use special regional URLs (currently using default routing)
- Image generation uses Fireworks' async workflow API which returns a request_id instead of images directly. This is not compatible with TensorZero's synchronous image generation interface
- No support for text-to-speech through Fireworks

### Testing

```bash
# Run unit tests
cargo test --package tensorzero-internal --lib fireworks::tests

# Test specific functionality
cargo test --package tensorzero-internal test_fireworks_embedding
cargo test --package tensorzero-internal test_fireworks_image
cargo test --package tensorzero-internal test_fireworks_audio
```

### Error Handling

All implementations include proper error handling for:
- Authentication failures
- Network errors
- Invalid responses
- Model-specific errors

The provider reuses the OpenAI error handling where applicable for consistency.
