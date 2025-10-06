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

"""OpenAI Response Formatter for converting pydantic-ai responses to OpenAI format."""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, ValidationError

from .schemas import Message, ModelSettings


logger = logging.getLogger(__name__)

__all__ = [
    "OpenAIResponseSchema",
    "OpenAIPromptInfo",
    "OpenAIResponseFormatter",
    "map_status_to_error_type",
    "extract_validation_error_details",
]


# Error Mapping Utilities
def map_status_to_error_type(status_code: int) -> str:
    """Map HTTP status codes to OpenAI-compatible error types.

    Args:
        status_code: HTTP status code

    Returns:
        Error type string (e.g., 'bad_request', 'not_found')
    """
    error_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        422: "unprocessable_entity",
        429: "too_many_requests",
        500: "internal_server_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }
    # Default to internal_server_error for unknown 5xx codes
    if status_code >= 500:
        return error_map.get(status_code, "internal_server_error")
    # Default to bad_request for unknown 4xx codes
    elif 400 <= status_code < 500:
        return error_map.get(status_code, "bad_request")
    # Default fallback
    return "internal_server_error"


def extract_validation_error_details(e: ValidationError) -> Tuple[str, Optional[str], Optional[str]]:
    """Extract error details from Pydantic ValidationError.

    Args:
        e: Pydantic ValidationError

    Returns:
        Tuple of (message, param, code)
    """
    # Get the first error for simplicity (could be enhanced to handle multiple)
    if e.errors():
        first_error = e.errors()[0]

        # Build parameter path (e.g., 'prompt.variables.amount')
        param_parts = []
        for loc_item in first_error.get("loc", []):
            if loc_item != "__root__":  # Skip root markers
                param_parts.append(str(loc_item))
        param = ".".join(param_parts) if param_parts else None

        # Get error message
        message = first_error.get("msg", str(e))

        # Map Pydantic error type to our error codes
        error_type = first_error.get("type", "")
        code_map = {
            "missing": "required",
            "value_error": "invalid_value",
            "type_error": "invalid_type",
            "string_too_short": "invalid_length",
            "string_too_long": "invalid_length",
            "string_pattern_mismatch": "invalid_format",
            "enum": "invalid_choice",
        }

        # Try to find matching code
        code = None
        for pattern, mapped_code in code_map.items():
            if pattern in error_type:
                code = mapped_code
                break

        # Default to invalid_type if no match
        if not code:
            code = "invalid_type" if "type" in error_type else "invalid_value"

        return message, param, code

    # Fallback if no errors found
    return str(e), None, "validation_error"


# OpenAI Response Models
class OpenAIContentPart(BaseModel):
    """Content part for OpenAI messages."""

    type: Literal["input_text", "output_text", "thinking"]
    text: str
    annotations: Optional[List[Any]] = Field(default_factory=list)
    logprobs: Optional[List[Any]] = Field(default_factory=list)


class OpenAIInstructionMessage(BaseModel):
    """Instruction message structure for system/user messages."""

    type: Literal["message"] = "message"
    content: List[OpenAIContentPart]
    role: Literal["system", "developer", "user", "assistant"]


class OpenAIOutputMessage(BaseModel):
    """Output message structure for assistant responses."""

    id: str
    type: Literal["message"] = "message"
    status: Literal["completed", "failed", "in_progress"] = "completed"
    content: List[OpenAIContentPart]
    role: Literal["assistant"] = "assistant"


class OpenAIUsageDetails(BaseModel):
    """Token usage details."""

    cached_tokens: int = 0
    reasoning_tokens: int = 0


class OpenAIUsage(BaseModel):
    """Token usage information."""

    input_tokens: int
    input_tokens_details: OpenAIUsageDetails
    output_tokens: int
    output_tokens_details: OpenAIUsageDetails
    total_tokens: int


class OpenAITextFormat(BaseModel):
    """Text format configuration."""

    type: Literal["text", "json"] = "text"


class OpenAITextConfig(BaseModel):
    """Text configuration."""

    format: OpenAITextFormat
    verbosity: Optional[Literal["low", "medium", "high"]] = "medium"


class OpenAIReasoning(BaseModel):
    """Reasoning configuration."""

    effort: Optional[Literal["low", "medium", "high"]] = None
    summary: Optional[str] = None


class OpenAIPromptInfo(BaseModel):
    """Prompt template information."""

    id: str
    variables: Optional[Dict[str, Any]] = None
    version: Optional[str] = None


