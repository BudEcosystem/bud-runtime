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

"""Defines authentication routes for the microservices, providing endpoints for user authentication."""

from typing import Union

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import UserTypeEnum
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.rate_limiter import rate_limit
from budapp.commons.schemas import ErrorResponse

from .schemas import (
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserCreate,
    UserLogin,
    UserLoginResponse,
    UserRegisterResponse,
)
from .services import AuthService


logger = logging.get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/register",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": UserRegisterResponse,
            "description": "Successfully registered user",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ErrorResponse,
            "description": "Too many registration attempts",
        },
    },
    description="Register a user with email and password",
)
@rate_limit(max_requests=3, window_seconds=10 * 60)  # 3 requests per 10 minutes
async def register_user(
    request: Request, user: UserCreate, session: Annotated[Session, Depends(get_session)]
) -> Union[UserRegisterResponse, ErrorResponse]:
    """Register a user with email and password."""
    try:
        # Force user_type to CLIENT for public registration to prevent privilege escalation
        user.user_type = UserTypeEnum.CLIENT
        await AuthService(session).register_user(user)
        return UserRegisterResponse(
            code=status.HTTP_200_OK,
            message="User registered successfully",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"ClientException: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Something went wrong"
        ).to_http_response()


@auth_router.post(
    "/login",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": UserLoginResponse,
            "description": "Successfully logged in user",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ErrorResponse,
            "description": "Too many login attempts",
        },
    },
    description="Login a user with email and password",
)
@rate_limit(max_requests=10, window_seconds=60)  # 10 requests per minute
async def login_user(
    request: Request, user: UserLogin, session: Annotated[Session, Depends(get_session)]
) -> Union[UserLoginResponse, ErrorResponse]:
    """Login a user with email and password."""
    try:
        auth_token = await AuthService(session).login_user(user)
        return UserLoginResponse(
            code=status.HTTP_200_OK,
            message="User logged in successfully",
            token=auth_token.token,
            first_login=auth_token.first_login,
            is_reset_password=auth_token.is_reset_password,
            object="auth_token",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"ClientException: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Something went wrong"
        ).to_http_response()


@auth_router.post(
    "/logout",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": LogoutResponse,
            "description": "Successfully logged out user",
        },
    },
    description="Logout a user by invalidating their refresh token",
)
async def logout_user(
    logout_data: LogoutRequest, session: Annotated[Session, Depends(get_session)]
) -> Union[LogoutResponse, None]:
    """Logout a user by invalidating their refresh token."""
    try:
        await AuthService(session).logout_user(logout_data)
        return LogoutResponse(code=status.HTTP_200_OK, message="User logged out successfully").to_http_response()
    except ClientException as e:
        logger.error(f"ClientException: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Something went wrong"
        ).to_http_response()


# refresh token
@auth_router.post(
    "/refresh-token",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Token Expired or Invalid",
        },
        status.HTTP_200_OK: {
            "model": RefreshTokenResponse,
            "description": "Successfully refreshed user's access token",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ErrorResponse,
            "description": "Too many token refresh attempts",
        },
    },
    description="Refresh a user's access token using their refresh token",
)
@rate_limit(max_requests=20, window_seconds=60, use_user_id=True)  # 20 requests per minute per user
async def refresh_token(
    request: Request, token: RefreshTokenRequest, session: Annotated[Session, Depends(get_session)]
) -> Union[RefreshTokenResponse, ErrorResponse]:
    """Refresh a user's access token using their refresh token."""
    try:
        auth_token_response = await AuthService(session).refresh_token(token)
        return auth_token_response.to_http_response()
    except ClientException as e:
        logger.error(f"ClientException: {e}")
        return ErrorResponse(code=status.HTTP_401_UNAUTHORIZED, message="Token Expired or Invalid").to_http_response()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        return ErrorResponse(code=status.HTTP_401_UNAUTHORIZED, message="Token Expired or Invalid").to_http_response()
