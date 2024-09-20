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

"""Provides utility functions for managing various aspects of the application."""

import asyncio
import json
import os
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from . import logging


logger = logging.get_logger(__name__)


def retry(
    max_attempts: int = 3,
    delay: Optional[int] = None,
    backoff_factor: Optional[int] = 2,
    max_delay: Optional[int] = None,
) -> Callable:
    """Decorate a function to provide retry functionality with optional exponential backoff.

    Args:
        max_attempts (int, optional): The maximum number of attempts to retry the function. Defaults to 3.
        delay (int, optional): The initial delay in seconds before retrying the function. If None, defaults to 1 when backoff_factor is provided. Defaults to None.
        backoff_factor (int, optional): The multiplier by which the delay is increased after each failed attempt. Defaults to 2.
        max_delay (int, optional): The maximum delay allowed between retries. If None, the delay will increase without limit. Defaults to None.

    Returns:
        Callable: A wrapper function that retries the decorated function on failure. It supports both synchronous and asynchronous functions.

    Raises:
        Exception: Raises the last exception if the maximum number of attempts is reached.

    Examples:
        @retry(max_attempts=5, delay=2, backoff_factor=3)
        def my_function():
            # Function logic here

        @retry(max_attempts=5, delay=2, backoff_factor=3)
        async def my_async_function():
            # Async function logic here
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            wait_for = delay
            if wait_for is None and backoff_factor is not None:
                wait_for = 1

            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise e  # If max attempts reached, raise the last exception

                    logger.error(
                        f"Attempt {attempts} failed with {str(e)}. Retrying {func.__name__} in {wait_for} seconds..."
                    )

                    time.sleep(wait_for)

                    if backoff_factor is not None:
                        wait_for = (
                            min(wait_for * backoff_factor, max_delay) if max_delay else wait_for * backoff_factor
                        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            wait_for = delay
            if wait_for is None and backoff_factor is not None:
                wait_for = 1

            attempts = 0
            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise e  # If max attempts reached, raise the last exception

                    logger.error(
                        f"Attempt {attempts} failed with {str(e)}. Retrying {func.__name__} in {wait_for} seconds..."
                    )

                    await asyncio.sleep(wait_for)

                    if backoff_factor is not None:
                        wait_for = (
                            min(wait_for * backoff_factor, max_delay) if max_delay else wait_for * backoff_factor
                        )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Read content from a JSON file and return it as a dictionary. Handle possible errors during file reading and JSON parsing.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        Optional[Dict[str, Any]]: The parsed JSON data as a dictionary if successful, None if an error occurs.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If there are issues with file permissions.
        json.JSONDecodeError: If the file contains invalid JSON.

    """
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError as fnf_error:
        logger.error(f"Error: {fnf_error}")
    except PermissionError as perm_error:
        logger.error(f"Error: {perm_error}")
    except json.JSONDecodeError as json_error:
        logger.error(f"Error: Invalid JSON format. {json_error}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

    return None


def read_file_content(file_path: str) -> Optional[str]:
    """Read and returns the content of a file.

    This function reads the content of a file specified by the `file_path`.
    If any error occurs (e.g., the file does not exist or cannot be read),
    the function returns `None`.

    Args:
        file_path (str): The path to the file to be read.

    Returns:
        Optional[str]: The content of the file as a string, or `None` if an error occurs.
    """
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r") as file:
            return file.read()
    except (PermissionError, OSError):
        return None
