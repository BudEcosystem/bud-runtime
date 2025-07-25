# TensorZero SDK Integration Tests

This directory contains integration tests that validate TensorZero's compatibility with various AI provider SDKs including OpenAI, Anthropic, and more.

## Quick Start

```bash
# Run all CI tests (no API keys required)
./run_tests.sh

# Run OpenAI tests only
./run_tests.sh --provider openai

# Run Anthropic tests with real API
./run_tests.sh --provider anthropic --mode full

# Run Universal SDK Compatibility tests
./run_tests.sh --provider universal

# Run interactive architecture demonstration
./run_tests.sh --demo

# See all options
./run_tests.sh --help
```

## Setup

1. **Install Dependencies**
   ```bash
   cd gateway/tests/sdk
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your API keys for full tests
   ```

3. **Start TensorZero Gateway**
   ```bash
   # For CI tests (dummy provider)
   cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_[provider]_ci.toml
   
   # For full tests (real provider)
   cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_[provider].toml
   ```

## Recent Improvements

🎉 **Major SDK Test Suite Cleanup Completed!**

- ✅ **Removed redundant scripts** - Eliminated duplicate test runners  
- ✅ **Enhanced common infrastructure** - Added universal client factory and shared validation
- ✅ **Created universal test suites** - Reusable test classes that work across all providers
- ✅ **Consolidated duplicate tests** - Unified cross-provider testing in `universal_tests/`
- ✅ **Improved Together tests** - Updated to use shared infrastructure instead of duplicating code

### New Universal Test Architecture

The test suite now follows a **Universal SDK Architecture** with shared infrastructure:

```
common/
├── utils.py           # Universal client factory, validation, test data
├── test_suites.py     # Reusable test suites for all providers  
└── base_test.py       # Abstract base classes

universal_tests/       # NEW! Consolidated cross-provider tests
├── test_openai_sdk_all_providers.py    # Universal SDK compatibility  
├── test_cross_provider_comparison.py   # Side-by-side provider comparison
└── conftest.py        # Shared fixtures
```

## Running Tests

### Universal Test Runner

The `run_tests.sh` script provides a unified interface for all SDK tests:

```bash
# Run all providers in CI mode (default)
./run_tests.sh

# Run specific provider
./run_tests.sh --provider openai
./run_tests.sh --provider anthropic

# Run Universal SDK Compatibility tests (NEW!)
./run_tests.sh --provider universal

# Run interactive architecture demonstration (NEW!)
./run_tests.sh --demo

# Run new consolidated universal tests
cd universal_tests && pytest test_openai_sdk_all_providers.py -v
cd universal_tests && pytest test_cross_provider_comparison.py -v

# Run full integration tests (requires API keys)
./run_tests.sh --provider openai --mode full
./run_tests.sh --provider anthropic --mode full

# Run with comparison tests
./run_tests.sh --provider openai --mode full --compare

# Custom port
./run_tests.sh --port 3002
```

**Note**: If the gateway is running with `test_config_unified_ci.toml`, individual provider tests will still work since the unified config includes all models from both providers. The script will show the expected config file but won't fail if a compatible config is already running.

### Universal SDK Compatibility Tests

The universal tests demonstrate a key architectural principle: **OpenAI SDK works with ALL providers**:

```bash
# Test OpenAI SDK universal compatibility
./run_tests.sh --provider universal

# This runs:
# - openai_tests/test_all_providers.py (OpenAI SDK with all providers)
# - anthropic_tests/test_native_messages.py (Native SDK comparison)
```

### Architecture Demonstration

See the architecture in action:

```bash
# Run interactive demonstration
./run_tests.sh --demo

# Or run directly
python demonstrate_universal_sdk.py
```

### Direct Usage

Use the unified test runner directly:
- `./run_tests.sh --provider openai --mode full`  # Full OpenAI tests
- `./run_tests.sh --provider openai --mode ci`    # CI OpenAI tests

### Using the New Test Infrastructure

#### For Test Writers

Use the new shared infrastructure to avoid code duplication:

