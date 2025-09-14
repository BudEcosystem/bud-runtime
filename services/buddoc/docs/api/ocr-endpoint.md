# OCR Endpoint API Documentation

## Overview

The OCR endpoint provides Vision Language Model (VLM) powered document text extraction with support for multiple input formats and authentication methods.

## Endpoint

### POST `/documents/ocr`

Process a document for OCR using Vision Language Models.

## Authentication

The endpoint supports two authentication methods:

1. **Bearer Token in Header** (Recommended)
   - Pass token in `Authorization` header
   - Format: `Bearer <your-api-token>`
   - Takes precedence over environment variable

2. **Environment Variable** (Fallback)
   - Set `VLM_API_TOKEN` in environment
   - Used when no Authorization header is provided

## Request

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | Must be `application/json` |
| `Authorization` | No | Bearer token for VLM API authentication. Format: `Bearer <token>` |

### Request Body Schema

```typescript
{
  "model": string,           // VLM model to use (default: "qwen2-vl-7b")
  "document": {
    "type": "image_url" | "document_url",  // Document input type
    "image_url"?: string,    // URL or data URI for images
    "document_url"?: string  // URL for documents (PDF, etc.)
  },
  "prompt"?: string         // Optional custom prompt for VLM
}
```

### Input Formats

#### 1. URL Input
Direct URL to a document or image:

```json
{
  "model": "qwen2-vl-7b",
  "document": {
    "type": "document_url",
    "document_url": "https://example.com/document.pdf"
  }
}
```

#### 2. Base64 Data URI
Base64-encoded document as data URI:

```json
{
  "model": "qwen2-vl-7b",
  "document": {
    "type": "image_url",
    "image_url": "data:image/png;base64,iVBORw0KGgoAAAANS..."
  }
}
```

### Supported File Formats

- **Documents**: PDF, DOCX, PPTX, XLSX, HTML
- **Images**: PNG, JPG, JPEG, TIFF
- **Max Size**: 50MB (configurable)

## Response

### Success Response (200 OK)

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "qwen2-vl-7b",
  "pages": [
    {
      "page_number": 1,
      "markdown": "# Document Title\n\nExtracted text content in markdown format..."
    },
    {
      "page_number": 2,
      "markdown": "## Page 2\n\nMore content..."
    }
  ],
  "usage_info": {
    "pages_processed": 2,
    "size_bytes": 125432,
    "filename": "document.pdf"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | UUID | Unique identifier for the processed document |
| `model` | string | VLM model used for processing |
| `pages` | array | Array of page results |
| `pages[].page_number` | integer | Page number (1-indexed) |
| `pages[].markdown` | string | Extracted text in markdown format |
| `usage_info` | object | Processing metrics |
| `usage_info.pages_processed` | integer | Number of pages processed |
| `usage_info.size_bytes` | integer | Document size in bytes |
| `usage_info.filename` | string | Processed file name |

### Error Responses

#### 400 Bad Request
Invalid request format or unsupported document type:

```json
{
  "detail": "Unsupported document type: invalid_type"
}
```

#### 401 Unauthorized
Invalid or missing authentication:

```json
{
  "detail": "Invalid bearer token"
}
```

#### 422 Unprocessable Entity
Validation error:

```json
{
  "detail": [
    {
      "loc": ["body", "document", "document_url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

#### 500 Internal Server Error
Processing error:

```json
{
  "detail": "Failed to process document: VLM API error"
}
```

## Examples

### cURL Examples

#### With URL and Bearer Token

```bash
curl -X POST http://localhost:9081/documents/ocr \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "qwen2-vl-7b",
    "document": {
      "type": "document_url",
      "document_url": "https://example.com/invoice.pdf"
    },
    "prompt": "Extract all invoice details including amounts and dates"
  }'
```

#### With Base64 Image

```bash
# First encode your image
base64 -i image.png > image_base64.txt

# Then send request
curl -X POST http://localhost:9081/documents/ocr \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"qwen2-vl-7b\",
    \"document\": {
      \"type\": \"image_url\",
      \"image_url\": \"data:image/png;base64,$(cat image_base64.txt)\"
    }
  }"
```

### Python Examples

#### Using httpx (Async)

```python
import httpx
import asyncio
import base64

