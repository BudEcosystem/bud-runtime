"""A2A JSON-RPC dispatch service for budprompt.

Encapsulates store management, protobuf conversion, validation,
and JSON-RPC method dispatch. Routes.py provides the thin HTTP wrapper.
"""

import json
import logging
from typing import Optional, Union

from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import DatabaseTaskStore
from a2a.types import (
    CancelTaskRequest,
    GetTaskRequest,
    ListTasksRequest,
    Message,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    StreamResponse,
    SubscribeToTaskRequest,
    Task,
)
from a2a.utils.errors import (
    ContentTypeNotSupportedError,
    InvalidParamsError,
    MethodNotFoundError,
    UnsupportedOperationError,
)
from fastapi.responses import JSONResponse, StreamingResponse
from google.protobuf.json_format import MessageToDict, ParseDict, ParseError
from jsonrpc.jsonrpc2 import JSONRPC20Response
from sqlalchemy.ext.asyncio import create_async_engine

from ..commons.config import app_settings
from .config_resolver import A2AConfigResolver
from .context_store import PostgreSQLContextStore
from .executor import BudPromptAgentExecutor


logger = logging.getLogger(__name__)

# v0.3 → v1.0 enum normalization maps
_V03_ROLE_MAP = {
    "user": "ROLE_USER",
    "agent": "ROLE_AGENT",
}


