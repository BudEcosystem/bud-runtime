# Documents API

The `/v1/documents` endpoint processes documents (PDFs, images, etc.) and extracts their content as structured markdown. This endpoint is designed for document understanding and OCR capabilities, enabling extraction of text, tables, and structured data from various document formats.

## Endpoint

```
POST /v1/documents
```

## Authentication

This endpoint requires API key authentication when authentication is enabled in the gateway configuration.

**Required Header:**
```
Authorization: Bearer <YOUR_API_KEY>
```

## Request Format

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes* | Bearer token for API authentication (*when authentication is enabled) |
| `Content-Type` | Yes | Must be `application/json` |

### Request Body

```json
{
  "model": "string",
  "document": {
    "type": "document_url" | "image_url",
    "document_url": "string",
    "image_url": "string"
  },
  "prompt": "string"
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | The model identifier to use for document processing (e.g., `buddoc-v1`, `pixtral-12b`, etc.) |
| `document` | object | Yes | The document input specification |
| `document.type` | string | Yes | Type of input: `"document_url"` for PDFs and documents, `"image_url"` for images |
| `document.document_url` | string | Conditional | URL of the document (required when `type` is `"document_url"`) |
| `document.image_url` | string | Conditional | URL of the image (required when `type` is `"image_url"`) |
| `prompt` | string | No | Optional prompt to guide the document extraction or ask specific questions about the document |

## Response Format

### Success Response (200 OK)

```json
{
  "id": "doc_123e4567-e89b-12d3-a456-426614174000",
  "object": "document",
  "created": 1699536000,
  "model": "buddoc-v1",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "pages": [
    {
      "page_number": 1,
      "markdown": "# Document Title\n\nThis is the extracted content from page 1..."
    },
    {
      "page_number": 2,
      "markdown": "## Section 2\n\nContent from page 2..."
    }
  ],
  "usage_info": {
    "pages_processed": 2,
    "size_bytes": 245678,
    "filename": "document.pdf"
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the document processing request |
| `object` | string | Always `"document"` |
| `created` | integer | Unix timestamp of when the processing was completed |
| `model` | string | The model used for processing |
| `document_id` | string | Unique identifier for the processed document |
| `pages` | array | Array of page results |
| `pages[].page_number` | integer | Page number (1-indexed) |
| `pages[].markdown` | string | Extracted content in markdown format |
| `usage_info` | object | Information about the processed document |
| `usage_info.pages_processed` | integer | Number of pages processed |
| `usage_info.size_bytes` | integer | Size of the document in bytes |
| `usage_info.filename` | string | Name of the processed file |

### Error Response

```json
{
  "error": {
    "type": "invalid_request_error",
    "message": "Model 'invalid-model' not found or does not support document processing"
  }
}
```

## Supported Models

Models must have the `document` endpoint capability configured. Example configuration:

```toml
[models."buddoc-v1"]
routing = ["buddoc"]
endpoints = ["document"]

[models."buddoc-v1".providers.buddoc]
type = "buddoc"
api_base = "http://buddoc-service:8000"
```

## Use Cases

### 1. PDF Document Extraction

Extract text and structure from a PDF document:

```bash
curl -X POST http://localhost:3000/v1/documents \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "buddoc-v1",
    "document": {
      "type": "document_url",
      "document_url": "https://example.com/document.pdf"
    }
  }'
```

### 2. Image OCR with Guided Extraction

Process an image and extract specific information:

```bash
curl -X POST http://localhost:3000/v1/documents \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "buddoc-v1",
    "document": {
      "type": "image_url",
      "image_url": "https://example.com/invoice.png"
    },
    "prompt": "Extract the invoice number, date, total amount, and line items"
  }'
```

### 3. Multi-page Document Analysis

Process a multi-page document with specific analysis instructions:

```bash
curl -X POST http://localhost:3000/v1/documents \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "buddoc-v1",
    "document": {
      "type": "document_url",
      "document_url": "https://example.com/report.pdf"
    },
    "prompt": "Summarize the key findings and extract all data tables"
  }'
```

## Provider Implementation

The document processing capability is implemented through the `DocumentProcessingProvider` trait. Currently supported providers:

### BudDoc Provider

The BudDoc provider integrates with the BudDoc service for document processing:

- **Endpoint**: Configurable via `api_base` parameter
- **Authentication**: Supports static and dynamic API keys
- **Formats**: Supports both PDF documents and images
- **Features**:
  - Multi-page document processing
  - Table extraction
  - Structured markdown output
  - OCR for scanned documents
  - Prompt-guided extraction

Example provider configuration:

```toml
[models."buddoc-v1".providers.buddoc]
type = "buddoc"
api_base = "http://buddoc-service:8000"
api_key_location = { env = "BUDDOC_API_KEY" }  # Optional
```

## Response Format Details

### Markdown Structure

The extracted content is returned in markdown format with proper structure:

- **Headers**: Document sections are preserved with appropriate heading levels
- **Tables**: Extracted as markdown tables
- **Lists**: Bullet points and numbered lists are maintained
- **Formatting**: Bold, italic, and other formatting is preserved where possible
- **Links**: URLs and references are extracted and formatted as markdown links

### Page Ordering

Pages are returned in sequential order, with `page_number` starting from 1.

## Error Handling

Common error scenarios:

| Error Type | Description | Example |
|------------|-------------|---------|
| `invalid_request_error` | Model doesn't support documents | Model 'gpt-4' does not support document processing |
| `authentication_error` | Invalid or missing API key | Invalid API key provided |
| `not_found_error` | Document URL cannot be accessed | Failed to fetch document from URL |
| `processing_error` | Document processing failed | Unable to extract text from document |
| `size_limit_error` | Document exceeds size limits | Document size exceeds maximum allowed (100MB) |

## Limitations

- **File Size**: Documents are typically limited to 100MB
- **Page Count**: Very large documents (>100 pages) may have processing limits
- **Formats**: Supported formats depend on the provider (PDF, PNG, JPG, etc.)
- **Timeout**: Long documents may take time to process; consider timeout settings
- **Caching**: Document processing results are not cached by default

## Best Practices

1. **URL Accessibility**: Ensure document URLs are publicly accessible or properly authenticated
2. **Format Validation**: Verify the document format is supported by your chosen model
3. **Error Handling**: Implement proper error handling for large or complex documents
4. **Prompt Engineering**: Use specific prompts to guide extraction for better results
5. **Model Selection**: Choose models optimized for your document type (text-heavy vs. image-heavy)

## Integration Examples

### Python Example

```python
import requests
import json

def process_document(document_url, model="buddoc-v1", prompt=None):
    url = "http://localhost:3000/v1/documents"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": document_url
        }
    }

    if prompt:
        payload["prompt"] = prompt

    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# Extract content from a PDF
result = process_document(
    "https://example.com/document.pdf",
    prompt="Extract all tables and key metrics"
)

# Process pages
for page in result["pages"]:
    print(f"Page {page['page_number']}:")
    print(page["markdown"])
```

### Node.js Example

```javascript
const axios = require('axios');

async function processDocument(documentUrl, model = 'buddoc-v1', prompt = null) {
    const url = 'http://localhost:3000/v1/documents';

    const payload = {
        model: model,
        document: {
            type: 'document_url',
            document_url: documentUrl
        }
    };

    if (prompt) {
        payload.prompt = prompt;
    }

    try {
        const response = await axios.post(url, payload, {
            headers: {
                'Authorization': `Bearer ${process.env.API_KEY}`,
                'Content-Type': 'application/json'
            }
        });

        return response.data;
    } catch (error) {
        console.error('Error processing document:', error.response?.data || error.message);
        throw error;
    }
}

// Usage
processDocument('https://example.com/invoice.pdf', 'buddoc-v1', 'Extract invoice details')
    .then(result => {
        result.pages.forEach(page => {
            console.log(`Page ${page.page_number}:`);
            console.log(page.markdown);
        });
    });
```

## Related Endpoints

- `/v1/chat/completions` - For conversational AI about document content
- `/v1/images/generations` - For generating images from text
- `/v1/embeddings` - For creating vector embeddings of document content

## Changelog

- **v1.0.0** - Initial document processing API implementation with BudDoc provider support
