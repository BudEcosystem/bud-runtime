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

"""Middleware to validate Dapr APP_API_TOKEN for internal service-to-service endpoints."""

import os

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from . import logging


logger = logging.get_logger(__name__)


def validate_internal_request(request: Request) -> None:
    """Validate that request came from Dapr sidecar.

    Checks the dapr-api-token header against the APP_API_TOKEN env var.
    Raises 403 Forbidden if token is missing, not configured, or doesn't match.

    This ensures that internal endpoints (e.g., /internal/*) can only be accessed
    by services calling through Dapr, not directly from external sources.

    Args:
        request: The FastAPI request object.

    Raises:
        HTTPException: 403 Forbidden if validation fails.
    """
    expected_token = os.environ.get("APP_API_TOKEN")
    if not expected_token:
        # Token not configured - this is a misconfiguration, reject all requests
        logger.warning("APP_API_TOKEN not configured - rejecting internal request")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden - Internal auth not configured",
        )

    # Check both dapr-api-token (for direct Dapr calls) and x-app-api-token
    # (for calls where Dapr consumes dapr-api-token but forwards x-app-api-token)
    actual_token = request.headers.get("dapr-api-token") or request.headers.get("x-app-api-token")
    if actual_token != expected_token:
        logger.warning("Invalid dapr-api-token header - rejecting internal request")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden - Invalid internal token",
        )


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Dapr APP_API_TOKEN for /internal/ endpoints."""

    async def dispatch(self, request: Request, call_next):
        """Check token for internal endpoints before processing request."""
        # Only validate requests to /internal/ paths
        if "/internal/" in request.url.path:
            expected_token = os.environ.get("APP_API_TOKEN")
            if not expected_token:
                logger.warning("APP_API_TOKEN not configured - rejecting internal request to %s", request.url.path)
                return Response(
                    content='{"detail":"Forbidden - Internal auth not configured"}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )

            # Check both dapr-api-token and x-app-api-token (same as validate_internal_request)
            actual_token = request.headers.get("dapr-api-token") or request.headers.get("x-app-api-token")
            if actual_token != expected_token:
                logger.warning("Invalid internal token header - rejecting internal request to %s", request.url.path)
                return Response(
                    content='{"detail":"Forbidden - Invalid internal token"}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )

        return await call_next(request)
