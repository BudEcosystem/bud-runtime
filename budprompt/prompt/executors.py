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

"""Prompt executors for running AI prompts."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import ModelSettings as OpenAIModelSettings
from pydantic_ai.output import NativeOutput

from budprompt.commons.exceptions import PromptExecutionException, SchemaGenerationException
from budprompt.shared.providers import BudServeProvider

from .schema_builder import PydanticModelGenerator
from .schemas import Message, ModelSettings
from .template_renderer import render_template
from .utils import contains_pydantic_model, validate_input_data_type


logger = logging.getLogger(__name__)


class SimplePromptExecutor:
    """Executor for simple prompt execution with Pydantic AI.

    This executor handles the conversion of JSON schemas to Pydantic models,
    creates AI agents, and executes prompts with structured input/output.
    """

    def __init__(self):
        """Initialize the SimplePromptExecutor."""
        self.provider = BudServeProvider()
        self.model_generator = PydanticModelGenerator()

    async def execute(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        system_prompt: str,
        messages: List[Message],
        input_data: Optional[Union[Dict[str, Any], str]] = None,
    ) -> Union[Dict[str, Any], str]:
        """Execute a prompt with structured or unstructured input and output.

        Args:
            deployment_name: Name of the model deployment
            model_settings: Model configuration settings
            input_schema: JSON schema for input validation (None for unstructured)
            output_schema: JSON schema for output structure (None for unstructured)
            system_prompt: System prompt to guide the model
            messages: List of messages for context
            input_data: Input data to process (Dict for structured, str for unstructured)

        Returns:
            Output data (Dict for structured, str for unstructured)

        Raises:
            SchemaGenerationException: If schema conversion fails
            ValidationError: If input validation fails
            PromptExecutionException: If prompt execution fails
        """
        try:
            # Validate input data type matches schema presence
            validate_input_data_type(input_data, input_schema)

            # Handle input validation
            validated_input = None
            if input_schema is not None and input_data is not None:
                # Structured input: create model and validate
                input_model = await self._get_pydantic_model(input_schema, "InputModel")
                try:
                    validated_input = input_model.model_validate(input_data)
                except ValidationError:
                    # Let the ValidationError bubble up directly
                    raise
            else:
                # Unstructured input: use string directly
                validated_input = input_data

            # Prepare context for template rendering
            context = self._prepare_template_context(validated_input, input_schema is not None)

            # Render system prompt with Jinja2
            rendered_system_prompt = render_template(system_prompt, context)

            # Handle output type
            output_type = await self._get_output_type(output_schema)

            # Create AI agent with appropriate output type
            agent = await self._create_agent(deployment_name, model_settings, output_type, rendered_system_prompt)

            # Build message history from all messages
            message_history = self._build_message_history(messages, context)

            # Get user prompt from input_data
            user_prompt = self._prepare_user_prompt(input_data)

            # Execute the agent with both history and current prompt
            result = await self._run_agent(agent, user_prompt, message_history)

            # Process and return result
            if output_schema is not None:
                # Structured output: return as dict
                return result.model_dump() if hasattr(result, "model_dump") else result
            else:
                # Unstructured output: return as string
                return result

        except (SchemaGenerationException, ValidationError, PromptExecutionException):
            raise
        except Exception as e:
            logger.error(f"Prompt execution failed: {str(e)}")
            raise PromptExecutionException("Failed to execute prompt") from e

    async def _get_output_type(self, output_schema: Optional[Dict[str, Any]]) -> Any:
        """Extract output type from schema's content field.

        Args:
            output_schema: JSON schema with content field

        Returns:
            The type of the content field, wrapped in NativeOutput if it contains BaseModel
        """
        if output_schema is None:
            return str

        # Generate Pydantic model from schema
        output_model = await self._get_pydantic_model(output_schema, "OutputModel")

        # Extract type from content field using Pydantic v2 field access
        output_type = output_model.__pydantic_fields__["content"].annotation

        # Return NativeOutput if type contains BaseModel, otherwise return raw type
        if contains_pydantic_model(output_type):
            return NativeOutput(output_type)
        else:
            return output_type

    async def _get_pydantic_model(self, schema: Dict[str, Any], model_name: str) -> Type[BaseModel]:
        """Convert JSON schema to Pydantic model.

        Args:
            schema: JSON schema dictionary
            model_name: Name for the generated model

        Returns:
            Pydantic model class

        Raises:
            SchemaGenerationException: If conversion fails
        """
        # Use the model generator to create Pydantic model from schema
        return self.model_generator.from_json_schema(schema, model_name)

    async def _create_agent(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        output_type: Union[Type[BaseModel], Type[str], NativeOutput],
        system_prompt: str,
    ) -> Agent:
        """Create Pydantic AI agent.

        Args:
            deployment_name: Model deployment name
            model_settings: Model configuration
            output_type: Output type (Pydantic model for structured, str for unstructured)
            system_prompt: System prompt

        Returns:
            Configured AI agent
        """
        # Create model using BudServeProvider
        model = self.provider.get_model(
            model_name=deployment_name,
            settings=OpenAIModelSettings(
                temperature=model_settings.temperature,
                max_tokens=model_settings.max_tokens,
                top_p=model_settings.top_p,
                frequency_penalty=model_settings.frequency_penalty,
                presence_penalty=model_settings.presence_penalty,
                stop=model_settings.stop_sequences if model_settings.stop_sequences else None,
                seed=model_settings.seed,
            ),
        )

        # Create agent with output type
        agent = Agent(
            model=model,
            output_type=output_type,
            system_prompt=system_prompt,
        )

        return agent

    def _prepare_template_context(self, input_data: Any, is_structured: bool) -> Dict[str, Any]:
        """Prepare context for Jinja2 template rendering.

        Args:
            input_data: Validated input data
            is_structured: Whether the input is structured

        Returns:
            Context dictionary for template rendering
        """
        context = {}

        if input_data is not None:
            if is_structured and hasattr(input_data, "model_dump"):
                # Structured input: use model fields as context
                context = input_data.model_dump()
            elif isinstance(input_data, dict):
                # Direct dict input
                context = input_data
            elif isinstance(input_data, str):
                # Unstructured string input
                context["input"] = input_data

        return context

    def _build_message_history(self, messages: List[Message], context: Dict[str, Any]) -> List[ModelMessage]:
        """Build message history from messages list.

        Args:
            messages: List of messages with roles and content
            context: Context for template rendering

        Returns:
            List of Pydantic AI ModelMessage objects
        """
        message_history = []

        for msg in messages:
            # Render message content with Jinja2
            rendered_content = render_template(msg.content, context)

            if msg.role == "user":
                # Create user message
                message_history.append(ModelRequest(parts=[UserPromptPart(content=rendered_content)]))
            elif msg.role == "assistant":
                # Create assistant message
                message_history.append(
                    ModelResponse(
                        parts=[TextPart(content=rendered_content)],
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            elif msg.role == "developer":
                # Developer messages are system-level instructions
                message_history.append(ModelRequest(parts=[SystemPromptPart(content=rendered_content)]))

        return message_history

    def _prepare_user_prompt(self, input_data: Optional[Union[Dict[str, Any], str]]) -> Optional[str]:
        """Prepare the user prompt from input data.

        Args:
            input_data: The input data from the request (string or dict)

        Returns:
            The user prompt as a string, or None if no input data
        """
        if input_data is None:
            return None
        elif isinstance(input_data, str):
            return input_data
        else:
            # Convert dict to JSON string for structured input
            return json.dumps(input_data)

    async def _run_agent(self, agent: Agent, user_prompt: Optional[str], message_history: List[ModelMessage]) -> Any:
        """Run the agent with message history and current prompt.

        Args:
            agent: Configured AI agent
            user_prompt: Current user prompt from input_data
            message_history: Conversation history from messages

        Returns:
            Agent execution result

        Raises:
            PromptExecutionException: If execution fails
        """
        try:
            # Always pass both user_prompt and message_history
            # Pydantic AI will handle None user_prompt appropriately
            result = await agent.run(
                user_prompt=user_prompt,
                message_history=message_history,
            )

            return result.output
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise PromptExecutionException("Agent execution failed") from e
