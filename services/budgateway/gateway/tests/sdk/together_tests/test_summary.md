# Together AI SDK Test Coverage Summary

This directory contains comprehensive tests for Together AI's integration with TensorZero through the OpenAI-compatible SDK interface.

## Test Files

### 1. `test_ci_together.py`
Basic CI tests for Together AI models without requiring API keys:
- Model routing verification
- Streaming capabilities
- Special character handling in model names
- Cross-provider compatibility
- Multi-turn conversations
- Parameter testing (temperature, max_tokens, etc.)
- Error handling

### 2. `test_universal_openai_sdk.py`
Comprehensive tests demonstrating OpenAI SDK compatibility:
- All Together chat models (Llama, Qwen, Mistral, DeepSeek)
- Streaming responses
- System prompts
- Temperature control
- Multi-turn conversations
- JSON mode support
- Tool calling capabilities
- Cross-provider comparisons
- Edge cases and error scenarios

### 3. `test_together_multimodal.py`
Tests for Together's multimodal capabilities:

#### Embeddings
- Single text embeddings with BGE and M2-BERT models
- Batch embedding processing
- Dimension verification
- Special character and unicode handling
- Empty input error handling
- Format comparison with OpenAI embeddings

#### Image Generation
- FLUX model testing
- Multiple image generation
- Base64 response format
- Different image sizes
- Detailed prompt handling

#### Text-to-Speech
- Basic TTS functionality
- Standard voice testing (alloy, echo, fable, etc.)
- Together-specific voice names (100+ voices)
- Multiple audio formats (mp3, opus, aac, flac, wav, pcm)
- Long text handling
- Multilingual support
- Speed variations

#### Multimodal Integration
- Embedding search pipelines
- Content generation across modalities
- RAG pipeline with embeddings

### 4. `test_together_advanced.py`
Advanced Together AI features:

#### JSON Mode
- Basic JSON output
- Structured output with schemas
- Complex nested JSON structures

#### Tool Calling
- Single tool calls
- Multiple available tools
- Forced tool usage
- Parallel tool calls

#### Reasoning Models
- DeepSeek reasoning capabilities
- Complex multi-step reasoning
- Code analysis and reasoning

#### Advanced Parameters
- Temperature variations
- Top-p sampling
- Frequency and presence penalties
- Seed reproducibility

#### Advanced Streaming
- Streaming with tool calls
- Stop sequences
- Usage statistics in streams

#### Error Handling
- Invalid model names
- Context length limits
- Invalid parameter combinations

### 5. `test_embeddings.py` (NEW)
Comprehensive embedding tests for Together AI:
- Single and batch embedding generation
- Embedding similarity calculations
- Special characters and multilingual text
- Long text handling
- Embedding determinism verification
- Edge cases (empty input, whitespace, etc.)
- Real-world applications (semantic search, clustering)
- Error scenarios

### 6. `test_image_generation.py` (NEW)
Comprehensive image generation tests:
- FLUX model testing with various parameters
- Multiple image generation
- Different response formats (URL, base64)
- Various image sizes and aspect ratios
- Detailed and artistic prompts
- Style variations
- Batch generation
- Special characters in prompts
- Advanced composition and techniques
- Error handling

### 7. `test_text_to_speech.py` (NEW)
Comprehensive TTS tests:
- Basic TTS with all standard voices
- Together's 100+ native voice names
- Multilingual voice testing
- Multiple audio formats
- Long text handling
- Special characters and formatting
- Character and specialty voices
- Conversational and technical content
- Emotional variations
- Sequential audio generation
- Error scenarios

### 8. `test_advanced_features.py` (NEW)
Advanced capability tests:

#### JSON Mode
- Basic JSON generation
- Structured data with schemas
- Nested structures
- Schema compliance

#### Tool Calling
- Single and multiple tools
- Tool selection logic
- Forced tool usage
- Parallel tool calls
- Contextual tool calling

#### Streaming
- Basic streaming
- Streaming with system prompts
- Tool call streaming
- Stop sequences
- Async streaming

