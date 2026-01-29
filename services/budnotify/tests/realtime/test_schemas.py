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

"""Tests for realtime schemas."""

import pytest

from notify.realtime.schemas import (
    AuthenticatedResponse,
    Channel,
    DataResponse,
    ErrorResponse,
    PongResponse,
    SpanEvent,
    SubscribedResponse,
    Subscription,
    TraceEvent,
    TraceLink,
    UnsubscribedResponse,
    UserInfo,
)


class TestChannel:
    """Tests for Channel enum."""

    def test_observability_channel_value(self) -> None:
        """Test that observability channel has correct value."""
        assert Channel.OBSERVABILITY.value == "observability"

    def test_channel_from_string(self) -> None:
        """Test creating channel from string value."""
        channel = Channel("observability")
        assert channel == Channel.OBSERVABILITY

    def test_invalid_channel_raises(self) -> None:
        """Test that invalid channel string raises ValueError."""
        with pytest.raises(ValueError):
            Channel("invalid")


class TestSubscription:
    """Tests for Subscription model."""

    def test_subscription_hashable(self) -> None:
        """Test that subscriptions can be used in sets."""
        sub1 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub2 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub3 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "456"})

        sub_set = {sub1, sub2, sub3}
        assert len(sub_set) == 2

    def test_subscription_equality(self) -> None:
        """Test subscription equality comparison."""
        sub1 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub2 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})
        sub3 = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "456"})

        assert sub1 == sub2
        assert sub1 != sub3

    def test_subscription_matches_empty_filter(self) -> None:
        """Test that empty subscription filter matches all events."""
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={})

        assert sub.matches({"project_id": "123"}) is True
        assert sub.matches({"endpoint_id": "456"}) is True
        assert sub.matches({}) is True

    def test_subscription_matches_exact_filter(self) -> None:
        """Test that subscription filter matches exact event filters."""
        sub = Subscription(channel=Channel.OBSERVABILITY, filters={"project_id": "123"})

        assert sub.matches({"project_id": "123"}) is True
        assert sub.matches({"project_id": "123", "endpoint_id": "456"}) is True
        assert sub.matches({"project_id": "456"}) is False
        assert sub.matches({}) is False

    def test_subscription_matches_multiple_filters(self) -> None:
        """Test matching with multiple filter fields."""
        sub = Subscription(
            channel=Channel.OBSERVABILITY,
            filters={"project_id": "123", "endpoint_id": "456"},
        )

        assert sub.matches({"project_id": "123", "endpoint_id": "456"}) is True
        assert sub.matches({"project_id": "123", "endpoint_id": "456", "extra": "data"}) is True
        assert sub.matches({"project_id": "123"}) is False
        assert sub.matches({"project_id": "123", "endpoint_id": "789"}) is False


class TestServerMessages:
    """Tests for server response message models."""

    def test_authenticated_response(self) -> None:
        """Test AuthenticatedResponse serialization."""
        response = AuthenticatedResponse(user_id="user-123")
        data = response.model_dump()

        assert data["type"] == "authenticated"
        assert data["user_id"] == "user-123"

    def test_subscribed_response(self) -> None:
        """Test SubscribedResponse serialization."""
        response = SubscribedResponse(channel=Channel.OBSERVABILITY)
        data = response.model_dump()

        assert data["type"] == "subscribed"
        assert data["channel"] == "observability"

    def test_unsubscribed_response(self) -> None:
        """Test UnsubscribedResponse serialization."""
        response = UnsubscribedResponse(channel=Channel.OBSERVABILITY)
        data = response.model_dump()

        assert data["type"] == "unsubscribed"
        assert data["channel"] == "observability"

    def test_data_response(self) -> None:
        """Test DataResponse serialization."""
        response = DataResponse(
            channel=Channel.OBSERVABILITY,
            data=[{"trace_id": "abc", "span_id": "123"}],
        )
        data = response.model_dump()

        assert data["type"] == "data"
        assert data["channel"] == "observability"
        assert len(data["data"]) == 1
        assert data["data"][0]["trace_id"] == "abc"

    def test_pong_response(self) -> None:
        """Test PongResponse serialization."""
        response = PongResponse()
        data = response.model_dump()

        assert data["type"] == "pong"

    def test_error_response(self) -> None:
        """Test ErrorResponse serialization."""
        response = ErrorResponse(error="Something went wrong")
        data = response.model_dump()

        assert data["type"] == "error"
        assert data["error"] == "Something went wrong"


class TestTraceEvent:
    """Tests for TraceEvent model (matches budmetrics)."""

    def test_trace_event_creation(self) -> None:
        """Test TraceEvent creation with all fields."""
        event = TraceEvent(
            timestamp="2024-01-07T06:17:13",
            name="exception",
            attributes={"exception.type": "ValueError"},
        )

        assert event.timestamp == "2024-01-07T06:17:13"
        assert event.name == "exception"
        assert event.attributes["exception.type"] == "ValueError"


