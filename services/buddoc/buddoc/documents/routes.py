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

"""API routes for document processing and OCR operations."""

from typing import Any, Dict, Optional

from budmicroframe.commons import logging
from fastapi import APIRouter, Header, HTTPException, status

from ..commons.config import app_settings
from .schemas import (
    DocumentStatus,
    OCRRequest,
    OCRResponse,
    UsageInfo,
)
from .services import DocumentService


logger = logging.get_logger(__name__)

document_router = APIRouter(prefix="/documents", tags=["Documents"])

# Initialize document service
document_service = DocumentService()


@document_router.post(
    "/ocr",
    response_model=OCRResponse,
    summary="Process document with OCR (Mistral format)",
    description="Process a document for OCR using base64 or URL input matching Mistral AI format",
)
async def process_document_ocr(
    request: OCRRequest,
    authorization: Optional[str] = Header(None, description="Bearer token for VLM API authentication"),
) -> OCRResponse:
    """Process a document with OCR using Mistral-style API format.

    This endpoint accepts documents as base64 encoded strings or URLs,
    similar to Mistral AI's OCR API format.

    Args:
        request: OCR request with document input and processing options

    Returns:
        OCRResponse with page-level results

    Examples:
        Image with base64 data URI:
        ```json
        {
            "model": "qwen2-vl-7b",
            "document": {
                "type": "image_url",
                "image_url": "data:image/png;base64,iVBORw0KG..."
            }
        }
        ```

        Image with URL:
        ```json
        {
            "model": "qwen2-vl-7b",
            "document": {
                "type": "image_url",
                "image_url": "https://example.com/image.png"
            }
        }
        ```

        Document with URL:
        ```json
        {
            "model": "qwen2-vl-7b",
            "document": {
                "type": "document_url",
                "document_url": "https://example.com/document.pdf"
            }
        }
        ```
    """
    try:
        # Extract bearer token from Authorization header if provided
        api_token = None
        if authorization and authorization.startswith("Bearer "):
            api_token = authorization[7:]  # Remove "Bearer " prefix

        # Process the document with optional token
        result = await document_service.process_document(request, api_token=api_token)

        # Check if processing failed - raise proper HTTP exception
        if result.status == DocumentStatus.FAILED:
            error_msg = result.error_message or "Document processing failed"
            logger.error(f"OCR processing failed: {error_msg}")
            # Return proper error status code instead of HTTP 200
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document processing failed: {error_msg}",
            )

        # Return OCR response in Mistral format
        return OCRResponse(
            document_id=result.document_id,
            model=request.model,
            pages=result.pages,
            usage_info=result.usage_info
            or UsageInfo(pages_processed=len(result.pages), size_bytes=0, filename="unknown"),
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}",
        ) from e


@document_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the document processing service is healthy",
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for the document processing service."""
    return {
        "status": "healthy",
        "service": "buddoc",
        "version": app_settings.version,
    }
