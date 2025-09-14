"""Shared fixtures and configuration for tests."""

import base64
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pytest_httpserver import HTTPServer

# Set test environment variables before importing the app
os.environ.setdefault("LOG_LEVEL", "INFO")
# Use tempfile to create secure temporary directory
test_log_dir = os.path.join(tempfile.gettempdir(), "buddoc_test_logs")
os.environ.setdefault("LOG_DIR", test_log_dir)
os.environ.setdefault("VLM_API_URL", "http://test-vlm:1234/v1/chat/completions")

# Create log directory if it doesn't exist
log_dir = Path(os.environ.get("LOG_DIR", test_log_dir))
log_dir.mkdir(parents=True, exist_ok=True)

# Import app after setting environment variables
from buddoc.main import app


# Test configuration
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client():
    """Create an async test client."""
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_document_id():
    """Generate a sample document ID."""
    return uuid4()


@pytest.fixture
def sample_pdf_content():
    """Create sample PDF content."""
    # Minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test Document) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000117 00000 n
0000000229 00000 n
0000000328 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
421
%%EOF"""


@pytest.fixture
def sample_image_content():
    """Create sample PNG image content (1x1 pixel transparent PNG)."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )


@pytest.fixture
def sample_base64_image():
    """Create a base64-encoded image data URI."""
    image_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    base64_content = base64.b64encode(image_content).decode()
    return f"data:image/png;base64,{base64_content}"


@pytest.fixture
def sample_ocr_request_url():
    """Create a sample OCR request with URL."""
    return {
        "model": "qwen2-vl-7b",
        "document": {
            "type": "document_url",
            "document_url": "https://example.com/test.pdf"
        }
    }


@pytest.fixture
def sample_ocr_request_base64(sample_base64_image):
    """Create a sample OCR request with base64 image."""
    return {
        "model": "qwen2-vl-7b",
        "document": {
            "type": "image_url",
            "image_url": sample_base64_image
        }
    }


@pytest.fixture
def sample_ocr_request_with_prompt():
    """Create a sample OCR request with custom prompt."""
    return {
        "model": "qwen2-vl-7b",
        "document": {
            "type": "document_url",
            "document_url": "https://example.com/invoice.pdf"
        },
        "prompt": "Extract invoice number and total amount"
    }


@pytest.fixture
def mock_vlm_success_response():
    """Mock successful VLM API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "qwen2-vl-7b",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "# Document Title\n\nThis is the extracted text from the document.\n\n## Section 1\n\nContent of section 1."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }


@pytest.fixture
def mock_vlm_error_response():
    """Mock VLM API error response."""
    return {
        "error": {
            "message": "Invalid API key provided",
            "type": "authentication_error",
            "code": "invalid_api_key"
        }
    }


@pytest.fixture
def mock_document_service():
    """Mock document service."""
    from buddoc.documents.schemas import (
        DocumentOCRResult,
        DocumentStatus,
        PageResult,
        UsageInfo
    )
    from datetime import datetime

    mock_service = Mock()

    # Default successful response
    mock_result = DocumentOCRResult(
        document_id=uuid4(),
        status=DocumentStatus.COMPLETED,
        pages=[
            PageResult(
                page_number=1,
                markdown="# Test Document\n\nExtracted text content."
            )
        ],
        usage_info=UsageInfo(
            pages_processed=1,
            size_bytes=1024,
            filename="test.pdf"
        ),
        created_at=datetime.now()
    )

    mock_service.process_document = AsyncMock(return_value=mock_result)
    return mock_service


@pytest.fixture
def mock_httpx_client(mock_vlm_success_response):
    """Mock httpx client for VLM API calls."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value=mock_vlm_success_response)
    mock_response.raise_for_status = Mock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def mock_docling_converter():
    """Mock Docling DocumentConverter."""
    mock_converter = Mock()

    # Create mock conversion result
    mock_result = Mock()
    mock_result.document = Mock()
    mock_result.document.export_to_markdown = Mock(return_value="# Test Document\n\nTest content")

    mock_converter.convert = Mock(return_value=mock_result)
    return mock_converter


@pytest.fixture
def temp_file_path(tmp_path):
    """Create a temporary file path."""
    return tmp_path / "test_document.pdf"


