"""Mock responses for testing."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class VLMResponses:
    """Mock VLM API responses."""

    @staticmethod
    def success_response(
        content: str = "# Document Title\n\nExtracted text content from the document.",
        model: str = "qwen2-vl-7b",
        prompt_tokens: int = 100,
        completion_tokens: int = 50
    ) -> Dict[str, Any]:
        """Generate a successful VLM response."""
        return {
            "id": f"chatcmpl-{uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }

    @staticmethod
    def multipage_response(pages: int = 3) -> Dict[str, Any]:
        """Generate a multi-page VLM response."""
        content_parts = []
        for i in range(1, pages + 1):
            content_parts.append(f"# Page {i}\n\nContent of page {i}.")

        return VLMResponses.success_response(
            content="\n\n---\n\n".join(content_parts),
            completion_tokens=50 * pages
        )

    @staticmethod
    def invoice_response() -> Dict[str, Any]:
        """Generate an invoice extraction response."""
        content = """# Invoice #INV-2024-001

**Date:** January 15, 2024
**Due Date:** February 15, 2024

## Vendor Information
Acme Corporation
123 Business St.
City, State 12345

## Items
| Description | Quantity | Price | Total |
|-------------|----------|-------|-------|
| Product A   | 10       | $50   | $500  |
| Product B   | 5        | $100  | $500  |

**Subtotal:** $1,000
**Tax (10%):** $100
**Total:** $1,100"""

        return VLMResponses.success_response(content=content)

    @staticmethod
    def error_response(
        error_type: str = "authentication_error",
        message: str = "Invalid API key provided"
    ) -> Dict[str, Any]:
        """Generate an error response."""
        return {
            "error": {
                "message": message,
                "type": error_type,
                "code": f"err_{error_type}"
            }
        }

    @staticmethod
    def rate_limit_response() -> Dict[str, Any]:
        """Generate a rate limit error response."""
        return VLMResponses.error_response(
            error_type="rate_limit_error",
            message="Rate limit exceeded. Please try again later."
        )

    @staticmethod
    def timeout_response() -> Dict[str, Any]:
        """Generate a timeout error response."""
        return VLMResponses.error_response(
            error_type="timeout_error",
            message="Request timeout after 90 seconds"
        )


class DocumentSamples:
    """Sample document data for testing."""

    @staticmethod
    def minimal_pdf() -> bytes:
        """Generate minimal valid PDF content."""
        return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000117 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
186
%%EOF"""

    @staticmethod
    def text_document() -> str:
        """Generate sample text document content."""
        return """Sample Document

This is a test document used for OCR testing.

Section 1: Introduction
This document contains sample text for testing the OCR functionality.

Section 2: Content
- Item 1: Test content
- Item 2: More test content
- Item 3: Additional content

Section 3: Conclusion
This concludes the test document."""

    @staticmethod
    def html_document() -> str:
        """Generate sample HTML document."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Test Document</title>
</head>
<body>
    <h1>Sample HTML Document</h1>
    <p>This is a test HTML document for OCR processing.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
</body>
</html>"""

    @staticmethod
    def csv_data() -> str:
        """Generate sample CSV data."""
        return """Name,Age,Email,Department
John Doe,30,john@example.com,Engineering
Jane Smith,28,jane@example.com,Marketing
Bob Johnson,35,bob@example.com,Sales
Alice Brown,32,alice@example.com,HR"""


class RequestSamples:
    """Sample request data for testing."""

    @staticmethod
    def ocr_request_url(
        url: str = "https://example.com/document.pdf",
        model: str = "qwen2-vl-7b",
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate OCR request with URL."""
        request = {
            "model": model,
            "document": {
                "type": "document_url",
                "document_url": url
            }
        }
        if prompt:
            request["prompt"] = prompt
        return request

    @staticmethod
    def ocr_request_base64(
        base64_data: str,
        model: str = "qwen2-vl-7b",
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate OCR request with base64 data."""
        request = {
            "model": model,
            "document": {
                "type": "image_url",
                "image_url": base64_data
            }
        }
        if prompt:
            request["prompt"] = prompt
        return request

    @staticmethod
    def batch_requests(count: int = 5) -> List[Dict[str, Any]]:
        """Generate multiple OCR requests."""
        requests = []
        for i in range(count):
            requests.append(
                RequestSamples.ocr_request_url(
                    url=f"https://example.com/doc{i}.pdf",
                    model="qwen2-vl-7b"
                )
            )
        return requests


class TestDataFactory:
    """Factory for generating test data."""

    @staticmethod
    def create_page_result(
        page_number: int = 1,
        content: str = "Test page content"
    ) -> Dict[str, Any]:
        """Create a page result."""
        return {
            "page_number": page_number,
            "markdown": content
        }

    @staticmethod
    def create_usage_info(
        pages: int = 1,
        size: int = 1024,
        filename: str = "test.pdf"
    ) -> Dict[str, Any]:
        """Create usage info."""
        return {
            "pages_processed": pages,
            "size_bytes": size,
            "filename": filename
        }

    @staticmethod
    def create_ocr_response(
        document_id: Optional[str] = None,
        model: str = "qwen2-vl-7b",
        pages: int = 1,
        size: int = 1024
    ) -> Dict[str, Any]:
        """Create a complete OCR response."""
        if document_id is None:
            document_id = str(uuid4())

        page_results = [
            TestDataFactory.create_page_result(i + 1, f"Content of page {i + 1}")
            for i in range(pages)
        ]

        return {
            "document_id": document_id,
            "model": model,
            "pages": page_results,
            "usage_info": TestDataFactory.create_usage_info(pages, size)
        }

    @staticmethod
    def create_error_response(
        status_code: int = 500,
        detail: str = "Internal server error"
    ) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "detail": detail,
            "status_code": status_code
        }


# Predefined test scenarios
TEST_SCENARIOS = {
    "success": {
        "request": RequestSamples.ocr_request_url(),
        "vlm_response": VLMResponses.success_response(),
        "expected_status": 200
    },
    "multipage": {
        "request": RequestSamples.ocr_request_url(),
        "vlm_response": VLMResponses.multipage_response(5),
        "expected_status": 200
    },
    "invoice": {
        "request": RequestSamples.ocr_request_url(
            prompt="Extract invoice details"
        ),
        "vlm_response": VLMResponses.invoice_response(),
        "expected_status": 200
    },
    "auth_error": {
        "request": RequestSamples.ocr_request_url(),
        "vlm_response": VLMResponses.error_response(),
        "expected_status": 401
    },
    "rate_limit": {
        "request": RequestSamples.ocr_request_url(),
        "vlm_response": VLMResponses.rate_limit_response(),
        "expected_status": 429
    }
}
