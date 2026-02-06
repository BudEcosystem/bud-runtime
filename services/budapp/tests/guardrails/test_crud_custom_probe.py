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

"""Unit tests for custom probe CRUD operations."""

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from budapp.commons.constants import GuardrailStatusEnum, ProbeTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.guardrails.crud import GuardrailsDeploymentDataManager
from budapp.guardrails.models import GuardrailProbe, GuardrailRule


class TestCreateCustomProbeWithRule:
    """Tests for create_custom_probe_with_rule method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = MagicMock()
        session.begin_nested.return_value = MagicMock(is_active=True)
        return session

    @pytest.fixture
    def data_manager(self, mock_session):
        """Create a data manager with mocked session."""
        return GuardrailsDeploymentDataManager(mock_session)

    @pytest.fixture
    def base_params(self):
        """Base parameters for creating a custom probe."""
        return {
            "name": "Test Probe",
            "description": "Test description",
            "scanner_type": "llm",
            "model_config": {"handler": "test_handler"},
            "model_uri": "openai/gpt-test",
            "model_provider_type": "openai",
            "is_gated": False,
            "user_id": uuid4(),
            "provider_id": uuid4(),
        }

    @pytest.mark.asyncio
    async def test_create_probe_with_model_id(self, data_manager, mock_session, base_params):
        """Test creating a custom probe with model_id provided."""
        model_id = uuid4()

        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=model_id,
        )

        # Verify a probe and rule were added
        assert len(added_objects) == 2

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.model_id == model_id

    @pytest.mark.asyncio
    async def test_create_probe_without_model_id(self, data_manager, mock_session, base_params):
        """Test creating a custom probe without model_id (model_id is None)."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
        )

        # Verify a probe and rule were added
        assert len(added_objects) == 2

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.model_id is None

    @pytest.mark.asyncio
    async def test_create_probe_with_guard_types(self, data_manager, mock_session, base_params):
        """Test creating a custom probe with guard_types provided."""
        guard_types = ["input", "output"]

        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
            guard_types=guard_types,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.guard_types == ["input", "output"]

    @pytest.mark.asyncio
    async def test_create_probe_without_guard_types(self, data_manager, mock_session, base_params):
        """Test creating a custom probe without guard_types (defaults to None)."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.guard_types is None

    @pytest.mark.asyncio
    async def test_create_probe_with_modality_types(self, data_manager, mock_session, base_params):
        """Test creating a custom probe with modality_types provided."""
        modality_types = ["text", "image"]

        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
            modality_types=modality_types,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.modality_types == ["text", "image"]

    @pytest.mark.asyncio
    async def test_create_probe_without_modality_types(self, data_manager, mock_session, base_params):
        """Test creating a custom probe without modality_types (defaults to None)."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.modality_types is None

    @pytest.mark.asyncio
    async def test_create_probe_with_all_new_fields(self, data_manager, mock_session, base_params):
        """Test creating a custom probe with all new optional fields."""
        model_id = uuid4()
        guard_types = ["input"]
        modality_types = ["text"]

        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=model_id,
            guard_types=guard_types,
            modality_types=modality_types,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.model_id == model_id
        assert rule.guard_types == ["input"]
        assert rule.modality_types == ["text"]

    @pytest.mark.asyncio
    async def test_create_probe_with_none_for_all_optional_fields(self, data_manager, mock_session, base_params):
        """Test creating a custom probe with explicit None for all optional fields."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
            guard_types=None,
            modality_types=None,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.model_id is None
        assert rule.guard_types is None
        assert rule.modality_types is None

    @pytest.mark.asyncio
    async def test_probe_attributes_are_set_correctly(self, data_manager, mock_session, base_params):
        """Test that probe attributes are set correctly regardless of new fields."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
            guard_types=["input"],
            modality_types=["text"],
        )

        # Find the probe object
        probe = next((obj for obj in added_objects if isinstance(obj, GuardrailProbe)), None)
        assert probe is not None
        assert probe.name == base_params["name"]
        assert probe.description == base_params["description"]
        assert probe.probe_type == ProbeTypeEnum.CUSTOM
        assert probe.status == GuardrailStatusEnum.ACTIVE

    @pytest.mark.asyncio
    async def test_rule_inherits_probe_name_and_description(self, data_manager, mock_session, base_params):
        """Test that rule inherits name and description from probe."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        assert rule.name == base_params["name"]
        assert rule.description == base_params["description"]

    @pytest.mark.asyncio
    async def test_duplicate_probe_raises_client_exception(self, data_manager, mock_session, base_params):
        """Test that creating a duplicate probe raises ClientException."""
        # Mock finding an existing probe
        mock_session.query.return_value.filter_by.return_value.first.return_value = Mock()

        with pytest.raises(ClientException) as exc_info:
            await data_manager.create_custom_probe_with_rule(
                **base_params,
                model_id=None,
            )

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_empty_guard_types_list(self, data_manager, mock_session, base_params):
        """Test creating a probe with empty guard_types list."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
            guard_types=[],
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        # Empty list should be passed through as-is
        assert rule.guard_types == []

    @pytest.mark.asyncio
    async def test_empty_modality_types_list(self, data_manager, mock_session, base_params):
        """Test creating a probe with empty modality_types list."""
        # Mock the duplicate check query
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Capture what gets added to the session
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        await data_manager.create_custom_probe_with_rule(
            **base_params,
            model_id=None,
            modality_types=[],
        )

        # Find the rule object
        rule = next((obj for obj in added_objects if isinstance(obj, GuardrailRule)), None)
        assert rule is not None
        # Empty list should be passed through as-is
        assert rule.modality_types == []
