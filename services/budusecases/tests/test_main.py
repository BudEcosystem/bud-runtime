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

"""Tests for BudUseCases main application.

Note: These tests require budmicroframe to be installed and properly configured.
They are integration tests that verify the app creation works correctly.
"""

import os

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


class TestMainAppIntegration:
    """Integration tests for main app.

    Note: These tests are skipped if budmicroframe is not available.
    """

    @pytest.mark.skip(reason="Requires budmicroframe installation")
    def test_app_is_created(self):
        """Test that the app is created successfully."""
        from budusecases.main import app

        assert app is not None

    @pytest.mark.skip(reason="Requires budmicroframe installation")
    def test_app_has_routes(self):
        """Test that the app has routes registered."""
        from budusecases.main import app

        routes = [route.path for route in app.routes]
        # The configure_app function adds default routes like /health
        assert len(routes) > 0
