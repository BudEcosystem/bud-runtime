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

"""Tests for ingest routes and ChannelManager filter extraction."""

import pytest

from notify.realtime.channel_manager import ChannelManager


class TestExtractFilters:
    """Tests for _extract_filters function in ChannelManager.

    Note: _extract_filters only checks bud.* prefixed attributes in
    span_attributes (TraceItem-compatible schema).
    """

    def test_extract_all_filter_fields(self) -> None:
        """Test extracting all filter fields from bud-prefixed span_attributes."""
        manager = ChannelManager()
        span = {
            "trace_id": "abc123",
            "span_attributes": {
                "bud.project_id": "project-123",
                "bud.endpoint_id": "endpoint-456",
                "bud.prompt_id": "prompt-789",
            },
        }

        filters = manager._extract_filters(span)

        assert filters["project_id"] == "project-123"
        assert filters["endpoint_id"] == "endpoint-456"
        assert filters["prompt_id"] == "prompt-789"

    def test_extract_project_id_only(self) -> None:
        """Test extracting only project_id."""
        manager = ChannelManager()
        span = {
            "trace_id": "abc123",
            "span_attributes": {"bud.project_id": "project-123"},
        }

        filters = manager._extract_filters(span)

        assert filters == {"project_id": "project-123"}

    def test_extract_prompt_id_only(self) -> None:
        """Test extracting only prompt_id."""
        manager = ChannelManager()
        span = {
            "trace_id": "abc123",
            "span_attributes": {"bud.prompt_id": "prompt-abc"},
        }

        filters = manager._extract_filters(span)

        assert filters == {"prompt_id": "prompt-abc"}

    def test_extract_empty_when_no_bud_attributes(self) -> None:
        """Test that empty dict is returned when no bud.* attributes exist."""
        manager = ChannelManager()
        span = {
            "trace_id": "abc123",
            "span_id": "def456",
            "other_field": "value",
            "span_attributes": {"some.other.attr": "value"},
        }

        filters = manager._extract_filters(span)

        assert filters == {}

    def test_extract_empty_when_no_span_attributes(self) -> None:
        """Test that empty dict is returned when span_attributes is missing."""
        manager = ChannelManager()
        span = {"trace_id": "abc123", "span_id": "def456"}

        filters = manager._extract_filters(span)

        assert filters == {}

    def test_converts_to_string(self) -> None:
        """Test that filter values are converted to strings."""
        manager = ChannelManager()
        span = {
            "trace_id": "abc123",
            "span_attributes": {
                "bud.project_id": 123,
                "bud.endpoint_id": 456,
            },
        }

        filters = manager._extract_filters(span)

        assert filters["project_id"] == "123"
        assert filters["endpoint_id"] == "456"

    def test_ignores_non_bud_prefixed_attributes(self) -> None:
        """Test that non bud.* prefixed attributes are ignored."""
        manager = ChannelManager()
        span = {
            "trace_id": "abc123",
            "span_attributes": {
                "project_id": "should-be-ignored",
                "endpoint_id": "should-be-ignored",
                "bud.project_id": "correct-project",
            },
        }

        filters = manager._extract_filters(span)

        assert filters == {"project_id": "correct-project"}
        assert "endpoint_id" not in filters
