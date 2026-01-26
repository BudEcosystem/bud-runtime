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

"""Business logic services for the realtime module.

This module provides service classes that encapsulate business logic,
following the thin controller pattern used across the project.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs


# ============================================================================
# WebSocket Service
# ============================================================================


class WebSocketService:
    """Service for WebSocket utilities and channel manager DI.

    Provides pure utility functions for WebSocket operations like
    room name generation and token extraction, as well as channel
    manager dependency injection for Socket.IO handlers.
    """

    # Constants for room management
    ROOM_SEPARATOR = ":"
    FILTER_SEPARATOR = ","

    # Channel manager instance (injected at startup)
    _channel_manager: Optional[Any] = None

    @classmethod
    def set_channel_manager(cls, manager: Any) -> None:
        """Set the channel manager instance for Socket.IO handlers.

        This is called during app startup to inject the ChannelManager dependency.

        Args:
            manager: The ChannelManager instance.
        """
        cls._channel_manager = manager

    @classmethod
    def get_channel_manager(cls) -> Any:
        """Get the channel manager instance.

        Returns:
            The ChannelManager instance.

        Raises:
            RuntimeError: If channel manager is not initialized.
        """
        if cls._channel_manager is None:
            raise RuntimeError("ChannelManager not initialized")
        return cls._channel_manager

    @staticmethod
    def make_room_name(channel: str, filters: Dict[str, str]) -> str:
        """Create room name from channel and filters.

        Args:
            channel: The channel name.
            filters: The subscription filters.

        Returns:
            A unique room name string.
        """
        if not filters:
            return channel
        filter_str = ",".join(f"{k}={v}" for k, v in sorted(filters.items()))
        return f"{channel}:{filter_str}"

    @staticmethod
    def extract_token(auth: Optional[Dict[str, Any]], environ: Dict[str, Any]) -> Optional[str]:
        """Extract JWT token from Socket.IO auth, headers, or query string.

        Checks multiple locations for the token in order of priority:
        1. auth dict from Socket.IO handshake
        2. Authorization header (ASGI or WSGI format)
        3. Query string parameter

        Args:
            auth: Authentication data from Socket.IO client.
            environ: WSGI/ASGI environ dict.

        Returns:
            The extracted token or None if not found.
        """
        # 1. Check auth dict from Socket.IO
        if auth and auth.get("token"):
            return auth["token"]

        # 2. Check ASGI scope headers (bytes pairs) or WSGI style
        scope = environ.get("asgi.scope", environ)
        headers = scope.get("headers", []) or []
        for key, value in headers:
            if key.lower() == b"authorization":
                header_value = value.decode("utf-8")
                if header_value.lower().startswith("bearer "):
                    return header_value.split(" ", 1)[1].strip()
                return header_value.strip()

        # 3. Check WSGI-style HTTP_AUTHORIZATION header
        auth_header = environ.get("HTTP_AUTHORIZATION")
        if isinstance(auth_header, str) and auth_header:
            if auth_header.lower().startswith("bearer "):
                return auth_header.split(" ", 1)[1].strip()
            return auth_header.strip()

        # 4. Check query string
        query_string = scope.get("query_string", b"")
        if query_string:
            params = parse_qs(query_string.decode("utf-8"))
            if "token" in params and params["token"]:
                return params["token"][0]

        return None


# ============================================================================
# OTLP Transform Service
# ============================================================================


class OTLPTransformService:
    """Service for transforming OTLP spans to TraceItem format.

    Converts the nested OTLP structure into a flat list of span dictionaries
    that exactly match the budmetrics TraceItem schema.
    """

    # Exact ClickHouse exporter mappings for SpanKind
    SPAN_KIND_MAP: Dict[int, str] = {
        0: "Unspecified",
        1: "Internal",
        2: "Server",
        3: "Client",
        4: "Producer",
        5: "Consumer",
    }

    # Exact ClickHouse exporter mappings for StatusCode
    STATUS_CODE_MAP: Dict[int, str] = {
        0: "Unset",
        1: "Ok",
        2: "Error",
    }

    @classmethod
    def parse_otlp_spans(cls, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse OTLP format into TraceItem-compatible span list.

        Converts the nested OTLP structure into a flat list of span dictionaries
        that exactly match the budmetrics TraceItem schema.

        Args:
            body: The OTLP request body.

        Returns:
            List of TraceItem-compatible span dictionaries.
        """
        spans: List[Dict[str, Any]] = []

        for resource_span in body.get("resourceSpans") or []:
            resource = resource_span.get("resource") or {}
            resource_attrs = cls._parse_otlp_attributes(resource.get("attributes") or [])

            for scope_span in resource_span.get("scopeSpans") or []:
                scope = scope_span.get("scope") or {}
                scope_name = scope.get("name") or ""
                scope_version = scope.get("version") or ""

                for span in scope_span.get("spans") or []:
                    flat_span = cls.flatten_otlp_span(span, resource_attrs, scope_name, scope_version)
                    spans.append(flat_span)

        return spans

    @classmethod
    def flatten_otlp_span(
        cls,
        span: Dict[str, Any],
        resource_attrs: Dict[str, Any],
        scope_name: str,
        scope_version: str,
    ) -> Dict[str, Any]:
        """Flatten OTLP span to TraceItem-compatible format.

        Exactly matches the schema used by budmetrics TraceItem and
        the ClickHouse otel_traces table.

        Args:
            span: The OTLP span object.
            resource_attrs: Resource-level attributes (parsed).
            scope_name: The instrumentation scope name.
            scope_version: The instrumentation scope version.

        Returns:
            TraceItem-compatible span dictionary.
        """
        span_attrs = cls._parse_otlp_attributes(span.get("attributes") or [])
        status = span.get("status") or {}

        # Compute duration (nanoseconds)
        start_nanos = cls._safe_int(span.get("startTimeUnixNano"))
        end_nanos = cls._safe_int(span.get("endTimeUnixNano"))
        duration = max(0, end_nanos - start_nanos)

        return {
            # Timestamp (ISO 8601 string for JSON serialization)
            "timestamp": cls._unix_nanos_to_iso(start_nanos),
            # Identifiers (hex strings)
            "trace_id": span.get("traceId") or "",
            "span_id": span.get("spanId") or "",
            "parent_span_id": span.get("parentSpanId") or "",
            "trace_state": span.get("traceState") or "",
            # Span metadata
            "span_name": span.get("name") or "",
            "span_kind": cls._map_span_kind(span.get("kind")),
            "service_name": resource_attrs.get("service.name") or scope_name or "",
            # Scope info
            "scope_name": scope_name,
            "scope_version": scope_version,
            # Attributes (separated, stringified for Map(String,String) compat)
            "resource_attributes": cls._stringify_attributes(resource_attrs),
            "span_attributes": cls._stringify_attributes(span_attrs),
            # Timing
            "duration": duration,
            # Status
            "status_code": cls._map_status_code(status.get("code")),
            "status_message": status.get("message") or "",
            # Events and links
            "events": cls._parse_otlp_events(span.get("events") or []),
            "links": cls._parse_otlp_links(span.get("links") or []),
            # Computed at query time in budmetrics (always 0 for streaming)
            "child_span_count": 0,
        }

    @staticmethod
    def _safe_int(value: Any) -> int:
        """Safely convert a value to int, returning 0 on failure."""
        try:
            return int(value or 0)
        except (ValueError, TypeError):
            return 0

    @classmethod
    def _unix_nanos_to_iso(cls, unix_nanos: Any) -> str:
        """Convert Unix nanoseconds to ISO 8601 string.

        Returns ISO format string matching budmetrics API output (no timezone suffix).

        Args:
            unix_nanos: Unix timestamp in nanoseconds (string or int).

        Returns:
            ISO 8601 formatted datetime string without timezone suffix.
        """
        nanos = cls._safe_int(unix_nanos)
        if nanos <= 0:
            # Use UTC time but format without timezone to match API
            dt = datetime.now(timezone.utc).replace(tzinfo=None)
            return dt.isoformat()
        seconds = nanos / 1_000_000_000
        # Convert to UTC then remove timezone info to match API format
        dt = datetime.fromtimestamp(seconds, timezone.utc).replace(tzinfo=None)
        return dt.isoformat()

    @classmethod
    def _map_span_kind(cls, kind: Any) -> str:
        """Map OTLP span kind integer to ClickHouse string.

        Args:
            kind: OTLP SpanKind integer (0-5).

        Returns:
            ClickHouse-compatible string like "Server", "Client", etc.
        """
        try:
            return cls.SPAN_KIND_MAP.get(int(kind), "Unspecified")
        except (ValueError, TypeError):
            return "Unspecified"

    @classmethod
    def _map_status_code(cls, code: Any) -> str:
        """Map OTLP status code integer to ClickHouse string.

        Args:
            code: OTLP StatusCode integer (0-2).

        Returns:
            ClickHouse-compatible string like "Unset", "Ok", "Error".
        """
        try:
            return cls.STATUS_CODE_MAP.get(int(code), "Unset")
        except (ValueError, TypeError):
            return "Unset"

    @staticmethod
    def _stringify_value(v: Any) -> str:
        """Convert a value to string matching ClickHouse format.

        Booleans are lowercase ("true"/"false") to match ClickHouse/API output.
        """
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    @classmethod
    def _stringify_attributes(cls, attrs: Dict[str, Any]) -> Dict[str, str]:
        """Convert all attribute values to strings.

        Matches ClickHouse Map(String, String) storage format.
        Booleans use lowercase "true"/"false" to match API output.

        Args:
            attrs: Dictionary with mixed-type values.

        Returns:
            Dictionary with all values as strings.
        """
        return {str(k): cls._stringify_value(v) for k, v in attrs.items() if v is not None}

    @classmethod
    def _parse_otlp_events(cls, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse OTLP events to TraceEvent format.

        Args:
            events: List of OTLP event objects.

        Returns:
            List of TraceEvent-compatible dictionaries.
        """
        if not events:
            return []
        result = []
        for event in events:
            result.append(
                {
                    "timestamp": cls._unix_nanos_to_iso(event.get("timeUnixNano")),
                    "name": event.get("name") or "",
                    "attributes": cls._stringify_attributes(cls._parse_otlp_attributes(event.get("attributes") or [])),
                }
            )
        return result

    @classmethod
    def _parse_otlp_links(cls, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse OTLP links to TraceLink format.

        Args:
            links: List of OTLP link objects.

        Returns:
            List of TraceLink-compatible dictionaries.
        """
        if not links:
            return []
        result = []
        for link in links:
            result.append(
                {
                    "trace_id": link.get("traceId") or "",
                    "span_id": link.get("spanId") or "",
                    "trace_state": link.get("traceState") or "",
                    "attributes": cls._stringify_attributes(cls._parse_otlp_attributes(link.get("attributes") or [])),
                }
            )
        return result

    @staticmethod
    def _parse_otlp_attributes(attrs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse OTLP attribute array into a flat dictionary.

        OTLP attributes are in the format:
        [{"key": "name", "value": {"stringValue": "test"}}]

        Args:
            attrs: List of OTLP attribute objects.

        Returns:
            Flat dictionary of attribute key-value pairs.
        """
        result: Dict[str, Any] = {}

        for attr in attrs:
            key = attr.get("key")
            value_obj = attr.get("value", {})

            if not key:
                continue

            if "stringValue" in value_obj:
                result[key] = value_obj["stringValue"]
            elif "intValue" in value_obj:
                result[key] = int(value_obj["intValue"])
            elif "doubleValue" in value_obj:
                result[key] = float(value_obj["doubleValue"])
            elif "boolValue" in value_obj:
                result[key] = value_obj["boolValue"]
            elif "arrayValue" in value_obj:
                result[key] = value_obj["arrayValue"].get("values", [])
            elif "kvlistValue" in value_obj:
                result[key] = OTLPTransformService._parse_otlp_attributes(value_obj["kvlistValue"].get("values", []))
            elif "bytesValue" in value_obj:
                result[key] = value_obj["bytesValue"]

        return result
