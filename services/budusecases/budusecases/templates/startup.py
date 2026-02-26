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

"""Startup synchronization for templates."""

import logging
from collections.abc import Callable
from typing import Any

from .sync import TemplateSyncService

logger = logging.getLogger(__name__)


def sync_templates_on_startup(
    session_maker: Callable[[], Any],
    enabled: bool = True,
    templates_path: str | None = None,
) -> None:
    """Synchronize templates on application startup.

    This function should be called during application initialization
    to ensure database templates are in sync with YAML files.

    Args:
        session_maker: Callable that returns a database session.
        enabled: Whether to perform the sync.
        templates_path: Optional path to templates directory.
    """
    if not enabled:
        logger.debug("Template sync on startup is disabled")
        return

    logger.info("Starting template synchronization...")

    try:
        with session_maker() as session:
            service = TemplateSyncService(
                session=session,
                templates_path=templates_path,
            )
            result = service.sync_templates(delete_orphans=False)

            logger.info(
                f"Template sync completed: "
                f"created={result.created}, "
                f"updated={result.updated}, "
                f"skipped={result.skipped}"
            )

            if result.errors:
                for error in result.errors:
                    logger.warning(f"Template sync error: {error}")

    except Exception as e:
        logger.error(f"Template sync failed: {e}")
        # Don't re-raise - we don't want to prevent app startup
