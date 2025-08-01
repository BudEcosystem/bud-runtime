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


"""Implements token services and business logic that power the microservices, including key functionality and integrations."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

import jwt

from budapp.auth.schemas import AccessTokenData, AuthToken
from budapp.commons import logging
from budapp.commons.config import app_settings, secrets_settings
from budapp.commons.constants import JWT_ALGORITHM, TokenTypeEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.security import HashManager

from .crud import TokenDataManager
from .models import Token as TokenModel
from .schemas import RefreshTokenData, TokenCreate


logger = logging.get_logger(__name__)


class TokenService(SessionMixin):
    async def create_auth_token(self, auth_id: str) -> AuthToken:
        """Create an authentication token for a given auth ID.

        This method generates both an access token and a refresh token
        for the provided auth ID and returns them wrapped in an AuthToken object.

        Args:
            auth_id (str): The unique identifier for the authentication entity.

        Returns:
            AuthToken: An object containing the access token, refresh token,
                and token type.

        Raises:
            ValueError: If the auth_id is empty or invalid.
            TokenCreationError: If there's an error during token creation.
        """
        # Create and return the Token instance
        auth_token = AuthToken(
            access_token=await self._create_access_token(auth_id),
            refresh_token=await self._create_refresh_token(auth_id),
            token_type="Bearer",
        )

        return auth_token

    async def _create_access_token(self, auth_id: str) -> str:
        """Create an access token for the given auth ID.

        This method generates an access token using the provided auth ID. The token
        includes the auth ID as the subject and has an expiration time set according
        to the application settings.

        Args:
            auth_id (str): The unique identifier for the authentication entity.

        Returns:
            str: A JWT access token as a string.

        Raises:
            ValueError: If the auth_id is empty or invalid.
            JWTError: If there's an error during JWT token creation.
        """
        access_token_data = AccessTokenData(sub=auth_id)

        # Generate access token
        access_token = await self._create_jwt_token(
            access_token_data.model_dump(),
            expires_delta=timedelta(minutes=app_settings.access_token_expire_minutes),
        )
        logger.debug("Access token generated")

        return access_token

    async def _create_refresh_token(self, auth_id: str) -> str:
        """Create a refresh token for the given auth ID and stores its information in the database.

        This method generates a refresh token using the provided auth ID and a dynamically
        generated secret key. The token is then stored in the database along with its hash
        and other relevant information.

        Args:
            auth_id (str): The unique identifier for the authentication entity.

        Returns:
            str: A JWT refresh token as a string.

        Raises:
            ValueError: If the auth_id is empty or invalid.
            JWTError: If there's an error during JWT token creation.
            DatabaseError: If there's an error storing the token information in the database.
        """
        # Generate a dynamic secret key for the refresh token
        dynamic_secret_key = uuid4().hex
        refresh_token_data = RefreshTokenData(sub=auth_id, secret_key=dynamic_secret_key)

        refresh_token = await self._create_jwt_token(
            refresh_token_data.model_dump(),
            expires_delta=timedelta(minutes=app_settings.refresh_token_expire_minutes),
        )
        logger.debug("Refresh token generated")

        # Store refresh token info in the database
        token_data = TokenCreate(
            auth_id=UUID(auth_id),
            secret_key=await HashManager().get_hash(refresh_token_data.secret_key),
            token_hash=await HashManager().create_sha_256_hash(refresh_token),
            type=TokenTypeEnum.REFRESH.value,
        )

        token_model = TokenModel(**token_data.model_dump())

        _ = await TokenDataManager(self.session).insert_one(token_model)
        logger.debug("Refresh token info stored in the database")

        return refresh_token

    async def _create_jwt_token(self, data: Dict[str, Any], expires_delta: timedelta | None = None) -> str:
        """Create a JWT token with the given data and expiration time.

        This method generates a JWT token using the provided data and expiration time.
        If no expiration time is provided, it defaults to 15 minutes from the current time.

        Args:
            data (Dict[str, Any]): A dictionary containing the data to be encoded in the token.
            expires_delta (timedelta | None, optional): The time delta for token expiration.
                If None, defaults to 15 minutes. Defaults to None.

        Returns:
            str: A JWT token as a string.

        Raises:
            JWTError: If there's an error during JWT token creation.
        """
        # Make a copy of the data to encode
        to_encode = data.copy()

        # Default token expiration time if expires_delta is not provided
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)

        to_encode.update({"exp": expire})

        # Encode and return the token
        encoded_jwt = jwt.encode(to_encode, secrets_settings.jwt_secret_key, algorithm=JWT_ALGORITHM)

        return encoded_jwt
