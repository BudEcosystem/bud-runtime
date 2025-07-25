# Azure Testing for TensorZero

This directory contains tests for Azure OpenAI models through TensorZero's OpenAI-compatible interface.

## Architecture Overview

TensorZero acts as an **OpenAI-compatible API server** that supports Azure models through standard endpoints. Azure models work perfectly when accessed via the OpenAI SDK, but Azure SDK's specific URL patterns are not supported.

### Supported Access Pattern ✅
```python
# Using OpenAI SDK with Azure models (WORKS)
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3001/v1",
    api_key="your-tensorzero-api-key"
)

# All endpoints work with Azure models
response = client.chat.completions.create(
    model="gpt-35-turbo-azure",  # Azure model name
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Unsupported Access Pattern ❌
```python
# Using Azure SDK (DOES NOT WORK)
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint="http://localhost:3001",
    api_key="your-api-key",
    api_version="2024-10-21"
)

# This fails because TensorZero doesn't implement Azure's URL routing:
# POST /openai/deployments/{deployment_id}/chat/completions
```

## Azure Provider Capabilities

The Azure provider in TensorZero supports all endpoint types:

### ✅ Chat Completions
- Basic chat completions
- Streaming responses
- Function calling / Tool use
- JSON mode
- System messages
- All OpenAI-compatible parameters

### ✅ Embeddings
- Single and batch embeddings
- Multiple embedding models
- Custom dimensions (model-dependent)
- Base64 encoding support

### ✅ Audio Processing
- **Transcription**: Convert audio to text
- **Translation**: Convert non-English audio to English text  
- **Text-to-Speech**: Generate audio from text
- Multiple voices and response formats
- Language specification and temperature control

### ✅ Image Generation
- DALL-E image generation
- Multiple sizes and quality settings
- URL and base64 response formats
- Model-specific parameters (style, quality)

## Configuration

Azure models are configured like any other model in TensorZero:

```toml
# Azure chat model
[models."gpt-35-turbo-azure"]
routing = ["azure"]
endpoints = ["chat"]

[models."gpt-35-turbo-azure".providers.azure]
type = "azure"
deployment_id = "gpt-35-turbo"
endpoint = "https://your-resource.openai.azure.com"
api_key_location = { env = "AZURE_OPENAI_API_KEY" }

# Azure embedding model
[models."text-embedding-ada-002-azure"]
routing = ["azure"]  
endpoints = ["embedding"]

[models."text-embedding-ada-002-azure".providers.azure]
type = "azure"
deployment_id = "text-embedding-ada-002"
endpoint = "https://your-resource.openai.azure.com"
api_key_location = { env = "AZURE_OPENAI_API_KEY" }

# Azure audio model
[models."whisper-1-azure"]
routing = ["azure"]
endpoints = ["audio_transcription", "audio_translation"]

[models."whisper-1-azure".providers.azure]
type = "azure"
deployment_id = "whisper-1"
endpoint = "https://your-resource.openai.azure.com"
api_key_location = { env = "AZURE_OPENAI_API_KEY" }

# Azure TTS model
[models."tts-1-azure"]
routing = ["azure"]
endpoints = ["text_to_speech"]

[models."tts-1-azure".providers.azure]
type = "azure"
deployment_id = "tts-1"
endpoint = "https://your-resource.openai.azure.com"
api_key_location = { env = "AZURE_OPENAI_API_KEY" }

# Azure image generation model
[models."dall-e-3-azure"]
routing = ["azure"]
endpoints = ["image_generation"]

[models."dall-e-3-azure".providers.azure]
type = "azure"
deployment_id = "dall-e-3"
endpoint = "https://your-resource.openai.azure.com"
api_key_location = { env = "AZURE_OPENAI_API_KEY" }
```

## Test Files

### `test_ci_azure.py`
CI tests that run with dummy provider (no API keys required):
- Azure embeddings via OpenAI SDK
- Azure audio transcription/translation/TTS via OpenAI SDK
- Azure image generation via OpenAI SDK
- Azure batch operations via OpenAI SDK
- Error handling

### `test_azure_sdk_params.py`
Full integration tests with real API keys:
- All Azure endpoint types via OpenAI SDK
- Function calling with Azure models
- JSON mode support
- Streaming responses
- Batch operations
- Content safety and filtering

## Running Tests

```bash
# Run CI tests (no API keys required)
./run_tests.sh --provider azure

# Run full tests (requires API keys)
./run_tests.sh --provider azure --mode full
```

## Key Benefits

1. **Universal SDK Support**: Use the familiar OpenAI SDK with Azure models
2. **Full Feature Parity**: All Azure model capabilities are available
3. **Simplified Development**: No need to learn Azure-specific SDK patterns
4. **Consistent Interface**: Same API patterns work across all providers
5. **Provider Abstraction**: Switch between OpenAI and Azure models seamlessly

## Limitations

- Azure SDK with deployment-specific URLs is not supported
- Azure-specific features like "On Your Data" require configuration at the provider level
- Content filtering is handled by Azure backend, not TensorZero gateway

## Migration from Azure SDK

If you're currently using the Azure SDK, migration is straightforward:

```python
# Before (Azure SDK)
from openai import AzureOpenAI
client = AzureOpenAI(
    azure_endpoint="https://your-resource.openai.azure.com",
    api_key="your-azure-key",
    api_version="2024-10-21"
)

# After (OpenAI SDK with TensorZero)
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:3001/v1",
    api_key="your-tensorzero-api-key"
)

# Same API calls work with both!
response = client.chat.completions.create(
    model="gpt-35-turbo-azure",  # Use your configured model name
    messages=[{"role": "user", "content": "Hello"}]
)
```

This approach provides the best of both worlds: Azure's powerful models with OpenAI's familiar and widely-supported SDK interface.