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

"""Tests for realtime service classes."""

from datetime import datetime, timezone

import pytest

from notify.realtime.services import OTLPTransformService, WebSocketService


# ============================================================================
# WebSocketService Tests
# ============================================================================


class TestChannelManagerDI:
    """Tests for WebSocketService channel manager dependency injection."""

    def teardown_method(self) -> None:
        """Reset channel manager after each test."""
        WebSocketService._channel_manager = None

    def test_set_and_get_channel_manager(self) -> None:
        """Test setting and getting channel manager."""
        mock_manager = object()  # Use a simple object as mock

        WebSocketService.set_channel_manager(mock_manager)

        assert WebSocketService.get_channel_manager() is mock_manager

    def test_get_channel_manager_not_initialized(self) -> None:
        """Test that get_channel_manager raises RuntimeError when not initialized."""
        WebSocketService._channel_manager = None

        with pytest.raises(RuntimeError, match="ChannelManager not initialized"):
            WebSocketService.get_channel_manager()

    def test_set_channel_manager_overwrites(self) -> None:
        """Test that setting channel manager overwrites previous value."""
        first_manager = object()
        second_manager = object()

        WebSocketService.set_channel_manager(first_manager)
        WebSocketService.set_channel_manager(second_manager)

        assert WebSocketService.get_channel_manager() is second_manager


class TestMakeRoomName:
    """Tests for WebSocketService.make_room_name function."""

    def test_channel_only(self) -> None:
        """Test room name with no filters."""
        result = WebSocketService.make_room_name("observability", {})
        assert result == "observability"

    def test_single_filter(self) -> None:
        """Test room name with single filter."""
        result = WebSocketService.make_room_name("observability", {"project_id": "abc123"})
        assert result == "observability:project_id=abc123"

    def test_multiple_filters_sorted(self) -> None:
        """Test room name with multiple filters (sorted alphabetically)."""
        result = WebSocketService.make_room_name(
            "observability",
            {"project_id": "abc", "endpoint_id": "def"},
        )
        # Filters should be sorted alphabetically
        assert result == "observability:endpoint_id=def,project_id=abc"

    def test_empty_channel(self) -> None:
        """Test room name with empty channel."""
        result = WebSocketService.make_room_name("", {"filter": "value"})
        assert result == ":filter=value"


class TestExtractToken:
    """Tests for WebSocketService.extract_token function."""

    def test_token_from_auth_dict(self) -> None:
        """Test extracting token from auth dict."""
        auth = {"token": "my-jwt-token"}
        environ = {}

        result = WebSocketService.extract_token(auth, environ)

        assert result == "my-jwt-token"

    def test_token_from_asgi_headers(self) -> None:
        """Test extracting token from ASGI headers."""
        auth = None
        environ = {
            "asgi.scope": {
                "headers": [(b"authorization", b"Bearer my-jwt-token")],
            }
        }

        result = WebSocketService.extract_token(auth, environ)

        assert result == "my-jwt-token"

    def test_token_from_asgi_headers_no_bearer(self) -> None:
        """Test extracting token without Bearer prefix."""
        auth = None
        environ = {
            "asgi.scope": {
                "headers": [(b"authorization", b"raw-token-value")],
            }
        }

        result = WebSocketService.extract_token(auth, environ)

        assert result == "raw-token-value"

    def test_token_from_wsgi_headers(self) -> None:
        """Test extracting token from WSGI headers."""
        auth = None
        environ = {"HTTP_AUTHORIZATION": "Bearer wsgi-token"}

        result = WebSocketService.extract_token(auth, environ)

        assert result == "wsgi-token"

    def test_token_from_query_string(self) -> None:
        """Test extracting token from query string."""
        auth = None
        environ = {
            "asgi.scope": {
                "query_string": b"token=query-token&other=value",
            }
        }

        result = WebSocketService.extract_token(auth, environ)

        assert result == "query-token"

    def test_no_token_found(self) -> None:
        """Test when no token is found."""
        auth = None
        environ = {}

        result = WebSocketService.extract_token(auth, environ)

        assert result is None

    def test_auth_dict_takes_priority(self) -> None:
        """Test that auth dict token takes priority over headers."""
        auth = {"token": "auth-token"}
        environ = {
            "asgi.scope": {
                "headers": [(b"authorization", b"Bearer header-token")],
            }
        }

        result = WebSocketService.extract_token(auth, environ)

        assert result == "auth-token"

    def test_empty_auth_dict(self) -> None:
        """Test with empty auth dict."""
        auth = {}
        environ = {"HTTP_AUTHORIZATION": "Bearer fallback-token"}

        result = WebSocketService.extract_token(auth, environ)

        assert result == "fallback-token"


# ============================================================================
# OTLPTransformService Tests
# ============================================================================


