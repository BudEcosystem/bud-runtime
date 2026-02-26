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

"""Template System for BudUseCases.

This module provides YAML-based template definitions for GenAI use cases
and their synchronization to the database.
"""

from .crud import TemplateDataManager
from .loader import TemplateLoader, TemplateNotFoundError, TemplateValidationError
from .models import Template, TemplateComponent
from .schemas import (
    TemplateComponentSchema,
    TemplateParameterSchema,
    TemplateResourcesSchema,
    TemplateSchema,
)
from .startup import sync_templates_on_startup
from .sync import SyncResult, TemplateSyncService

__all__ = [
    "Template",
    "TemplateComponent",
    "TemplateDataManager",
    "TemplateLoader",
    "TemplateNotFoundError",
    "TemplateValidationError",
    "TemplateSchema",
    "TemplateComponentSchema",
    "TemplateParameterSchema",
    "TemplateResourcesSchema",
    "TemplateSyncService",
    "SyncResult",
    "sync_templates_on_startup",
]
