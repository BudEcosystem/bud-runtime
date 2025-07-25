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

"""Manages application and secret configurations, utilizing environment variables and Dapr's configuration store for syncing."""

import os
from pathlib import Path

from budmicroframe.commons.config import BaseAppConfig, BaseSecretsConfig, register_settings
from pydantic import AnyHttpUrl, DirectoryPath, Field

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    inference_model: str = Field(..., alias="INFERENCE_MODEL")
    inference_url: str = Field(..., alias="INFERENCE_URL")
    inference_api_key: str = Field(..., alias="INFERENCE_API_KEY")

    dapr_base_url: AnyHttpUrl = Field(..., alias="DAPR_BASE_URL")
    bud_cluster_app_id: str = Field(..., alias="BUD_CLUSTER_APP_ID")
    bud_app_id: str = Field(..., alias="BUD_APP_ID")

    def model_post_init(self, __context: object) -> None:
        """Perform post-initialization setup or validation.

        This method is called after the model is initialized and validated.
        """
        os.environ["OPENAI_API_KEY"] = self.inference_api_key
        os.environ["OPENAI_ENDPOINT"] = self.inference_url


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
