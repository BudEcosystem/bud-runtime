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

"""Tests for ChannelManager with Socket.IO session IDs.

Note: Batching is handled by OTEL Collector (2s window), so
ChannelManager is stateless - no buffering or flush loops.
"""

import pytest

from notify.realtime.channel_manager import ChannelManager
from notify.realtime.schemas import Channel, Subscription


@pytest.fixture
def manager() -> ChannelManager:
    """Create a ChannelManager instance for testing."""
    return ChannelManager()


@pytest.fixture
def sid() -> str:
    """Create a session ID for testing."""
    return "test-session-123"


class TestChannelManagerBasics:
    """Tests for basic ChannelManager functionality."""

    def test_init(self) -> None:
        """Test ChannelManager initialization."""
        manager = ChannelManager()
        assert manager.client_count == 0


class TestClientManagement:
    """Tests for client registration and removal."""

    def test_add_client(self, manager: ChannelManager, sid: str) -> None:
        """Test adding a client."""
        manager.add_client(sid, "user-123")

        assert manager.client_count == 1
        assert sid in manager._clients
        assert manager._clients[sid].user_id == "user-123"

    def test_remove_client(self, manager: ChannelManager, sid: str) -> None:
        """Test removing a client."""
        manager.add_client(sid, "user-123")
        manager.remove_client(sid)

        assert manager.client_count == 0
        assert sid not in manager._clients

    def test_remove_nonexistent_client(self, manager: ChannelManager, sid: str) -> None:
        """Test removing a client that doesn't exist (should not raise)."""
        manager.remove_client(sid)
        assert manager.client_count == 0


class TestSubscriptionManagement:
    """Tests for subscription handling."""

    def test_subscribe(self, manager: ChannelManager, sid: str) -> None:
        """Test subscribing a client to a channel."""
        manager.add_client(sid, "user-123")

        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        result = manager.subscribe(sid, sub)

        assert result is True
        assert manager.has_subscribers(Channel.OBSERVABILITY)
        assert manager.get_subscriber_count(Channel.OBSERVABILITY) == 1

    def test_subscribe_unregistered_client(self, manager: ChannelManager, sid: str) -> None:
        """Test subscribing an unregistered client (should fail)."""
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={})
        result = manager.subscribe(sid, sub)

        assert result is False
        assert not manager.has_subscribers(Channel.OBSERVABILITY)

    def test_unsubscribe(self, manager: ChannelManager, sid: str) -> None:
        """Test unsubscribing from a channel."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        result = manager.unsubscribe(sid, sub)

        assert result is True
        assert not manager.has_subscribers(Channel.OBSERVABILITY)

    def test_unsubscribe_unregistered_client(self, manager: ChannelManager, sid: str) -> None:
        """Test unsubscribing an unregistered client (should fail)."""
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={})
        result = manager.unsubscribe(sid, sub)

        assert result is False

    def test_multiple_subscriptions(self, manager: ChannelManager) -> None:
        """Test multiple clients with different subscriptions."""
        sid1 = "session-1"
        sid2 = "session-2"

        manager.add_client(sid1, "user-1")
        manager.add_client(sid2, "user-2")

        sub1 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub2 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "456"})

        manager.subscribe(sid1, sub1)
        manager.subscribe(sid2, sub2)

        assert manager.get_subscriber_count(Channel.OBSERVABILITY) == 2

    def test_remove_client_cleans_subscriptions(self, manager: ChannelManager, sid: str) -> None:
        """Test that removing a client cleans up its subscriptions."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        assert manager.has_subscribers(Channel.OBSERVABILITY)

        manager.remove_client(sid)

        assert not manager.has_subscribers(Channel.OBSERVABILITY)


