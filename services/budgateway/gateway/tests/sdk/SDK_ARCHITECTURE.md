# TensorZero SDK Architecture: Universal Compatibility

## Overview

TensorZero implements a unique SDK architecture that provides **universal compatibility** through the OpenAI SDK while maintaining **native provider optimizations** through provider-specific SDKs.

## Key Architectural Principle

> **OpenAI SDK works universally with ALL providers through `/v1/chat/completions`**  
> **Native SDKs work only with their specific endpoints for provider-specific features**

## Universal OpenAI SDK Compatibility

### ✅ What Works

The OpenAI SDK can be used with **any provider** that supports chat completions:

```python
from openai import OpenAI

# Universal client - works with ALL providers
client = OpenAI(
    base_url="http://localhost:3001/v1",
    api_key="your-api-key"
)

# Works with OpenAI models
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}]
)

# Works with Anthropic models too!
response = client.chat.completions.create(
    model="claude-3-haiku-20240307", 
    messages=[{"role": "user", "content": "Hello"}]
)

# Works with ANY provider's chat models
response = client.chat.completions.create(
    model="any-provider-chat-model",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### 🔧 How It Works

1. **Universal Endpoint**: All chat requests go through `/v1/chat/completions`
2. **Format Conversion**: TensorZero converts OpenAI format to provider-specific format
3. **Provider Routing**: Requests are routed to the appropriate provider based on model configuration
4. **Response Normalization**: Provider responses are converted back to OpenAI format

### 🎯 Benefits

- **One SDK for everything**: Developers only need to learn OpenAI SDK
- **Easy provider switching**: Change model name, same code works
- **Consistent interface**: Same API across all providers
- **Future-proof**: New providers automatically work with existing OpenAI SDK code

## Native Provider SDKs

### 🔧 Provider-Specific Endpoints

Native SDKs work with their own endpoints for provider-specific features:

```python
from anthropic import Anthropic

# Native Anthropic SDK - works with /v1/messages
client = Anthropic(
    base_url="http://localhost:3001",
    api_key="your-api-key"
)

# Uses native Anthropic format and features
response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello"}]
)
```

### 🎯 When to Use Native SDKs

- **Provider-specific features**: Access to unique capabilities
- **Optimal performance**: Direct provider format, no conversion overhead
- **Advanced features**: Features not available in OpenAI format
- **Provider expertise**: When you need provider-specific optimizations

## Implementation Details

### Endpoint Mapping

| SDK | Endpoint | Purpose | Compatibility |
|-----|----------|---------|---------------|
| OpenAI | `/v1/chat/completions` | Universal chat | ALL providers |
| OpenAI | `/v1/embeddings` | Universal embeddings | Embedding providers |
| OpenAI | `/v1/moderations` | Universal moderation | Moderation providers |
| Anthropic | `/v1/messages` | Native Anthropic chat | Anthropic only |
| Future SDKs | `/v1/provider-specific` | Native features | Provider-specific |

### Test Architecture

Our test suite demonstrates both approaches:

```bash
# Universal OpenAI SDK tests (work with all providers)
gateway/tests/sdk/openai_tests/test_all_providers.py

# Native provider SDK tests  
gateway/tests/sdk/anthropic_tests/test_native_messages.py

# Architecture demonstration
gateway/tests/sdk/demonstrate_universal_sdk.py
```

## Configuration

### Unified Model Configuration

All models are configured in the same format, regardless of provider:

```toml
# OpenAI model - works with both OpenAI SDK and universal OpenAI SDK
[models."gpt-3.5-turbo"]
routing = ["openai"]
endpoints = ["chat"]

[models."gpt-3.5-turbo".providers.openai]
type = "openai"
model_name = "gpt-3.5-turbo"
api_key_location = { env = "OPENAI_API_KEY" }

# Anthropic model - works with both OpenAI SDK and native Anthropic SDK
[models."claude-3-haiku-20240307"]
routing = ["anthropic"] 
endpoints = ["chat"]

[models."claude-3-haiku-20240307".providers.anthropic]
type = "anthropic"
model_name = "claude-3-haiku-20240307"
api_key_location = { env = "ANTHROPIC_API_KEY" }
```

## Testing Universal Compatibility

### Run Universal Tests

```bash
# Test OpenAI SDK with all providers
cd gateway/tests/sdk
python -m pytest openai_tests/test_all_providers.py -v

# Demonstrate architecture
python demonstrate_universal_sdk.py
```

### Expected Results

```
✅ OpenAI SDK + OpenAI models: WORKS
✅ OpenAI SDK + Anthropic models: WORKS  
✅ OpenAI SDK + Any provider models: WORKS
✅ Native Anthropic SDK + /v1/messages: WORKS
```

## Migration Guide

### From Provider-Specific to Universal

```python
# Before: Different SDKs for different providers
from openai import OpenAI
from anthropic import Anthropic

openai_client = OpenAI(api_key="...")
anthropic_client = Anthropic(api_key="...")

# After: One SDK for everything
from openai import OpenAI

universal_client = OpenAI(
    base_url="http://tensorzero:3001/v1",
    api_key="your-tensorzero-key"
)

# Same code works with any provider
response = universal_client.chat.completions.create(
    model="gpt-3.5-turbo",  # or "claude-3-haiku" or any model
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Future Roadmap

### Planned Universal Endpoints

- [ ] `/v1/assistants` - Universal assistants API
- [ ] `/v1/threads` - Universal conversation threads  
- [ ] `/v1/files` - Universal file management
- [ ] `/v1/batch` - Universal batch processing

### Provider-Specific Endpoints

- [x] `/v1/messages` - Anthropic native
- [ ] `/v1/gemini/chat` - Google native
- [ ] `/v1/bedrock/invoke` - AWS Bedrock native

## Conclusion

This architecture provides the best of both worlds:

1. **🌍 Universal Access**: OpenAI SDK works with every provider
2. **🎯 Specialized Features**: Native SDKs for provider-specific optimizations
3. **🔮 Future-Proof**: New providers automatically work with OpenAI SDK
4. **🚀 Developer Experience**: One SDK to learn, infinite providers to use

The user's vision is fully implemented: **OpenAI SDK is universal, native SDKs are specialized.**