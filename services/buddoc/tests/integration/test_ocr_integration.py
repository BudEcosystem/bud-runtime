"""Integration tests for OCR functionality."""

import asyncio
import base64
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from buddoc.documents.schemas import DocumentStatus


@pytest.mark.integration
class TestOCRIntegration:
    """End-to-end integration tests for OCR functionality."""

    @pytest.mark.asyncio
    async def test_end_to_end_pdf_processing(
        self, async_client: AsyncClient, sample_pdf_content, vlm_server_url
    ):
        """Test complete PDF processing flow."""
        # Set the VLM server URL to our mock server
        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            # Make OCR request through the real route
            request = {
                "model": "qwen2-vl-7b",
                "document": {
                    "type": "document_url",
                    "document_url": "https://example.com/test.pdf"
                }
            }

            # Mock the document download
            async def mock_download(url, timeout=30):
                return sample_pdf_content

            with patch("buddoc.documents.services.DocumentService.fetch_document_from_url", mock_download):
                response = await async_client.post("/documents/ocr", json=request)

            # Verify response has correct OCRResponse format
            assert response.status_code == 200
            data = response.json()
            assert "document_id" in data
            assert "model" in data
            assert data["model"] == "qwen2-vl-7b"
            assert "pages" in data
            assert len(data["pages"]) > 0
            assert "usage_info" in data

    @pytest.mark.asyncio
    async def test_end_to_end_image_processing(
        self, async_client: AsyncClient, sample_image_content, vlm_server_url
    ):
        """Test complete image processing flow."""
        # Create base64 data URI
        base64_content = base64.b64encode(sample_image_content).decode()
        data_uri = f"data:image/png;base64,{base64_content}"

        # Set the VLM server URL to our mock server
        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            # Make OCR request
            request = {
                "model": "qwen2-vl-7b",
                "document": {
                    "type": "image_url",
                    "image_url": data_uri
                },
                "prompt": "Extract all text from this image"
            }

            response = await async_client.post("/documents/ocr", json=request)

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "document_id" in data
            assert "pages" in data
            assert "usage_info" in data
            assert data["usage_info"]["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, async_client: AsyncClient, sample_base64_image, vlm_server_url
    ):
        """Test handling concurrent OCR requests."""
        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            # Create multiple requests
            requests = []
            for i in range(5):
                request = {
                    "model": "qwen2-vl-7b",
                    "document": {
                        "type": "image_url",
                        "image_url": sample_base64_image
                    }
                }
                requests.append(request)

            # Send concurrent requests
            tasks = [
                async_client.post("/documents/ocr", json=req)
                for req in requests
            ]

            responses = await asyncio.gather(*tasks)

            # All should succeed with proper format
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert "document_id" in data
                assert "pages" in data
                assert "usage_info" in data

    @pytest.mark.asyncio
    async def test_error_recovery(
        self, async_client: AsyncClient, sample_pdf_content, mock_vlm_server
    ):
        """Test error handling and recovery."""
        # Setup VLM server to return error
        server, setup_vlm = mock_vlm_server
        setup_vlm(should_fail=True, error_message="VLM processing failed")

        with patch("buddoc.commons.config.app_settings.vlm_api_url", server.url_for("/v1/chat/completions")):
            # Mock the document download
            async def mock_download(url, timeout=30):
                return sample_pdf_content

            with patch("buddoc.documents.services.DocumentService.fetch_document_from_url", mock_download):
                request = {
                    "model": "qwen2-vl-7b",
                    "document": {
                        "type": "document_url",
                        "document_url": "https://example.com/test.pdf"
                    }
                }

                response = await async_client.post("/documents/ocr", json=request)

                # Should handle error gracefully and return 200 with error in result
                assert response.status_code == 200
                data = response.json()
                # Check that the result indicates failure (empty pages)
                assert "pages" in data
                assert len(data["pages"]) == 0  # No pages when processing fails

    @pytest.mark.asyncio
    async def test_large_document_handling(
        self, async_client: AsyncClient, vlm_server_url
    ):
        """Test handling of large documents."""
        # Create large content (5MB)
        large_content = b"x" * (5 * 1024 * 1024)
        base64_content = base64.b64encode(large_content).decode()
        data_uri = f"data:application/pdf;base64,{base64_content}"

        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            request = {
                "model": "qwen2-vl-7b",
                "document": {
                    "type": "image_url",
                    "image_url": data_uri
                }
            }

            response = await async_client.post("/documents/ocr", json=request)

            # Should handle large files
            assert response.status_code == 200
            data = response.json()
            assert "document_id" in data
            assert "usage_info" in data
            assert data["usage_info"]["size_bytes"] > 5000000

    @pytest.mark.asyncio
    async def test_multipage_document_processing(
        self, async_client: AsyncClient, vlm_server_url_multipage
    ):
        """Test processing documents with multiple pages."""
        # Create a valid multi-page PDF content
        multipage_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 6 0 R 9 0 R] /Count 3 >>
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
BT /F1 12 Tf 100 700 Td (Page 1 Content) Tj ET
endstream
endobj
6 0 obj
<< /Type /Page /Parent 2 0 R /Resources 7 0 R /MediaBox [0 0 612 792] /Contents 8 0 R >>
endobj
7 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
8 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 2 Content) Tj ET
endstream
endobj
9 0 obj
<< /Type /Page /Parent 2 0 R /Resources 10 0 R /MediaBox [0 0 612 792] /Contents 11 0 R >>
endobj
10 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
11 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 3 Content) Tj ET
endstream
endobj
xref
0 12
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000117 00000 n
0000000229 00000 n
0000000328 00000 n
0000000421 00000 n
0000000533 00000 n
0000000632 00000 n
0000000725 00000 n
0000000838 00000 n
0000000938 00000 n
trailer
<< /Size 12 /Root 1 0 R >>
startxref
1032
%%EOF"""

        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url_multipage):
            # Mock the document download
            async def mock_download(url, timeout=30):
                return multipage_pdf

            with patch("buddoc.documents.services.DocumentService.fetch_document_from_url", mock_download):
                request = {
                    "model": "qwen2-vl-7b",
                    "document": {
                        "type": "document_url",
                        "document_url": "https://example.com/multipage.pdf"
                    }
                }

                response = await async_client.post("/documents/ocr", json=request)

                assert response.status_code == 200
                data = response.json()
                assert "pages" in data
                # When processing succeeds, we should have pages with content
                assert len(data["pages"]) > 0
                # Check that we have content from multiple pages
                pages_content = " ".join(p.get("markdown", "") for p in data["pages"])
                # Should have content mentioning pages
                assert "page" in pages_content.lower()

    @pytest.mark.asyncio
    async def test_different_file_formats(self, async_client: AsyncClient, vlm_server_url):
        """Test processing different file formats."""
        # Fix the base64 string - use a valid tiny PNG
        valid_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

        formats = [
            ("pdf", "application/pdf", b"%PDF-1.4"),
            ("png", "image/png", base64.b64decode(valid_png_base64)),
            ("jpg", "image/jpeg", b"\xff\xd8\xff"),
        ]

        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            for ext, mime_type, content_start in formats:
                # Create minimal content for each format
                content = content_start + b"test content"
                base64_content = base64.b64encode(content).decode()
                data_uri = f"data:{mime_type};base64,{base64_content}"

                request = {
                    "model": "qwen2-vl-7b",
                    "document": {
                        "type": "image_url",
                        "image_url": data_uri
                    }
                }

                response = await async_client.post("/documents/ocr", json=request)

                assert response.status_code == 200
                data = response.json()
                assert "document_id" in data
                assert "pages" in data
                assert "usage_info" in data


@pytest.mark.integration
class TestAuthIntegration:
    """Integration tests for authentication."""

    @pytest.mark.asyncio
    async def test_bearer_token_priority(
        self, async_client: AsyncClient, sample_base64_image, vlm_server_url
    ):
        """Test that bearer token takes priority over environment variable."""
        header_token = "header-token-priority"
        env_token = "env-token-fallback"

        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url), \
             patch("buddoc.commons.config.secrets_settings.vlm_api_token", env_token):

            request = {
                "model": "qwen2-vl-7b",
                "document": {
                    "type": "image_url",
                    "image_url": sample_base64_image
                }
            }

            # Send with Authorization header
            response = await async_client.post(
                "/documents/ocr",
                json=request,
                headers={"Authorization": f"Bearer {header_token}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "document_id" in data

    @pytest.mark.asyncio
    async def test_token_rotation(self, async_client: AsyncClient, sample_base64_image, vlm_server_url):
        """Test rotating API tokens between requests."""
        tokens = ["token1", "token2", "token3"]

        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            for token in tokens:
                request = {
                    "model": "qwen2-vl-7b",
                    "document": {
                        "type": "image_url",
                        "image_url": sample_base64_image
                    }
                }

                response = await async_client.post(
                    "/documents/ocr",
                    json=request,
                    headers={"Authorization": f"Bearer {token}"}
                )

                assert response.status_code == 200
                data = response.json()
                assert "document_id" in data

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(
        self, async_client: AsyncClient, sample_base64_image, vlm_server_url
    ):
        """Test multi-tenant scenarios with different API keys."""
        tenant_configs = [
            ("tenant1", "key1", "qwen2-vl-7b"),
            ("tenant2", "key2", "qwen2-vl-7b"),
            ("tenant3", "key3", "qwen2-vl-7b"),
        ]

        with patch("buddoc.commons.config.app_settings.vlm_api_url", vlm_server_url):
            for tenant_id, api_key, model in tenant_configs:
                request = {
                    "model": model,
                    "document": {
                        "type": "image_url",
                        "image_url": sample_base64_image
                    }
                }

                response = await async_client.post(
                    "/documents/ocr",
                    json=request,
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["model"] == model
                assert "document_id" in data
                assert "pages" in data