class TestParseOtlpAttributes:
    """Tests for OTLPTransformService._parse_otlp_attributes function."""

    def test_parse_string_value(self) -> None:
        """Test parsing string attribute value."""
        attrs = [{"key": "name", "value": {"stringValue": "test"}}]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert result["name"] == "test"

    def test_parse_int_value(self) -> None:
        """Test parsing integer attribute value."""
        attrs = [{"key": "count", "value": {"intValue": "42"}}]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert result["count"] == 42

    def test_parse_double_value(self) -> None:
        """Test parsing double attribute value."""
        attrs = [{"key": "score", "value": {"doubleValue": 3.14}}]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert result["score"] == 3.14

    def test_parse_bool_value(self) -> None:
        """Test parsing boolean attribute value."""
        attrs = [{"key": "enabled", "value": {"boolValue": True}}]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert result["enabled"] is True

    def test_parse_array_value(self) -> None:
        """Test parsing array attribute value."""
        attrs = [
            {
                "key": "tags",
                "value": {"arrayValue": {"values": [{"stringValue": "a"}, {"stringValue": "b"}]}},
            }
        ]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert len(result["tags"]) == 2

    def test_parse_multiple_attributes(self) -> None:
        """Test parsing multiple attributes."""
        attrs = [
            {"key": "service.name", "value": {"stringValue": "budgateway"}},
            {"key": "http.status_code", "value": {"intValue": "200"}},
            {"key": "is_error", "value": {"boolValue": False}},
        ]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert result["service.name"] == "budgateway"
        assert result["http.status_code"] == 200
        assert result["is_error"] is False

    def test_skip_empty_key(self) -> None:
        """Test that attributes without keys are skipped."""
        attrs = [{"value": {"stringValue": "test"}}]

        result = OTLPTransformService._parse_otlp_attributes(attrs)

        assert result == {}


class TestHelperFunctions:
    """Tests for OTLPTransformService helper functions."""

    def test_unix_nanos_to_iso(self) -> None:
        """Test converting Unix nanoseconds to ISO string (no timezone suffix)."""
        # 1 second in nanoseconds
        result = OTLPTransformService._unix_nanos_to_iso(1000000000)
        # No timezone suffix to match budmetrics API format
        assert result == "1970-01-01T00:00:01"

    def test_unix_nanos_to_iso_string_input(self) -> None:
        """Test converting string nanoseconds to ISO string."""
        result = OTLPTransformService._unix_nanos_to_iso("1000000000")
        assert result == "1970-01-01T00:00:01"

    def test_unix_nanos_to_iso_zero(self) -> None:
        """Test that zero returns current time as ISO string."""
        result = OTLPTransformService._unix_nanos_to_iso(0)
        # Should be a valid ISO string close to now (naive datetime)
        parsed = datetime.fromisoformat(result)
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert (now_utc_naive - parsed).total_seconds() < 1

    def test_unix_nanos_to_iso_none(self) -> None:
        """Test that None returns current time as ISO string."""
        result = OTLPTransformService._unix_nanos_to_iso(None)
        parsed = datetime.fromisoformat(result)
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert (now_utc_naive - parsed).total_seconds() < 1

    def test_map_span_kind(self) -> None:
        """Test mapping OTLP span kind integers to strings."""
        assert OTLPTransformService._map_span_kind(0) == "Unspecified"
        assert OTLPTransformService._map_span_kind(1) == "Internal"
        assert OTLPTransformService._map_span_kind(2) == "Server"
        assert OTLPTransformService._map_span_kind(3) == "Client"
        assert OTLPTransformService._map_span_kind(4) == "Producer"
        assert OTLPTransformService._map_span_kind(5) == "Consumer"

    def test_map_span_kind_invalid(self) -> None:
        """Test that invalid span kind returns Unspecified."""
        assert OTLPTransformService._map_span_kind(99) == "Unspecified"
        assert OTLPTransformService._map_span_kind(None) == "Unspecified"
        assert OTLPTransformService._map_span_kind("invalid") == "Unspecified"

    def test_map_status_code(self) -> None:
        """Test mapping OTLP status code integers to strings."""
        assert OTLPTransformService._map_status_code(0) == "Unset"
        assert OTLPTransformService._map_status_code(1) == "Ok"
        assert OTLPTransformService._map_status_code(2) == "Error"

    def test_map_status_code_invalid(self) -> None:
        """Test that invalid status code returns Unset."""
        assert OTLPTransformService._map_status_code(99) == "Unset"
        assert OTLPTransformService._map_status_code(None) == "Unset"

    def test_stringify_attributes(self) -> None:
        """Test converting attribute values to strings."""
        attrs = {"str": "value", "int": 42, "float": 3.14, "bool": True}
        result = OTLPTransformService._stringify_attributes(attrs)

        # Booleans use lowercase to match ClickHouse/API format
        assert result == {"str": "value", "int": "42", "float": "3.14", "bool": "true"}

    def test_stringify_attributes_bool_false(self) -> None:
        """Test that False becomes lowercase 'false'."""
        attrs = {"is_error": False, "is_valid": True}
        result = OTLPTransformService._stringify_attributes(attrs)

        assert result == {"is_error": "false", "is_valid": "true"}

    def test_stringify_attributes_skips_none(self) -> None:
        """Test that None values are skipped."""
        attrs = {"valid": "value", "null": None}
        result = OTLPTransformService._stringify_attributes(attrs)

        assert result == {"valid": "value"}

    def test_parse_otlp_events(self) -> None:
        """Test parsing OTLP events to TraceEvent format."""
        events = [
            {
                "timeUnixNano": "1000000000",
                "name": "exception",
                "attributes": [{"key": "exception.message", "value": {"stringValue": "error"}}],
            }
        ]

        result = OTLPTransformService._parse_otlp_events(events)

        assert len(result) == 1
        assert result[0]["name"] == "exception"
        assert result[0]["attributes"]["exception.message"] == "error"
        # Timestamp is ISO string without timezone to match API
        assert result[0]["timestamp"] == "1970-01-01T00:00:01"

    def test_parse_otlp_events_empty(self) -> None:
        """Test that empty events list returns empty list."""
        assert OTLPTransformService._parse_otlp_events([]) == []
        assert OTLPTransformService._parse_otlp_events(None) == []

    def test_parse_otlp_links(self) -> None:
        """Test parsing OTLP links to TraceLink format."""
        links = [
            {
                "traceId": "linked-trace",
                "spanId": "linked-span",
                "traceState": "vendor=value",
                "attributes": [],
            }
        ]

        result = OTLPTransformService._parse_otlp_links(links)

        assert len(result) == 1
        assert result[0]["trace_id"] == "linked-trace"
        assert result[0]["span_id"] == "linked-span"
        assert result[0]["trace_state"] == "vendor=value"

    def test_parse_otlp_links_empty(self) -> None:
        """Test that empty links list returns empty list."""
        assert OTLPTransformService._parse_otlp_links([]) == []
        assert OTLPTransformService._parse_otlp_links(None) == []


