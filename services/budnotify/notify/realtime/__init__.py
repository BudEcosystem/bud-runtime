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

"""Real-time telemetry streaming module for BudNotify.

This module provides Socket.IO-based real-time data streaming for observability
channels, enabling live trace viewing and monitoring capabilities.
"""

from . import auth
from .channel_manager import ChannelManager
from .ingest_routes import ingest_router
from .schemas import Channel, ClientMessage, ServerMessage, Subscription
from .services import OTLPTransformService, WebSocketService


# Socket.IO related imports are optional (socketio may not be installed in test env)
try:
    from .websocket_routes import emit_to_subscribers, sio, socket_app
except ImportError:
    # When running tests without socketio installed
    emit_to_subscribers = None  # type: ignore[assignment]
    sio = None  # type: ignore[assignment]
    socket_app = None  # type: ignore[assignment]

__all__ = [
    "ChannelManager",
    "Channel",
    "Subscription",
    "ClientMessage",
    "ServerMessage",
    "ingest_router",
    "sio",
    "socket_app",
    "emit_to_subscribers",
    "OTLPTransformService",
    "WebSocketService",
]
