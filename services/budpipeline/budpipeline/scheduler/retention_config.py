"""Scheduler configuration for budpipeline service.

This module configures scheduled jobs including the retention cleanup
workflow (002-pipeline-event-persistence - T063).
"""

from budpipeline.commons.config import settings
from budpipeline.commons.observability import get_logger

logger = get_logger(__name__)


# Dapr cron binding name for retention cleanup
RETENTION_CLEANUP_BINDING = "retention-cleanup"


def get_dapr_bindings_config() -> list[dict]:
    """Get Dapr bindings configuration for scheduled jobs.

    Returns:
        List of Dapr binding configurations.
    """
    return [
        {
            "name": "schedule-poll",
            "type": "bindings.cron",
            "metadata": [
                {"name": "schedule", "value": "* * * * *"},  # Every minute
            ],
        },
        {
            "name": RETENTION_CLEANUP_BINDING,
            "type": "bindings.cron",
            "metadata": [
                {"name": "schedule", "value": settings.pipeline_cleanup_schedule},
            ],
        },
    ]


def log_scheduler_config():
    """Log the scheduler configuration at startup."""
    logger.info(
        "Scheduler configuration",
        schedule_poll="* * * * * (every minute)",
        retention_cleanup=settings.pipeline_cleanup_schedule,
        retention_days=settings.pipeline_retention_days,
    )