class TestFlattenOtlpSpan:
    """Tests for OTLPTransformService.flatten_otlp_span function (TraceItem-compatible output)."""

    def test_flatten_basic_span(self) -> None:
        """Test flattening a basic OTLP span to TraceItem format."""
        span = {
            "traceId": "abc123",
            "spanId": "def456",
            "parentSpanId": "parent123",
            "name": "test_operation",
            "kind": 2,
            "startTimeUnixNano": "1000000000",
            "endTimeUnixNano": "2000000000",
            "status": {"code": 0},
            "attributes": [],
        }

        result = OTLPTransformService.flatten_otlp_span(span, {}, "test-scope", "1.0.0")

        assert result["trace_id"] == "abc123"
        assert result["span_id"] == "def456"
        assert result["parent_span_id"] == "parent123"
        assert result["span_name"] == "test_operation"
        assert result["span_kind"] == "Server"  # kind=2 maps to Server
        assert result["service_name"] == "test-scope"
        assert result["scope_name"] == "test-scope"
        assert result["scope_version"] == "1.0.0"
        assert result["duration"] == 1000000000  # 2B - 1B nanoseconds
        assert result["status_code"] == "Unset"
        assert result["child_span_count"] == 0

    def test_flatten_with_resource_attrs(self) -> None:
        """Test flattening span with separated resource_attributes."""
        span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "test_operation",
            "attributes": [],
        }
        resource_attrs = {
            "service.name": "budgateway",
            "deployment.environment": "production",
        }

        result = OTLPTransformService.flatten_otlp_span(span, resource_attrs, "", "")

        assert result["service_name"] == "budgateway"
        # Resource attrs are separated, not merged
        assert result["resource_attributes"]["service.name"] == "budgateway"
        assert result["resource_attributes"]["deployment.environment"] == "production"
        # Span attributes are separate
        assert result["span_attributes"] == {}

    def test_flatten_preserves_bud_attrs_in_span_attributes(self) -> None:
        """Test flattening span preserves bud.* attributes in span_attributes."""
        span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "test_operation",
            "attributes": [
                {"key": "bud.project_id", "value": {"stringValue": "project-123"}},
                {"key": "bud.endpoint_id", "value": {"stringValue": "endpoint-456"}},
                {"key": "bud.prompt_id", "value": {"stringValue": "prompt-789"}},
            ],
        }

        result = OTLPTransformService.flatten_otlp_span(span, {}, "", "")

        # Bud attributes are in span_attributes (TraceItem-compatible)
        assert result["span_attributes"]["bud.project_id"] == "project-123"
        assert result["span_attributes"]["bud.endpoint_id"] == "endpoint-456"
        assert result["span_attributes"]["bud.prompt_id"] == "prompt-789"
        # No top-level extraction
        assert "project_id" not in result
        assert "endpoint_id" not in result
        assert "prompt_id" not in result

    def test_flatten_with_events_and_links(self) -> None:
        """Test flattening span with events and links."""
        span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "test_operation",
            "attributes": [],
            "events": [{"timeUnixNano": "1000000000", "name": "log", "attributes": []}],
            "links": [{"traceId": "linked", "spanId": "span", "attributes": []}],
        }

        result = OTLPTransformService.flatten_otlp_span(span, {}, "", "")

        assert len(result["events"]) == 1
        assert result["events"][0]["name"] == "log"
        assert len(result["links"]) == 1
        assert result["links"][0]["trace_id"] == "linked"

    def test_flatten_missing_parent_span_id(self) -> None:
        """Test that missing parentSpanId defaults to empty string."""
        span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "root_span",
            "attributes": [],
        }

        result = OTLPTransformService.flatten_otlp_span(span, {}, "", "")

        assert result["parent_span_id"] == ""

    def test_flatten_status_with_message(self) -> None:
        """Test flattening span with status message."""
        span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "error_span",
            "attributes": [],
            "status": {"code": 2, "message": "Something went wrong"},
        }

        result = OTLPTransformService.flatten_otlp_span(span, {}, "", "")

        assert result["status_code"] == "Error"
        assert result["status_message"] == "Something went wrong"


