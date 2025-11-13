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

"""Shared providers for AI model integrations."""

from typing import Optional

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from budprompt.commons.config import app_settings


class BudServeProvider:
    """Provider for BudServe inference gateway (OpenAI-compatible).

    This provider wraps the OpenAI provider to work with BudServe's
    inference gateway, which provides an OpenAI-compatible API.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the BudServe provider.

        Args:
            api_key: API key for authentication (default: "sk_" if not provided)
            base_url: Base URL for the API (default: from AppConfig)
        """
        # Use provided api_key or fallback to "sk_" for backwards compatibility
        self.api_key = api_key if api_key else "sk_"
        self.base_url = base_url or app_settings.bud_gateway_base_url
        self._provider = None

    @property
    def provider(self) -> OpenAIProvider:
        """Get or create the OpenAI provider instance.

        Returns:
            OpenAIProvider configured for BudServe
        """
        if self._provider is None:
            self._provider = OpenAIProvider(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._provider

    def get_model(self, model_name: str, **kwargs) -> OpenAIChatModel:
        """Create an OpenAI model instance configured for BudServe.

        Args:
            model_name: Name of the model deployment
            **kwargs: Additional arguments passed to OpenAIChatModel (including system_prompt_role)

        Returns:
            OpenAIChatModel configured with BudServe provider
        """
        return OpenAIChatModel(model_name=model_name, provider=self.provider, **kwargs)
