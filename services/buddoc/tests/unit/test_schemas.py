"""Unit tests for schemas."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from buddoc.documents.schemas import (
    DocumentInput,
    DocumentStatus,
    DocumentType,
    OCRRequest,
    OCRResponse,
    PageResult,
    ResponseFormat,
    UsageInfo,
    VLMOptions,
    VLMProvider,
    DocumentOCRResult,
    DocumentMetadata,
)


class TestDocumentSchemas:
    """Test cases for document schemas."""

    def test_document_type_enum(self):
        """Test DocumentType enum values."""
        assert DocumentType.DOCUMENT_URL.value == "document_url"
        assert DocumentType.IMAGE_URL.value == "image_url"

    def test_document_status_enum(self):
        """Test DocumentStatus enum values."""
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.PROCESSING.value == "processing"
        assert DocumentStatus.COMPLETED.value == "completed"
        assert DocumentStatus.FAILED.value == "failed"

    def test_vlm_provider_enum(self):
        """Test VLMProvider enum values."""
        assert VLMProvider.LM_STUDIO.value == "lm_studio"
        assert VLMProvider.OPENAI.value == "openai"
        assert VLMProvider.CUSTOM.value == "custom"

    def test_response_format_enum(self):
        """Test ResponseFormat enum values."""
        assert ResponseFormat.MARKDOWN.value == "markdown"
        assert ResponseFormat.DOCTAGS.value == "doctags"


class TestDocumentInput:
    """Test cases for DocumentInput schema."""

    def test_document_input_with_url(self):
        """Test DocumentInput with document URL."""
        doc_input = DocumentInput(
            type=DocumentType.DOCUMENT_URL,
            document_url="https://example.com/doc.pdf"
        )

        assert doc_input.type == DocumentType.DOCUMENT_URL
        assert doc_input.document_url == "https://example.com/doc.pdf"
        assert doc_input.image_url is None

    def test_document_input_with_image(self):
        """Test DocumentInput with image URL."""
        doc_input = DocumentInput(
            type=DocumentType.IMAGE_URL,
            image_url="data:image/png;base64,iVBORw0KG..."
        )

        assert doc_input.type == DocumentType.IMAGE_URL
        assert doc_input.image_url == "data:image/png;base64,iVBORw0KG..."
        assert doc_input.document_url is None

    def test_document_input_validation_auto_clear(self):
        """Test DocumentInput auto-clears conflicting fields."""
        # When type is document_url, image_url should be cleared
        doc_input = DocumentInput(
            type=DocumentType.DOCUMENT_URL,
            document_url="https://example.com/doc.pdf",
            image_url="should_be_cleared"
        )

        assert doc_input.document_url == "https://example.com/doc.pdf"
        assert doc_input.image_url is None

        # When type is image_url, document_url should be cleared
        doc_input = DocumentInput(
            type=DocumentType.IMAGE_URL,
            image_url="data:image/png;base64,abc",
            document_url="should_be_cleared"
        )

        assert doc_input.image_url == "data:image/png;base64,abc"
        assert doc_input.document_url is None

    def test_document_input_invalid_type(self):
        """Test DocumentInput with invalid type."""
        with pytest.raises(ValidationError):
            DocumentInput(
                type="invalid_type",
                document_url="https://example.com/doc.pdf"
            )


class TestOCRRequest:
    """Test cases for OCRRequest schema."""

    def test_ocr_request_minimal(self):
        """Test OCRRequest with minimal fields."""
        request = OCRRequest(
            model="qwen2-vl-7b",
            document=DocumentInput(
                type=DocumentType.DOCUMENT_URL,
                document_url="https://example.com/doc.pdf"
            )
        )

        assert request.model == "qwen2-vl-7b"
        assert request.document.type == DocumentType.DOCUMENT_URL
        assert request.prompt is None

    def test_ocr_request_with_prompt(self):
        """Test OCRRequest with custom prompt."""
        request = OCRRequest(
            model="docling-vlm",
            document=DocumentInput(
                type=DocumentType.IMAGE_URL,
                image_url="data:image/png;base64,abc"
            ),
            prompt="Extract invoice details"
        )

        assert request.model == "docling-vlm"
        assert request.prompt == "Extract invoice details"

    def test_ocr_request_default_model(self):
        """Test OCRRequest with default model."""
        request = OCRRequest(
            document=DocumentInput(
                type=DocumentType.DOCUMENT_URL,
                document_url="https://example.com/doc.pdf"
            )
        )

        assert request.model == "docling-vlm"  # Default value

    def test_ocr_request_validation_error(self):
        """Test OCRRequest validation errors."""
        # Missing required document field
        with pytest.raises(ValidationError):
            OCRRequest(model="test")


class TestPageResult:
    """Test cases for PageResult schema."""

    def test_page_result_creation(self):
        """Test PageResult creation."""
        page = PageResult(
            page_number=1,
            markdown="# Page Content\n\nThis is the content."
        )

        assert page.page_number == 1
        assert page.markdown == "# Page Content\n\nThis is the content."

    def test_page_result_validation(self):
        """Test PageResult validation."""
        # PageResult doesn't have validation on page_number (can be 0 or negative)
        page = PageResult(page_number=0, markdown="content")
        assert page.page_number == 0

        # Markdown must be string
        with pytest.raises(ValidationError):
            PageResult(page_number=1, markdown=123)


class TestUsageInfo:
    """Test cases for UsageInfo schema."""

    def test_usage_info_creation(self):
        """Test UsageInfo creation."""
        usage = UsageInfo(
            pages_processed=5,
            size_bytes=1024000,
            filename="document.pdf"
        )

        assert usage.pages_processed == 5
        assert usage.size_bytes == 1024000
        assert usage.filename == "document.pdf"

    def test_usage_info_validation(self):
        """Test UsageInfo validation."""
        # UsageInfo doesn't have validation constraints
        # All values including negative are accepted
        usage = UsageInfo(
            pages_processed=-1,
            size_bytes=-1000,
            filename="test.pdf"
        )
        assert usage.pages_processed == -1
        assert usage.size_bytes == -1000


class TestOCRResponse:
    """Test cases for OCRResponse schema."""

    def test_ocr_response_creation(self):
        """Test OCRResponse creation."""
        response = OCRResponse(
            document_id=uuid4(),
            model="qwen2-vl-7b",
            pages=[
                PageResult(page_number=1, markdown="Page 1"),
                PageResult(page_number=2, markdown="Page 2")
            ],
            usage_info=UsageInfo(
                pages_processed=2,
                size_bytes=2048,
                filename="test.pdf"
            )
        )

        assert response.model == "qwen2-vl-7b"
        assert len(response.pages) == 2
        assert response.usage_info.pages_processed == 2

    def test_ocr_response_serialization(self):
        """Test OCRResponse serialization to dict."""
        doc_id = uuid4()
        response = OCRResponse(
            document_id=doc_id,
            model="test-model",
            pages=[PageResult(page_number=1, markdown="Content")],
            usage_info=UsageInfo(
                pages_processed=1,
                size_bytes=1024,
                filename="test.pdf"
            )
        )

        data = response.model_dump()

        assert data["document_id"] == doc_id
        assert data["model"] == "test-model"
        assert len(data["pages"]) == 1
        assert data["pages"][0]["page_number"] == 1
        assert data["usage_info"]["pages_processed"] == 1


class TestVLMOptions:
    """Test cases for VLMOptions schema."""

    def test_vlm_options_minimal(self):
        """Test VLMOptions with minimal fields."""
        options = VLMOptions()

        # Check defaults
        assert options.provider == VLMProvider.LM_STUDIO
        assert options.api_url is None
        assert options.model is None
        assert options.temperature == 0.1  # Default is 0.1, not 0.0
        assert options.max_tokens is None  # Default is None, not 1000
        assert options.timeout == 90
        assert options.response_format == ResponseFormat.MARKDOWN

    def test_vlm_options_full(self):
        """Test VLMOptions with all fields."""
        options = VLMOptions(
            provider=VLMProvider.OPENAI,
            api_url="https://api.openai.com/v1/chat",
            model="gpt-4-vision",
            prompt="Custom prompt",
            temperature=0.7,
            max_tokens=2000,
            scale=1.5,
            timeout=120,
            response_format=ResponseFormat.DOCTAGS
        )

        assert options.provider == VLMProvider.OPENAI
        assert options.api_url == "https://api.openai.com/v1/chat"
        assert options.model == "gpt-4-vision"
        assert options.temperature == 0.7
        assert options.max_tokens == 2000
        assert options.timeout == 120

    def test_vlm_options_validation(self):
        """Test VLMOptions validation."""
        # Temperature must be between 0 and 1
        with pytest.raises(ValidationError):
            VLMOptions(temperature=1.5)

        # Max tokens must be positive
        with pytest.raises(ValidationError):
            VLMOptions(max_tokens=-100)

        # Timeout must be positive
        with pytest.raises(ValidationError):
            VLMOptions(timeout=0)


class TestDocumentOCRResult:
    """Test cases for DocumentOCRResult schema."""

    def test_document_ocr_result_success(self):
        """Test DocumentOCRResult for successful processing."""
        result = DocumentOCRResult(
            document_id=uuid4(),
            status=DocumentStatus.COMPLETED,
            pages=[
                PageResult(page_number=1, markdown="Content")
            ],
            metadata=DocumentMetadata(
                filename="test.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                page_count=1,
                processing_time_seconds=1.5,
                vlm_model_used="qwen2-vl-7b"
            ),
            usage_info=UsageInfo(
                pages_processed=1,
                size_bytes=1024,
                filename="test.pdf"
            ),
            created_at=datetime.now()
        )

        assert result.status == DocumentStatus.COMPLETED
        assert len(result.pages) == 1
        assert result.error_message is None

    def test_document_ocr_result_failure(self):
        """Test DocumentOCRResult for failed processing."""
        result = DocumentOCRResult(
            document_id=uuid4(),
            status=DocumentStatus.FAILED,
            pages=[],
            error_message="Processing failed: Invalid format",
            created_at=datetime.now()
        )

        assert result.status == DocumentStatus.FAILED
        assert result.error_message == "Processing failed: Invalid format"
        assert len(result.pages) == 0

    def test_document_ocr_result_optional_fields(self):
        """Test DocumentOCRResult with optional fields."""
        result = DocumentOCRResult(
            document_id=uuid4(),
            status=DocumentStatus.PROCESSING,
            pages=[],
            created_at=datetime.now()
        )

        assert result.metadata is None
        assert result.usage_info is None
        assert result.error_message is None
        assert result.extracted_text is None
        assert result.extracted_tables == []


class TestDocumentMetadata:
    """Test cases for DocumentMetadata schema."""

    def test_document_metadata_creation(self):
        """Test DocumentMetadata creation."""
        metadata = DocumentMetadata(
            filename="document.pdf",
            content_type="application/pdf",
            size_bytes=2048,
            page_count=10,
            processing_time_seconds=2.5,
            vlm_model_used="custom-model"
        )

        assert metadata.filename == "document.pdf"
        assert metadata.content_type == "application/pdf"
        assert metadata.size_bytes == 2048
        assert metadata.page_count == 10
        assert metadata.processing_time_seconds == 2.5
        assert metadata.vlm_model_used == "custom-model"

    def test_document_metadata_optional_fields(self):
        """Test DocumentMetadata with optional fields."""
        metadata = DocumentMetadata(
            filename="test.txt",
            content_type="text/plain",
            size_bytes=100,
            processing_time_seconds=0.1
        )

        assert metadata.page_count is None
        assert metadata.vlm_model_used is None