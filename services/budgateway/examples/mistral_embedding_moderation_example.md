# Mistral Embedding and Moderation Example

This example demonstrates how to use TensorZero with Mistral's embedding and moderation capabilities.

## Prerequisites

1. Set up your Mistral API key:
```bash
export MISTRAL_API_KEY="your-mistral-api-key"
```

2. Start TensorZero with the example configuration:
```bash
cargo run --bin gateway -- --config-file examples/mistral_embedding_moderation_config.toml
```

## Embedding Examples

### Basic Embedding Request

Create embeddings for a single text:

```bash
curl -X POST http://localhost:3000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-embed",
    "input": "The quick brown fox jumps over the lazy dog"
  }'
```

### Batch Embedding Request

Create embeddings for multiple texts:

```bash
curl -X POST http://localhost:3000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-embed",
    "input": [
      "Machine learning is transforming industries",
      "Natural language processing enables human-computer interaction",
      "Deep learning models require large amounts of data"
    ]
  }'
```

### Embedding with Custom Encoding Format

Request embeddings in base64 format:

```bash
curl -X POST http://localhost:3000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-embed",
    "input": "Convert this text to embeddings",
    "encoding_format": "base64"
  }'
```

## Moderation Examples

### Basic Moderation Request

Check if content violates policies:

```bash
curl -X POST http://localhost:3000/v1/moderations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ministral-8b-2410",
    "input": "This is a test message to check for content moderation"
  }'
```

### Batch Moderation Request

Moderate multiple pieces of content:

```bash
curl -X POST http://localhost:3000/v1/moderations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ministral-8b-2410",
    "input": [
      "First message to moderate",
      "Second message to check",
      "Third piece of content"
    ]
  }'
```

### Using Multi-Purpose Model

Use a model that supports both chat and moderation:

```bash
# For chat completion
curl -X POST http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-large-2411",
    "messages": [{"role": "user", "content": "Hello, how are you?"}]
  }'

# For moderation
curl -X POST http://localhost:3000/v1/moderations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-large-2411",
    "input": "Content to moderate"
  }'
```

## Using Fallback Models

### Embedding with Fallback

If Mistral is unavailable, the request will automatically fall back to OpenAI:

```bash
curl -X POST http://localhost:3000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embedding-with-fallback",
    "input": "This will use Mistral first, then OpenAI if needed"
  }'
```

### Moderation with Fallback

```bash
curl -X POST http://localhost:3000/v1/moderations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "moderation-with-fallback",
    "input": "Content that will be moderated by Mistral or OpenAI"
  }'
```

## Response Examples

### Embedding Response

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.023, -0.045, 0.178, ...]
    }
  ],
  "model": "mistral-embed",
  "usage": {
    "prompt_tokens": 10,
    "total_tokens": 10
  }
}
```

### Moderation Response

Note: Since Mistral uses chat models for moderation, the response simulates OpenAI's moderation format:

```json
{
  "id": "modr-abc123",
  "model": "ministral-8b-2410",
  "results": [
    {
      "flagged": false,
      "categories": {
        "hate": false,
        "hate/threatening": false,
        "self-harm": false,
        "sexual": false,
        "sexual/minors": false,
        "violence": false,
        "violence/graphic": false
      },
      "category_scores": {
        "hate": 0.0001,
        "hate/threatening": 0.0001,
        "self-harm": 0.0001,
        "sexual": 0.0001,
        "sexual/minors": 0.0001,
        "violence": 0.0001,
        "violence/graphic": 0.0001
      }
    }
  ]
}
```

## Implementation Notes

1. **Embedding Model**: Mistral's `mistral-embed` model produces 1024-dimensional embeddings optimized for retrieval tasks.

2. **Moderation Approach**: Since Mistral doesn't have a dedicated moderation API, TensorZero uses Mistral's chat models with specialized prompting to perform content moderation. The system:
   - Sends content to the chat model with a moderation-specific system prompt
   - Parses the response to extract moderation decisions
   - Formats the result in OpenAI's moderation response format

3. **Error Handling**: If the primary provider fails, requests automatically fall back to the next provider in the routing list.

4. **Performance**: 
   - Embedding requests are processed efficiently with Mistral's dedicated embedding model
   - Moderation requests may have higher latency due to using chat models

5. **Cost Considerations**: 
   - Mistral's embedding model is cost-effective for large-scale embedding generation
   - Using chat models for moderation may be more expensive than dedicated moderation APIs

## Troubleshooting

### Common Issues

1. **API Key Not Set**
   ```
   Error: Mistral API key not found
   ```
   Solution: Ensure `MISTRAL_API_KEY` environment variable is set.

2. **Model Not Found**
   ```
   Error: Model 'mistral-embed' not found in configuration
   ```
   Solution: Check that your configuration file includes the model definition.

3. **Unsupported Endpoint**
   ```
   Error: Model 'mistral-embed' does not support endpoint 'chat'
   ```
   Solution: Ensure you're using the correct endpoint for each model type.

## Advanced Usage

### Custom Moderation Prompts

While TensorZero uses a default moderation prompt, you can customize the moderation behavior by modifying the provider implementation.

### Monitoring and Metrics

TensorZero provides built-in metrics for:
- Request latency
- Token usage
- Error rates
- Fallback triggers

Access metrics at: `http://localhost:3000/metrics`

## Further Resources

- [Mistral AI Documentation](https://docs.mistral.ai/)
- [TensorZero Documentation](https://tensorzero.com/docs)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference) (for response format compatibility)