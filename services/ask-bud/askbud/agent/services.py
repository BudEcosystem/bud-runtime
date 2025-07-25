import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from agents import Agent, Runner
from fastapi.responses import StreamingResponse

from ..tools.cluster import ClusterRegistry
from .cluster import ClusterAgent
from .schemas import ChatCompletionRequest, ChatCompletionResponse, SessionContext


logger = logging.getLogger(__name__)


class AgentService:
    _instance = None
    _initialized = False
    SESSIONS: Dict[str, SessionContext] = {}
    REGISTRY: Dict[str, Any] = {}

    def __new__(cls) -> "AgentService":
        """Implement singleton pattern to ensure session persistence across requests."""
        if cls._instance is None:
            logger.info("Creating new AgentService singleton instance")
            cls._instance = super(AgentService, cls).__new__(cls)
            # Explicitly type _initialized as a boolean
            cls._instance._initialized = False  # noqa: E701
        return cls._instance

    def __init__(self) -> None:
        """Initialize the AgentService with a ClusterAgent instance.

        This constructor creates a new ClusterAgent and assigns it to the service,
        making it available for handling Kubernetes-related queries and operations.
        """
        # Only initialize once when the singleton is first created
        if not hasattr(self, "_initialized") or not self._initialized:
            logger.info("Initializing AgentService")
            self.agent = ClusterAgent()
            self._initialized = True  # noqa: E701

    def get_agent(self) -> Agent:
        """Get the agent instance associated with this service.

        Returns:
            The ClusterAgent instance that was initialized with this service.
        """
        return self.agent

    def _get_session(self, sid: Optional[str]) -> str:
        logger.info(f"Getting session for {sid}")
        if not sid:
            sid = str(uuid.uuid4())
        if sid not in self.SESSIONS:
            logger.info(f"Creating new session for {sid}")
            self.SESSIONS[sid] = SessionContext(registry=ClusterRegistry())
        return sid

    async def _stream_events(self, user_msg: List[Dict[str, str]], ctx: SessionContext) -> AsyncGenerator[bytes, None]:
        def sse(data: Union[Dict[str, Any], str]) -> bytes:
            return f"data: {json.dumps(data) if isinstance(data, dict) else data}\n\n".encode()

        try:
            async for ev in Runner.run_streamed(self.agent, user_msg, context=ctx).stream_events():
                if hasattr(ev, "type") and ev.type == "raw_response_event":  # noqa: SIM102
                    if ev.data.type == "response.output_text.delta":
                        yield sse(
                            {"choices": [{"delta": {"content": ev.data.delta}, "index": 0, "finish_reason": None}]}
                        )

            yield sse({"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]})
        except Exception as e:
            logging.exception(f"Error in stream_events: {str(e)}")
            # Ensure we send a proper closing message even on error
            yield sse({"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]})

        # Only send [DONE] once at the end
        yield b"data: [DONE]\n\n"

    async def process_chat_completion(
        self, request: ChatCompletionRequest
    ) -> Union[ChatCompletionResponse, StreamingResponse]:
        """Process a chat completion request from the client.

        This method handles both streaming and non-streaming chat completion requests.
        For streaming requests, it returns a StreamingResponse with Server-Sent Events.
        For non-streaming requests, it returns a complete ChatCompletionResponse.

        Args:
            request (ChatCompletionRequest): The chat completion request containing messages
                and configuration options.

        Returns:
            Union[ChatCompletionResponse, StreamingResponse]: Either a complete response object
            or a streaming response, depending on the request's stream parameter.
        """
        # Take only the *last* user message as new input; previous ones are already inside the agent's memory via ctx
        # user_msg = request.messages
        sid = self._get_session(request.session_id)
        ctx = self.SESSIONS[sid]
        user_msg = []
        for message in request.messages:
            user_msg.append({"content": message.content, "role": message.role})
        # logger.info(f"Processing chat completion for {user_msg.model_dump()}")
        if request.stream:
            return StreamingResponse(self._stream_events(user_msg, ctx), media_type="text/event-stream")
        else:
            res = await Runner.run(self.agent, user_msg, context=ctx)
            return {
                "id": str(uuid.uuid4()),
                "object": "chat.completion",
                "model": "k8s-assistant",
                "created": int(__import__("time").time()),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": res.final_output},
                        "finish_reason": "stop",
                    }
                ],
            }
