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

"""Schemas for responses module - OpenAI-compatible API."""

from typing import Any, Dict, Literal, Optional, Union

from budmicroframe.commons.schemas import SuccessResponse
from pydantic import BaseModel, Field


class ResponseInputTextParam(BaseModel):
    """Input text parameter matching OpenAI's responses API."""

    type: Literal["input_text"] = "input_text"
    text: str


class ResponsePromptParam(BaseModel):
    """Parameters for prompt template execution.

    Compatible with OpenAI's responses API format.
    """

    id: str = Field(..., description="The unique identifier of the prompt template to use")
    variables: Optional[Dict[str, Union[str, ResponseInputTextParam]]] = Field(
        None,
        description="Optional map of values to substitute in for variables in your prompt. "
        "The substitution values can either be strings or ResponseInputTextParam.",
    )
    version: Optional[str] = Field(None, description="Optional version of the prompt template")


class ResponseCreateRequest(BaseModel):
    """Request model for creating responses via OpenAI-compatible API.

    This model follows OpenAI's responses API structure for compatibility.
    """

    prompt: ResponsePromptParam = Field(..., description="Prompt parameters including id, variables, and version")
    input: Optional[str] = Field(None, description="Optional input text for the prompt")


class ResponsePromptResponse(SuccessResponse):
    """Response model for prompt execution via responses API."""

    data: Optional[Dict[str, Any]] = Field(None, description="Response data from prompt execution")
