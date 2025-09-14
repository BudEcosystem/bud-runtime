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

"""Document processing service with VLM integration for OCR."""

import base64
import os
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

import aiofiles
import httpx
from budmicroframe.commons import logging
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmPipelineOptions
from docling.datamodel.pipeline_options_vlm_model import ApiVlmOptions
from docling.datamodel.pipeline_options_vlm_model import ResponseFormat as DoclingResponseFormat
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from fastapi import HTTPException, status

from ..commons.config import app_settings, secrets_settings
from .pipeline import DirectTextVlmPipeline
from .schemas import (
    DocumentOCRResult,
    DocumentStatus,
    DocumentType,
    OCRRequest,
    PageResult,
    ResponseFormat,
    UsageInfo,
    VLMOptions,
)


logger = logging.get_logger(__name__)


class DocumentService:
    """Service for document processing and OCR using VLM."""

    def __init__(self):
        """Initialize the document service."""
        self.converter = DocumentConverter()

    def encode_document_base64(self, file_path: str) -> str:
        """Encode a document file to base64."""
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error encoding file to base64: {e}")
            raise

    def decode_base64_document(self, base64_string: str) -> bytes:
        """Decode a base64 document string."""
        try:
            # Handle data URI format (e.g., "data:application/pdf;base64,...")
            if base64_string.startswith("data:"):
                # Extract the base64 part after the comma
                base64_string = base64_string.split(",", 1)[1]
            return base64.b64decode(base64_string)
        except Exception as e:
            logger.error(f"Error decoding base64: {e}")
            raise ValueError(f"Invalid base64 string: {e}") from e

    async def fetch_document_from_url(self, url: str) -> bytes:
        """Fetch a document from a URL."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as e:
            logger.error(f"Error fetching document from URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to fetch document from URL: {e}"
            ) from e

    async def save_document_bytes(self, document_bytes: bytes, filename: str) -> str:
        """Save document bytes to a temporary file."""
        os.makedirs(app_settings.temp_upload_dir, exist_ok=True)

        temp_file_path = os.path.join(app_settings.temp_upload_dir, f"{uuid4()}_{filename}")

        async with aiofiles.open(temp_file_path, "wb") as f:
            await f.write(document_bytes)

        return temp_file_path

    def _get_docling_response_format(self, format: ResponseFormat) -> DoclingResponseFormat:
        """Convert our ResponseFormat to Docling's ResponseFormat.

        Note: Docling only supports MARKDOWN and DOCTAGS formats.
        JSON and TEXT formats will be mapped to MARKDOWN as a structured fallback.
        """
        # Docling only supports MARKDOWN and DOCTAGS
        if format in [ResponseFormat.MARKDOWN, ResponseFormat.JSON, ResponseFormat.TEXT]:
            return DoclingResponseFormat.MARKDOWN
        elif format == ResponseFormat.DOCTAGS:
            return DoclingResponseFormat.DOCTAGS
        else:
            return DoclingResponseFormat.MARKDOWN  # Default fallback

    def _configure_vlm_options(
        self, vlm_options: Optional[VLMOptions] = None, api_token: Optional[str] = None
    ) -> ApiVlmOptions:
        """Configure VLM options for the pipeline."""
        if not vlm_options:
            # Use default configuration from settings
            options_kwargs = {
                "url": app_settings.vlm_api_url,
                "params": {"model": app_settings.vlm_model_name},
                "prompt": "Convert this document page to text, preserving all content and structure.",
                "timeout": app_settings.vlm_api_timeout,
                "scale": 1.0,
                "response_format": self._get_docling_response_format(ResponseFormat(app_settings.vlm_response_format)),
            }

            # Add authentication headers - prioritize request token over environment variable
            token = api_token or secrets_settings.vlm_api_token
            if token:
                options_kwargs["headers"] = {"Authorization": f"Bearer {token}"}
                # Log which token source is being used for debugging
                if api_token:
                    logger.debug("Using bearer token from request Authorization header")
                else:
                    logger.debug("Using bearer token from environment variable")

            return ApiVlmOptions(**options_kwargs)

        # Build custom configuration based on provided options
        api_url = vlm_options.api_url or app_settings.vlm_api_url
        model_name = vlm_options.model or app_settings.vlm_model_name

        params = {
            "model": model_name,
            "temperature": vlm_options.temperature,
        }
        if vlm_options.max_tokens:
            params["max_tokens"] = vlm_options.max_tokens

        # Build options kwargs
        options_kwargs = {
            "url": api_url,
            "params": params,
            "prompt": vlm_options.prompt,
            "timeout": vlm_options.timeout,
            "scale": vlm_options.scale,
            "response_format": self._get_docling_response_format(vlm_options.response_format),
        }

        # Add authentication headers - prioritize request token over environment variable
        token = api_token or secrets_settings.vlm_api_token
        if token:
            options_kwargs["headers"] = {"Authorization": f"Bearer {token}"}
            # Log which token source is being used for debugging
            if api_token:
                logger.debug("Using bearer token from request Authorization header")
            else:
                logger.debug("Using bearer token from environment variable")

        return ApiVlmOptions(**options_kwargs)

    async def process_document(
        self,
        request: OCRRequest,
        api_token: Optional[str] = None,
    ) -> DocumentOCRResult:
        """Process a document and perform OCR using VLM with Mistral format."""
        document_id = uuid4()
        start_time = time.time()
        temp_file_path = None
        filename = "document"
        content_type = "application/octet-stream"

        try:
            # Determine document source and get content
            document_input = request.document
            document_bytes = None
            original_url = None  # Track if we have a direct URL for VLM

            # Get the URL or data URI based on type
            if document_input.type == DocumentType.DOCUMENT_URL:
                input_value = document_input.document_url
            elif document_input.type == DocumentType.IMAGE_URL:
                input_value = document_input.image_url
            else:
                raise ValueError(f"Unsupported document type: {document_input.type}")

            if not input_value:
                raise ValueError(f"No {document_input.type} provided")

            # Detect if it's a base64 data URI or a regular URL
            if input_value.startswith("data:"):
                # It's a base64 data URI (e.g., "data:image/png;base64,...")
                try:
                    # Parse data URI
                    header, encoded = input_value.split(",", 1)
                    # Extract MIME type if present
                    if ";" in header:
                        mime_type = header.split(":")[1].split(";")[0]
                        content_type = mime_type
                        # Determine filename extension from MIME type
                        if "pdf" in mime_type:
                            filename = f"document_{document_id}.pdf"
                        elif "png" in mime_type:
                            filename = f"image_{document_id}.png"
                        elif "jpeg" in mime_type or "jpg" in mime_type:
                            filename = f"image_{document_id}.jpg"
                        else:
                            filename = f"document_{document_id}.bin"
                    # Decode base64
                    document_bytes = base64.b64decode(encoded)
                except Exception as e:
                    raise ValueError(f"Invalid base64 data URI: {e}") from e
            else:
                # It's a regular URL - we could use it directly with VLM
                original_url = input_value
                document_bytes = await self.fetch_document_from_url(input_value)
                # Extract filename from URL
                parsed_url = urlparse(input_value)
                path_parts = parsed_url.path.split("/")
                if path_parts and path_parts[-1]:
                    filename = path_parts[-1]

            # Track document size
            document_size = len(document_bytes) if document_bytes else 0

            # Save to temporary file
            temp_file_path = await self.save_document_bytes(document_bytes, filename)
            logger.info(f"Processing document: {filename} (ID: {document_id}, Size: {document_size} bytes)")

            # Configure VLM options from request
            vlm_options = VLMOptions(
                model=request.model,
                prompt=request.prompt
                or "Do OCR of the image and give this in markdown format. Don't add the markdown wrapper.",
                response_format=ResponseFormat.MARKDOWN,
            )

            # Configure pipeline options
            pipeline_options = VlmPipelineOptions(
                enable_remote_services=True  # Required for API-based VLM
            )

            # Configure VLM options with optional API token from request
            pipeline_options.vlm_options = self._configure_vlm_options(vlm_options, api_token)

            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                        pipeline_cls=DirectTextVlmPipeline,  # Use our custom pipeline
                    ),
                    InputFormat.IMAGE: ImageFormatOption(
                        pipeline_options=pipeline_options,
                        pipeline_cls=DirectTextVlmPipeline,  # Use our custom pipeline for images too
                    ),
                }
            )

            # Convert document
            result = converter.convert(temp_file_path)

            # Extract text content
            extracted_text = result.document.export_to_markdown() if result.document else ""

            # Calculate processing time
            processing_time = time.time() - start_time

            # Create pages for Mistral format
            pages = []
            if result.pages:
                for i, page in enumerate(result.pages, 1):
                    # Get page text from VLM response
                    page_text = ""
                    if (hasattr(page, "predictions") and hasattr(page.predictions, "vlm_response") and
                        page.predictions.vlm_response and page.predictions.vlm_response.text):
                        page_text = page.predictions.vlm_response.text.strip()

                    pages.append(
                        PageResult(
                            page_number=i,
                            markdown=page_text,
                        )
                    )
            else:
                # Single page fallback
                pages.append(
                    PageResult(
                        page_number=1,
                        markdown=extracted_text,
                    )
                )

            # Create usage info
            usage_info = UsageInfo(
                pages_processed=len(pages),
                size_bytes=document_size,
                filename=filename,
            )

            # Create result with both formats
            return DocumentOCRResult(
                document_id=document_id,
                status=DocumentStatus.COMPLETED,
                pages=pages,
                metadata=None,  # Removed from response
                usage_info=usage_info,
                # Legacy fields for compatibility
                extracted_text=extracted_text,
                extracted_tables=[],
                created_at=datetime.utcnow(),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")

            # Return error result
            return DocumentOCRResult(
                document_id=document_id,
                status=DocumentStatus.FAILED,
                pages=[],
                metadata=None,
                usage_info=UsageInfo(
                    pages_processed=0,
                    size_bytes=document_size if "document_size" in locals() else 0,
                    filename=filename,
                ),
                error_message=str(e),
                created_at=datetime.utcnow(),
            )
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"Error removing temporary file: {e}")
