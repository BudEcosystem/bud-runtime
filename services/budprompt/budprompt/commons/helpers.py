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

"""Helper functions for the budprompt service."""

import asyncio
import concurrent.futures
from typing import Any, Coroutine


def run_async(coro: Coroutine) -> Any:
    """Run async coroutine safely in both sync and async contexts.

    This function handles the case where we need to run async code from
    both sync (workflow) and async (debug mode) contexts.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine

    Notes:
        - In async context (e.g., FastAPI route): Runs in a separate thread
        - In sync context (e.g., workflow): Uses asyncio.run() directly
    """
    try:
        # Check if there's a running event loop
        loop = asyncio.get_running_loop()  # noqa: F841
        # We're in an async context, create a new thread to run the coroutine
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        # No running loop, we can use asyncio.run() directly
        return asyncio.run(coro)
