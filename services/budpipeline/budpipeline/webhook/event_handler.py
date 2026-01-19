"""Event Handler - processes platform events and triggers matching workflows.

Handles events from the budpipelineEvents pub/sub topic and triggers
any matching event-driven workflows.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from budpipeline.commons.database import get_db_session
from budpipeline.pipeline.service import workflow_service
from budpipeline.scheduler.services import event_trigger_service
from budpipeline.scheduler.storage import schedule_storage

logger = logging.getLogger(__name__)


class EventHandler:
    """Handles platform events and triggers matching workflows.

    Processes events from the Dapr pub/sub topic and checks for
    event triggers that match. When a match is found, executes
    the associated workflow.
    """

    async def handle_event(self, event_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Handle an incoming platform event and trigger matching workflows.

        Called from the /workflow-events endpoint when a non-completion
        event is received.

        Args:
            event_data: The event data from pub/sub

        Returns:
            List of trigger results (execution IDs and statuses)
        """
        event_type = event_data.get("type")

        # Skip completion events (handled separately)
        if event_type == "workflow_completed":
            return []

        # Skip unsupported events
        if event_type not in event_trigger_service.SUPPORTED_EVENTS:
            logger.debug(f"Event type '{event_type}' not supported for triggers")
            return []

        logger.info(f"Processing event for triggers: type={event_type}")

        # Find all triggers for this event type
        try:
            triggers = await schedule_storage.list_event_triggers(
                event_type=event_type,
                enabled=True,
            )
        except Exception as e:
            logger.error(f"Failed to list event triggers: {e}")
            return []

        if not triggers:
            logger.debug(f"No triggers configured for event type: {event_type}")
            return []

        logger.info(f"Found {len(triggers)} triggers for event type: {event_type}")

        results: list[dict[str, Any]] = []

        for trigger in triggers:
            # Check filters
            if trigger.filters and not event_trigger_service.matches_filters(
                event_data, trigger.filters
            ):
                logger.debug(f"Trigger {trigger.id} filters did not match event data")
                continue

            # Build trigger info
            trigger_info = {
                "type": "event",
                "trigger_id": trigger.id,
                "trigger_name": trigger.name,
                "event_type": event_type,
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }

            # Merge params
            merged_params = {
                **trigger.params,
                "event": event_data,
                "_trigger": trigger_info,
            }

            # Execute workflow
            try:
                logger.info(
                    f"Triggering workflow {trigger.workflow_id} from event trigger {trigger.id}"
                )

                async with get_db_session() as session:
                    result = await workflow_service.execute_pipeline_async(
                        session=session,
                        pipeline_id=trigger.workflow_id,
                        params=merged_params,
                    )

                # Update trigger stats
                await schedule_storage.update_event_trigger_triggered(trigger.id)

                results.append(
                    {
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "workflow_id": trigger.workflow_id,
                        "execution_id": result.get("execution_id", ""),
                        "status": "triggered",
                    }
                )

                logger.info(
                    f"Event trigger {trigger.id} executed workflow {trigger.workflow_id}, "
                    f"execution_id={result.get('execution_id')}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to trigger workflow for event {event_type} "
                    f"via trigger {trigger.id}: {e}"
                )
                results.append(
                    {
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "workflow_id": trigger.workflow_id,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        if results:
            triggered_count = sum(1 for r in results if r.get("status") == "triggered")
            logger.info(
                f"Event {event_type} triggered {triggered_count} workflows, "
                f"{len(results) - triggered_count} failed"
            )

        return results


# Global instance
event_handler = EventHandler()
