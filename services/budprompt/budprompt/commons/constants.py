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
    GEN_AI_OPENAI_RESPONSE_SERVICE_TIER,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_OUTPUT_TYPE,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_RESPONSE_ID,
    GEN_AI_RESPONSE_MODEL,
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

    # Standard attributes (from SDK)
    GEN_AI_OPERATION_NAME = GEN_AI_OPERATION_NAME
    GEN_AI_RESPONSE_ID = GEN_AI_RESPONSE_ID
    GEN_AI_RESPONSE_MODEL = GEN_AI_RESPONSE_MODEL
    GEN_AI_USAGE_INPUT_TOKENS = GEN_AI_USAGE_INPUT_TOKENS
    GEN_AI_USAGE_OUTPUT_TOKENS = GEN_AI_USAGE_OUTPUT_TOKENS

    # Request/sampling params (from SDK)
    GEN_AI_REQUEST_TEMPERATURE = GEN_AI_REQUEST_TEMPERATURE
    GEN_AI_REQUEST_TOP_P = GEN_AI_REQUEST_TOP_P
    GEN_AI_REQUEST_MAX_TOKENS = GEN_AI_REQUEST_MAX_TOKENS

    # OpenAI-specific (from SDK)
    GEN_AI_OPENAI_RESPONSE_SERVICE_TIER = GEN_AI_OPENAI_RESPONSE_SERVICE_TIER
    GEN_AI_OUTPUT_TYPE = GEN_AI_OUTPUT_TYPE
    GEN_AI_OUTPUT_MESSAGES = GEN_AI_OUTPUT_MESSAGES

    # Custom attributes (BudPrompt specific - no SDK equivalent)
    GEN_AI_PROMPT_ID = "gen_ai.prompt.id"
    GEN_AI_PROMPT_VERSION = "gen_ai.prompt.version"
    GEN_AI_PROMPT_VARIABLES = "gen_ai.prompt.variables"
    GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
    GEN_AI_RESPONSE_CREATED_AT = "gen_ai.response.created_at"
    GEN_AI_RESPONSE_OBJECT = "gen_ai.response.object"
    GEN_AI_RESPONSE_STATUS = "gen_ai.response.status"
    GEN_AI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"


class ErrorAttributes:
    """Error semantic convention attribute keys (from stable SDK).

    Reference: https://opentelemetry.io/docs/specs/semconv/attributes-registry/error/
    """

    ERROR_TYPE = ERROR_TYPE
