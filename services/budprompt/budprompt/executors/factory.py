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

"""Factory for creating prompt executor instances based on version.

This module implements the Factory design pattern to provide version-based
executor instantiation with proper encapsulation and single responsibility.
"""

from typing import Union

from budmicroframe.commons import logging

from .v1 import SimplePromptExecutorDeprecated
from .v2 import SimplePromptExecutor
from .v3 import SimplePromptExecutor_V1
from .v4 import SimplePromptExecutor_V4


logger = logging.get_logger(__name__)


class PromptExecutorFactory:
    """Factory for creating prompt executors based on version.

    This factory follows the Factory design pattern to provide clean
    separation of concerns and make it easy to add new executor versions
    without modifying existing code (Open/Closed Principle).

    Supported Versions:
        - Version 1: SimplePromptExecutorDeprecated (basic functionality)
        - Version 2: SimplePromptExecutor (improved with better formatters)
        - Version 3: SimplePromptExecutor_V1 (active version with MCP tools support)

    Example:
        >>> executor = PromptExecutorFactory.get_executor(version=3)
        >>> # Use version 2
        >>> executor_v2 = PromptExecutorFactory.get_executor(version=2)
    """

    @staticmethod
    def get_executor(
        version: int = 4,
    ) -> Union[SimplePromptExecutorDeprecated, SimplePromptExecutor, SimplePromptExecutor_V1]:
        """Get executor instance for the specified version.

        Args:
            version: Executor version (1, 2, or 3). Default: 4

        Returns:
            Executor instance of the requested version.

        Raises:
            ValueError: If version is not 1, 2, or 3.
        """
        if version == 1:
            logger.debug("Creating SimplePromptExecutorDeprecated (version 1)")
            return SimplePromptExecutorDeprecated()
        elif version == 2:
            logger.debug("Creating SimplePromptExecutor (version 2)")
            return SimplePromptExecutor()
        elif version == 3:
            logger.debug("Creating SimplePromptExecutor_V1 (version 3)")
            return SimplePromptExecutor_V1()
        elif version == 4:
            logger.debug("Creating SimplePromptExecutor_V4 (version 4)")
            return SimplePromptExecutor_V4()
        else:
            logger.error("Invalid executor version requested: %s", version)
            raise ValueError("Invalid executor version: %s." % version)
