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

"""Socket.IO server for real-time telemetry streaming.

This module provides the Socket.IO server for clients to subscribe to
real-time observability data with authentication and channel-based filtering.

Replaces the previous plain WebSocket implementation for better client
compatibility, automatic reconnection, and easier testing.
"""

from typing import Any, Dict, Optional

import socketio

from notify.commons import logging

from .auth import validate_keycloak_token
from .schemas import Channel, Subscription
from .services import WebSocketService


logger = logging.get_logger(__name__)


sio: socketio.AsyncServer = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
)


socket_app: socketio.ASGIApp = socketio.ASGIApp(
    sio,
    socketio_path=None,
)


@sio.event
async def connect(sid: str, environ: Dict[str, Any], auth: Optional[Dict[str, Any]]) -> bool:
    """Handle new Socket.IO connection with authentication.

    Clients must provide a token in the auth dict during connection:
    ```javascript
    const socket = io('http://server', {
        auth: { token: 'your-jwt-token' }
    });
    ```

    Args:
        sid: The Socket.IO session ID.
        environ: WSGI environ dict.
        auth: Authentication data from client.

    Returns:
        True if connection is accepted.

    Raises:
        socketio.exceptions.ConnectionRefusedError: If authentication fails.
    """
    token = WebSocketService.extract_token(auth, environ)
    if not token:
        logger.warning(f"Connection refused for {sid}: token required")
        raise socketio.exceptions.ConnectionRefusedError("Token required")
    user = await validate_keycloak_token(token)

    if user is None:
        logger.warning(f"Connection refused for {sid}: invalid token")
        raise socketio.exceptions.ConnectionRefusedError("Invalid or expired token")

    await sio.save_session(sid, {"user_id": user.id, "user": user})

    manager = WebSocketService.get_channel_manager()
    manager.add_client(sid, user.id)

    await sio.emit("authenticated", {"user_id": user.id}, to=sid)

    logger.info(f"Socket.IO client connected: sid={sid}, user_id={user.id}")
    return True


@sio.event
async def disconnect(sid: str) -> None:
    """Handle Socket.IO disconnection.

    Cleans up client registration and subscriptions.

    Args:
        sid: The Socket.IO session ID.
    """
    manager = WebSocketService.get_channel_manager()
    manager.remove_client(sid)
    logger.info(f"Socket.IO client disconnected: sid={sid}")


@sio.event
async def subscribe(sid: str, data: Dict[str, Any]) -> None:
    """Handle subscription request from client.

    Expected data format:
    ```javascript
    socket.emit('subscribe', {
        channel: 'observability',
        filters: { project_id: 'uuid-here' }
    });
    ```

    Args:
        sid: The Socket.IO session ID.
        data: Subscription request data.
    """
    channel_str = data.get("channel")
    filters = data.get("filters", {})

    if not channel_str:
        await sio.emit("error", {"error": "Missing 'channel' field"}, to=sid)
        return

    try:
        channel = Channel(channel_str)
    except ValueError:
        await sio.emit("error", {"error": f"Invalid channel: {channel_str}"}, to=sid)
        return

    if not isinstance(filters, dict):
        await sio.emit("error", {"error": "'filters' must be an object"}, to=sid)
        return

    room = WebSocketService.make_room_name(channel.value, filters)
    await sio.enter_room(sid, room)

    subscription = Subscription(channel=channel, filters=filters)
    manager = WebSocketService.get_channel_manager()
    success = manager.subscribe(sid, subscription)

    if success:
        await sio.emit("subscribed", {"channel": channel.value, "filters": filters}, to=sid)
        session = await sio.get_session(sid)
        user_id = session.get("user_id", "unknown")
        logger.debug(f"Subscription added: user_id={user_id}, channel={channel.value}, filters={filters}")
    else:
        await sio.emit("error", {"error": "Failed to subscribe"}, to=sid)


@sio.event
async def unsubscribe(sid: str, data: Dict[str, Any]) -> None:
    """Handle unsubscription request from client.

    Expected data format:
    ```javascript
    socket.emit('unsubscribe', {
        channel: 'observability',
        filters: { project_id: 'uuid-here' }
    });
    ```

    Args:
        sid: The Socket.IO session ID.
        data: Unsubscription request data.
    """
    channel_str = data.get("channel")
    filters = data.get("filters", {})

    if not channel_str:
        await sio.emit("error", {"error": "Missing 'channel' field"}, to=sid)
        return

    try:
        channel = Channel(channel_str)
    except ValueError:
        await sio.emit("error", {"error": f"Invalid channel: {channel_str}"}, to=sid)
        return

    if not isinstance(filters, dict):
        await sio.emit("error", {"error": "'filters' must be an object"}, to=sid)
        return

    room = WebSocketService.make_room_name(channel.value, filters)
    await sio.leave_room(sid, room)

    subscription = Subscription(channel=channel, filters=filters)
    manager = WebSocketService.get_channel_manager()
    success = manager.unsubscribe(sid, subscription)

    if success:
        await sio.emit("unsubscribed", {"channel": channel.value, "filters": filters}, to=sid)
        session = await sio.get_session(sid)
        user_id = session.get("user_id", "unknown")
        logger.debug(f"Subscription removed: user_id={user_id}, channel={channel.value}, filters={filters}")
    else:
        await sio.emit("error", {"error": "Failed to unsubscribe"}, to=sid)


async def emit_to_subscribers(channel: Channel, filters: Dict[str, str], data: Any) -> None:
    """Emit data to all subscribers matching the channel and filters.

    This is called by the ChannelManager when flushing buffered data.

    Args:
        channel: The channel to emit on.
        filters: The filters that determine the room.
        data: The data to emit.
    """
    room = WebSocketService.make_room_name(channel.value, filters)
    await sio.emit("data", {"channel": channel.value, "data": data}, room=room)
