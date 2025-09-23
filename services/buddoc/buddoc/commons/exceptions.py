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

"""Custom exceptions for the buddoc service."""


class BudDocException(Exception):
    """Base exception for buddoc service."""

    pass


class DocumentProcessingException(BudDocException):
    """Exception raised when document processing fails."""

    pass


class VLMException(BudDocException):
    """Exception raised when VLM API calls fail."""

    pass


class FileValidationException(BudDocException):
    """Exception raised when file validation fails."""

    pass


class MinioException(BudDocException):
    """Exception raised when MinIO operations fail."""

    pass


class DocumentNotFoundException(BudDocException):
    """Exception raised when a document is not found."""

    pass
