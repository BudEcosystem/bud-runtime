from typing import Optional
import pytest
from uuid import uuid4

from budsim.shared.dapr_service import DaprService


@pytest.mark.asyncio
async def test_pubsub(dapr_http_port: int, dapr_api_token: str) -> None:
    """Test the pubsub publish method."""
    with DaprService(dapr_http_port=dapr_http_port, dapr_api_token=dapr_api_token) as dapr_service:
        await dapr_service.publish_to_topic(
            pubsub_name="pubsub-redis",
            target_topic_name="notificationMessages",
            data={"subscriber_id": str(uuid4()), "title": "Test", "message": "Hello, World!"},
            event_type="notification",
        )
