"""Unit tests for OCR routes."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from buddoc.documents.schemas import (
    DocumentOCRResult,
    DocumentStatus,
    OCRResponse,
    PageResult,
    UsageInfo,
)


class TestOCRRoutes:
    """Test cases for OCR endpoint routes."""

    @pytest.mark.asyncio
    async def test_ocr_with_url_success(
        self, async_client: AsyncClient, sample_ocr_request_url, mock_document_service
    ):
        """Test successful OCR processing with URL input."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert "document_id" in data
            assert data["model"] == "qwen2-vl-7b"
            assert len(data["pages"]) > 0
            assert data["pages"][0]["page_number"] == 1
            assert "markdown" in data["pages"][0]
            assert "usage_info" in data

    @pytest.mark.asyncio
    async def test_ocr_with_base64_success(
        self, async_client: AsyncClient, sample_ocr_request_base64, mock_document_service
    ):
        """Test successful OCR processing with base64 input."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_base64
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert "document_id" in data
            assert data["model"] == "qwen2-vl-7b"
            assert "pages" in data
            assert "usage_info" in data

    @pytest.mark.asyncio
    async def test_ocr_with_bearer_token(
        self, async_client: AsyncClient, sample_ocr_request_url, mock_document_service, bearer_token
    ):
        """Test OCR with bearer token authentication."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            # Verify the service is called with the token
            mock_document_service.process_document = AsyncMock()

            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url,
                headers={"Authorization": bearer_token}
            )

            # Check that process_document was called with api_token
            mock_document_service.process_document.assert_called_once()
            call_kwargs = mock_document_service.process_document.call_args.kwargs
            assert call_kwargs.get("api_token") == "test-api-key-from-header"

    @pytest.mark.asyncio
    async def test_ocr_without_bearer_token(
        self, async_client: AsyncClient, sample_ocr_request_url, mock_document_service
    ):
        """Test OCR without bearer token (should use env fallback)."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            mock_document_service.process_document = AsyncMock()

            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url
            )

            # Check that process_document was called without api_token
            mock_document_service.process_document.assert_called_once()
            call_kwargs = mock_document_service.process_document.call_args.kwargs
            assert call_kwargs.get("api_token") is None

    @pytest.mark.asyncio
    async def test_ocr_with_custom_prompt(
        self, async_client: AsyncClient, sample_ocr_request_with_prompt, mock_document_service
    ):
        """Test OCR with custom prompt."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_with_prompt
            )

            assert response.status_code == status.HTTP_200_OK
            # Verify prompt was passed to service
            mock_document_service.process_document.assert_called_once()
            call_args = mock_document_service.process_document.call_args[0]
            assert call_args[0].prompt == "Extract invoice number and total amount"

    @pytest.mark.asyncio
    async def test_ocr_invalid_document_type(self, async_client: AsyncClient):
        """Test OCR with invalid document type."""
        invalid_request = {
            "model": "qwen2-vl-7b",
            "document": {
                "type": "invalid_type",
                "document_url": "https://example.com/doc.pdf"
            }
        }

        response = await async_client.post(
            "/documents/ocr",
            json=invalid_request
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_ocr_missing_document_url(self, async_client: AsyncClient):
        """Test OCR with missing document URL."""
        invalid_request = {
            "model": "qwen2-vl-7b",
            "document": {
                "type": "document_url"
                # Missing document_url field
            }
        }

        response = await async_client.post(
            "/documents/ocr",
            json=invalid_request
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_ocr_missing_image_url(self, async_client: AsyncClient):
        """Test OCR with missing image URL."""
        invalid_request = {
            "model": "qwen2-vl-7b",
            "document": {
                "type": "image_url"
                # Missing image_url field
            }
        }

        response = await async_client.post(
            "/documents/ocr",
            json=invalid_request
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_ocr_different_models(self, async_client: AsyncClient, mock_document_service):
        """Test OCR with different VLM models."""
        models = ["qwen2-vl-7b", "docling-vlm", "mistral-ocr-latest", "pixtral-12b"]

        with patch("buddoc.documents.routes.document_service", mock_document_service):
            for model in models:
                request = {
                    "model": model,
                    "document": {
                        "type": "document_url",
                        "document_url": "https://example.com/doc.pdf"
                    }
                }

                response = await async_client.post(
                    "/documents/ocr",
                    json=request
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["model"] == model

    @pytest.mark.asyncio
    async def test_ocr_service_exception(
        self, async_client: AsyncClient, sample_ocr_request_url
    ):
        """Test OCR when service raises an exception."""
        with patch("buddoc.documents.routes.document_service") as mock_service:
            mock_service.process_document = AsyncMock(
                side_effect=Exception("Service error")
            )

            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "Error processing document" in data["detail"]

    @pytest.mark.asyncio
    async def test_ocr_invalid_bearer_format(
        self, async_client: AsyncClient, sample_ocr_request_url, mock_document_service
    ):
        """Test OCR with invalid Authorization header format."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            # The mock_document_service already has a proper return value configured
            # Invalid format - missing "Bearer " prefix
            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url,
                headers={"Authorization": "invalid-token-format"}
            )

            # Should still process but without token
            assert response.status_code == status.HTTP_200_OK
            call_kwargs = mock_document_service.process_document.call_args.kwargs
            assert call_kwargs.get("api_token") is None

    @pytest.mark.asyncio
    async def test_ocr_empty_request_body(self, async_client: AsyncClient):
        """Test OCR with empty request body."""
        response = await async_client.post(
            "/documents/ocr",
            json={}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_ocr_response_structure(
        self, async_client: AsyncClient, sample_ocr_request_url, mock_document_service
    ):
        """Test OCR response structure matches schema."""
        with patch("buddoc.documents.routes.document_service", mock_document_service):
            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Validate response structure
            assert isinstance(data["document_id"], str)
            assert isinstance(data["model"], str)
            assert isinstance(data["pages"], list)
            assert isinstance(data["usage_info"], dict)

            # Validate page structure
            if data["pages"]:
                page = data["pages"][0]
                assert "page_number" in page
                assert "markdown" in page
                assert isinstance(page["page_number"], int)
                assert isinstance(page["markdown"], str)

            # Validate usage info structure
            usage = data["usage_info"]
            assert "pages_processed" in usage
            assert "size_bytes" in usage
            assert "filename" in usage

    @pytest.mark.asyncio
    async def test_ocr_multipage_document(
        self, async_client: AsyncClient, sample_ocr_request_url
    ):
        """Test OCR with multi-page document."""
        # Create multi-page result
        multipage_result = DocumentOCRResult(
            document_id=uuid4(),
            status=DocumentStatus.COMPLETED,
            pages=[
                PageResult(page_number=1, markdown="Page 1 content"),
                PageResult(page_number=2, markdown="Page 2 content"),
                PageResult(page_number=3, markdown="Page 3 content"),
            ],
            usage_info=UsageInfo(
                pages_processed=3,
                size_bytes=5120,
                filename="multipage.pdf"
            ),
            created_at=datetime(2024, 1, 1, 0, 0, 0)
        )

        mock_service = Mock()
        mock_service.process_document = AsyncMock(return_value=multipage_result)

        with patch("buddoc.documents.routes.document_service", mock_service):
            response = await async_client.post(
                "/documents/ocr",
                json=sample_ocr_request_url
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert len(data["pages"]) == 3
            assert data["usage_info"]["pages_processed"] == 3
            for i, page in enumerate(data["pages"], 1):
                assert page["page_number"] == i
                assert f"Page {i} content" in page["markdown"]