async def ocr_from_url():
    """Process document from URL"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9081/documents/ocr",
            json={
                "model": "qwen2-vl-7b",
                "document": {
                    "type": "document_url",
                    "document_url": "https://example.com/document.pdf"
                }
            },
            headers={
                "Authorization": "Bearer your-api-key"
            },
            timeout=60.0
        )
        return response.json()

async def ocr_from_file():
    """Process local file as base64"""
    with open("document.pdf", "rb") as f:
        base64_content = base64.b64encode(f.read()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9081/documents/ocr",
            json={
                "model": "qwen2-vl-7b",
                "document": {
                    "type": "image_url",
                    "image_url": f"data:application/pdf;base64,{base64_content}"
                }
            },
            timeout=60.0
        )
        return response.json()

# Run the async function
result = asyncio.run(ocr_from_url())
print(f"Extracted text: {result['pages'][0]['markdown']}")
```

#### Using requests (Sync)

```python
import requests
import base64

def process_document(file_path):
    """Process a local document file"""

    # Read and encode file
    with open(file_path, "rb") as f:
        file_content = f.read()
        base64_content = base64.b64encode(file_content).decode()

    # Determine MIME type
    mime_type = "application/pdf" if file_path.endswith(".pdf") else "image/png"

    # Prepare request
    response = requests.post(
        "http://localhost:9081/documents/ocr",
        json={
            "model": "qwen2-vl-7b",
            "document": {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{base64_content}"
            }
        },
        headers={
            "Authorization": "Bearer your-api-key"
        }
    )

    if response.status_code == 200:
        result = response.json()
        return result["pages"][0]["markdown"]
    else:
        raise Exception(f"OCR failed: {response.text}")

# Process a document
text = process_document("invoice.pdf")
print(text)
```

### JavaScript/TypeScript Example

```typescript
interface OCRRequest {
  model: string;
  document: {
    type: "image_url" | "document_url";
    image_url?: string;
    document_url?: string;
  };
  prompt?: string;
}

interface OCRResponse {
  document_id: string;
  model: string;
  pages: Array<{
    page_number: number;
    markdown: string;
  }>;
  usage_info: {
    pages_processed: number;
    size_bytes: number;
    filename: string;
  };
}

async function processDocument(url: string, apiKey?: string): Promise<OCRResponse> {
  const request: OCRRequest = {
    model: "qwen2-vl-7b",
    document: {
      type: "document_url",
      document_url: url
    }
  };

  const headers: HeadersInit = {
    "Content-Type": "application/json"
  };

  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const response = await fetch("http://localhost:9081/documents/ocr", {
    method: "POST",
    headers,
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    throw new Error(`OCR failed: ${await response.text()}`);
  }

  return response.json();
}

// Usage
processDocument("https://example.com/document.pdf", "your-api-key")
  .then(result => {
    console.log(`Processed ${result.usage_info.pages_processed} pages`);
    result.pages.forEach(page => {
      console.log(`Page ${page.page_number}: ${page.markdown.substring(0, 100)}...`);
    });
  })
  .catch(error => console.error(error));
```

## Rate Limiting

- Default timeout: 90 seconds (configurable via `VLM_API_TIMEOUT`)
- Max file size: 50MB (configurable via `MAX_FILE_SIZE_MB`)
- Concurrent requests: Depends on VLM API provider limits

## Best Practices

1. **Use Bearer Tokens**: Pass API keys via Authorization header rather than environment variables for multi-tenancy
2. **Handle Timeouts**: Large documents may take time; set appropriate timeout values
3. **Validate Input**: Ensure URLs are accessible and files are within size limits
4. **Error Handling**: Implement proper error handling for network and processing failures
5. **Compression**: Use base64 encoding efficiently; consider URL input for large files

## VLM Models

Available models (configure in request):
- `qwen2-vl-7b` - Default, balanced performance
- `docling-vlm` - Optimized for document processing
- `mistral-ocr-latest` - Latest Mistral OCR model
- `pixtral-12b` - High-accuracy model for complex documents

## Troubleshooting

### Common Issues

1. **"Connection refused" error**
   - Ensure VLM API is running and accessible
   - Check `VLM_API_URL` configuration

2. **"Invalid bearer token"**
   - Verify token format: `Bearer <token>`
   - Check token validity with your VLM provider

3. **"File too large"**
   - Check file size against `MAX_FILE_SIZE_MB`
   - Consider using URL input instead of base64

4. **"Timeout error"**
   - Increase `VLM_API_TIMEOUT` for large documents
   - Check VLM API performance

5. **"Unsupported format"**
   - Verify file extension is supported
   - Check MIME type in data URI is correct