#### Reasoning Models
- DeepSeek R1 reasoning
- Complex problem solving
- Code analysis
- Logical puzzles

#### Advanced Parameters
- Temperature effects
- Top-p sampling
- Frequency/presence penalties
- Max tokens control
- Seed reproducibility

#### Integration Scenarios
- RAG pipelines
- Multi-modal workflows
- Conversational assistants
- Code generation pipelines

### 9. `test_ci_together_models.py`
Specific model testing for CI environments with dummy providers.

### 10. `demonstrate_together_openai_sdk.py`
Demonstration script showing real-world usage patterns.

## Rust E2E Tests

In `tensorzero-internal/tests/e2e/openai_compatible.rs`:

### Together-Specific Tests Added:
1. **`test_openai_compatible_embeddings_together`**
   - Tests BGE and M2-BERT embedding models
   - Verifies response format and structure

2. **`test_openai_compatible_embeddings_together_batch`**
   - Batch embedding processing
   - Multiple text inputs
   - Index verification

3. **`test_openai_compatible_audio_speech_together_voices`**
   - Together-specific voice name testing
   - Multiple voice variants
   - Native Together voice names

4. **`test_openai_compatible_image_generation_together_comprehensive`**
   - FLUX model with various parameters
   - Multiple images, sizes, and formats
   - Base64 and URL responses

5. **`test_openai_compatible_together_json_mode`**
   - JSON mode with Together models

6. **`test_openai_compatible_together_tool_calling`**
   - Tool calling with Together models

7. **`test_openai_compatible_together_streaming`**
   - Streaming responses with Together models

8. **`test_openai_compatible_together_error_handling`**
   - Invalid model scenarios
   - Wrong capability usage
   - Cross-endpoint validation

## Coverage Summary

### Endpoints Tested:
- ✅ `/v1/chat/completions` - Full coverage
- ✅ `/v1/embeddings` - Full coverage  
- ✅ `/v1/images/generations` - Full coverage
- ✅ `/v1/audio/speech` - Full coverage
- ❌ `/v1/audio/transcriptions` - Not supported by Together
- ❌ `/v1/audio/translations` - Not supported by Together

### Capabilities Tested:
- ✅ Chat completions with all Together models
- ✅ Embeddings (BGE, M2-BERT)
- ✅ Image generation (FLUX models)
- ✅ Text-to-speech (Cartesia Sonic, 100+ voices)
- ✅ JSON mode
- ✅ Tool calling
- ✅ Streaming
- ✅ Advanced parameters
- ✅ Error handling
- ✅ Cross-provider compatibility

### Models Covered:
- Meta Llama (3.1, 3.2, 3.3 variants)
- Qwen 2.5
- Mistral/Mixtral
- DeepSeek (v2.5, R1)
- FLUX (image generation)
- BGE/M2-BERT (embeddings)
- Cartesia Sonic (TTS)

## Running the Tests

### Python Tests
```bash
# Run all Together tests
pytest gateway/tests/sdk/together_tests/ -v

# Run specific test file
pytest gateway/tests/sdk/together_tests/test_together_multimodal.py -v

# Run with real API key (not CI mode)
TOGETHER_API_KEY=your_key pytest gateway/tests/sdk/together_tests/test_universal_openai_sdk.py -v
```

### Rust Tests
```bash
# Run all OpenAI-compatible tests including Together
cargo test --package tensorzero-internal --test e2e test_openai_compatible

# Run specific Together tests
cargo test --package tensorzero-internal test_openai_compatible_embeddings_together
cargo test --package tensorzero-internal test_openai_compatible_audio_speech_together
cargo test --package tensorzero-internal test_openai_compatible_image_generation_together
```

## Notes

1. Most tests use dummy providers for CI environments and don't require real API keys
2. Tests verify request routing and response structure rather than actual model outputs
3. Error scenarios test proper error handling without making real API calls
4. The tests demonstrate that Together AI models work seamlessly with the OpenAI SDK
5. All Together-specific features (native voice names, model naming conventions) are properly handled