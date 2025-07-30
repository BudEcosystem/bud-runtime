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

"""Utility functions for prompt execution."""

import sys
from typing import Any, Dict

from budmicroframe.commons import logging

from budprompt.commons.exceptions import InputValidationError


logger = logging.get_logger(__name__)


def clean_model_cache():
    """Clean up any temporary modules from sys.modules."""
    modules_to_remove = [key for key in sys.modules.keys() if key.startswith("temp_models_")]
    for module_name in modules_to_remove:
        logger.debug("Removing module from sys.modules: %s", module_name)
        del sys.modules[module_name]


def validate_input_data_type(input_data: Any, input_schema: Dict[str, Any] = None) -> None:
    """Validate that input_data type matches the schema presence.

    Args:
        input_data: The input data to validate
        input_schema: The input schema (None for unstructured)

    Raises:
        InputValidationError: If input_data type doesn't match schema presence
    """
    if input_schema is not None:
        # Structured input expected
        if not isinstance(input_data, dict):
            raise InputValidationError(
                "Structured input expected (input_schema provided) but got non-dict input_data. "
                f"Got type: {type(input_data).__name__}"
            )
    else:
        # Unstructured input expected
        if input_data is not None and not isinstance(input_data, str):
            raise InputValidationError(
                "Unstructured input expected (input_schema is None) but got non-string input_data. "
                f"Got type: {type(input_data).__name__}"
            )
