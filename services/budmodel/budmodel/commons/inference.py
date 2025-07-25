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

"""The LLM utils for the budmodel module."""

from budmicroframe.commons import logging
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from ..commons.config import app_settings, secrets_settings
from ..commons.exceptions import InferenceClientException


logger = logging.get_logger(__name__)


class InferenceClient:
    """The inference client for the budmodel module."""

    def __init__(self):
        """Initialize the inference client."""
        self.client = OpenAI(base_url=app_settings.bud_llm_base_url, api_key=secrets_settings.bud_llm_api_key)

    def completions(self, prompt: str, model: str = app_settings.bud_llm_model, **kwargs) -> str:
        """Completion method for the inference client."""
        try:
            response = self.client.completions.create(
                model=model,
                prompt=prompt,
                **kwargs,
            )

            return response.choices[0].text
        except (
            APIError,
            RateLimitError,
            APITimeoutError,
            BadRequestError,
            APIConnectionError,
            AuthenticationError,
            InternalServerError,
            APIStatusError,
        ) as e:
            logger.error("Error in completions: %s", e.message)
            raise InferenceClientException(e.message) from e
        except Exception as e:
            logger.error("Error in completions: %s", e)
            raise InferenceClientException("Unknown error in completions") from e

    def chat_completions(
        self,
        prompt: str,
        model: str = app_settings.bud_llm_model,
        system_prompt: str = "You are a helpful assistant that can answer questions and help with tasks.",
        **kwargs,
    ) -> str:
        """Chat completion method for the inference client."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                **kwargs,
            )

            return response.choices[0].message.content
        except (
            APIError,
            RateLimitError,
            APITimeoutError,
            BadRequestError,
            APIConnectionError,
            AuthenticationError,
            InternalServerError,
            APIStatusError,
        ) as e:
            logger.error("Error in chat completions: %s", e.message)
            raise InferenceClientException(e.message) from e
        except Exception as e:
            logger.error("Error in chat completions: %s", e)
            raise InferenceClientException("Unknown error in chat completions") from e