class A2ADispatcherService:
    """A2A JSON-RPC dispatch service.

    Manages A2A stores (task store, context store, config resolver)
    and dispatches JSON-RPC methods to the appropriate SDK handlers.
    """

    def __init__(self) -> None:
        """Initialize with no stores — call initialize() before use."""
        self._engine = None
        self._task_store: Optional[DatabaseTaskStore] = None
        self._context_store: Optional[PostgreSQLContextStore] = None
        self._config_resolver: Optional[A2AConfigResolver] = None

    async def initialize(self) -> None:
        """Initialize A2A task store and context store using shared async engine."""
        self._engine = create_async_engine(app_settings.async_database_url, echo=False)

        self._task_store = DatabaseTaskStore(engine=self._engine, table_name="a2a_tasks")
        await self._task_store.initialize()  # Auto-creates a2a_tasks table

        self._context_store = PostgreSQLContextStore()
        self._context_store.initialize(self._engine)

        self._config_resolver = A2AConfigResolver()

        logger.info("A2A stores initialized")

    async def shutdown(self) -> None:
        """Dispose async engine on shutdown."""
        if self._engine:
            await self._engine.dispose()
            logger.info("A2A stores shut down")

    @staticmethod
    def _parse_params(params: dict, message_class):
        """Parse JSON-RPC params into protobuf, rejecting unknown fields."""
        try:
            return ParseDict(params, message_class())
        except ParseError as e:
            raise InvalidParamsError(message=str(e)) from e

    async def dispatch(
        self,
        prompt_id: str,
        version: int,
        method: str,
        request_id: Union[int, str, None],
        params: dict,
        api_key: Optional[str],
    ) -> Union[JSONResponse, StreamingResponse]:
        """Dispatch JSON-RPC method to appropriate handler."""
        # Resolve prompt config from Redis (v0 resolves to actual default version)
        config, resolved_version = await self._config_resolver.resolve(prompt_id, version)

        # Validate streaming mode match (Scenario 1.1.18)
        is_streaming_method = method in ("SendStreamingMessage", "message/sendStream")
        is_streaming_agent = getattr(config, "stream", False)
        if method in ("SendMessage", "message/send", "SendStreamingMessage", "message/sendStream"):
            if is_streaming_agent and not is_streaming_method:
                raise UnsupportedOperationError(
                    message="This agent is configured for streaming. Use SendStreamingMessage instead."
                )
            if not is_streaming_agent and is_streaming_method:
                raise UnsupportedOperationError(
                    message="This agent is not configured for streaming. Use SendMessage instead."
                )
            self._validate_output_modes(params, config)

        # Create per-request executor and handler
        executor = BudPromptAgentExecutor(
            prompt_config=config,
            api_key=api_key,
            context_store=self._context_store,
            prompt_id=prompt_id,
            version=resolved_version,
        )
        handler = DefaultRequestHandler(agent_executor=executor, task_store=self._task_store)
        server_context = ServerCallContext()

        # Dispatch by method
        if method in ("SendMessage", "message/send"):
            params = self._normalize_v03_params(params)
            send_req = self._parse_params(params, SendMessageRequest)
            if send_req.message.role == Role.ROLE_UNSPECIFIED:
                send_req.message.role = Role.ROLE_USER
            self._validate_message_parts(send_req.message, config.input_schema)
            result = await handler.on_message_send(send_req, server_context)
            return JSONResponse(JSONRPC20Response(result=self._wrap_send_result(result), _id=request_id).data)

        if method in ("SendStreamingMessage", "message/sendStream"):
            params = self._normalize_v03_params(params)
            send_req = self._parse_params(params, SendMessageRequest)
            if send_req.message.role == Role.ROLE_UNSPECIFIED:
                send_req.message.role = Role.ROLE_USER
            self._validate_message_parts(send_req.message, config.input_schema)

            async def sse_generator():
                async for event in handler.on_message_send_stream(send_req, server_context):
                    rpc_resp = JSONRPC20Response(result=self._wrap_stream_event(event), _id=request_id).data
                    yield f"data: {json.dumps(rpc_resp)}\n\n"

            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        if method in ("GetTask", "tasks/get"):
            get_req = self._parse_params(params, GetTaskRequest)
            task = await handler.on_get_task(get_req, server_context)
            return JSONResponse(
                JSONRPC20Response(result=self._proto_to_dict(task) if task else None, _id=request_id).data
            )

        if method in ("ListTasks", "tasks/list"):
            list_req = self._parse_params(params, ListTasksRequest)
            result = await handler.on_list_tasks(list_req, server_context)
            return JSONResponse(JSONRPC20Response(result=self._proto_to_dict(result), _id=request_id).data)

        if method in ("CancelTask", "tasks/cancel"):
            cancel_req = self._parse_params(params, CancelTaskRequest)
            result = await handler.on_cancel_task(cancel_req, server_context)
            return JSONResponse(
                JSONRPC20Response(result=self._proto_to_dict(result) if result else None, _id=request_id).data
            )

        if method in ("SubscribeToTask", "tasks/subscribe"):
            if not is_streaming_agent:
                raise UnsupportedOperationError(
                    message="This agent does not support streaming. Use GetTask for polling."
                )
            sub_req = self._parse_params(params, SubscribeToTaskRequest)

            async def sse_subscribe():
                async for event in handler.on_subscribe_to_task(sub_req, server_context):
                    rpc_resp = JSONRPC20Response(result=self._wrap_stream_event(event), _id=request_id).data
                    yield f"data: {json.dumps(rpc_resp)}\n\n"

            return StreamingResponse(
                sse_subscribe(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        raise MethodNotFoundError(message=f"Method not found: {method}")

    @staticmethod
    def _proto_to_dict(result) -> dict:
        """Convert protobuf message to dict."""
        return MessageToDict(result, preserving_proto_field_name=False)

    @staticmethod
    def _wrap_send_result(result) -> dict:
        """Wrap on_message_send result (Task|Message) in SendMessageResponse."""
        if isinstance(result, Task):
            resp = SendMessageResponse(task=result)
        elif isinstance(result, Message):
            resp = SendMessageResponse(message=result)
        else:
            resp = SendMessageResponse(task=result)
        return A2ADispatcherService._proto_to_dict(resp)

    @staticmethod
    def _wrap_stream_event(event) -> dict:
        """Wrap on_message_send_stream event in StreamResponse."""
        if isinstance(event, Task):
            sr = StreamResponse(task=event)
        elif isinstance(event, Message):
            sr = StreamResponse(message=event)
        else:
            type_name = type(event).__name__
            if "Status" in type_name:
                sr = StreamResponse(status_update=event)
            elif "Artifact" in type_name:
                sr = StreamResponse(artifact_update=event)
            else:
                sr = StreamResponse(task=event)
        return A2ADispatcherService._proto_to_dict(sr)

    @staticmethod
    def _validate_output_modes(params: dict, config) -> None:
        """Validate acceptedOutputModes against agent's output capability."""
        configuration = params.get("configuration", {})
        accepted = configuration.get("acceptedOutputModes", [])
        if not accepted:
            return
        agent_mode = "application/json" if config.output_schema else "text/plain"
        if agent_mode not in accepted:
            raise ContentTypeNotSupportedError(
                message=f"Agent produces {agent_mode} output, but client only accepts: {', '.join(accepted)}"
            )

    @staticmethod
    def _normalize_v03_params(params: dict) -> dict:
        """Normalize v0.3 short enum names to v1.0 protobuf format.

        Idempotent — v1.0 payloads pass through unchanged since their
        values are not in the mapping dicts.
        """
        msg = params.get("message")
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role in _V03_ROLE_MAP:
                msg["role"] = _V03_ROLE_MAP[role]
        return params

    @staticmethod
    def _validate_message_parts(message, input_schema=None) -> None:
        """Validate message parts before SDK handler creates a task.

        Request-level validations per A2A spec — must raise before
        DefaultRequestHandler stores the message in task.history.
        """
        if not message.parts:
            raise InvalidParamsError(message="Message must contain at least one part.")

        has_text = False
        has_data = False
        for part in message.parts:
            if part.HasField("raw"):
                raise ContentTypeNotSupportedError(
                    message="Binary content (raw) is not supported by this agent."
                )
            if part.HasField("url"):
                raise ContentTypeNotSupportedError(
                    message="URL/file content is not supported by this agent."
                )
            if part.HasField("text"):
                has_text = True
            if part.HasField("data"):
                has_data = True

        if input_schema:
            if has_text:
                raise InvalidParamsError(
                    message="Agent expects structured input matching input_schema. "
                    "Provide data in Part.data field."
                )
            if not has_data:
                raise InvalidParamsError(
                    message="Agent expects structured input matching input_schema. "
                    "Provide data in Part.data field."
                )
        else:
            if has_data:
                raise InvalidParamsError(
                    message="Agent expects text input. "
                    "Provide content in Part.text field."
                )
