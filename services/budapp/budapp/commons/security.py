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

"""Provides utility functions for managing security tasks."""

import hashlib
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.types import (
    PrivateKeyTypes,
    PublicKeyTypes,
)
from passlib.context import CryptContext

from . import logging
from .config import secrets_settings


logger = logging.get_logger(__name__)


def hash_token(token: str):
    # Hash the string using SHA-256
    hashed_token = hashlib.sha256(token.encode()).hexdigest()

    return hashed_token


class HashManager:
    """A class for managing various hashing operations.

    This class provides methods for hashing and verifying passwords using bcrypt,
    as well as creating SHA-256 hashes.

    Attributes:
        pwd_context (CryptContext): A CryptContext instance for password hashing.
    """

    def __init__(self) -> None:
        """Initialize the HashManager with a CryptContext for bcrypt."""
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def get_hash(self, plain_string: str) -> str:
        """Hash a plain string using bcrypt.

        Args:
            plain_string (str): The string to be hashed.

        Returns:
            str: The bcrypt hash of the input string.
        """
        return self.pwd_context.hash(plain_string)

    async def verify_hash(self, plain_string: str, hashed_string: str) -> bool:
        """Verify a plain string against a bcrypt hash.

        Args:
            plain_string (str): The plain string to verify.
            hashed_string (str): The bcrypt hash to verify against.

        Returns:
            bool: True if the plain string matches the hash, False otherwise.
        """
        return self.pwd_context.verify(plain_string, hashed_string)

    @staticmethod
    async def create_sha_256_hash(input_string: str) -> str:
        """Create a SHA-256 hash of the input string.

        Args:
            input_string (str): The string to be hashed.

        Returns:
            str: The hexadecimal representation of the SHA-256 hash.
        """
        # Convert the input string to bytes
        input_bytes = input_string.encode("utf-8")

        # Create a SHA-256 hash object
        sha_256_hash = hashlib.sha256(input_bytes)

        # Get the hexadecimal representation of the hash
        return sha_256_hash.hexdigest()


class RSAHandler:
    @staticmethod
    async def encrypt(message: Any, public_key: PublicKeyTypes = secrets_settings.public_key) -> str:
        encoded_message = message.encode("utf-8")
        encrypted_message = public_key.encrypt(
            encoded_message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # Convert the encrypted message to a hex string to store it in the database
        return encrypted_message.hex()

    @staticmethod
    async def decrypt(message_encrypted: Any, private_key: PrivateKeyTypes = secrets_settings.private_key) -> str:
        # Convert the encrypted message from a hex string to bytes
        message_encrypted_bytes = bytes.fromhex(message_encrypted)

        try:
            # Decrypt the encrypted message using the private key
            message_decrypted = private_key.decrypt(
                message_encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        except ValueError:
            logger.error("Could not decrypt message")

        # Convert the decrypted message to a string
        message_decrypted = message_decrypted.decode("utf-8")

        return message_decrypted


class AESHandler:
    def __init__(self, key: bytes = secrets_settings.aes_key):
        self.fernet = Fernet(key)

    async def encrypt(self, message: Any) -> str:
        """Encrypt a message using the symmetric key."""
        encoded_message = message.encode("utf-8")
        encrypted_message = self.fernet.encrypt(encoded_message)

        # Convert the encrypted message to a hex string for storage
        return encrypted_message.hex()

    async def decrypt(self, encrypted_message: str) -> str:
        """Decrypt a message using the symmetric key."""
        try:
            # Convert the encrypted message from a hex string to bytes
            encrypted_message_bytes = bytes.fromhex(encrypted_message)
            decrypted_message = self.fernet.decrypt(encrypted_message_bytes)
        except Exception as e:
            logger.error(f"Could not decrypt message: {e}")
            raise

        # Convert the decrypted message back to a string
        return decrypted_message.decode("utf-8")