class OpenAIResponseSchema(BaseModel):
    """Complete OpenAI response structure."""

    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed", "failed", "in_progress", "cancelled", "queued", "incomplete"] = "completed"
    background: bool = False
    billing: Optional[Dict[str, str]] = None
    error: Optional[Dict[str, Any]] = None
    incomplete_details: Optional[Dict[str, Any]] = None
    instructions: List[OpenAIInstructionMessage]
    max_output_tokens: Optional[int] = None
    max_tool_calls: Optional[int] = None
    model: str
    output: List[Union[OpenAIOutputMessage, Dict[str, Any]]]
    parallel_tool_calls: bool = True
    previous_response_id: Optional[str] = None
    prompt: Optional[OpenAIPromptInfo] = None
    prompt_cache_key: Optional[str] = None
    reasoning: OpenAIReasoning
    safety_identifier: Optional[str] = None
    service_tier: Literal["auto", "default", "flex", "priority"] = "default"
    store: bool = True
    temperature: float = 1.0
    text: OpenAITextConfig
    tool_choice: Union[Literal["auto", "none", "required"], Dict[str, Any]] = "auto"
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    top_logprobs: int = 0
    top_p: float = 1.0
    truncation: Literal["auto", "disabled"] = "disabled"
    usage: OpenAIUsage
    user: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OpenAIResponseFormatter:
    """Formatter for converting pydantic-ai responses to OpenAI format."""

    def format_response(
        self,
        pydantic_result: Any,
        model_settings: Optional[ModelSettings] = None,
        messages: Optional[List[Message]] = None,
        deployment_name: Optional[str] = None,
    ) -> OpenAIResponseSchema:
        """Format pydantic-ai result to OpenAI response structure.

        Args:
            pydantic_result: The result from pydantic-ai agent.run()
            model_settings: Model configuration settings
            messages: Original input messages
            deployment_name: Model deployment name

        Returns:
            OpenAIResponseSchema object matching OpenAI response structure
        """
        try:
            # Generate unique response ID
            response_id = f"resp_{uuid.uuid4().hex}"

            # Parse messages from result
            all_messages = json.loads(pydantic_result.all_messages_json())

            # Extract instructions from input messages
            instructions = self._format_instructions(messages or [], all_messages)

            # Extract output and reasoning from response
            output, reasoning_summary = self._format_output_with_reasoning(all_messages, response_id)

            # Get usage information
            usage = self._format_usage(pydantic_result.usage())

            # Get model name
            model_name = deployment_name or "unknown"
            # Try to get from all_messages if available
            if all_messages and len(all_messages) > 1:
                for msg in all_messages:
                    if msg.get("kind") == "response" and msg.get("model_name"):
                        model_name = msg["model_name"]
                        break

            # Build reasoning object with extracted summary
            reasoning = OpenAIReasoning(summary=reasoning_summary)

            # Build response
            response = OpenAIResponseSchema(
                id=response_id,
                created_at=int(time.time()),
                instructions=instructions,
                model=model_name,
                output=output,
                temperature=model_settings.temperature if model_settings else 1.0,
                top_p=model_settings.top_p if model_settings else 1.0,
                max_output_tokens=model_settings.max_tokens if model_settings else None,
                text=OpenAITextConfig(
                    format=OpenAITextFormat(type="json" if self._is_json_output(pydantic_result) else "text")
                ),
                reasoning=reasoning,
                usage=usage,
            )

            return response

        except Exception as e:
            logger.error(f"Error formatting OpenAI response: {str(e)}")
            raise

    def _format_instructions(self, messages: List[Message], all_messages: List[Dict]) -> List[Dict]:
        """Format instruction messages from input."""
        instructions = []

        # Always extract ALL messages from pydantic-ai messages (they contain everything)
        if all_messages:
            for msg in all_messages:
                if msg.get("kind") == "request":
                    parts = msg.get("parts", [])
                    for part in parts:
                        part_kind = part.get("part_kind", "")
                        if part_kind == "system-prompt":
                            instructions.append(
                                {
                                    "type": "message",
                                    "content": [{"type": "input_text", "text": part.get("content", "")}],
                                    "role": "system",
                                }
                            )
                        elif part_kind == "user-prompt":
                            instructions.append(
                                {
                                    "type": "message",
                                    "content": [{"type": "input_text", "text": part.get("content", "")}],
                                    "role": "user",
                                }
                            )

        # Fallback to original messages only if no pydantic-ai messages available
        if not instructions and messages:
            for msg in messages:
                if msg.role in ["system", "developer", "user"]:
                    instructions.append(
                        {
                            "type": "message",
                            "content": [{"type": "input_text", "text": msg.content}],
                            "role": msg.role,
                        }
                    )

        return instructions

    def _format_output_with_reasoning(
        self, all_messages: List[Dict], response_id: str
    ) -> Tuple[List[Dict], Optional[str]]:
        """Format output messages and extract reasoning from response.

        Returns:
            Tuple of (output_messages, reasoning_summary)
        """
        output = []
        thinking_parts = []

        for msg in all_messages:
            if msg.get("kind") == "response":
                parts = msg.get("parts", [])
                content_parts = []

                for part in parts:
                    part_kind = part.get("part_kind", "")
                    content = part.get("content", "")

                    if part_kind == "thinking":
                        # Collect thinking content for reasoning summary
                        if content:
                            thinking_parts.append(content)
                    elif part_kind in ["text", "tool-call-part"]:
                        content_parts.append(
                            {
                                "type": "output_text",
                                "text": content,
                                "annotations": [],
                                "logprobs": [],
                            }
                        )

                if content_parts:
                    output.append(
                        {
                            "id": f"msg_{uuid.uuid4().hex}",
                            "type": "message",
                            "status": "completed",
                            "content": content_parts,
                            "role": "assistant",
                        }
                    )

        # Combine thinking parts into reasoning summary
        reasoning_summary = "\n".join(thinking_parts) if thinking_parts else None

        return output, reasoning_summary

    def _format_usage(self, usage_info: Any) -> Dict:
        """Format usage information."""
        if not usage_info:
            return {
                "input_tokens": 0,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 0,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 0,
            }

        # Handle dict-like usage info
        usage_dict = usage_info if isinstance(usage_info, dict) else usage_info.__dict__

        return {
            "input_tokens": usage_dict.get("request_tokens", 0),
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": usage_dict.get("response_tokens", 0),
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": usage_dict.get("total_tokens", 0),
        }

    def _is_json_output(self, result: Any) -> bool:
        """Check if the output is JSON formatted."""
        try:
            if hasattr(result, "output"):
                output = result.output
                if hasattr(output, "model_dump"):
                    # It's a Pydantic model, so it's structured/JSON
                    return True
                elif isinstance(output, dict):
                    return True
            return False
        except Exception:
            return False
