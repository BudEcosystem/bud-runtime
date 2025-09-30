# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Service Overview

BudDoc is a document management and OCR service within the bud-stack ecosystem. It provides VLM (Vision Language Model) powered document text extraction with support for multiple input formats and authentication methods. The service is designed to be compatible with Mistral AI's OCR API format.

## Key Features

- **VLM-Powered OCR**: Uses Vision Language Models (qwen2-vl-7b by default) for text extraction
- **Multiple Input Formats**: Processes documents from URLs or base64-encoded data (PDF, images, Office documents)
- **Flexible Authentication**: Bearer token authentication in headers or environment variables
- **Custom Pipeline**: DirectTextVlmPipeline that provides raw VLM output without additional parsing
- **Async Processing**: Built on FastAPI for high-performance asynchronous operations

## Development Commands

### Setup and Running

```bash
# Setup environment
cp .env.sample .env
# Edit .env with your VLM API configuration (especially VLM_API_URL and SECRETS_VLM_API_TOKEN)

# Start the service with dependencies (PostgreSQL, Redis, Dapr)
./deploy/start_dev.sh

# Stop the service
./deploy/stop_dev.sh

# Service runs on port 9081 by default
```

### Code Quality

```bash
# Linting and formatting
ruff check . --fix
ruff format .

# Type checking
mypy buddoc/

# Run all tests
pytest

# Run specific test
pytest tests/unit/test_ocr_routes.py::test_process_document_ocr_success

# Install pre-commit hooks
./scripts/install_hooks.sh
```

### Database Operations

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

## Architecture and Key Components

### Service Structure

The service follows the standard bud-stack microservice pattern:

- **`buddoc/main.py`**: FastAPI app initialization using budmicroframe
- **`buddoc/documents/routes.py`**: API endpoints (`/documents/ocr`, `/documents/health`)
- **`buddoc/documents/services.py`**: Core business logic for document processing
- **`buddoc/documents/schemas.py`**: Pydantic models for request/response validation
- **`buddoc/documents/pipeline.py`**: Custom DirectTextVlmPipeline for VLM text extraction
- **`buddoc/commons/config.py`**: Configuration management using budmicroframe

### Document Processing Flow

1. **Input Handling**: Accepts documents as URLs or base64 data URIs
2. **Authentication**: Bearer token from Authorization header or VLM_API_TOKEN env var
3. **Document Download**: Fetches URL content or decodes base64 data
4. **VLM Processing**: Uses docling with custom DirectTextVlmPipeline
5. **Response Formation**: Returns page-level markdown results with usage info

### Custom VLM Pipeline

The `DirectTextVlmPipeline` (in `pipeline.py`) extends docling's VlmPipeline to:
- Skip document assembly and parsing
- Return raw VLM text responses directly
- Concatenate multi-page results with page separators
- Use TEXT label to avoid additional processing

### API Compatibility

The service mimics Mistral AI's OCR API format:
- Request structure with `model` and `document` fields
- Support for `image_url` and `document_url` types
- Response with `pages` array containing markdown text
- Usage information including pages processed and file size

## Configuration

### Environment Variables

Key configuration in `.env`:
- **VLM_API_URL**: VLM API endpoint (default: `http://localhost:1234/v1/chat/completions`)
- **VLM_MODEL_NAME**: Default model (default: `qwen2-vl-7b`)
- **VLM_API_TIMEOUT**: Request timeout in seconds (default: 90)
- **SECRETS_VLM_API_TOKEN**: Bearer token for VLM API (optional, can be passed in request)
- **MAX_FILE_SIZE_MB**: Maximum file size (default: 50)
- **TEMP_UPLOAD_DIR**: Temporary storage for uploads (default: `/tmp/buddoc_uploads`)

### Supported File Formats

- Documents: PDF, DOCX, PPTX, XLSX, HTML
- Images: PNG, JPG, JPEG, TIFF
- Maximum size: 50MB (configurable)

## Testing Strategy

The service includes comprehensive test coverage:
- **Unit tests**: Test individual components (routes, services, schemas, pipeline)
- **Integration tests**: Test end-to-end OCR processing
- **Mock fixtures**: Predefined responses for VLM API testing

Key test files:
- `tests/unit/test_ocr_routes.py`: API endpoint testing
- `tests/unit/test_document_service.py`: Service logic testing
- `tests/unit/test_vlm_pipeline.py`: Custom pipeline testing
- `tests/integration/test_ocr_integration.py`: Full workflow testing

## Integration with Bud-Stack

BudDoc integrates with the broader bud-stack ecosystem:
- Uses **budmicroframe** for consistent configuration and logging
- Runs with **Dapr sidecar** for service mesh capabilities
- Connects to **PostgreSQL** for metadata storage
- Uses **Redis** for state management
- Follows standard bud-stack service patterns

## API Usage Examples

### Process document from URL
```bash
curl -X POST http://localhost:9081/documents/ocr \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2-vl-7b", "document": {"type": "document_url", "document_url": "https://example.com/doc.pdf"}}'
```

### Process base64-encoded image
```bash
curl -X POST http://localhost:9081/documents/ocr \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2-vl-7b", "document": {"type": "image_url", "image_url": "data:image/png;base64,iVBORw0KG..."}}'
```

## Deployment

The service can be deployed using:
- **Development**: `./deploy/start_dev.sh` (includes PostgreSQL, Redis, Dapr)
- **Production**: Docker image built from `deploy/Dockerfile`
- **Dependencies**: Requires VLM API endpoint (e.g., local LLM server or cloud provider)

## Key Dependencies

- **docling >= 2.0.0**: Document processing and VLM integration
- **budmicroframe**: Bud ecosystem microservice framework
- **FastAPI**: Web framework
- **httpx**: Async HTTP client for fetching documents
- **Dapr**: Distributed runtime for service mesh
