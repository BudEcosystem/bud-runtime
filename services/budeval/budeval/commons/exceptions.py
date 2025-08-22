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

"""The exceptions used in the budconnect module."""


class BaseException(Exception):
    """Base exception class for BudConnect."""

    def __init__(self, message: str) -> None:
        """Initialize the base exception.

        Args:
            message: Error message
        """
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the exception.

        Returns:
            Formatted error message with exception class name
        """
        return f"{self.__class__.__name__}: {self.message}"


class SeederException(BaseException):
    """Exception raised for errors in the seeder."""

    pass