class TestGroupBySubscription:
    """Tests for group_by_subscription method."""

    def test_group_no_subscribers(self, manager: ChannelManager) -> None:
        """Test grouping when no subscribers (should return empty)."""
        spans = [{"trace_id": "123", "span_attributes": {"bud.project_id": "abc"}}]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert result == {}

    def test_group_with_matching_subscriber(self, manager: ChannelManager, sid: str) -> None:
        """Test grouping with a matching subscriber."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        spans = [{"trace_id": "abc", "span_attributes": {"bud.project_id": "123"}}]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 1
        assert "observability:project_id=123" in result
        assert len(result["observability:project_id=123"]) == 1

    def test_group_no_match(self, manager: ChannelManager, sid: str) -> None:
        """Test grouping with non-matching filter."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        spans = [{"trace_id": "abc", "span_attributes": {"bud.project_id": "456"}}]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert result == {}

    def test_group_empty_subscription_filter_matches_all(self, manager: ChannelManager, sid: str) -> None:
        """Test that empty subscription filter matches all events."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={})
        manager.subscribe(sid, sub)

        spans = [
            {
                "trace_id": "abc",
                "span_attributes": {"bud.project_id": "123", "bud.endpoint_id": "456"},
            }
        ]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 1
        assert "observability" in result
        assert len(result["observability"]) == 1

    def test_group_multiple_spans_to_same_room(self, manager: ChannelManager, sid: str) -> None:
        """Test grouping multiple spans to the same subscription room."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        spans = [
            {"trace_id": "span1", "span_attributes": {"bud.project_id": "123"}},
            {"trace_id": "span2", "span_attributes": {"bud.project_id": "123"}},
            {"trace_id": "span3", "span_attributes": {"bud.project_id": "123"}},
        ]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 1
        assert len(result["observability:project_id=123"]) == 3

    def test_group_spans_to_different_rooms(self, manager: ChannelManager) -> None:
        """Test grouping spans to different subscription rooms."""
        sid1 = "session-1"
        sid2 = "session-2"

        manager.add_client(sid1, "user-1")
        manager.add_client(sid2, "user-2")

        sub1 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub2 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "456"})

        manager.subscribe(sid1, sub1)
        manager.subscribe(sid2, sub2)

        spans = [
            {"trace_id": "span1", "span_attributes": {"bud.project_id": "123"}},
            {"trace_id": "span2", "span_attributes": {"bud.project_id": "456"}},
        ]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 2
        assert "observability:project_id=123" in result
        assert "observability:project_id=456" in result
        assert len(result["observability:project_id=123"]) == 1
        assert len(result["observability:project_id=456"]) == 1

    def test_group_span_matches_multiple_subscriptions(self, manager: ChannelManager) -> None:
        """Test that a span can match multiple subscriptions."""
        sid1 = "session-1"
        sid2 = "session-2"

        manager.add_client(sid1, "user-1")
        manager.add_client(sid2, "user-2")

        sub1 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub2 = Subscription(channel=Channel.OBSERVABILITY, filters={})

        manager.subscribe(sid1, sub1)
        manager.subscribe(sid2, sub2)

        spans = [{"trace_id": "span1", "span_attributes": {"bud.project_id": "123"}}]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 2
        assert "observability:project_id=123" in result
        assert "observability" in result

    def test_group_extracts_bud_prefixed_span_attributes(self, manager: ChannelManager, sid: str) -> None:
        """Test that bud-prefixed span_attributes are extracted as filters."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        spans = [
            {
                "trace_id": "abc",
                "span_attributes": {"bud.project_id": "123"},
            }
        ]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 1
        assert "observability:project_id=123" in result

    def test_group_with_prompt_id_filter(self, manager: ChannelManager, sid: str) -> None:
        """Test grouping with prompt_id filter."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"prompt_id": "prompt-abc"})
        manager.subscribe(sid, sub)

        spans = [{"trace_id": "abc", "span_attributes": {"bud.prompt_id": "prompt-abc"}}]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 1
        assert "observability:prompt_id=prompt-abc" in result

    def test_group_with_all_three_filters(self, manager: ChannelManager, sid: str) -> None:
        """Test grouping with project_id, endpoint_id, and prompt_id."""
        manager.add_client(sid, "user-123")
        sub = Subscription(
            channel=Channel.OBSERVABILITY,
            filters={"project_id": "proj", "endpoint_id": "ep", "prompt_id": "pr"},
        )
        manager.subscribe(sid, sub)

        spans = [
            {
                "trace_id": "abc",
                "span_attributes": {
                    "bud.project_id": "proj",
                    "bud.endpoint_id": "ep",
                    "bud.prompt_id": "pr",
                },
            }
        ]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert len(result) == 1
        # Room name has sorted filter keys
        assert "observability:endpoint_id=ep,project_id=proj,prompt_id=pr" in result

    def test_group_prompt_id_filter_no_match(self, manager: ChannelManager, sid: str) -> None:
        """Test that prompt_id filter rejects non-matching spans."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"prompt_id": "prompt-abc"})
        manager.subscribe(sid, sub)

        spans = [{"trace_id": "abc", "span_attributes": {"bud.prompt_id": "different-prompt"}}]
        result = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

        assert result == {}


class TestStats:
    """Tests for statistics reporting."""

    def test_get_stats(self, manager: ChannelManager, sid: str) -> None:
        """Test getting channel manager statistics."""
        manager.add_client(sid, "user-123")
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        manager.subscribe(sid, sub)

        stats = manager.get_stats()

        assert stats["client_count"] == 1
        assert stats["channels"]["observability"]["subscription_count"] == 1

    def test_get_stats_empty(self, manager: ChannelManager) -> None:
        """Test getting stats with no clients or subscriptions."""
        stats = manager.get_stats()

        assert stats["client_count"] == 0
        assert stats["channels"] == {}