```python
# Instead of duplicating client setup:
from common.utils import create_universal_client
client = create_universal_client(provider_hint="together")

# Instead of duplicating validation logic:
from common.utils import validate_chat_response, validate_embedding_response
validate_chat_response(response, provider_type="together")

# Instead of writing custom test classes:
from common.test_suites import UniversalChatTestSuite, UniversalEmbeddingTestSuite
chat_suite = UniversalChatTestSuite(models=["gpt-3.5-turbo"], provider_hint="openai")
chat_suite.test_basic_chat()
```

#### Universal Test Data

Access standardized test data:

```python  
from common.utils import UniversalTestData

models = UniversalTestData.get_provider_models()["together"]
embedding_models = UniversalTestData.get_embedding_models()["openai"]
test_messages = UniversalTestData.get_basic_chat_messages()
```

### Provider-Specific Shortcuts

```bash
# Together tests (improved versions available)
pytest together_tests/test_ci_together_improved.py -v
pytest together_tests/test_embeddings_improved.py -v
```

### Run Specific Test Module

```bash
# CI tests (for dummy provider)
pytest openai_tests/test_ci_basic.py -v
pytest openai_tests/test_ci_chat.py -v
pytest anthropic_tests/test_ci_messages.py -v

# Full tests (requires real API keys)
pytest openai_tests/test_chat.py -v
pytest openai_tests/test_embeddings.py -v
pytest anthropic_tests/test_messages.py -v
pytest anthropic_tests/test_streaming.py -v
```

**Important**: When running with the dummy provider (CI mode), use `test_ci_*.py` files. The regular test files expect real API responses and will fail with dummy provider.

## Supported Providers

### OpenAI
- Chat Completions
- Embeddings
- Moderation
- Audio (Transcription, Translation, TTS)
- Images (Generation, Editing, Variations)
- Realtime API

### Anthropic
- **Native Messages API** (`/v1/messages`) - Full native Anthropic SDK support
- **Universal OpenAI SDK** - Anthropic models also work via OpenAI SDK through `/v1/chat/completions`
- Streaming - Both native and OpenAI SDK
- Tool Use / Function Calling - Both native and OpenAI SDK
- Content Types - Both native and OpenAI SDK
- Error Handling - Both native and OpenAI SDK

### Universal SDK Architecture

TensorZero implements a unique architecture where:
- **OpenAI SDK is universal**: Works with ALL providers through `/v1/chat/completions`
- **Native SDKs are specialized**: Work with their provider-specific endpoints

This means you can use the OpenAI SDK with Anthropic models, Google models, or any other provider!

### Coming Soon
- Google (Gemini)
- Cohere
- AWS Bedrock
- Azure OpenAI

## Test Coverage

### Chat Completions (`test_chat.py`)
- Basic completions
- Streaming responses
- Function calling
- Multiple models
- Various parameters (temperature, max_tokens, etc.)
- Error handling
- Async operations

### Embeddings (`test_embeddings.py`)
- Single and batch embeddings
- Different models (ada-002, text-embedding-3-small)
- Custom dimensions
- Large batches
- Special characters
- Similarity testing
- Async operations

### Moderation (`test_moderation.py`)
- Content moderation
- Batch moderation
- Category scores
- Unicode and special characters
- Large batches
- Async operations

### Audio (`test_audio.py`)
- **Transcription**: Convert audio to text
- **Translation**: Convert non-English audio to English text
- **Text-to-Speech**: Generate audio from text
- Various voices and formats
- Response format options
- Async operations

### Images (`test_images.py`)
- **Generation**: Create images from text prompts (DALL-E 2, DALL-E 3, GPT-Image-1)
- **Editing**: Modify existing images with prompts and masks
- **Variations**: Generate variations of existing images
- Multiple image sizes and quality settings
- URL and base64 response formats
- Model-specific parameters (style, quality, background)
- Async operations
- Performance and stress testing

## Configuration

### Configuration Files

- `test_config_openai.toml` - OpenAI models with real API
- `test_config_openai_ci.toml` - OpenAI models with dummy provider
- `test_config_anthropic.toml` - Anthropic models with real API
- `test_config_anthropic_ci.toml` - Anthropic models with dummy provider
- `test_config_unified_ci.toml` - **NEW!** Unified config for universal SDK tests

