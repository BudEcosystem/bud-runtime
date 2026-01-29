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

"""Ingest routes for receiving OTEL telemetry data.

This module provides HTTP endpoints for receiving span data from the
OTEL Collector and routing it to subscribed WebSocket clients.

Architecture: OTEL Collector batches spans (2s window) and sends to this
endpoint. We parse, filter by subscription, and emit immediately to Socket.IO
rooms. No buffering in this service - it's stateless.

Schema: Output exactly matches budmetrics TraceItem for client compatibility.
"""

from typing import Any, Dict

from fastapi import APIRouter, Request, status

from notify.commons import logging

from .channel_manager import ChannelManager
from .schemas import Channel
from .services import OTLPTransformService


logger = logging.get_logger(__name__)

ingest_router = APIRouter(prefix="/realtime", tags=["realtime-ingest"])


@ingest_router.get(
    "/stats",
    response_model=Dict[str, Any],
)
async def get_stats(request: Request) -> Dict[str, Any]:
    """Get real-time channel statistics.

    Returns statistics about connected clients and subscriptions.

    Returns:
        Dict with channel manager statistics.
    """
    manager: ChannelManager = request.app.state.channel_manager
    stats = manager.get_stats()
    return stats


@ingest_router.post(
    "/ingest/otlp",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Dict[str, Any],
)
async def ingest_otlp(request: Request) -> Dict[str, Any]:
    """Ingest OTLP-formatted trace data from OTEL Collector.

    This endpoint handles the OTLP HTTP JSON format used by the
    OTEL Collector's otlphttp exporter. Data is parsed, filtered by
    subscription, and emitted immediately to Socket.IO rooms.

    Note: Batching is handled by OTEL Collector (2s timeout).
    This endpoint is stateless - no buffering.

    OTLP format structure:
    ```json
    {
        "resourceSpans": [
            {
                "resource": {...},
                "scopeSpans": [
                    {
                        "scope": {...},
                        "spans": [...]
                    }
                ]
            }
        ]
    }
    ```

    Args:
        request: The HTTP request.

    Returns:
        Response with accepted count and emit info.
    """
    manager: ChannelManager = request.app.state.channel_manager

    if not manager.has_subscribers(Channel.OBSERVABILITY):
        return {
            "accepted": 0,
            "subscribers": 0,
            "message": "No active subscribers",
        }

    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"Failed to parse OTLP request body: {e}")
        return {
            "accepted": 0,
            "error": "Invalid JSON body",
        }

    spans = OTLPTransformService.parse_otlp_spans(body)

    if not spans:
        return {
            "accepted": 0,
            "total": 0,
            "rooms_emitted": 0,
            "subscribers": manager.get_subscriber_count(Channel.OBSERVABILITY),
        }

    grouped = manager.group_by_subscription(Channel.OBSERVABILITY, spans)

    # Lazy import to avoid circular import and socketio dependency at module level
    from .websocket_routes import emit_to_subscribers

    rooms_emitted = 0
    for room, room_spans in grouped.items():
        try:
            channel_str, filter_str = room.split(":", 1) if ":" in room else (room, "")
            filters: Dict[str, str] = {}
            if filter_str:
                for pair in filter_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        filters[k] = v

            await emit_to_subscribers(Channel(channel_str), filters, room_spans)
            rooms_emitted += 1
        except Exception as e:
            logger.error(f"Failed to emit to room {room}: {e}")

    logger.debug(f"Ingested {len(spans)} OTLP spans, emitted to {rooms_emitted} rooms")

    return {
        "accepted": len(spans),
        "total": len(spans),
        "rooms_emitted": rooms_emitted,
        "subscribers": manager.get_subscriber_count(Channel.OBSERVABILITY),
    }
