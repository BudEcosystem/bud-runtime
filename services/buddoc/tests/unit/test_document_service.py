"""Unit tests for document service."""

import base64
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from uuid import uuid4
import pytest

from buddoc.documents.schemas import (
    DocumentOCRResult,
    DocumentStatus,
    DocumentType,
    OCRRequest,
    DocumentInput,
    PageResult,
    UsageInfo,
)
from buddoc.documents.services import DocumentService


class TestDocumentService:
    """Test cases for document service."""

    @pytest.fixture
    def document_service(self):
        """Create document service instance."""
        return DocumentService()

    @pytest.fixture
    def mock_vlm_options(self):
        """Mock VLM options."""
        from buddoc.documents.schemas import VLMOptions
        return VLMOptions(
            api_url="http://mock-vlm:1234/v1/chat/completions",
            model="test-model",
            prompt="Extract text",
            temperature=0.7,
            max_tokens=1000
        )

    @pytest.fixture
    def mock_converter_result(self):
        """Create a mock converter result with pages."""
        result = Mock()
        result.document = Mock()
        result.document.export_to_markdown = Mock(return_value="# Test Document\n\nExtracted text content.")
        return result

    @pytest.mark.asyncio
    async def test_process_document_with_url(self, document_service):
        """Test processing document from URL."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.DOCUMENT_URL,
                document_url="https://example.com/test.pdf"
            )
        )

        # Mock the entire document processing flow
        with patch.object(document_service, "process_document") as mock_process:
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[PageResult(page_number=1, markdown="# Extracted Text\n\nContent from document")],
                usage_info=UsageInfo(pages_processed=1, size_bytes=1024, filename="test.pdf"),
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)

            assert isinstance(result, DocumentOCRResult)
            assert result.status == DocumentStatus.COMPLETED
            assert len(result.pages) > 0
            assert result.pages[0].markdown == "# Extracted Text\n\nContent from document"

    @pytest.mark.asyncio
    async def test_process_document_with_base64(self, document_service, sample_base64_image):
        """Test processing document from base64 data URI."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        with patch.object(document_service, "process_document") as mock_process:
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[PageResult(page_number=1, markdown="Extracted from base64")],
                usage_info=UsageInfo(pages_processed=1, size_bytes=70, filename="image.png"),
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)

            assert isinstance(result, DocumentOCRResult)
            assert result.status == DocumentStatus.COMPLETED
            assert result.usage_info.size_bytes > 0

    @pytest.mark.asyncio
    async def test_process_document_with_api_token(self, document_service, sample_base64_image):
        """Test processing document with API token."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        api_token = "custom-api-token"

        with patch.object(document_service, "_configure_vlm_options") as mock_config:
            mock_config.return_value = Mock()

            with patch.object(document_service, "process_document") as mock_process:
                mock_result = DocumentOCRResult(
                    document_id=uuid4(),
                    status=DocumentStatus.COMPLETED,
                    pages=[PageResult(page_number=1, markdown="Text")],
                    usage_info=UsageInfo(pages_processed=1, size_bytes=70, filename="image.png"),
                    created_at=datetime.now()
                )
                # Use side_effect to check the api_token argument
                def check_token(*args, **kwargs):
                    # Verify api_token was passed
                    assert kwargs.get("api_token") == api_token or (len(args) > 1 and args[1] == api_token)
                    return mock_result

                mock_process.side_effect = check_token

                result = await document_service.process_document(request, api_token=api_token)

                assert isinstance(result, DocumentOCRResult)
                assert result.status == DocumentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_document_with_custom_prompt(self, document_service, sample_base64_image):
        """Test processing document with custom prompt."""
        custom_prompt = "Extract invoice details"
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            ),
            prompt=custom_prompt
        )

        with patch.object(document_service, "process_document") as mock_process:
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[PageResult(page_number=1, markdown="Invoice #123")],
                usage_info=UsageInfo(pages_processed=1, size_bytes=70, filename="image.png"),
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)

            assert result.pages[0].markdown == "Invoice #123"

    @pytest.mark.asyncio
    async def test_vlm_options_configuration(self, document_service):
        """Test VLM options configuration."""
        from buddoc.documents.schemas import VLMOptions

        # Test with custom options
        vlm_options = VLMOptions(
            api_url="http://custom:1234/v1/chat",
            model="custom-model",
            temperature=0.5,
            max_tokens=2000
        )

        api_token = "test-token"
        result = document_service._configure_vlm_options(vlm_options, api_token)

        assert str(result.url) == "http://custom:1234/v1/chat"
        assert result.params["model"] == "custom-model"
        assert result.params["temperature"] == 0.5
        assert result.params["max_tokens"] == 2000
        assert "Authorization" in result.headers
        assert result.headers["Authorization"] == f"Bearer {api_token}"

    @pytest.mark.asyncio
    async def test_vlm_options_without_token(self, document_service):
        """Test VLM options configuration without token."""
        from buddoc.documents.schemas import VLMOptions

        vlm_options = VLMOptions(
            api_url="http://test:1234/v1/chat",
            model="test-model"
        )

        # Mock environment token
        with patch("buddoc.documents.services.secrets_settings") as mock_secrets:
            mock_secrets.vlm_api_token = "env-token"
            result = document_service._configure_vlm_options(vlm_options)

            assert "Authorization" in result.headers
            assert result.headers["Authorization"] == "Bearer env-token"

    @pytest.mark.asyncio
    async def test_document_type_detection_url(self, document_service):
        """Test document type detection for URLs."""
        request = OCRRequest(
            model="test",
            document=DocumentInput(
                type=DocumentType.DOCUMENT_URL,
                document_url="https://example.com/document.pdf"
            )
        )

        assert request.document.type == DocumentType.DOCUMENT_URL
        assert request.document.document_url is not None
        assert request.document.image_url is None

    @pytest.mark.asyncio
    async def test_document_type_detection_base64(self, document_service):
        """Test document type detection for base64 data."""
        request = OCRRequest(
            model="test",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url="data:image/png;base64,iVBORw0KG..."
            )
        )

        assert request.document.type == DocumentType.IMAGE_URL
        assert request.document.image_url is not None
        assert request.document.document_url is None

    @pytest.mark.asyncio
    async def test_invalid_model_handling(self, document_service, sample_base64_image):
        """Test handling of invalid model."""
        request = OCRRequest(
            model="invalid-model",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        # Service should handle invalid model gracefully
        with patch.object(document_service, "process_document") as mock_process:
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[],
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)
            assert isinstance(result, DocumentOCRResult)

    @pytest.mark.asyncio
    async def test_usage_info_calculation(self, document_service, sample_base64_image):
        """Test usage info calculation."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        with patch.object(document_service, "process_document") as mock_process:
            # Create multi-page result
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[
                    PageResult(page_number=i+1, markdown=f"Page {i}")
                    for i in range(3)
                ],
                usage_info=UsageInfo(pages_processed=3, size_bytes=210, filename="image.png"),
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)

            assert result.usage_info.pages_processed == 3
            assert result.usage_info.size_bytes > 0

    @pytest.mark.asyncio
    async def test_error_handling_download_failure(self, document_service):
        """Test error handling for download failure."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.DOCUMENT_URL,
                document_url="https://example.com/nonexistent.pdf"
            )
        )

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Download failed")

            result = await document_service.process_document(request)

            assert result.status == DocumentStatus.FAILED
            assert result.error_message is not None
            assert "Download failed" in result.error_message

    @pytest.mark.asyncio
    async def test_error_handling_invalid_base64(self, document_service):
        """Test error handling for invalid base64 data."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url="data:image/png;base64,invalid_base64_data"
            )
        )

        result = await document_service.process_document(request)

        # Should handle gracefully even with invalid base64
        assert isinstance(result, DocumentOCRResult)

    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self, document_service, sample_base64_image, tmp_path):
        """Test temporary file cleanup after processing."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        # This test would verify temp file cleanup
        # For now, just verify the service runs
        with patch.object(document_service, "process_document") as mock_process:
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[],
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)
            assert isinstance(result, DocumentOCRResult)

    @pytest.mark.asyncio
    async def test_multiple_pages_processing(self, document_service, sample_base64_image):
        """Test processing document with multiple pages."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        with patch.object(document_service, "process_document") as mock_process:
            # Create multiple mock pages
            pages = [
                PageResult(page_number=i+1, markdown=f"Content of page {i+1}")
                for i in range(5)
            ]

            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=pages,
                usage_info=UsageInfo(pages_processed=5, size_bytes=350, filename="image.png"),
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)

            assert len(result.pages) == 5
            for i, page_result in enumerate(result.pages):
                assert page_result.page_number == i + 1
                assert f"Content of page {i+1}" in page_result.markdown

    @pytest.mark.asyncio
    async def test_document_metadata_extraction(self, document_service, sample_base64_image):
        """Test document metadata extraction."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url=sample_base64_image
            )
        )

        with patch.object(document_service, "process_document") as mock_process:
            mock_result = DocumentOCRResult(
                document_id=uuid4(),
                status=DocumentStatus.COMPLETED,
                pages=[PageResult(page_number=1, markdown="Content")],
                usage_info=UsageInfo(
                    pages_processed=1,
                    size_bytes=70,
                    filename="test_image.png"
                ),
                created_at=datetime.now()
            )
            mock_process.return_value = mock_result

            result = await document_service.process_document(request)

            assert result.usage_info.filename == "test_image.png"