All configurations use:
- Port 3001 (configurable)
- Authentication disabled for testing
- Debug mode enabled

For universal SDK tests, use the unified configuration:
```bash
cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_unified_ci.toml
```

## Troubleshooting

### Gateway Not Running
```
Error: TensorZero gateway is not running!
```
Solution: Start the gateway with the test configuration file.

### Missing API Key
```
Error: OPENAI_API_KEY is not set!
```
Solution: Set your OpenAI API key in the `.env` file.

### Audio Tests Failing
The audio tests require a sample MP3 file. The test runner automatically downloads a sample, but if this fails:
```bash
cd fixtures/audio_samples
# Download any small MP3 file and name it sample.mp3
```

### Image Tests Failing
The image tests require test images which are automatically generated by `create_test_images.py`. If this fails:
```bash
cd fixtures/images
# The script creates various test images including:
# - test_image.png (512x512 test image)
# - simple_shape.png (simple shape for variations)
# - mask.png (mask for editing tests)
```

## Adding New Provider Tests

See [SDK_TESTING.md](SDK_TESTING.md) for a detailed guide on adding tests for new providers.

Quick overview:
1. Create provider directory: `mkdir provider_name_tests` (note the `_tests` suffix)
2. Add SDK to `requirements.txt`
3. Create test configuration files
4. Implement test classes inheriting from base classes
5. Add CI tests for dummy provider
6. Update documentation

## CI Integration

### For GitHub Actions (No API Keys Required)

```yaml
# Test all providers
- name: Start TensorZero (OpenAI CI)
  run: cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_openai_ci.toml &
  
- name: Run OpenAI CI Tests
  run: cd gateway/tests/sdk && ./run_tests.sh --provider openai --mode ci

- name: Restart TensorZero (Anthropic CI)
  run: |
    pkill -f "cargo run --bin gateway" || true
    cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_anthropic_ci.toml &
    
- name: Run Anthropic CI Tests  
  run: cd gateway/tests/sdk && ./run_tests.sh --provider anthropic --mode ci
```

### For Full Testing (Requires API Keys)

```yaml
- name: Start TensorZero
  run: cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_${{ matrix.provider }}.toml &
  
- name: Run Full Integration Tests
  run: cd gateway/tests/sdk && ./run_tests.sh --provider ${{ matrix.provider }} --mode full
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Directory Structure

```
/gateway/tests/sdk/
├── common/                    # 🆕 Enhanced shared infrastructure
│   ├── base_test.py          # Abstract base test classes
│   ├── utils.py              # 🆕 Universal client factory, validation, test data
│   └── test_suites.py        # 🆕 Reusable test suites for all providers
├── universal_tests/           # 🆕 Consolidated cross-provider tests
│   ├── test_openai_sdk_all_providers.py  # Universal SDK compatibility
│   ├── test_cross_provider_comparison.py # Side-by-side comparisons
│   └── conftest.py           # Shared fixtures
├── openai_tests/             # OpenAI SDK tests
│   ├── test_*.py            # Full integration tests
│   ├── test_ci_*.py         # CI tests with dummy provider
│   ├── test_all_providers.py # ⚠️ Consider migrating to universal_tests/
│   └── test_universal_sdk_demo.py # Focused demo tests
├── anthropic_tests/          # Anthropic SDK tests
│   ├── test_*.py            # Full integration tests
│   ├── test_ci_*.py         # CI tests with dummy provider
│   └── test_native_messages.py # Native Anthropic SDK tests
├── together_tests/           # Together AI tests
│   ├── test_*.py            # Original tests
│   ├── test_*_improved.py   # 🆕 Improved versions using shared infrastructure
│   └── test_ci_*.py         # CI tests
├── fixtures/                 # Test data
├── test_config_*.toml       # Provider configurations
├── test_config_unified_ci.toml # Unified config for universal tests
├── demonstrate_universal_sdk.py # Architecture demonstration script
├── run_tests.sh             # Universal test runner
├── requirements.txt         # Python dependencies
├── SDK_TESTING.md          # Guide for adding new providers
└── SDK_ARCHITECTURE.md     # Universal SDK architecture guide
```