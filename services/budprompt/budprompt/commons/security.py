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

"""Security utilities for the budprompt service."""

import hashlib


class HashManager:
    """A class for managing various hashing operations.

    This class provides methods for hashing and verifying passwords using bcrypt,
    as well as creating SHA-256 hashes.
    """

    @staticmethod
    def create_sha_256_hash(input_string: str) -> str:
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
