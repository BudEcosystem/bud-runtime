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

import logging
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.models.openai import ModelSettings as OpenAIModelSettings

from budprompt.commons.exceptions import PromptExecutionException, SchemaGenerationException
from budprompt.shared.providers import BudServeProvider

from .schema_builder import PydanticModelGenerator
from .schemas import Message, ModelSettings
from .utils import validate_input_data_type


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

            # Handle output type
            if output_schema is not None:
                # Structured output: create Pydantic model
                output_type = await self._get_pydantic_model(output_schema, "OutputModel")
            else:
                # Unstructured output: use str type
                output_type = str

            # Create AI agent with appropriate output type
            agent = await self._create_agent(deployment_name, model_settings, output_type, system_prompt)

            # Prepare messages
            prompt_messages = self._prepare_messages(messages, validated_input, input_schema is not None)

            # Execute the agent
            result = await self._run_agent(agent, prompt_messages)

            # Process and return result
            if output_schema is not None:
                # Structured output: return as dict
                return result.model_dump() if hasattr(result, "model_dump") else result
            else:
                # Unstructured output: return as string
                return result

        except (SchemaGenerationException, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Prompt execution failed: {str(e)}")
            raise PromptExecutionException("Failed to execute prompt")

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
        output_type: Union[Type[BaseModel], Type[str]],
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

    def _prepare_messages(self, messages: List[Message], input_data: Any = None, is_structured: bool = True) -> str:
        """Prepare messages for the agent.

        Args:
            messages: List of messages
            input_data: Validated input data (Pydantic model for structured, string for unstructured)
            is_structured: Whether the input is structured

        Returns:
            Formatted prompt string
        """
        # For now, we'll concatenate user messages
        # In future, we can add support for message templates with Jinja2
        user_messages = [msg.content for msg in messages if msg.role == "user"]

        if input_data is not None:
            if is_structured and hasattr(input_data, "model_dump"):
                # Structured input: add as JSON context
                user_messages.append(f"Input data: {input_data.model_dump()}")
            elif not is_structured and isinstance(input_data, str):
                # Unstructured input: add string directly
                user_messages.append(input_data)

        return "\n\n".join(user_messages)

    async def _run_agent(self, agent: Agent, prompt: str) -> Any:
        """Run the agent with the prepared prompt.

        Args:
            agent: Configured AI agent
            prompt: Prepared prompt string

        Returns:
            Agent execution result

        Raises:
            PromptExecutionException: If execution fails
        """
        try:
            result = await agent.run(prompt)
            return result.output
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise PromptExecutionException("Agent execution failed")
