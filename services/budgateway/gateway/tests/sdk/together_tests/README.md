# Together AI SDK Tests

This directory contains comprehensive tests demonstrating Together AI models working through TensorZero's universal OpenAI SDK compatibility layer.

## Overview

These tests showcase how Together AI's diverse model portfolio (Llama, Qwen, Mistral, DeepSeek, FLUX, embeddings, TTS) works seamlessly with the OpenAI SDK through TensorZero, without requiring the Together AI Python SDK.

## Test Files

### Core Tests
- `test_universal_openai_sdk.py` - Full integration tests with real Together AI API
- `test_ci_together.py` - CI-friendly tests using dummy providers (no API key required)
- `demonstrate_together_openai_sdk.py` - Interactive demonstration script

### Capability-Specific Tests
- `test_embeddings.py` - Comprehensive embedding tests (BGE, M2-BERT)
- `test_image_generation.py` - FLUX image generation tests
- `test_text_to_speech.py` - Cartesia Sonic TTS with 100+ voices
- `test_advanced_features.py` - JSON mode, tool calling, streaming, reasoning

### Additional Tests
- `test_together_multimodal.py` - Multimodal integration scenarios
- `test_together_advanced.py` - Advanced features and parameters
- `test_ci_together_models.py` - Model-specific CI tests

## Running Tests

### CI Tests (No API Key Required)

```bash
# From the sdk directory
cd gateway/tests/sdk
./run_tests.sh --provider together --mode ci
```

### Full Integration Tests

Requires `TOGETHER_API_KEY` environment variable:

```bash
# Set your API key
export TOGETHER_API_KEY="your-together-api-key"

# Run full tests
./run_tests.sh --provider together --mode full
```

### Using the Together-specific runner

```bash
# Run all Together AI tests
./run_tests_together.sh
```

## Test Configuration

Tests use two configuration files:

1. `test_config_together.toml` - Real Together AI provider configuration
2. `test_config_together_ci.toml` - Dummy provider for CI testing

## Supported Models

The tests cover Together AI's full model portfolio:

### Chat Models
- **Llama Models**: Llama 3.3, 3.2, 3.1 (8B to 405B)
- **Qwen Models**: Qwen 2.5 72B
- **Mistral Models**: Mixtral 8x7B
- **DeepSeek Models**: DeepSeek v2.5, DeepSeek R1

### Embedding Models
- **BGE Base**: BAAI/bge-base-en-v1.5 (768 dimensions)
- **M2-BERT**: togethercomputer/m2-bert-80M-8k-retrieval

### Image Generation
- **FLUX Models**: FLUX.1 schnell for fast generation

### Text-to-Speech
- **Cartesia Sonic**: 100+ voices including multilingual options

## Key Features Tested

### Chat Completions
1. **Basic Chat** - Standard message generation
2. **Streaming** - Real-time token streaming
3. **System Prompts** - Model instruction capabilities
4. **Tool Calling** - Function calling with parallel execution
5. **JSON Mode** - Structured output generation
6. **Advanced Parameters** - Temperature, top-p, frequency penalties

### Embeddings
1. **Single & Batch** - Process one or multiple texts
2. **Similarity** - Semantic similarity calculations
3. **Multilingual** - Support for various languages
4. **Applications** - RAG, semantic search, clustering

### Image Generation
1. **Multiple Images** - Generate up to N images
2. **Sizes** - Various resolutions and aspect ratios
3. **Formats** - URL or base64 responses
4. **Styles** - Artistic techniques and compositions

### Text-to-Speech
1. **Voice Variety** - 100+ voices with different accents
2. **Languages** - Multilingual voice support
3. **Formats** - MP3, Opus, AAC, FLAC, WAV, PCM
4. **Customization** - Speed control, emotional variations

## Architecture Benefits

These tests demonstrate that:

- ✅ Together AI models work perfectly with OpenAI SDK
- ✅ No Together AI SDK required - just OpenAI SDK
- ✅ Same code works across OpenAI, Anthropic, and Together AI
- ✅ Full feature parity with native implementations

## Example Usage

```python
from openai import OpenAI

# One client for all providers
client = OpenAI(
    base_url="http://localhost:3001/v1",
    api_key="your-tensorzero-key"
)

# Chat completion
response = client.chat.completions.create(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Embeddings
embeddings = client.embeddings.create(
    model="together-bge-base",
    input=["Text to embed"]
)

# Image generation
images = client.images.generate(
    model="flux-schnell",
    prompt="A beautiful sunset",
    n=1
)

# Text-to-speech
audio = client.audio.speech.create(
    model="together-tts",
    voice="storyteller lady",
    input="Once upon a time..."
)
```

## Adding New Together AI Models

To test a new Together AI model:

1. Add it to `test_config_together.toml` and `test_config_together_ci.toml`
2. Include it in the model lists in test files
3. Configure with appropriate endpoints:
   - Chat models: `endpoints = ["chat"]`
   - Embedding models: `endpoints = ["embedding"]`
   - Image models: `endpoints = ["image_generation"]`
   - TTS models: `endpoints = ["text_to_speech"]`

## Test Coverage

| Feature | Test File | Coverage |
|---------|-----------|----------|
| Chat Completions | `test_universal_openai_sdk.py` | ✅ Full |
| Embeddings | `test_embeddings.py` | ✅ Full |
| Image Generation | `test_image_generation.py` | ✅ Full |
| Text-to-Speech | `test_text_to_speech.py` | ✅ Full |
| JSON Mode | `test_advanced_features.py` | ✅ Full |
| Tool Calling | `test_advanced_features.py` | ✅ Full |
| Streaming | `test_advanced_features.py` | ✅ Full |
| Reasoning Models | `test_advanced_features.py` | ✅ Full |

## Troubleshooting

- **Gateway not running**: Start with `cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_together.toml`
- **API key errors**: Ensure `TOGETHER_API_KEY` is set in your environment
- **Model not found**: Check the model name matches Together AI's exact naming
- **Endpoint errors**: Verify model is configured for the correct endpoint capability
- **Rate limits**: Together has rate limits; add delays if needed

## Contributing

When adding new Together features:
1. Create tests in appropriate test file
2. Test both success and error cases
3. Verify OpenAI SDK compatibility
4. Update this README
5. Ensure CI tests work without API keys