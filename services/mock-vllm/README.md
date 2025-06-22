# Mock vLLM Service

A lightweight mock implementation of the vLLM OpenAI-compatible API server for integration testing. This service provides all the same API endpoints as vLLM but returns mock responses, making it perfect for testing without the resource overhead of running actual language models.

## Features

- **Full API Compatibility**: Implements all vLLM OpenAI-compatible endpoints
- **Lightweight**: Minimal resource usage (~256MB RAM, 100m CPU)
- **Configurable**: Adjustable processing delays and response patterns
- **Deterministic**: Responses are based on input for consistent testing
- **Streaming Support**: Supports both streaming and non-streaming responses

## API Endpoints

- `/health` - Health check
- `/v1/models` - List available models
- `/v1/chat/completions` - Chat completions (streaming supported)
- `/v1/completions` - Text completions (streaming supported)
- `/v1/embeddings` - Generate embeddings
- `/tokenize` - Tokenize text
- `/detokenize` - Detokenize tokens
- `/pooling` - Pooling operations
- `/classify` - Text classification
- `/score` - Scoring pairs of texts
- `/rerank` - Document reranking
- `/v1/audio/transcriptions` - Audio transcription (mock)

## Quick Start

### Using Docker Compose

```bash
cd services/mock-vllm
docker-compose up --build
```

### Using Docker

```bash
cd services/mock-vllm
docker build -t mock-vllm .
docker run -p 8000:8000 mock-vllm
```

### Local Development

```bash
cd services/mock-vllm
pip install -r requirements.txt
python -m src.api_server --host 0.0.0.0 --port 8000
```

## Configuration

### Environment Variables

- `MOCK_PROCESSING_DELAY` - Simulated processing delay in seconds (default: 0.1)
- `VLLM_API_KEY` - Optional API key for authentication

### Command Line Arguments

```bash
python -m src.api_server \
  --host 0.0.0.0 \
  --port 8000 \
  --model mock-gpt-3.5-turbo \
  --served-model-name gpt-3.5-turbo gpt-4 \
  --api-key YOUR_API_KEY
```

## Kubernetes Deployment

### Using Helm Chart

The mock vLLM service has its own Helm chart for easy deployment:

```bash
# Install mock vLLM
helm install mock-vllm ./helm/mock-vllm \
  --namespace mock-vllm \
  --create-namespace

# Install with custom values
helm install mock-vllm ./helm/mock-vllm \
  --namespace mock-vllm \
  --create-namespace \
  --set config.apiKey=your-api-key \
  --set config.processingDelay=0.5
```

### Building and Pushing Docker Image

```bash
# Build the image
cd services/mock-vllm
docker build -t your-registry/mock-vllm:latest .

# Push to registry
docker push your-registry/mock-vllm:latest

# Update Helm values
helm upgrade mock-vllm ./helm/mock-vllm \
  --set image.repository=your-registry/mock-vllm \
  --set image.tag=latest
```

### Integration with Other Services

To use mock vLLM with other services (like budproxy), simply point them to the mock vLLM service:

```yaml
# Example: Configure budproxy to use mock vLLM
env:
  - name: VLLM_BASE_URL
    value: "http://mock-vllm.mock-vllm.svc.cluster.local:8000/v1"
```

## Testing

### Run Simple Tests

```bash
# Start the service
docker-compose up -d

# Run simple test script
python tests/simple_test.py
```

### Run Integration Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/test_integration.py -v
```

## Mock Response Behavior

- **Chat/Completion**: Returns contextual responses from a predefined set
- **Embeddings**: Generates deterministic 768-dimensional vectors based on input
- **Tokenization**: Simple character-based tokenization (4 chars ≈ 1 token)
- **Classification**: Random selection from provided labels with high confidence
- **Reranking**: Deterministic scoring based on query-document similarity
- **Scores**: Deterministic scores based on text pair hashing

## Development

### Adding New Endpoints

1. Add protocol models in `src/protocol.py`
2. Add response generator in `src/mock_responses.py`
3. Add endpoint handler in `src/api_server.py`
4. Add tests in `tests/test_integration.py`

### Customizing Responses

Edit `src/mock_responses.py` to modify:
- Response content patterns
- Processing delays
- Embedding dimensions
- Score calculations

## Troubleshooting

### Service Not Responding
- Check if port 8000 is available
- Verify Docker/Python environment
- Check logs: `docker-compose logs`

### Authentication Errors
- Ensure API key matches between client and server
- API key can be set via `--api-key` or `VLLM_API_KEY` env var

### Helm Deployment Issues
- Verify mock vLLM image is accessible
- Check pod logs: `kubectl logs -n mock-vllm <pod-name>`
- Check service endpoints: `kubectl get svc -n mock-vllm`
- Verify deployment status: `kubectl get deploy -n mock-vllm`