@pytest.fixture
def mock_env_variables(monkeypatch):
    """Mock environment variables."""
    test_upload_dir = os.path.join(tempfile.gettempdir(), "test_uploads")
    env_vars = {
        "VLM_API_URL": "http://mock-vlm:1234/v1/chat/completions",
        "VLM_MODEL_NAME": "test-model",
        "VLM_API_TOKEN": "test-token-from-env",
        "MAX_FILE_SIZE_MB": "50",
        "ALLOWED_EXTENSIONS": "pdf,png,jpg,jpeg,docx",
        "TEMP_UPLOAD_DIR": test_upload_dir
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def bearer_token():
    """Sample bearer token for testing."""
    return "Bearer test-api-key-from-header"


@pytest.fixture
def mock_download_file():
    """Mock file download from URL."""
    async def _download(url: str, **kwargs) -> bytes:
        # Accept any keyword arguments like timeout
        if "pdf" in url:
            return b"%PDF-1.4 test content"
        elif "image" in url or "png" in url or "jpg" in url:
            # Return minimal PNG
            return base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
        else:
            return b"test document content"

    return AsyncMock(side_effect=_download)


@pytest.fixture
def sample_page_result():
    """Create a sample page result."""
    from buddoc.documents.schemas import PageResult

    return PageResult(
        page_number=1,
        markdown="# Sample Page\n\nThis is sample extracted text."
    )


@pytest.fixture
def sample_usage_info():
    """Create sample usage info."""
    from buddoc.documents.schemas import UsageInfo

    return UsageInfo(
        pages_processed=2,
        size_bytes=2048,
        filename="sample.pdf"
    )


@pytest.fixture
def sample_ocr_response(sample_document_id, sample_page_result, sample_usage_info):
    """Create a sample OCR response."""
    from buddoc.documents.schemas import OCRResponse

    return OCRResponse(
        document_id=sample_document_id,
        model="qwen2-vl-7b",
        pages=[sample_page_result],
        usage_info=sample_usage_info
    )


# Async fixtures for testing async functions
@pytest_asyncio.fixture
async def mock_async_download():
    """Mock async download function."""
    async def download(url: str) -> bytes:
        if "error" in url:
            raise Exception("Download failed")
        return b"downloaded content"

    return download


# Test data factories
@pytest.fixture
def ocr_request_factory():
    """Factory for creating OCR requests."""
    def _create(
        model: str = "qwen2-vl-7b",
        doc_type: str = "document_url",
        url: Optional[str] = None,
        base64_data: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": model,
            "document": {"type": doc_type}
        }

        document = request["document"]
        if doc_type == "document_url":
            document["document_url"] = url or "https://example.com/doc.pdf"
        elif doc_type == "image_url":
            document["image_url"] = base64_data or "data:image/png;base64,abc123"

        if prompt:
            request["prompt"] = prompt

        return request

    return _create


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files(tmp_path):
    """Cleanup temporary files after tests."""
    yield
    # Cleanup happens automatically with tmp_path


# Mock VLM Server fixtures for integration testing
@pytest.fixture
def mock_vlm_server(httpserver: HTTPServer):
    """Create a mock VLM server that mimics the actual VLM API."""

    def setup_vlm_endpoints(
        response_content: str = "# Extracted Document\n\nThis is the extracted text from the document.",
        should_fail: bool = False,
        error_message: str = "VLM processing failed"
    ):
        """Setup VLM server endpoints with customizable responses."""

        # Clear any existing expectations first
        httpserver.clear()

        if should_fail:
            # Setup error response
            httpserver.expect_request(
                "/v1/chat/completions",
                method="POST"
            ).respond_with_json(
                {"error": {"message": error_message, "type": "processing_error"}},
                status=500
            )
        else:
            # Setup successful response
            response = {
                "id": f"chatcmpl-{uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "qwen2-vl-7b",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                }
            }

            httpserver.expect_request(
                "/v1/chat/completions",
                method="POST"
            ).respond_with_json(response, status=200)

    # Set default successful response
    setup_vlm_endpoints()

    # Return both the server and the setup function for customization
    return httpserver, setup_vlm_endpoints


@pytest.fixture
def mock_vlm_server_multipage(httpserver: HTTPServer):
    """Create a mock VLM server that returns multipage responses."""

    # Setup multipage response
    page_contents = [
        "# Page 1\n\nContent of the first page.",
        "# Page 2\n\nContent of the second page.",
        "# Page 3\n\nContent of the third page."
    ]

    # Counter to return different content for each call
    call_count = {"count": 0}

    def handle_request(request):
        """Handle VLM requests and return page content sequentially."""
        from werkzeug.wrappers import Response

        idx = call_count["count"] % len(page_contents)
        response_data = {
            "id": f"chatcmpl-{uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "qwen2-vl-7b",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": page_contents[idx]
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 100 + idx * 10,
                "completion_tokens": 50 + idx * 5,
                "total_tokens": 150 + idx * 15
            }
        }
        call_count["count"] += 1

        return Response(
            json.dumps(response_data),
            status=200,
            mimetype='application/json'
        )

    httpserver.expect_request(
        "/v1/chat/completions",
        method="POST"
    ).respond_with_handler(handle_request)

    return httpserver


@pytest.fixture
def vlm_server_url(mock_vlm_server):
    """Get the URL of the mock VLM server."""
    server, _ = mock_vlm_server
    return server.url_for("/v1/chat/completions")


@pytest.fixture
def vlm_server_url_multipage(mock_vlm_server_multipage):
    """Get the URL of the mock VLM server for multipage tests."""
    return mock_vlm_server_multipage.url_for("/v1/chat/completions")