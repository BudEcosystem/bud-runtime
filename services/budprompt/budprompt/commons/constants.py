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

"""The constants used in the budprompt module."""

from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
)
from opentelemetry.semconv.attributes.error_attributes import ERROR_TYPE
from pydantic_ai._output import DEFAULT_OUTPUT_TOOL_NAME


# MCP Cleanup Registry
CLEANUP_REGISTRY_KEY = "prompt:cleanup_registry"

# Default internal tool name, description in pydantic ai to generate structured output
STRUCTURED_OUTPUT_TOOL_NAME = DEFAULT_OUTPUT_TOOL_NAME
STRUCTURED_OUTPUT_TOOL_DESCRIPTION = "Final result processed."

# Model name for validator code generation
VALIDATION_MODEL_NAME = "qwen3-32b"


class GenAIAttributes:
    """GenAI semantic convention attribute keys.

    Standard attributes use SDK values, custom attributes are BudPrompt-specific.
    Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/
    """

    # Standard attributes (values from SDK)
    OPERATION_NAME = GEN_AI_OPERATION_NAME
    AGENT_NAME = GEN_AI_AGENT_NAME
    AGENT_ID = GEN_AI_AGENT_ID
    AGENT_DESCRIPTION = GEN_AI_AGENT_DESCRIPTION
    REQUEST_MODEL = GEN_AI_REQUEST_MODEL
    RESPONSE_MODEL = GEN_AI_RESPONSE_MODEL
    SYSTEM = GEN_AI_SYSTEM
    USAGE_INPUT_TOKENS = GEN_AI_USAGE_INPUT_TOKENS
    USAGE_OUTPUT_TOKENS = GEN_AI_USAGE_OUTPUT_TOKENS

    # Custom attributes (BudPrompt specific)
    PROMPT_ID = "gen_ai.prompt.id"
    PROMPT_VERSION = "gen_ai.prompt.version"
    PROMPT_VARIABLES = "gen_ai.prompt.variables"
    INPUT_MESSAGES = "gen_ai.input.messages"


class ErrorAttributes:
    """Error semantic convention attribute keys (from stable SDK).

    Reference: https://opentelemetry.io/docs/specs/semconv/attributes-registry/error/
    """

    TYPE = ERROR_TYPE
