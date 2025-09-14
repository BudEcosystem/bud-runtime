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

from pathlib import Path
from typing import Optional

from budmicroframe.commons.config import BaseAppConfig, BaseSecretsConfig, register_settings
from pydantic import DirectoryPath, Field

from ..__about__ import __version__


class AppConfig(BaseAppConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]
    description: str = ""
    api_root: str = ""

    # Base Directory
    base_dir: DirectoryPath = Path(__file__).parent.parent.parent.resolve()

    # VLM Configuration. This is set to the BudGateway URL
    vlm_api_url: str = Field(..., description="VLM API endpoint")
    vlm_model_name: str = Field(default="smoldocling-256m-preview-mlx-docling-snap", description="VLM model name")
    vlm_api_timeout: int = Field(default=90, description="VLM API timeout in seconds")
    vlm_response_format: str = Field(default="markdown", description="VLM response format")

    # Document Processing Configuration
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    allowed_extensions: str = Field(
        default="pdf,docx,pptx,xlsx,png,jpg,jpeg,tiff,html", description="Allowed file extensions"
    )
    temp_upload_dir: str = Field(default="/tmp/buddoc_uploads", description="Temporary upload directory")


class SecretsConfig(BaseSecretsConfig):
    name: str = __version__.split("@")[0]
    version: str = __version__.split("@")[-1]

    # VLM API Secrets
    vlm_api_token: Optional[str] = Field(default=None, description="VLM API authentication token")


app_settings = AppConfig()
secrets_settings = SecretsConfig()

register_settings(app_settings, secrets_settings)
