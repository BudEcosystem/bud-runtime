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

"""Provides logging utilities and preconfigured loggers for consistent and structured logging across the microservices."""

import logging.config
from enum import Enum
from pathlib import Path
from typing import Any, Union

import structlog
from structlog import BoundLogger


def configure_logging(log_dir: Union[str, Path], log_level: Any) -> None:
    """Configure logging settings for the application.

    Set up logging with the specified log directory and log level. This function configures the logging handlers
    and formatters to ensure that logs are written to the specified directory with the desired log level.

    Args:
        log_dir (str | Path): Directory where log files will be stored. This can be a string path or a Path object.
        log_level (Any): The log level to set for the logger. It should be one of the standard logging levels
                         such as logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, or logging.CRITICAL.

    Returns:
        None: This function does not return any value.
    """
    log_dir = Path(log_dir) if isinstance(log_dir, str) else log_dir
    log_dir.mkdir(exist_ok=True, parents=True)

    if isinstance(log_level, Enum):
        log_level = log_level.value
    elif isinstance(log_level, str):
        log_level = log_level.upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json_formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(),
                },
                "plain_formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(),
                },
            },
            "handlers": {
                "console_plain": {
                    "class": "logging.StreamHandler",
                    "formatter": "plain_formatter",
                },
                "console_json": {
                    "class": "logging.StreamHandler",
                    "formatter": "json_formatter",
                },
                "plain_file": {
                    "class": "logging.handlers.WatchedFileHandler",
                    "filename": f"{log_dir.as_posix()}/app.log",
                    "formatter": "plain_formatter",
                },
                "json_file": {
                    "class": "logging.handlers.WatchedFileHandler",
                    "filename": f"{log_dir.as_posix()}/app.log",
                    "formatter": "json_formatter",
                },
            },
            "loggers": {
                "structlog": {
                    "handlers": ["console_json"],
                    "level": log_level,
                },
                "root": {
                    "handlers": ["console_json"],
                    "level": log_level,
                },
            },
        }
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    """Retrieve a logger instance with the specified name.

    Obtain a `BoundLogger` instance from `structlog` with the given name. This logger can be used to log messages
    with the provided logger name.

    Args:
        name (str): The name to associate with the logger instance.

    Returns:
        BoundLogger: A `BoundLogger` instance configured with the specified name.
    """
    return structlog.get_logger(name)
