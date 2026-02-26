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

"""Pytest configuration and fixtures for BudUseCases tests."""

import os
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

# Set test environment variables before importing modules
os.environ.setdefault("PSQL_HOST", "localhost")
os.environ.setdefault("PSQL_PORT", "5432")
os.environ.setdefault("PSQL_USER", "test")
os.environ.setdefault("PSQL_PASSWORD", "test")
os.environ.setdefault("PSQL_DB_NAME", "test")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("APP_NAME", "budusecases")
os.environ.setdefault("NAMESPACE", "test")
os.environ.setdefault("APP_PORT", "9084")
os.environ.setdefault("DAPR_HTTP_PORT", "3512")
os.environ.setdefault("DAPR_GRPC_PORT", "50012")


@pytest.fixture
def mock_session() -> Generator[MagicMock, None, None]:
    """Create a mock database session."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=None)
    yield mock


@pytest.fixture
def mock_dapr_client() -> Generator[MagicMock, None, None]:
    """Create a mock Dapr client."""
    mock = MagicMock()
    yield mock
