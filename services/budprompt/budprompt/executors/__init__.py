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

"""Executor Module for Managing Prompt Executors.

This module provides a factory pattern for creating prompt executor instances
based on version numbers. The factory pattern ensures clean separation of
concerns and makes it easy to switch between different executor versions.

Usage:
    >>> from budprompt.executors import PromptExecutorFactory
    >>>
    >>> # Get the latest executor (version 3)
    >>> executor = PromptExecutorFactory.get_executor()
    >>>
    >>> # Get a specific version
    >>> executor_v2 = PromptExecutorFactory.get_executor(version=2)

Available Versions:
    - Version 1: SimplePromptExecutorDeprecated (basic functionality)
    - Version 2: SimplePromptExecutor (improved formatters)
    - Version 3: SimplePromptExecutor_V1 (active, with MCP tools)
"""

from .factory import PromptExecutorFactory
from .v1 import SimplePromptExecutorDeprecated
from .v2 import SimplePromptExecutor
from .v3 import SimplePromptExecutor_V1
from .v4 import SimplePromptExecutor_V4


__all__ = [
    "PromptExecutorFactory",
    "SimplePromptExecutor_V1",
    "SimplePromptExecutor",
    "SimplePromptExecutorDeprecated",
    "SimplePromptExecutor_V4",
]
