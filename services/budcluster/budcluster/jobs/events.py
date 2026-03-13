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


"""Publish job lifecycle events to Dapr pub/sub for pipeline integration."""

from __future__ import annotations

from typing import Any

from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.dapr_service import DaprService


logger = get_logger(__name__)

# Topic where BudPipeline listens for events
PIPELINE_EVENTS_TOPIC = "budpipelineEvents"


def publish_job_event(
    job_id: str,
    job_type: str,
    source: str,
    source_id: str | None,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Publish a job completion/failure event to the BudPipeline events topic.

    Args:
        job_id: The job UUID as string (used as workflow_id correlation)
        job_type: Job type string (e.g., "helm_deploy")
        source: Job source string (e.g., "budpipeline")
        source_id: Source service entity ID
        status: "COMPLETED" or "FAILED"
        result: Result dict on success (namespace, release_name, endpoint_url, services)
        error: Error message on failure
    """
    event_type = "job_completed" if status == "COMPLETED" else "job_failed"

    event_data = {
        "type": event_type,
        "workflow_id": job_id,
        "payload": {
            "job_id": job_id,
            "job_type": job_type,
            "source": source,
            "source_id": source_id,
            "status": status,
            "content": {
                "result": result or {},
                "status": status,
            },
        },
    }
    if error:
        event_data["payload"]["error"] = error

    try:
        with DaprService() as dapr_service:
            dapr_service.publish_to_topic(
                data=event_data,
                target_topic_name=PIPELINE_EVENTS_TOPIC,
                target_name=None,
                event_type=event_type,
            )
        logger.info(f"Job event published: job_id={job_id}, event_type={event_type}, topic={PIPELINE_EVENTS_TOPIC}")
    except Exception:
        logger.exception(f"Failed to publish job event: job_id={job_id}, event_type={event_type}")
