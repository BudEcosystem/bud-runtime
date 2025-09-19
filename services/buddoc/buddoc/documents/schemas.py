#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Pydantic schemas for document processing and OCR operations."""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ResponseFormat(str, Enum):
    """Supported response formats for VLM output."""

    MARKDOWN = "markdown"
    DOCTAGS = "doctags"
    JSON = "json"
    TEXT = "text"


class VLMProvider(str, Enum):
    """Supported VLM providers."""

    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"
    OPENAI = "openai"
    MISTRAL = "mistral"
    CUSTOM = "custom"


class DocumentType(str, Enum):
    """Document input types."""

    DOCUMENT_URL = "document_url"
    IMAGE_URL = "image_url"


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VLMOptions(BaseModel):
    """Configuration options for VLM processing."""

    provider: VLMProvider = Field(default=VLMProvider.LM_STUDIO, description="VLM provider to use")
    model: Optional[str] = Field(default=None, description="Model name to use")
    api_url: Optional[str] = Field(default=None, description="Custom API URL")
    prompt: str = Field(default="Convert this document to text.", description="Prompt for VLM")
    timeout: int = Field(default=90, ge=1, le=600, description="API timeout in seconds")
    scale: float = Field(default=1.0, ge=0.1, le=2.0, description="Image scale factor")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")
    temperature: float = Field(default=0.1, ge=0, le=1, description="Model temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Maximum tokens to generate")


class DocumentInput(BaseModel):
    """Document input structure matching OpenAI/Mistral format."""

    type: DocumentType = Field(description="Type of document input")
    document_url: Optional[str] = Field(default=None, description="Document URL or base64 data URI")
    image_url: Optional[str] = Field(default=None, description="Image URL or base64 data URI")

    @model_validator(mode="after")
    def validate_document_field(self) -> "DocumentInput":
        """Ensure the correct field is provided based on type."""
        if self.type == DocumentType.DOCUMENT_URL:
            if not self.document_url:
                raise ValueError("'document_url' must be provided when type is 'document_url'")
            if self.image_url:
                self.image_url = None  # Clear image_url if document_url is used
        elif self.type == DocumentType.IMAGE_URL:
            if not self.image_url:
                raise ValueError("'image_url' must be provided when type is 'image_url'")
            if self.document_url:
                self.document_url = None  # Clear document_url if image_url is used
        return self


class OCRRequest(BaseModel):
    """Request schema for OCR endpoint matching Mistral format."""

    model: str = Field(default="docling-vlm", description="OCR model to use")
    document: DocumentInput = Field(description="Document input")
    prompt: Optional[str] = Field(default=None, description="Custom prompt for OCR")


class DocumentUploadRequest(BaseModel):
    """Legacy request schema for document upload (for backward compatibility)."""

    vlm_options: Optional[VLMOptions] = Field(default=None, description="VLM processing options")
    extract_tables: bool = Field(default=True, description="Extract tables from document")
    extract_images: bool = Field(default=False, description="Extract images from document")


class DocumentMetadata(BaseModel):
    """Metadata about the processed document."""

    filename: str = Field(description="Original filename")
    content_type: str = Field(description="MIME type of the document")
    size_bytes: int = Field(description="File size in bytes")
    page_count: Optional[int] = Field(default=None, description="Number of pages (if applicable)")
    processing_time_seconds: float = Field(description="Time taken to process")
    vlm_model_used: Optional[str] = Field(default=None, description="VLM model used for processing")


class ExtractedTable(BaseModel):
    """Schema for extracted table data."""

    page_number: Optional[int] = Field(default=None, description="Page where table was found")
    headers: List[str] = Field(default_factory=list, description="Table headers")
    rows: List[List[str]] = Field(default_factory=list, description="Table rows")
    caption: Optional[str] = Field(default=None, description="Table caption if available")


class ImageBoundingBox(BaseModel):
    """Bounding box coordinates for an image."""

    x: float = Field(description="X coordinate")
    y: float = Field(description="Y coordinate")
    width: float = Field(description="Width")
    height: float = Field(description="Height")


class ExtractedImage(BaseModel):
    """Schema for extracted image data matching Mistral format."""

    id: str = Field(description="Image identifier")
    page_number: Optional[int] = Field(default=None, description="Page where image was found")
    image_base64: Optional[str] = Field(default=None, description="Base64 encoded image")
    bbox: Optional[ImageBoundingBox] = Field(default=None, description="Bounding box coordinates")
    caption: Optional[str] = Field(default=None, description="Image caption if available")
    alt_text: Optional[str] = Field(default=None, description="Alternative text for image")


class PageDimensions(BaseModel):
    """Page dimensions information."""

    dpi: int = Field(default=72, description="Dots per inch")
    height: float = Field(description="Page height")
    width: float = Field(description="Page width")


class PageResult(BaseModel):
    """Result for a single page matching Mistral format."""

    page_number: int = Field(description="Page number")
    markdown: str = Field(description="Extracted text in markdown format")


class UsageInfo(BaseModel):
    """Usage information for the OCR processing."""

    pages_processed: int = Field(description="Number of pages processed")
    size_bytes: int = Field(description="Size of the document in bytes")
    filename: str = Field(description="Name of the processed file")


class DocumentOCRResult(BaseModel):
    """Result schema for document OCR processing matching Mistral format."""

    document_id: UUID = Field(description="Unique identifier for the processed document")
    status: DocumentStatus = Field(description="Processing status")
    pages: List[PageResult] = Field(default_factory=list, description="Processed pages")
    metadata: Optional[DocumentMetadata] = Field(default=None, description="Document metadata")
    usage_info: Optional[UsageInfo] = Field(default=None, description="Usage information")
    error_message: Optional[str] = Field(default=None, description="Error message if processing failed")
    created_at: datetime = Field(description="Timestamp of processing")

    # Legacy fields for backward compatibility
    extracted_text: Optional[str] = Field(default=None, description="Combined extracted text (deprecated)")
    extracted_tables: List[Any] = Field(
        default_factory=list, description="All extracted tables (deprecated, always empty)"
    )


class OCRResponse(BaseModel):
    """Response schema for OCR endpoint matching Mistral format."""

    document_id: UUID = Field(description="Document ID for tracking")
    model: str = Field(description="Model used for processing")
    pages: List[PageResult] = Field(description="Processed pages")
    usage_info: UsageInfo = Field(description="Usage information")


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload endpoint."""

    success: bool = Field(description="Whether the upload was successful")
    document_id: UUID = Field(description="Document ID for tracking")
    message: str = Field(description="Response message")
    result: Optional[DocumentOCRResult] = Field(default=None, description="OCR result if processing completed")


class DocumentProcessingError(BaseModel):
    """Error schema for document processing failures."""

    error_code: str = Field(description="Error code")
    error_message: str = Field(description="Detailed error message")
    document_id: Optional[UUID] = Field(default=None, description="Document ID if available")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class DocumentListRequest(BaseModel):
    """Request schema for listing documents."""

    status: Optional[DocumentStatus] = Field(default=None, description="Filter by status")
    start_date: Optional[datetime] = Field(default=None, description="Filter by start date")
    end_date: Optional[datetime] = Field(default=None, description="Filter by end date")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=10, ge=1, le=100, description="Page size")


class DocumentListResponse(BaseModel):
    """Response schema for document listing."""

    documents: List[DocumentOCRResult] = Field(description="List of documents")
    total_count: int = Field(description="Total number of documents")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Page size")
    total_pages: int = Field(description="Total number of pages")
