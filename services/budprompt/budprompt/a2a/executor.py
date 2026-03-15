"""A2A protocol executor bridge and SDK adapter.

Two classes with distinct roles:
- A2APromptExecutor: Engine — inherits V4, adds context store integration
- BudPromptAgentExecutor: Adapter — implements A2A SDK's AgentExecutor interface
"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Part, Task, TaskState, TaskStatus
from google.protobuf import struct_pb2
from openai.types.responses import ResponseInputItem
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_ai.messages import ModelMessage
from pydantic_ai.run import AgentRunResult

from budprompt.commons.exceptions import (
    PromptExecutionException,
    SchemaGenerationException,
    TemplateRenderingException,
)
from budprompt.executors.v4.executor import SimplePromptExecutor_V4
from budprompt.executors.v4.streaming_validation_executor import StreamingValidationExecutor
from budprompt.executors.v4.template_renderer import render_template
from budprompt.executors.v4.utils import (
    contains_pydantic_model,
    strip_none_values,
    validate_input_data_type,
    validate_template_variables,
)
from budprompt.prompt.schemas import MCPToolConfig, Message, ModelSettings, PromptExecuteData

from .context_store import PostgreSQLContextStore
from .helper import strip_response_metadata
from .streaming_adapter import A2AStreamingAdapter


logger = logging.getLogger(__name__)

_messages_ta = TypeAdapter(list[ModelMessage])


class A2APromptExecutor(SimplePromptExecutor_V4):
    """A2A-compatible prompt executor.

    execute_a2a() = execute() code structure + context load/save.
    Always returns raw pydantic-ai result (no return_raw param — always raw).
    """

    async def execute_a2a(
        self,
        # Same params as execute() minus return_raw
        deployment_name: str,
        model_settings: ModelSettings,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        messages: List[Message],
        input_data: Optional[Union[str, List[ResponseInputItem]]] = None,
        stream: bool = False,
        output_validation: Optional[Dict[str, Any]] = None,
        input_validation: Optional[Dict[str, Any]] = None,
        llm_retry_limit: Optional[int] = 3,
        enable_tools: bool = False,
        allow_multiple_calls: bool = True,
        system_prompt_role: Optional[str] = None,
        api_key: Optional[str] = None,
        tools: Optional[List[MCPToolConfig]] = None,
        system_prompt: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        # A2A-specific params
        context_id: Optional[str] = None,
        context_store: Optional[PostgreSQLContextStore] = None,
        agent_id: Optional[str] = None,
    ) -> Union[AgentRunResult, AsyncGenerator]:
        """Execute a prompt for A2A protocol.

        Same phases 1-7 as execute(). Always returns raw pydantic-ai result.
        A2A additions: context load before execution, context save after.
        """
        try:
            # === Phases 1-2: Validation + rendering (same as execute()) ===
            validate_input_data_type(input_schema, variables)
            validate_template_variables(variables, system_prompt, messages)

            validated_variables = variables

            if input_schema is not None and variables:
                input_model = await self._get_input_model_with_validation(input_schema, input_validation)
                try:
                    cleaned_variables = strip_none_values(variables)
                    validated_input = input_model.model_validate(cleaned_variables, extra="forbid")
                    validated_variables = validated_input.model_dump()
                except ValidationError as e:
                    from budprompt.executors.v4.openai_response_formatter import extract_validation_error_details

                    message, param, code = extract_validation_error_details(e)
                    logger.error("Input validation failed: %s", message)
                    raise PromptExecutionException(
                        message=message,
                        status_code=400,
                        err_type="invalid_request_error",
                        param=f"prompt.variables.{param}" if param else "prompt.variables",
                        code=code,
                    ) from e

            if variables:
                rendered_system_prompt = render_template(system_prompt, validated_variables) if system_prompt else None
                rendered_messages = [
                    Message(role=message.role, content=render_template(message.content, validated_variables))
                    for message in messages
                ]
            else:
                rendered_system_prompt = system_prompt
                rendered_messages = messages

            # === Phase 3: Build message history ===
            message_history = self._build_message_history(rendered_messages, rendered_system_prompt)

            # ** A2A ADDITION: Load stored context and prepend **
            if context_id and context_store:
                stored_messages = await context_store.get_messages(context_id)
                if stored_messages:
                    try:
                        stored_history = _messages_ta.validate_python(stored_messages)
                        message_history = stored_history + message_history
                    except Exception:
                        logger.warning("Failed to deserialize stored context for %s", context_id, exc_info=True)

            # Handle input_data
            if isinstance(input_data, list):
                input_message_history = self._convert_response_input_to_message_history(input_data)
                message_history.extend(input_message_history)
                user_prompt = None
            else:
                user_prompt = input_data

            # === Phases 4-6: Output type, tools, agent creation (same as execute()) ===
            output_type = await self._get_output_type(output_schema, output_validation, tools)
            toolsets = await self._load_toolsets(tools)
            agent, agent_kwargs = await self._create_agent(
                deployment_name,
                model_settings,
                output_type,
                llm_retry_limit,
                allow_multiple_calls,
                system_prompt_role,
                api_key=api_key,
                toolsets=toolsets,
            )

            # === Phase 7: Execute — always returns raw ===
            if stream:
                if output_validation and output_schema and contains_pydantic_model(output_type):
                    executor = StreamingValidationExecutor(
                        output_type=output_type,
                        prompt=user_prompt,
                        validation_prompt=output_validation,
                        messages=rendered_messages,
                        message_history=message_history,
                        api_key=api_key,
                        agent_kwargs=agent_kwargs,
                        deployment_name=deployment_name,
                        model_settings=model_settings,
                        tools=tools,
                        output_schema=output_schema,
                    )
                    return executor.stream_raw()
                return self._run_agent_raw_stream(agent, user_prompt, message_history)
            else:
                result = await self._run_agent(agent, user_prompt, message_history, output_schema)

                # ** A2A ADDITION: Save context after non-streaming execution **
                if context_id and context_store:
                    try:
                        all_msgs = strip_response_metadata(
                            _messages_ta.dump_python(result.all_messages(), mode="json")
                        )
                        await context_store.save_messages(context_id, all_msgs, agent_id=agent_id)
                    except Exception:
                        logger.warning("Failed to save context for %s", context_id, exc_info=True)

                return result

        except (SchemaGenerationException, ValidationError, PromptExecutionException, TemplateRenderingException):
            raise
        except Exception as e:
            logger.exception("A2A prompt execution failed: %s", e)
            raise PromptExecutionException("Failed to execute prompt") from e


class BudPromptAgentExecutor(AgentExecutor):
    """A2A SDK AgentExecutor adapter.

    Bridges A2A protocol -> A2APromptExecutor by:
    1. Extracting input from A2A Parts
    2. Unpacking PromptExecuteData (same pattern as PromptExecutorService)
    3. Converting raw result to A2A v1.0 Parts
    """

    def __init__(
        self,
        prompt_config: PromptExecuteData,
        api_key: Optional[str],
        context_store: PostgreSQLContextStore,
        prompt_id: str,
        version: int,
    ) -> None:
        """Initialize with prompt config, API key, and context store."""
        self._config = prompt_config
        self._api_key = api_key
        self._context_store = context_store
        self._prompt_id = prompt_id
        self._version = version
        self._agent_id = f"{prompt_id}:v{version}"
        self._a2a_executor = A2APromptExecutor()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute A2A request by delegating to A2APromptExecutor."""
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        # A2A v1.0 spec: stream MUST begin with Task object as initial snapshot
        # Ensure user message has a messageId (protobuf defaults to "" if client omits it)
        if context.message and not context.message.message_id:
            context.message.message_id = str(uuid4())

        initial_task = Task(
            id=context.task_id,
            context_id=context.context_id,
            status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
            history=[context.message] if context.message else [],
        )
        await event_queue.enqueue_event(initial_task)

        await updater.start_work()

        try:
            user_input, variables = self._extract_a2a_input(context.message)

            # Unpack PromptExecuteData (mirrors PromptExecutorService.execute_prompt)
            result = await self._a2a_executor.execute_a2a(
                deployment_name=self._config.deployment_name,
                model_settings=self._config.model_settings,
                input_schema=self._config.input_schema,
                output_schema=self._config.output_schema,
                messages=self._config.messages,
                input_data=user_input,
                stream=self._config.stream,
                input_validation=self._config.input_validation,
                output_validation=self._config.output_validation,
                llm_retry_limit=self._config.llm_retry_limit,
                enable_tools=self._config.enable_tools,
                allow_multiple_calls=self._config.allow_multiple_calls,
                system_prompt_role=self._config.system_prompt_role,
                api_key=self._api_key,
                tools=self._config.tools,
                system_prompt=self._config.system_prompt,
                variables=variables,
                context_id=context.context_id,
                context_store=self._context_store,
                agent_id=self._agent_id,
            )

            if self._config.stream:
                # Streaming: adapter emits per-chunk artifactUpdate events
                adapter = A2AStreamingAdapter(
                    context_store=self._context_store,
                    context_id=context.context_id,
                    agent_id=self._agent_id,
                )
                parts = await adapter.translate(result, updater, output_schema=self._config.output_schema)
                if adapter._chunk_count == 0:
                    # Edge case: no deltas streamed (e.g., structured output)
                    await updater.add_artifact(parts=parts, last_chunk=True)
                else:
                    # Replace accumulated per-token Parts with single coalesced artifact
                    await updater.add_artifact(
                        parts=parts,
                        artifact_id=adapter._artifact_id,
                        append=False,
                        last_chunk=True,
                    )
            else:
                # Non-streaming: convert result directly
                parts = self._result_to_parts(result)
                await updater.add_artifact(parts=parts, last_chunk=True)

            agent_msg = updater.new_agent_message(parts=parts)
            # Emit WORKING status with the agent message so the SDK's rotation
            # mechanism appends it to task.history when complete() arrives.
            await updater.update_status(state=TaskState.TASK_STATE_WORKING, message=agent_msg)
            await updater.complete(message=agent_msg)

        except Exception as e:
            logger.exception("Agent execution failed for task %s", context.task_id)
            error_msg = updater.new_agent_message(parts=[Part(text=f"Agent execution failed: {e}")])
            await updater.failed(message=error_msg)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task."""
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()

    def _result_to_parts(self, result: AgentRunResult) -> list:
        """Convert AgentRunResult -> A2A v1.0 Parts."""
        if self._config.output_schema and isinstance(result.output, BaseModel):
            value = struct_pb2.Value()
            value.struct_value.update(result.output.model_dump())
            return [Part(data=value)]
        return [Part(text=str(result.output))]

    def _extract_a2a_input(self, message: Any) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Extract user_input and variables from already-validated A2A message Parts."""
        text_parts: list[str] = []
        data_parts: list[dict] = []

        for part in message.parts:
            if part.HasField("text"):
                text_parts.append(part.text)
            if part.HasField("data"):
                data_parts.append(dict(part.data.struct_value))

        if self._config.input_schema:
            variables: Dict[str, Any] = {}
            for d in data_parts:
                variables.update(d)
            return None, variables
        else:
            user_input = " ".join(text_parts) if text_parts else None
            return user_input, None
