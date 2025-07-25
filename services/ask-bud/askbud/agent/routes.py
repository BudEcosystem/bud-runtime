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

from typing import Union

from budmicroframe.commons import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .schemas import ChatCompletionRequest, ChatCompletionResponse
from .services import AgentService


logger = logging.get_logger(__name__)

agent_router = APIRouter(prefix="/v1", tags=["agent"])


@agent_router.post("/chat/completions", response_model=ChatCompletionResponse)
async def get_agent(request: ChatCompletionRequest) -> Union[ChatCompletionResponse, StreamingResponse]:
    """Process a chat completion request using Agent.

    This endpoint accepts a ChatCompletionRequest and forwards it to the Agent service
    for processing. It supports both streaming and non-streaming responses.

    Args:
        request: The ChatCompletionRequest containing messages and configuration

    Returns:
        Either a ChatCompletionResponse or a StreamingResponse depending on the request
    """
    # if request.model != "k8s-assistant":
    #     raise HTTPException(400, "Unknown model")
    if not request.messages:
        raise HTTPException(400, "messages required")
    response = await AgentService().process_chat_completion(request)
    if isinstance(response, dict):
        return response
    elif isinstance(response, StreamingResponse):
        return response  # StreamingResponse is returned as is
    else:
        return response
