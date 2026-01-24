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

"""Channel manager for real-time subscription management.

This module implements subscription management and filter-based routing
for real-time telemetry streaming. Batching is handled by the OTEL Collector
(2s window), so this module only parses, filters, and emits immediately.

Updated to work with Socket.IO session IDs instead of WebSocket objects.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from notify.commons import logging

from .schemas import Channel, Subscription


logger = logging.get_logger(__name__)


@dataclass
class AuthenticatedClient:
    """Represents an authenticated Socket.IO client with subscriptions."""

    sid: str
    user_id: str
    subscriptions: Set[Subscription] = field(default_factory=set)


class ChannelManager:
    """Manages Socket.IO subscriptions and real-time data routing.

    The ChannelManager handles:
    - Client registration and authentication tracking
    - Subscription management per channel
    - Filter-based routing via group_by_subscription()

    Note: Batching is handled by the OTEL Collector (2s timeout).
    This manager is stateless - no memory buffering.
    """

    def __init__(self) -> None:
        """Initialize the channel manager."""
        self._clients: Dict[str, AuthenticatedClient] = {}
        self._channel_subscriptions: Dict[Channel, Set[Subscription]] = defaultdict(set)
        self._subscription_counts: Dict[Subscription, int] = defaultdict(int)

    def add_client(self, sid: str, user_id: str) -> None:
        """Register an authenticated client.

        Args:
            sid: The Socket.IO session ID.
            user_id: The authenticated user's ID.
        """
        self._clients[sid] = AuthenticatedClient(
            sid=sid,
            user_id=user_id,
        )
        logger.debug(f"Client registered: sid={sid}, user_id={user_id}")

    def remove_client(self, sid: str) -> None:
        """Unregister a client and clean up its subscriptions.

        Args:
            sid: The Socket.IO session ID to remove.
        """
        client = self._clients.pop(sid, None)
        if client is None:
            return

        for sub in client.subscriptions:
            self._decrement_subscription(sub)

        logger.debug(f"Client removed: sid={sid}, user_id={client.user_id}")

    def subscribe(self, sid: str, subscription: Subscription) -> bool:
        """Add a subscription for a client.

        Args:
            sid: The client's Socket.IO session ID.
            subscription: The subscription to add.

        Returns:
            True if subscription was added, False if client not found.
        """
        client = self._clients.get(sid)
        if client is None:
            return False

        if subscription in client.subscriptions:
            return True

        client.subscriptions.add(subscription)
        self._increment_subscription(subscription)

        logger.debug(
            f"Subscription added: user_id={client.user_id}, "
            f"channel={subscription.channel.value}, filters={subscription.filters}"
        )
        return True

    def unsubscribe(self, sid: str, subscription: Subscription) -> bool:
        """Remove a subscription for a client.

        Args:
            sid: The client's Socket.IO session ID.
            subscription: The subscription to remove.

        Returns:
            True if subscription was removed, False if client not found.
        """
        client = self._clients.get(sid)
        if client is None:
            return False

        if subscription not in client.subscriptions:
            return True

        client.subscriptions.discard(subscription)
        self._decrement_subscription(subscription)

        logger.debug(
            f"Subscription removed: user_id={client.user_id}, "
            f"channel={subscription.channel.value}, filters={subscription.filters}"
        )
        return True

    def has_subscribers(self, channel: Channel) -> bool:
        """Check if any clients are subscribed to a channel.

        Args:
            channel: The channel to check.

        Returns:
            True if at least one subscription exists for the channel.
        """
        return len(self._channel_subscriptions.get(channel, set())) > 0

    def get_subscriber_count(self, channel: Channel) -> int:
        """Get the number of unique subscriptions for a channel.

        Args:
            channel: The channel to check.

        Returns:
            Number of subscriptions for the channel.
        """
        return len(self._channel_subscriptions.get(channel, set()))

    def group_by_subscription(
        self,
        channel: Channel,
        spans: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group spans by matching subscription room.

        For each span, finds all subscriptions that match the span's filters
        and groups spans by their destination room name.

        Args:
            channel: The channel to route on.
            spans: List of span dictionaries with filter attributes.

        Returns:
            Dict mapping room_name to list of matching spans.
        """
        if not self.has_subscribers(channel):
            return {}

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for span in spans:
            filters = self._extract_filters(span)
            for subscription in self._channel_subscriptions.get(channel, set()):
                if subscription.matches(filters):
                    room = self._make_room_name(channel.value, subscription.filters)
                    grouped[room].append(span)

        return dict(grouped)

    def _extract_filters(self, span: Dict[str, Any]) -> Dict[str, str]:
        """Extract filter fields from span_attributes for subscription matching.

        Extracts bud.* prefixed attributes (propagated via OTEL baggage):
        - bud.project_id → project_id
        - bud.endpoint_id → endpoint_id
        - bud.prompt_id → prompt_id

        Note: Uses span_attributes (TraceItem-compatible schema), not merged
        attributes dict. The bud.* attributes come from span-level baggage.

        Args:
            span: The span data dictionary (TraceItem-compatible).

        Returns:
            Dictionary of filter key-value pairs.
        """
        filters: Dict[str, str] = {}

        span_attrs = span.get("span_attributes", {})
        if not isinstance(span_attrs, dict):
            return filters

        # Extract bud.* prefixed attributes only (set via OTEL baggage)
        for bud_key, filter_key in [
            ("bud.project_id", "project_id"),
            ("bud.endpoint_id", "endpoint_id"),
            ("bud.prompt_id", "prompt_id"),
        ]:
            if bud_key in span_attrs:
                filters[filter_key] = str(span_attrs[bud_key])

        return filters

    def _make_room_name(self, channel: str, filters: Dict[str, str]) -> str:
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

    def _increment_subscription(self, subscription: Subscription) -> None:
        """Increment the reference count for a subscription."""
        if self._subscription_counts[subscription] == 0:
            self._channel_subscriptions[subscription.channel].add(subscription)
        self._subscription_counts[subscription] += 1

    def _decrement_subscription(self, subscription: Subscription) -> None:
        """Decrement the reference count for a subscription."""
        count = self._subscription_counts.get(subscription, 0)
        if count <= 1:
            self._subscription_counts.pop(subscription, None)
            self._channel_subscriptions[subscription.channel].discard(subscription)
            return
        self._subscription_counts[subscription] = count - 1

    @property
    def client_count(self) -> int:
        """Return the number of connected clients."""
        return len(self._clients)

    def get_stats(self) -> Dict[str, Any]:
        """Get current channel manager statistics.

        Returns:
            Dictionary with stats about clients and subscriptions.
        """
        channel_stats = {
            channel.value: {"subscription_count": len(subs)} for channel, subs in self._channel_subscriptions.items()
        }
        return {
            "client_count": self.client_count,
            "channels": channel_stats,
        }
