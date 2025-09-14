# 📄 BudDoc

---

BudDoc is a comprehensive document management service within the bud-stack ecosystem. It
provides essential document processing, storage, and retrieval capabilities with a robust
API for document-centric operations. BudDoc is designed to handle various document types,
offering secure storage, efficient processing, and seamless integration with other bud-stack services.

### 🔧 Features

- 🤖 **VLM-Powered OCR**: Advanced document OCR using Vision Language Models (qwen2-vl-7b) for superior text extraction
- 📁 **Multiple Input Formats**: Process documents from URLs or base64-encoded data (PDF, images, Office documents)
- 🔐 **Flexible Authentication**: Bearer token authentication with multi-tenancy support
- 🚀 **Direct VLM Pipeline**: Custom DirectTextVlmPipeline that bypasses traditional OCR for raw VLM output
- 🔄 **Document Processing**: Automated processing pipelines for document conversion, extraction, and analysis
- 🔗 **Mistral AI Compatible**: API format compatible with Mistral AI's OCR endpoints
- ⚡ **Async Processing**: Built on FastAPI for high-performance asynchronous operations
- 📊 **Usage Tracking**: Detailed usage information including pages processed, file sizes, and processing metrics

### ❓ Why BudDoc?

- 📄 **Unified Storage**: Centralized document management across all your projects and teams.
- 🔒 **Security**: Enterprise-grade security with encryption, access controls, and audit trails.
- ⚡ **Performance**: High-performance document processing and retrieval with intelligent caching.
- 🔗 **Integration**: Seamless integration with other bud-stack services and external systems.
- 📊 **Insights**: Comprehensive analytics and reporting on document usage and lifecycle.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker and Docker Compose
- Redis (for Dapr state management)
- PostgreSQL (for metadata storage)

### Installation

1. **Clone and navigate to the service:**
```bash
cd services/buddoc
```

2. **Set up environment:**
```bash
cp .env.sample .env
# Edit .env with your VLM API configuration
```

3. **Start the service:**
```bash
./deploy/start_dev.sh
```

The service will be available at `http://localhost:9081`

## 📚 API Documentation

### OCR Endpoint

**POST** `/documents/ocr` - Process documents using Vision Language Models

#### Request Example:
```json
{
  "model": "qwen2-vl-7b",
  "document": {
    "type": "document_url",
    "document_url": "https://example.com/document.pdf"
  }
}
```

#### With Bearer Token:
```bash
curl -X POST http://localhost:9081/documents/ocr \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2-vl-7b", "document": {"type": "document_url", "document_url": "https://example.com/doc.pdf"}}'
```

#### Response:
```json
{
  "document_id": "uuid",
  "model": "qwen2-vl-7b",
  "pages": [
    {
      "page_number": 1,
      "markdown": "Extracted text content..."
    }
  ],
  "usage_info": {
    "pages_processed": 1,
    "size_bytes": 12345,
    "filename": "document.pdf"
  }
}
```

For detailed API documentation, run the service and visit: `http://localhost:9081/docs`

## Table of Contents

- [Development Guidelines](./docs/git_guidelines.md)
    - [Commit Messages](./docs/git_guidelines.md#-commit-messages)
    - [Issues](./docs/git_guidelines.md#-issues)
    - [Pull Requests](./docs/git_guidelines.md#-pull-requests)
    - [Code Reviews](./docs/git_guidelines.md#-code-reviews)
    - [Merges](./docs/git_guidelines.md#-merges)
- [Service Setup & Workflows](./docs/hooks_and_workflows.md)
    - [Installation / Setup](./docs/hooks_and_workflows.md#-installation--setup)
    - [Pre-Commit Stage Hooks](./docs/hooks_and_workflows.md#-pre-commit-stage-hooks)
    - [Development Workflows](./docs/hooks_and_workflows.md#-worth-a-read)
- [Service Architecture](./docs/microservice_guidelines.md)
    - [Application Structure](./docs/microservice_guidelines.md#-application-structure)
    - [API Design Practices](./docs/api_design_practices.md)
    - [Dapr Integration](./docs/dapr_a_distributed_runtime.md)
    - [Testing Strategy](./docs/unit_testing.md)
    - [Performance Monitoring](./docs/profiling.md)
    - [Deployment Guide](./docs/deployment.md)