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

from pydantic_ai._output import DEFAULT_OUTPUT_TOOL_NAME


# MCP Cleanup Registry
CLEANUP_REGISTRY_KEY = "prompt:cleanup_registry"

# Default internal tool name, description in pydantic ai to generate structured output
STRUCTURED_OUTPUT_TOOL_NAME = DEFAULT_OUTPUT_TOOL_NAME
STRUCTURED_OUTPUT_TOOL_DESCRIPTION = "Final result processed."

# Model name for validator code generation
VALIDATION_MODEL_NAME = "qwen3-32b"
