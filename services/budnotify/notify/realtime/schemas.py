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

"""Schemas for real-time telemetry streaming."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class Channel(str, Enum):
    """Supported real-time streaming channels."""

    OBSERVABILITY = "observability"


class Subscription(BaseModel):
    """Represents a client subscription to a channel with optional filters."""

    model_config = ConfigDict(frozen=True)

    channel: Channel
    filters: Dict[str, str] = Field(default_factory=dict)

    def __hash__(self) -> int:
        """Make subscription hashable for use in sets."""
        return hash((self.channel, tuple(sorted(self.filters.items()))))

    def __eq__(self, other: object) -> bool:
        """Check equality based on channel and filters."""
        if not isinstance(other, Subscription):
            return False
        return self.channel == other.channel and self.filters == other.filters

    def matches(self, event_filters: Dict[str, str]) -> bool:
        """Check if an event matches this subscription's filters.

        An empty subscription filter matches all events.
        Otherwise, all subscription filter keys must be present in the event
        and have matching values.

        Args:
            event_filters: The filters from the incoming event.

        Returns:
            True if the event matches this subscription.
        """
        if not self.filters:
            return True

        for key, value in self.filters.items():
            if key not in event_filters or event_filters[key] != value:
                return False
        return True


class AuthMessage(BaseModel):
    """Client authentication message."""

    action: Literal["auth"]
    token: str


class SubscribeMessage(BaseModel):
    """Client subscribe message."""

    action: Literal["subscribe"]
    channel: Channel
    filters: Dict[str, str] = Field(default_factory=dict)


class UnsubscribeMessage(BaseModel):
    """Client unsubscribe message."""

    action: Literal["unsubscribe"]
    channel: Channel
    filters: Dict[str, str] = Field(default_factory=dict)


class PingMessage(BaseModel):
    """Client ping message for keep-alive."""

    action: Literal["ping"]


ClientMessage = Union[AuthMessage, SubscribeMessage, UnsubscribeMessage, PingMessage]


class AuthenticatedResponse(BaseModel):
    """Server response after successful authentication."""

    type: Literal["authenticated"] = "authenticated"
    user_id: str


class SubscribedResponse(BaseModel):
    """Server response after successful subscription."""

    type: Literal["subscribed"] = "subscribed"
    channel: Channel


class UnsubscribedResponse(BaseModel):
    """Server response after successful unsubscription."""

    type: Literal["unsubscribed"] = "unsubscribed"
    channel: Channel


class DataResponse(BaseModel):
    """Server message containing streamed data."""

    type: Literal["data"] = "data"
    channel: Channel
    data: List[Dict[str, Any]]


class PongResponse(BaseModel):
    """Server pong response to client ping."""

    type: Literal["pong"] = "pong"


class ErrorResponse(BaseModel):
    """Server error response."""

    type: Literal["error"] = "error"
    error: str


ServerMessage = Union[
    AuthenticatedResponse,
    SubscribedResponse,
    UnsubscribedResponse,
    DataResponse,
    PongResponse,
    ErrorResponse,
]


class TraceEvent(BaseModel):
    """Schema for span events (matches budmetrics TraceEvent).

    Note: timestamp is ISO 8601 string for JSON serialization compatibility
    with Socket.IO emission.
    """

    timestamp: str  # ISO 8601 format
    name: str
    attributes: Dict[str, str]


class TraceLink(BaseModel):
    """Schema for span links (matches budmetrics TraceLink)."""

    trace_id: str
    span_id: str
    trace_state: str
    attributes: Dict[str, str]


class SpanEvent(BaseModel):
    """Exactly matches TraceItem from budmetrics.

    This schema ensures clients receive the same structure whether
    from REST API (budmetrics) or real-time WebSocket (budnotify).

    Filter fields are in span_attributes["bud.project_id"], etc.

    Note: timestamp is ISO 8601 string for JSON serialization compatibility
    with Socket.IO emission.
    """

    timestamp: str  # ISO 8601 format
    trace_id: str
    span_id: str
    parent_span_id: str
    trace_state: str
    span_name: str
    span_kind: str  # "Server", "Internal", "Client", "Producer", "Consumer", "Unspecified"
    service_name: str
    resource_attributes: Dict[str, str]
    scope_name: str
    scope_version: str
    span_attributes: Dict[str, str]
    duration: int  # nanoseconds
    status_code: str  # "Unset", "Ok", "Error"
    status_message: str
    events: List[TraceEvent]
    links: List[TraceLink]
    child_span_count: int = 0


class IngestRequest(BaseModel):
    """Request body for the ingest endpoint."""

    spans: List[SpanEvent]


class UserInfo(BaseModel):
    """User information extracted from validated JWT."""

    id: str
    email: Optional[str] = None
    username: Optional[str] = None
    realm: Optional[str] = None
