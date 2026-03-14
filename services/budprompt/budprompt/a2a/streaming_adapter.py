"""Streaming event translation from pydantic-ai AgentStreamEvent to A2A TaskUpdater updates."""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

from a2a.types import Part, TaskState
from pydantic import TypeAdapter
from pydantic_ai.messages import ModelMessage
from pydantic_ai.run import AgentRunResultEvent

from .context_store import PostgreSQLContextStore
from .helper import strip_response_metadata


logger = logging.getLogger(__name__)

_messages_ta = TypeAdapter(list[ModelMessage])


class A2AStreamingAdapter:
    """Translates AgentStreamEvent -> A2A v1.0 TaskUpdater updates.

    Iterates the raw event stream from execute_a2a(stream=True)
    and converts each event to A2A protocol updates.
    """

    def __init__(
        self,
        context_store: Optional[PostgreSQLContextStore] = None,
        context_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Initialize with optional context store for conversation persistence."""
        self.full_text = ""
        self._context_store = context_store
        self._context_id = context_id
        self._agent_id = agent_id

    async def translate(
        self,
        event_stream: AsyncGenerator[Any, None],
        updater: Any,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> list:
        """Iterate AgentStreamEvent, emit A2A updates, return final Parts.

        Returns:
            list of A2A Parts for the final artifact.
        """
        final_result = None

        async for event in event_stream:
            if isinstance(event, AgentRunResultEvent):
                final_result = event.result

                # Save context for streaming path
                if self._context_store and self._context_id:
                    try:
                        all_msgs = strip_response_metadata(
                            _messages_ta.dump_python(final_result.all_messages(), mode="json")
                        )
                        await self._context_store.save_messages(self._context_id, all_msgs, agent_id=self._agent_id)
                    except Exception:
                        logger.warning("Failed to save context for %s", self._context_id, exc_info=True)
                continue

            # Extract text deltas from PartDeltaEvent
            if hasattr(event, "delta") and hasattr(event.delta, "content_delta"):
                delta_text = event.delta.content_delta
                if delta_text:
                    self.full_text += delta_text
                    await updater.update_status(
                        state=TaskState.TASK_STATE_WORKING,
                        message=updater.new_agent_message(parts=[Part(text=delta_text)]),
                    )

        # Build final artifact Parts from result
        if final_result:
            return self._result_to_parts(final_result, output_schema)
        return [Part(text=self.full_text)]

    def _result_to_parts(self, result: Any, output_schema: Optional[Dict[str, Any]]) -> list:
        """Convert AgentRunResult -> A2A v1.0 Parts."""
        from google.protobuf import struct_pb2
        from pydantic import BaseModel

        if output_schema and isinstance(result.output, BaseModel):
            value = struct_pb2.Value()
            value.struct_value.update(result.output.model_dump())
            return [Part(data=value)]
        return [Part(text=str(result.output))]
