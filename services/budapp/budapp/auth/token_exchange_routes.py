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

"""Token exchange routes for secure OAuth token retrieval."""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.auth.token_exchange_service import TokenExchangeService
from budapp.commons import logging
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import SingleResponse


logger = logging.get_logger(__name__)

token_exchange_router = APIRouter(prefix="/auth/token", tags=["auth"])


class TokenExchangeRequest(BaseModel):
    """Request model for token exchange."""

    exchange_token: str = Field(..., description="The temporary exchange token")


class TokenExchangeResponse(BaseModel):
    """Response model for token exchange."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: Dict = Field(..., description="User information")


@token_exchange_router.post(
    "/exchange",
    response_model=SingleResponse[TokenExchangeResponse],
    responses={
        status.HTTP_200_OK: {
            "description": "Tokens retrieved successfully",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid or expired exchange token",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Exchange token already used",
        },
    },
    description="Exchange temporary token for JWT access and refresh tokens",
)
async def exchange_token(
    request: TokenExchangeRequest,
    session: Annotated[Session, Depends(get_session)],
) -> SingleResponse[TokenExchangeResponse]:
    """Exchange a temporary token for JWT tokens.

    This endpoint provides a secure way to retrieve authentication tokens
    after OAuth callback. Instead of passing tokens in URL parameters,
    the callback only includes a temporary exchange token that must be
    exchanged for the actual JWT tokens.

    Security features:
    - Exchange tokens are single-use only
    - Exchange tokens expire after 60 seconds
    - Tokens are generated fresh on exchange (not pre-generated)
    - No sensitive data in URL parameters

    Args:
        request: Contains the exchange token
        session: Database session

    Returns:
        JWT access and refresh tokens along with user information

    Raises:
        400: Invalid or expired exchange token
        401: Exchange token already used
    """
    try:
        exchange_service = TokenExchangeService(session)

        # Exchange the temporary token for JWT tokens
        token_data = await exchange_service.exchange_token_for_jwt(request.exchange_token)

        # Create response
        response = TokenExchangeResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type=token_data["token_type"],
            expires_in=token_data["expires_in"],
            user=token_data["user"],
        )

        return SingleResponse[TokenExchangeResponse](
            success=True,
            message="Tokens retrieved successfully",
            result=response,
        )

    except ClientException as e:
        logger.warning(f"Token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error during token exchange: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to exchange token",
        )