class TestParseOtlpSpans:
    """Tests for OTLPTransformService.parse_otlp_spans function."""

    def test_parse_empty_body(self) -> None:
        """Test parsing empty OTLP body."""
        body = {}

        result = OTLPTransformService.parse_otlp_spans(body)

        assert result == []

    def test_parse_single_span(self) -> None:
        """Test parsing body with single span."""
        body = {
            "resourceSpans": [
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "budgateway"}}]},
                    "scopeSpans": [
                        {
                            "scope": {"name": "test-scope"},
                            "spans": [
                                {
                                    "traceId": "abc123",
                                    "spanId": "def456",
                                    "name": "test_operation",
                                    "attributes": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        result = OTLPTransformService.parse_otlp_spans(body)

        assert len(result) == 1
        assert result[0]["trace_id"] == "abc123"
        assert result[0]["span_id"] == "def456"
        assert result[0]["service_name"] == "budgateway"

    def test_parse_multiple_spans(self) -> None:
        """Test parsing body with multiple spans."""
        body = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "scope": {"name": "scope1"},
                            "spans": [
                                {"traceId": "trace1", "spanId": "span1", "name": "op1", "attributes": []},
                                {"traceId": "trace1", "spanId": "span2", "name": "op2", "attributes": []},
                            ],
                        }
                    ],
                }
            ]
        }

        result = OTLPTransformService.parse_otlp_spans(body)

        assert len(result) == 2
        assert result[0]["span_name"] == "op1"
        assert result[1]["span_name"] == "op2"

    def test_parse_multiple_resource_spans(self) -> None:
        """Test parsing body with multiple resource spans."""
        body = {
            "resourceSpans": [
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "service1"}}]},
                    "scopeSpans": [
                        {
                            "scope": {},
                            "spans": [{"traceId": "t1", "spanId": "s1", "name": "op1", "attributes": []}],
                        }
                    ],
                },
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "service2"}}]},
                    "scopeSpans": [
                        {
                            "scope": {},
                            "spans": [{"traceId": "t2", "spanId": "s2", "name": "op2", "attributes": []}],
                        }
                    ],
                },
            ]
        }

        result = OTLPTransformService.parse_otlp_spans(body)

        assert len(result) == 2
        assert result[0]["service_name"] == "service1"
        assert result[1]["service_name"] == "service2"


class TestSpanKindMap:
    """Tests for OTLPTransformService.SPAN_KIND_MAP constant."""

    def test_span_kind_map_values(self) -> None:
        """Test that SPAN_KIND_MAP has all expected values."""
        expected = {
            0: "Unspecified",
            1: "Internal",
            2: "Server",
            3: "Client",
            4: "Producer",
            5: "Consumer",
        }
        assert expected == OTLPTransformService.SPAN_KIND_MAP


class TestStatusCodeMap:
    """Tests for OTLPTransformService.STATUS_CODE_MAP constant."""

    def test_status_code_map_values(self) -> None:
        """Test that STATUS_CODE_MAP has all expected values."""
        expected = {
            0: "Unset",
            1: "Ok",
            2: "Error",
        }
        assert expected == OTLPTransformService.STATUS_CODE_MAP
