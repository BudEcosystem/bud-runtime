# BudDoc Integration Guide

## Overview

This guide provides comprehensive examples and best practices for integrating BudDoc's OCR capabilities into your applications.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication Strategies](#authentication-strategies)
3. [Language-Specific Examples](#language-specific-examples)
4. [Advanced Use Cases](#advanced-use-cases)
5. [Error Handling](#error-handling)
6. [Performance Optimization](#performance-optimization)
7. [Testing](#testing)

## Quick Start

### Basic OCR Request

The simplest way to use BudDoc is to send a document URL:

```bash
curl -X POST http://localhost:9081/documents/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2-vl-7b",
    "document": {
      "type": "document_url",
      "document_url": "https://example.com/document.pdf"
    }
  }'
```

## Authentication Strategies

### 1. Shared API Key (Simple)

Use a single API key from environment variable:

```bash
# Set in .env file
VLM_API_TOKEN=sk-shared-api-key

# No Authorization header needed in requests
```

### 2. Per-Request API Key (Multi-tenant)

Each request provides its own API key:

```python
headers = {
    "Authorization": f"Bearer {user_specific_api_key}"
}
```

### 3. Token Rotation

Implement token rotation for security:

```python
import time
from typing import List

class TokenRotator:
    def __init__(self, tokens: List[str], rotation_interval: int = 3600):
        self.tokens = tokens
        self.rotation_interval = rotation_interval
        self.current_index = 0
        self.last_rotation = time.time()

    def get_current_token(self) -> str:
        if time.time() - self.last_rotation > self.rotation_interval:
            self.rotate()
        return self.tokens[self.current_index]

    def rotate(self):
        self.current_index = (self.current_index + 1) % len(self.tokens)
        self.last_rotation = time.time()

# Usage
rotator = TokenRotator(["token1", "token2", "token3"])
headers = {"Authorization": f"Bearer {rotator.get_current_token()}"}
```

## Language-Specific Examples

### Python Integration

#### Complete Python Client Class

```python
import asyncio
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import httpx

@dataclass
class OCRResult:
    document_id: str
    model: str
    pages: List[Dict[str, Any]]
    usage_info: Dict[str, Any]

    @property
    def full_text(self) -> str:
        """Get combined text from all pages"""
        return "\n\n".join(page["markdown"] for page in self.pages)

    @property
    def page_count(self) -> int:
        return self.usage_info.get("pages_processed", 0)

class BudDocClient:
    """Client for BudDoc OCR service"""

    def __init__(
        self,
        base_url: str = "http://localhost:9081",
        api_key: Optional[str] = None,
        timeout: float = 90.0
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    async def process_url(
        self,
        url: str,
        model: str = "qwen2-vl-7b",
        prompt: Optional[str] = None
    ) -> OCRResult:
        """Process document from URL"""

        request_data = {
            "model": model,
            "document": {
                "type": "document_url",
                "document_url": url
            }
        }

        if prompt:
            request_data["prompt"] = prompt

        return await self._make_request(request_data)

    async def process_file(
        self,
        file_path: Path,
        model: str = "qwen2-vl-7b",
        prompt: Optional[str] = None
    ) -> OCRResult:
        """Process local file"""

        # Read and encode file
        with open(file_path, "rb") as f:
            content = f.read()

        # Determine MIME type
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".html": "text/html"
        }

        suffix = file_path.suffix.lower()
        mime_type = mime_map.get(suffix, "application/octet-stream")

        # Create data URI
        base64_content = base64.b64encode(content).decode()
        data_uri = f"data:{mime_type};base64,{base64_content}"

        request_data = {
            "model": model,
            "document": {
                "type": "image_url",
                "image_url": data_uri
            }
        }

        if prompt:
            request_data["prompt"] = prompt

        return await self._make_request(request_data)

    async def process_bytes(
        self,
        content: bytes,
        mime_type: str = "application/pdf",
        model: str = "qwen2-vl-7b",
        prompt: Optional[str] = None
    ) -> OCRResult:
        """Process document from bytes"""

        base64_content = base64.b64encode(content).decode()
        data_uri = f"data:{mime_type};base64,{base64_content}"

        request_data = {
            "model": model,
            "document": {
                "type": "image_url",
                "image_url": data_uri
            }
        }

        if prompt:
            request_data["prompt"] = prompt

        return await self._make_request(request_data)

    async def _make_request(self, request_data: Dict[str, Any]) -> OCRResult:
        """Make HTTP request to OCR endpoint"""

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/documents/ocr",
                    json=request_data,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return OCRResult(**data)

            except httpx.HTTPStatusError as e:
                self.logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                self.logger.error(f"Request failed: {e}")
                raise

# Usage Example
async def main():
    client = BudDocClient(api_key="your-api-key")

    # Process URL
    result = await client.process_url("https://example.com/invoice.pdf")
    print(f"Document ID: {result.document_id}")
    print(f"Extracted text: {result.full_text}")

    # Process local file
    result = await client.process_file(Path("document.pdf"))
    print(f"Pages processed: {result.page_count}")

    # Process with custom prompt
    result = await client.process_url(
        "https://example.com/receipt.jpg",
        prompt="Extract all amounts and dates from this receipt"
    )

asyncio.run(main())
```

### JavaScript/TypeScript Integration

#### TypeScript Client with Error Handling

```typescript
// buddoc-client.ts
export interface OCRRequest {
  model: string;
  document: {
    type: "image_url" | "document_url";
    image_url?: string;
    document_url?: string;
  };
  prompt?: string;
}

export interface OCRPage {
  page_number: number;
  markdown: string;
}

export interface OCRResponse {
  document_id: string;
  model: string;
  pages: OCRPage[];
  usage_info: {
    pages_processed: number;
    size_bytes: number;
    filename: string;
  };
}

export class BudDocError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: any
  ) {
    super(message);
    this.name = "BudDocError";
  }
}

export class BudDocClient {
  private baseUrl: string;
  private apiKey?: string;
  private timeout: number;

  constructor(config: {
    baseUrl?: string;
    apiKey?: string;
    timeout?: number;
  } = {}) {
    this.baseUrl = config.baseUrl || "http://localhost:9081";
    this.apiKey = config.apiKey;
    this.timeout = config.timeout || 90000;
  }

  async processUrl(
    url: string,
    options: {
      model?: string;
      prompt?: string;
    } = {}
  ): Promise<OCRResponse> {
    const request: OCRRequest = {
      model: options.model || "qwen2-vl-7b",
      document: {
        type: "document_url",
        document_url: url,
      },
      prompt: options.prompt,
    };

    return this.makeRequest(request);
  }

  async processFile(
    file: File,
    options: {
      model?: string;
      prompt?: string;
    } = {}
  ): Promise<OCRResponse> {
    // Convert file to base64
    const base64 = await this.fileToBase64(file);
    const dataUri = `data:${file.type};base64,${base64}`;

    const request: OCRRequest = {
      model: options.model || "qwen2-vl-7b",
      document: {
        type: "image_url",
        image_url: dataUri,
      },
      prompt: options.prompt,
    };

    return this.makeRequest(request);
  }

  async processBase64(
    base64Content: string,
    mimeType: string,
    options: {
      model?: string;
      prompt?: string;
    } = {}
  ): Promise<OCRResponse> {
    const dataUri = `data:${mimeType};base64,${base64Content}`;

    const request: OCRRequest = {
      model: options.model || "qwen2-vl-7b",
      document: {
        type: "image_url",
        image_url: dataUri,
      },
      prompt: options.prompt,
    };

    return this.makeRequest(request);
  }

  private async makeRequest(request: OCRRequest): Promise<OCRResponse> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };

      if (this.apiKey) {
        headers["Authorization"] = `Bearer ${this.apiKey}`;
      }

      const response = await fetch(`${this.baseUrl}/documents/ocr`, {
        method: "POST",
        headers,
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        throw new BudDocError(
          `OCR request failed: ${response.statusText}`,
          response.status,
          errorText
        );
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof BudDocError) {
        throw error;
      }

      if (error.name === "AbortError") {
        throw new BudDocError("Request timeout", 408);
      }

      throw new BudDocError(`Network error: ${error.message}`);
    }
  }

  private fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(",")[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
}

// Usage Example
async function example() {
  const client = new BudDocClient({
    apiKey: "your-api-key",
    timeout: 120000, // 2 minutes
  });

  try {
    // Process URL
    const result = await client.processUrl("https://example.com/document.pdf");
    console.log(`Processed ${result.usage_info.pages_processed} pages`);

    // Process file upload
    const fileInput = document.getElementById("file-input") as HTMLInputElement;
    if (fileInput.files?.[0]) {
      const result = await client.processFile(fileInput.files[0]);
      console.log(result.pages[0].markdown);
    }

    // Process with custom prompt
    const result2 = await client.processUrl(
      "https://example.com/invoice.pdf",
      {
        prompt: "Extract invoice number, date, and total amount",
      }
    );

  } catch (error) {
    if (error instanceof BudDocError) {
      console.error(`Error ${error.statusCode}: ${error.message}`);
      console.error("Details:", error.details);
    }
  }
}
```

### Go Integration

```go
package buddoc

import (
    "bytes"
    "encoding/base64"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "time"
)

type DocumentType string

const (
    DocumentURL DocumentType = "document_url"
    ImageURL    DocumentType = "image_url"
)

type OCRRequest struct {
    Model    string   `json:"model"`
    Document Document `json:"document"`
    Prompt   string   `json:"prompt,omitempty"`
}

type Document struct {
    Type        DocumentType `json:"type"`
    DocumentURL string       `json:"document_url,omitempty"`
    ImageURL    string       `json:"image_url,omitempty"`
}

type OCRResponse struct {
    DocumentID string     `json:"document_id"`
    Model      string     `json:"model"`
    Pages      []Page     `json:"pages"`
    UsageInfo  UsageInfo  `json:"usage_info"`
}

type Page struct {
    PageNumber int    `json:"page_number"`
    Markdown   string `json:"markdown"`
}

type UsageInfo struct {
    PagesProcessed int    `json:"pages_processed"`
    SizeBytes      int    `json:"size_bytes"`
    Filename       string `json:"filename"`
}

type Client struct {
    BaseURL    string
    APIKey     string
    HTTPClient *http.Client
}

func NewClient(baseURL, apiKey string) *Client {
    return &Client{
        BaseURL: baseURL,
        APIKey:  apiKey,
        HTTPClient: &http.Client{
            Timeout: 90 * time.Second,
        },
    }
}

func (c *Client) ProcessURL(url string, model string, prompt string) (*OCRResponse, error) {
    req := OCRRequest{
        Model: model,
        Document: Document{
            Type:        DocumentURL,
            DocumentURL: url,
        },
        Prompt: prompt,
    }

    return c.makeRequest(req)
}

func (c *Client) ProcessFile(content []byte, mimeType, model, prompt string) (*OCRResponse, error) {
    encoded := base64.StdEncoding.EncodeToString(content)
    dataURI := fmt.Sprintf("data:%s;base64,%s", mimeType, encoded)

    req := OCRRequest{
        Model: model,
        Document: Document{
            Type:     ImageURL,
            ImageURL: dataURI,
        },
        Prompt: prompt,
    }

    return c.makeRequest(req)
}

func (c *Client) makeRequest(ocrReq OCRRequest) (*OCRResponse, error) {
    jsonData, err := json.Marshal(ocrReq)
    if err != nil {
        return nil, err
    }

    req, err := http.NewRequest("POST", c.BaseURL+"/documents/ocr", bytes.NewBuffer(jsonData))
    if err != nil {
        return nil, err
    }

    req.Header.Set("Content-Type", "application/json")
    if c.APIKey != "" {
        req.Header.Set("Authorization", "Bearer "+c.APIKey)
    }

    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        body, _ := io.ReadAll(resp.Body)
        return nil, fmt.Errorf("OCR request failed: %d - %s", resp.StatusCode, string(body))
    }

    var ocrResp OCRResponse
    if err := json.NewDecoder(resp.Body).Decode(&ocrResp); err != nil {
        return nil, err
    }

    return &ocrResp, nil
}

// Usage
func main() {
    client := NewClient("http://localhost:9081", "your-api-key")

    // Process URL
    result, err := client.ProcessURL(
        "https://example.com/document.pdf",
        "qwen2-vl-7b",
        "",
    )
    if err != nil {
        panic(err)
    }

    fmt.Printf("Document ID: %s\n", result.DocumentID)
    fmt.Printf("Pages: %d\n", result.UsageInfo.PagesProcessed)
}
```

## Advanced Use Cases

### 1. Batch Processing

Process multiple documents in parallel:

```python
import asyncio
from typing import List, Tuple

async def batch_process_urls(
    client: BudDocClient,
    urls: List[str],
    max_concurrent: int = 5
) -> List[Tuple[str, OCRResult]]:
    """Process multiple URLs with concurrency limit"""

    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(url: str) -> Tuple[str, OCRResult]:
        async with semaphore:
            try:
                result = await client.process_url(url)
                return (url, result)
            except Exception as e:
                print(f"Failed to process {url}: {e}")
                return (url, None)

    tasks = [process_with_limit(url) for url in urls]
    return await asyncio.gather(*tasks)

# Usage
urls = [
    "https://example.com/doc1.pdf",
    "https://example.com/doc2.pdf",
    "https://example.com/doc3.pdf",
]

results = await batch_process_urls(client, urls, max_concurrent=3)
for url, result in results:
    if result:
        print(f"{url}: {result.page_count} pages")
```

### 2. Document Classification

Use custom prompts for classification:

```python
async def classify_document(client: BudDocClient, url: str) -> str:
    """Classify document type using VLM"""

    classification_prompt = """
    Analyze this document and classify it as one of:
    - invoice
    - receipt
    - contract
    - report
    - letter
    - other

    Return only the classification label.
    """

    result = await client.process_url(url, prompt=classification_prompt)

    # Extract classification from first page
    text = result.pages[0]["markdown"].strip().lower()

    valid_types = ["invoice", "receipt", "contract", "report", "letter", "other"]
    for doc_type in valid_types:
        if doc_type in text:
            return doc_type

    return "other"
```

### 3. Data Extraction

Extract structured data from documents:

```python
import json
import re

async def extract_invoice_data(client: BudDocClient, url: str) -> dict:
    """Extract structured invoice data"""

    extraction_prompt = """
    Extract the following information from this invoice:
    - Invoice number
    - Invoice date
    - Due date
    - Vendor name
    - Total amount
    - Line items (description and amount)

    Format as JSON.
    """

    result = await client.process_url(url, prompt=extraction_prompt)
    text = result.full_text

    # Try to parse JSON from response
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback to regex extraction
    data = {}

    # Extract invoice number
    invoice_match = re.search(r'Invoice\s*#?\s*:?\s*(\w+)', text, re.IGNORECASE)
    if invoice_match:
        data['invoice_number'] = invoice_match.group(1)

    # Extract amounts
    amount_match = re.search(r'Total\s*:?\s*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
    if amount_match:
        data['total_amount'] = amount_match.group(1).replace(',', '')

    return data
```

### 4. Document Comparison

Compare two documents:

```python
async def compare_documents(
    client: BudDocClient,
    url1: str,
    url2: str
) -> dict:
    """Compare two documents for similarities and differences"""

    # Process both documents
    result1, result2 = await asyncio.gather(
        client.process_url(url1),
        client.process_url(url2)
    )

    text1 = result1.full_text
    text2 = result2.full_text

    # Simple comparison metrics
    from difflib import SequenceMatcher

    similarity = SequenceMatcher(None, text1, text2).ratio()

    return {
        'similarity_score': similarity,
        'doc1_pages': result1.page_count,
        'doc2_pages': result2.page_count,
        'doc1_size': result1.usage_info['size_bytes'],
        'doc2_size': result2.usage_info['size_bytes'],
        'identical': text1 == text2
    }
```

## Error Handling

### Comprehensive Error Handler

```python
from enum import Enum
from typing import Optional

class ErrorType(Enum):
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    PROCESSING = "processing"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"

class OCRError:
    def __init__(self, error_type: ErrorType, message: str, details: Optional[dict] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}

async def process_with_retry(
    client: BudDocClient,
    url: str,
    max_retries: int = 3,
    backoff_factor: float = 2.0
) -> Optional[OCRResult]:
    """Process document with exponential backoff retry"""

    for attempt in range(max_retries):
        try:
            return await client.process_url(url)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                error = OCRError(
                    ErrorType.AUTHENTICATION,
                    "Invalid or expired API token",
                    {"status_code": 401}
                )
                raise

            elif e.response.status_code == 429:
                # Rate limited - wait and retry
                wait_time = backoff_factor ** attempt
                await asyncio.sleep(wait_time)
                continue

            elif e.response.status_code == 422:
                error = OCRError(
                    ErrorType.VALIDATION,
                    "Invalid request format",
                    {"response": e.response.text}
                )
                raise

            elif e.response.status_code >= 500:
                # Server error - retry
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    await asyncio.sleep(wait_time)
                    continue

        except asyncio.TimeoutError:
            error = OCRError(
                ErrorType.TIMEOUT,
                f"Request timeout after {client.timeout} seconds",
                {"url": url}
            )

            if attempt < max_retries - 1:
                continue
            raise

        except Exception as e:
            error = OCRError(
                ErrorType.NETWORK,
                f"Network error: {str(e)}",
                {"url": url}
            )

            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                await asyncio.sleep(wait_time)
                continue
            raise

    return None
```

## Performance Optimization

### 1. Connection Pooling

```python
import httpx

class OptimizedBudDocClient(BudDocClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
            )
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _make_request(self, request_data):
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        # Use persistent client
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await self._client.post(
            f"{self.base_url}/documents/ocr",
            json=request_data,
            headers=headers
        )
        response.raise_for_status()
        return OCRResult(**response.json())

# Usage with connection pooling
async with OptimizedBudDocClient(api_key="key") as client:
    # All requests share the same connection pool
    results = await asyncio.gather(
        client.process_url("https://example.com/doc1.pdf"),
        client.process_url("https://example.com/doc2.pdf"),
        client.process_url("https://example.com/doc3.pdf"),
    )
```

### 2. Caching Results

```python
from functools import lru_cache
import hashlib

class CachedBudDocClient(BudDocClient):
    def __init__(self, *args, cache_size: int = 128, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = {}
        self.cache_size = cache_size

    def _get_cache_key(self, url: str, model: str, prompt: Optional[str]) -> str:
        """Generate cache key from request parameters"""
        key_string = f"{url}:{model}:{prompt or ''}"
        return hashlib.md5(key_string.encode()).hexdigest()

    async def process_url(self, url: str, model: str = "qwen2-vl-7b", prompt: Optional[str] = None) -> OCRResult:
        cache_key = self._get_cache_key(url, model, prompt)

        # Check cache
        if cache_key in self.cache:
            self.logger.info(f"Cache hit for {url}")
            return self.cache[cache_key]

        # Process and cache
        result = await super().process_url(url, model, prompt)

        # Manage cache size
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[cache_key] = result
        return result
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock

@pytest.mark.asyncio
async def test_process_url_success():
    """Test successful URL processing"""

    client = BudDocClient(api_key="test-key")

    mock_response = {
        "document_id": "test-id",
        "model": "qwen2-vl-7b",
        "pages": [{"page_number": 1, "markdown": "Test content"}],
        "usage_info": {"pages_processed": 1, "size_bytes": 1000, "filename": "test.pdf"}
    }

    with patch.object(client, '_make_request', new=AsyncMock(return_value=OCRResult(**mock_response))):
        result = await client.process_url("https://example.com/test.pdf")

        assert result.document_id == "test-id"
        assert result.page_count == 1
        assert "Test content" in result.full_text

@pytest.mark.asyncio
async def test_authentication_header():
    """Test that authentication header is properly set"""

    client = BudDocClient(api_key="secret-key")

    with patch('httpx.AsyncClient.post', new=AsyncMock()) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "document_id": "test",
            "model": "test",
            "pages": [],
            "usage_info": {}
        }

        await client.process_url("https://example.com/test.pdf")

        # Check Authorization header was set
        call_args = mock_post.call_args
        headers = call_args.kwargs.get('headers', {})
        assert headers.get('Authorization') == 'Bearer secret-key'
```

### Integration Tests

```python
import os
from pathlib import Path

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_document_processing():
    """Integration test with real service"""

    # Skip if service not available
    api_key = os.getenv("TEST_API_KEY")
    if not api_key:
        pytest.skip("TEST_API_KEY not set")

    client = BudDocClient(
        base_url="http://localhost:9081",
        api_key=api_key
    )

    # Test with a sample document
    test_file = Path("tests/fixtures/sample.pdf")
    result = await client.process_file(test_file)

    assert result.document_id
    assert result.page_count > 0
    assert result.full_text
    assert result.usage_info["size_bytes"] > 0
```

## Best Practices

1. **Always use async/await** for better performance
2. **Implement proper error handling** with retries for network issues
3. **Use connection pooling** for multiple requests
4. **Set appropriate timeouts** based on document size
5. **Cache results** when processing the same documents multiple times
6. **Use bearer tokens** for multi-tenant scenarios
7. **Validate input** before sending requests
8. **Log requests and responses** for debugging
9. **Monitor API usage** to avoid rate limits
10. **Test with various document types** to ensure compatibility

## Troubleshooting Guide

### Common Issues and Solutions

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| Connection refused | Service not running | Check service is running on correct port |
| 401 Unauthorized | Invalid API key | Verify API key is correct and active |
| 413 Payload too large | File exceeds size limit | Reduce file size or increase limit |
| 422 Validation error | Invalid request format | Check request schema matches documentation |
| 500 Internal error | VLM API issue | Check VLM service status and logs |
| Timeout | Large document or slow VLM | Increase timeout or optimize document |
| Empty response | Unsupported format | Verify file format is supported |
| Garbled text | Wrong encoding | Ensure proper UTF-8 encoding |