class TestTraceLink:
    """Tests for TraceLink model (matches budmetrics)."""

    def test_trace_link_creation(self) -> None:
        """Test TraceLink creation with all fields."""
        link = TraceLink(
            trace_id="linked-trace-123",
            span_id="linked-span-456",
            trace_state="vendor1=value1",
            attributes={"link.type": "parent"},
        )

        assert link.trace_id == "linked-trace-123"
        assert link.span_id == "linked-span-456"
        assert link.trace_state == "vendor1=value1"
        assert link.attributes["link.type"] == "parent"


class TestSpanEvent:
    """Tests for SpanEvent model (matches budmetrics TraceItem)."""

    def test_span_event_all_fields(self) -> None:
        """Test SpanEvent with all TraceItem-compatible fields."""
        span = SpanEvent(
            timestamp="2024-01-07T06:17:13.121932",
            trace_id="eabbcee5ecd7bde08b51580b32136a14",
            span_id="4e2df5b5dbeb1f65",
            parent_span_id="dcbb1843d1c22638",
            trace_state="",
            span_name="POST /v1/chat/completions",
            span_kind="Server",
            service_name="tensorzero-gateway",
            resource_attributes={"service.name": "tensorzero-gateway"},
            scope_name="tensorzero",
            scope_version="1.0.0",
            span_attributes={
                "bud.project_id": "proj-123",
                "http.request.method": "POST",
            },
            duration=2179880479,
            status_code="Unset",
            status_message="",
            events=[],
            links=[],
            child_span_count=0,
        )

        assert span.trace_id == "eabbcee5ecd7bde08b51580b32136a14"
        assert span.span_id == "4e2df5b5dbeb1f65"
        assert span.parent_span_id == "dcbb1843d1c22638"
        assert span.span_kind == "Server"
        assert span.service_name == "tensorzero-gateway"
        assert span.span_attributes["bud.project_id"] == "proj-123"
        assert span.duration == 2179880479
        assert span.status_code == "Unset"
        assert span.child_span_count == 0

    def test_span_event_with_events_and_links(self) -> None:
        """Test SpanEvent with nested events and links."""
        span = SpanEvent(
            timestamp="2024-01-07T06:17:13",
            trace_id="abc123",
            span_id="def456",
            parent_span_id="",
            trace_state="",
            span_name="test_operation",
            span_kind="Internal",
            service_name="test-service",
            resource_attributes={},
            scope_name="test-scope",
            scope_version="",
            span_attributes={"bud.project_id": "project-123"},
            duration=1000000,
            status_code="Ok",
            status_message="",
            events=[
                TraceEvent(
                    timestamp="2024-01-07T06:17:13",
                    name="exception",
                    attributes={"exception.message": "test error"},
                )
            ],
            links=[
                TraceLink(
                    trace_id="linked-trace",
                    span_id="linked-span",
                    trace_state="",
                    attributes={},
                )
            ],
            child_span_count=0,
        )

        assert len(span.events) == 1
        assert span.events[0].name == "exception"
        assert len(span.links) == 1
        assert span.links[0].trace_id == "linked-trace"

    def test_span_event_json_serialization(self) -> None:
        """Test SpanEvent JSON serialization preserves ISO timestamp."""
        span = SpanEvent(
            timestamp="2024-01-07T06:17:13",
            trace_id="abc123",
            span_id="def456",
            parent_span_id="",
            trace_state="",
            span_name="test",
            span_kind="Server",
            service_name="test",
            resource_attributes={},
            scope_name="",
            scope_version="",
            span_attributes={},
            duration=1000,
            status_code="Unset",
            status_message="",
            events=[],
            links=[],
        )

        data = span.model_dump(mode="json")
        assert data["timestamp"] == "2024-01-07T06:17:13"

    def test_span_event_default_child_span_count(self) -> None:
        """Test SpanEvent default child_span_count is 0."""
        span = SpanEvent(
            timestamp="2024-01-07T06:17:13",
            trace_id="abc",
            span_id="def",
            parent_span_id="",
            trace_state="",
            span_name="test",
            span_kind="Internal",
            service_name="svc",
            resource_attributes={},
            scope_name="",
            scope_version="",
            span_attributes={},
            duration=0,
            status_code="Unset",
            status_message="",
            events=[],
            links=[],
        )

        assert span.child_span_count == 0


class TestUserInfo:
    """Tests for UserInfo model."""

    def test_user_info_minimal(self) -> None:
        """Test UserInfo with minimal fields."""
        user = UserInfo(id="user-123")

        assert user.id == "user-123"
        assert user.email is None
        assert user.username is None
        assert user.realm is None

    def test_user_info_full(self) -> None:
        """Test UserInfo with all fields."""
        user = UserInfo(
            id="user-123",
            email="user@example.com",
            username="testuser",
            realm="bud",
        )

        assert user.id == "user-123"
        assert user.email == "user@example.com"
        assert user.username == "testuser"
        assert user.realm == "bud"
