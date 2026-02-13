"""Unit tests for event publishing.

Tests for T043 (002-pipeline-event-persistence):
- Multi-topic publishing (FR-013)
- Event types (FR-012)
- Non-blocking publishing (FR-014)
- Correlation IDs in events (FR-015)
- Retry queue (FR-046)
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from budpipeline.progress.publisher import EventPublisher, EventType, RetryableEvent


@pytest.fixture
def event_publisher():
    """Create a fresh event publisher instance."""
    return EventPublisher(
        pubsub_name="test-pubsub",
        max_queue_size=100,
        retry_interval_seconds=1,
    )


@pytest.fixture
def execution_id():
    """Generate a random execution ID."""
    return uuid4()


class TestMultiTopicPublishing:
    """Tests for multi-topic publishing (FR-013)."""

    @pytest.mark.asyncio
    async def test_publish_to_multiple_topics(self, event_publisher, execution_id):
        """Test that events are published to all active topics."""
        active_topics = ["topic1", "topic2", "topic3"]

        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=active_topics)

            with patch(
                "budpipeline.progress.publisher.EventPublisher._publish_single_topic",
                new_callable=AsyncMock,
            ) as mock_publish:
                mock_publish.return_value = True

                topics = await event_publisher.publish_to_topics(
                    execution_id=execution_id,
                    event_type=EventType.WORKFLOW_PROGRESS,
                    data={"progress_percentage": 50.0},
                )

        # Should return all topics
        assert set(topics) == set(active_topics)

    @pytest.mark.asyncio
    async def test_publish_no_active_topics(self, event_publisher, execution_id):
        """Test publishing when no topics are active."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=[])

            topics = await event_publisher.publish_to_topics(
                execution_id=execution_id,
                event_type=EventType.WORKFLOW_PROGRESS,
                data={"progress_percentage": 50.0},
            )

        assert topics == []

    @pytest.mark.asyncio
    async def test_publish_is_non_blocking(self, event_publisher, execution_id):
        """Test that publishing is non-blocking (FR-014)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            # Make publish slow
            async def slow_publish(*args, **kwargs):
                await asyncio.sleep(0.5)
                return True

            with patch.object(event_publisher, "_publish_single_topic", side_effect=slow_publish):
                start_time = asyncio.get_event_loop().time()
                topics = await event_publisher.publish_to_topics(
                    execution_id=execution_id,
                    event_type=EventType.WORKFLOW_PROGRESS,
                    data={"progress_percentage": 50.0},
                )
                elapsed = asyncio.get_event_loop().time() - start_time

        # Should return immediately, not wait for publish
        assert elapsed < 0.1  # Much less than 0.5s
        assert topics == ["topic1"]


class TestEventTypes:
    """Tests for event types (FR-012)."""

    @pytest.mark.asyncio
    async def test_workflow_progress_event(self, event_publisher, execution_id):
        """Test workflow progress event structure (NotificationPayload format)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []
            captured_event_types = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                captured_event_types.append(event_type)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_workflow_progress(
                    execution_id=execution_id,
                    progress_percentage=Decimal("75.00"),
                    eta_seconds=120,
                    current_step="Processing data",
                )

                # Give async task time to run
                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert captured_event_types[0] == EventType.WORKFLOW_PROGRESS
        assert payload["notification_type"] == "EVENT"
        assert payload["payload"]["type"] == "pipeline_execution"
        assert payload["payload"]["event"] == "progress"
        assert payload["payload"]["content"]["status"] == "RUNNING"
        assert "75.0%" in payload["payload"]["content"]["message"]

    @pytest.mark.asyncio
    async def test_workflow_progress_with_notification_workflow_id(
        self, event_publisher, execution_id
    ):
        """Test that notification_workflow_id overrides payload.workflow_id in convenience methods."""
        custom_wf_id = "external-wf-999"

        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_workflow_progress(
                    execution_id=execution_id,
                    progress_percentage=Decimal("50.00"),
                    notification_workflow_id=custom_wf_id,
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        assert published_payloads[0]["payload"]["workflow_id"] == custom_wf_id

    @pytest.mark.asyncio
    async def test_step_started_event(self, event_publisher, execution_id):
        """Test step started event structure (NotificationPayload format)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []
            captured_event_types = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                captured_event_types.append(event_type)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_step_started(
                    execution_id=execution_id,
                    step_id="step1",
                    step_name="First Step",
                    sequence_number=1,
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert captured_event_types[0] == EventType.STEP_STARTED
        assert payload["payload"]["event"] == "step1"
        assert payload["payload"]["content"]["title"] == "First Step"
        assert payload["payload"]["content"]["status"] == "STARTED"
        assert payload["payload"]["content"]["result"]["sequence_number"] == 1

    @pytest.mark.asyncio
    async def test_step_completed_event(self, event_publisher, execution_id):
        """Test step completed event structure (NotificationPayload format)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []
            captured_event_types = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                captured_event_types.append(event_type)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_step_completed(
                    execution_id=execution_id,
                    step_id="step1",
                    step_name="First Step",
                    progress_percentage=Decimal("50.00"),
                    duration_seconds=30,
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert captured_event_types[0] == EventType.STEP_COMPLETED
        assert payload["payload"]["content"]["status"] == "COMPLETED"
        assert payload["payload"]["content"]["result"]["duration_seconds"] == 30

    @pytest.mark.asyncio
    async def test_step_failed_event(self, event_publisher, execution_id):
        """Test step failed event structure (NotificationPayload format)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []
            captured_event_types = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                captured_event_types.append(event_type)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_step_failed(
                    execution_id=execution_id,
                    step_id="step1",
                    step_name="First Step",
                    error_message="Connection timeout",
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert captured_event_types[0] == EventType.STEP_FAILED
        assert payload["payload"]["content"]["status"] == "FAILED"
        assert payload["payload"]["content"]["message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_workflow_completed_success_event(self, event_publisher, execution_id):
        """Test workflow completed (success) event structure (NotificationPayload format)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []
            captured_event_types = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                captured_event_types.append(event_type)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_workflow_completed(
                    execution_id=execution_id,
                    success=True,
                    final_outputs={"result": "value"},
                    final_message="Completed successfully",
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert captured_event_types[0] == EventType.WORKFLOW_COMPLETED
        assert payload["payload"]["event"] == "results"
        assert payload["payload"]["content"]["status"] == "COMPLETED"
        assert payload["payload"]["content"]["result"]["success"] is True

    @pytest.mark.asyncio
    async def test_workflow_completed_failure_event(self, event_publisher, execution_id):
        """Test workflow completed (failure) event structure (NotificationPayload format)."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []
            captured_event_types = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                captured_event_types.append(event_type)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_workflow_completed(
                    execution_id=execution_id,
                    success=False,
                    final_message="Step 3 failed",
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert captured_event_types[0] == EventType.WORKFLOW_FAILED
        assert payload["payload"]["event"] == "results"
        assert payload["payload"]["content"]["status"] == "FAILED"
        assert payload["payload"]["content"]["result"]["success"] is False


class TestCorrelationIds:
    """Tests for correlation IDs in events (FR-015)."""

    @pytest.mark.asyncio
    async def test_correlation_id_included(self, event_publisher, execution_id):
        """Test that correlation ID is included in event payload."""
        correlation_id = "test-corr-123"

        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_workflow_progress(
                    execution_id=execution_id,
                    progress_percentage=Decimal("50.00"),
                    correlation_id=correlation_id,
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert payload["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_execution_id_always_included(self, event_publisher, execution_id):
        """Test that execution ID is always included in event payload."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(*, topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_to_topics(
                    execution_id=execution_id,
                    event_type=EventType.WORKFLOW_PROGRESS,
                    data={"test": "data"},
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert payload["payload"]["workflow_id"] == str(execution_id)

    @pytest.mark.asyncio
    async def test_step_id_included_for_step_events(self, event_publisher, execution_id):
        """Test that step ID is used as payload.event for step-level events."""
        step_id = "step1"

        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(*, topic, execution_id, event_type, payload):
                published_payloads.append(payload)
                return True

            with patch.object(
                event_publisher, "_publish_single_topic", side_effect=capture_payload
            ):
                await event_publisher.publish_step_completed(
                    execution_id=execution_id,
                    step_id=step_id,
                    step_name="First Step",
                    progress_percentage=Decimal("25.00"),
                )

                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert payload["payload"]["event"] == step_id


class TestRetryQueue:
    """Tests for retry queue (FR-046)."""

    def test_retryable_event_can_retry(self):
        """Test RetryableEvent retry logic."""
        event = RetryableEvent(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=uuid4(),
            topic="topic1",
            payload={"test": "data"},
            max_retries=3,
        )

        assert event.can_retry() is True
        event.retry_count = 3
        assert event.can_retry() is False

    @pytest.mark.asyncio
    async def test_failed_publish_queues_for_retry(self, event_publisher, execution_id):
        """Test that failed publish is queued for retry."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            # Mock Dapr client to raise exception
            with patch("dapr.aio.clients.DaprClient") as mock_dapr:
                mock_client = AsyncMock()
                mock_client.publish_event = AsyncMock(side_effect=Exception("Connection failed"))
                mock_dapr.return_value.__aenter__.return_value = mock_client

                await event_publisher.publish_to_topics(
                    execution_id=execution_id,
                    event_type=EventType.WORKFLOW_PROGRESS,
                    data={"test": "data"},
                )

                # Give async task time to run
                await asyncio.sleep(0.1)

        assert event_publisher.retry_queue_size > 0

    def test_queue_max_size_drops_oldest(self, event_publisher, execution_id):
        """Test that queue drops oldest event when full."""
        event_publisher._retry_queue.clear()
        event_publisher.max_queue_size = 3

        # Fill queue
        for i in range(4):
            event_publisher._queue_for_retry(
                event_type=EventType.WORKFLOW_PROGRESS,
                execution_id=execution_id,
                topic=f"topic{i}",
                payload={"index": i},
            )

        # Should only have 3 events (oldest dropped)
        assert event_publisher.retry_queue_size == 3

    @pytest.mark.asyncio
    async def test_retry_processor_processes_events(self, event_publisher, execution_id):
        """Test that retry processor processes queued events."""
        # Queue an event
        event_publisher._queue_for_retry(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            topic="topic1",
            payload={"test": "data"},
        )

        published_count = [0]

        async def mock_publish(*args, **kwargs):
            published_count[0] += 1
            return True

        with patch.object(event_publisher, "_publish_single_topic", side_effect=mock_publish):
            # Start processor
            await event_publisher.start()

            # Wait for retry interval + processing
            await asyncio.sleep(2)

            # Stop processor
            await event_publisher.stop()

        # Should have processed the queued event
        assert published_count[0] >= 1

    @pytest.mark.asyncio
    async def test_event_dropped_after_max_retries(self, event_publisher, execution_id):
        """Test that events are dropped after max retries."""
        # Create event that's exceeded retries
        event = RetryableEvent(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            topic="topic1",
            payload={"test": "data"},
            retry_count=3,  # Already at max
            max_retries=3,
        )
        event_publisher._retry_queue.append(event)

        async def failing_publish(*args, **kwargs):
            return False

        with patch.object(event_publisher, "_publish_single_topic", side_effect=failing_publish):
            await event_publisher.start()
            await asyncio.sleep(2)
            await event_publisher.stop()

        # Event should have been dropped (not re-queued)
        # Queue should be empty
        assert event_publisher.retry_queue_size == 0


class TestEventPayloadStructure:
    """Tests for NotificationPayload event structure."""

    def test_build_event_payload_required_fields(self, event_publisher, execution_id):
        """Test that required NotificationPayload fields are always present."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={"progress_percentage": 50.0},
        )

        assert payload["notification_type"] == "EVENT"
        assert payload["name"] == "bud-notification"
        assert "payload" in payload
        assert payload["payload"]["category"] == "internal"
        assert payload["payload"]["type"] == "pipeline_execution"
        assert payload["payload"]["workflow_id"] == str(execution_id)
        assert payload["payload"]["source"] == "budpipeline"
        assert "content" in payload["payload"]
        assert "title" in payload["payload"]["content"]
        assert "message" in payload["payload"]["content"]
        assert "status" in payload["payload"]["content"]

    def test_build_event_payload_optional_fields(self, event_publisher, execution_id):
        """Test optional fields are included when provided."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.STEP_COMPLETED,
            execution_id=execution_id,
            data={"step_name": "My Step", "progress_percentage": 50.0},
            correlation_id="corr-123",
            step_id="step1",
        )

        assert payload["correlation_id"] == "corr-123"
        assert payload["payload"]["event"] == "step1"

    def test_build_event_payload_custom_payload_type(self, event_publisher, execution_id):
        """Test that custom payload_type overrides default."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={},
            payload_type="model_benchmark",
        )

        assert payload["payload"]["type"] == "model_benchmark"

    def test_build_event_payload_subscriber_ids(self, event_publisher, execution_id):
        """Test that subscriber_ids is included in payload."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={},
            subscriber_ids="user-123",
        )

        assert payload["subscriber_ids"] == "user-123"

    def test_build_event_payload_notification_workflow_id_override(
        self, event_publisher, execution_id
    ):
        """Test that notification_workflow_id overrides payload.workflow_id."""
        custom_workflow_id = "external-workflow-abc-123"
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={},
            notification_workflow_id=custom_workflow_id,
        )

        assert payload["payload"]["workflow_id"] == custom_workflow_id
        assert payload["payload"]["workflow_id"] != str(execution_id)

    def test_build_event_payload_notification_workflow_id_default(
        self, event_publisher, execution_id
    ):
        """Test that payload.workflow_id defaults to execution_id when notification_workflow_id is None."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={},
            notification_workflow_id=None,
        )

        assert payload["payload"]["workflow_id"] == str(execution_id)

    def test_build_event_payload_notification_workflow_id_empty_string_uses_execution_id(
        self, event_publisher, execution_id
    ):
        """Test that empty string notification_workflow_id falls back to execution_id."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={},
            notification_workflow_id="",
        )

        assert payload["payload"]["workflow_id"] == str(execution_id)

    def test_build_event_payload_status_mapping(self, event_publisher, execution_id):
        """Test that event types map to correct content.status."""
        test_cases = [
            (EventType.STEP_STARTED, "STARTED"),
            (EventType.STEP_COMPLETED, "COMPLETED"),
            (EventType.STEP_FAILED, "FAILED"),
            (EventType.WORKFLOW_PROGRESS, "RUNNING"),
            (EventType.WORKFLOW_COMPLETED, "COMPLETED"),
            (EventType.WORKFLOW_FAILED, "FAILED"),
            (EventType.ETA_UPDATE, "RUNNING"),
        ]

        for event_type, expected_status in test_cases:
            payload = event_publisher._build_event_payload(
                event_type=event_type,
                execution_id=execution_id,
                data={},
            )
            assert payload["payload"]["content"]["status"] == expected_status, (
                f"Event {event_type} should map to status {expected_status}"
            )


class TestDualPublish:
    """Tests for dual-publish to budnotify when subscriber_ids is set."""

    @pytest.mark.asyncio
    async def test_dual_publish_with_subscriber_ids(self, event_publisher, execution_id):
        """Test that events are published to both budnotify and callback topics."""
        with (
            patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service,
            patch("budpipeline.progress.publisher.settings") as mock_settings,
        ):
            mock_sub_service.get_active_topics = AsyncMock(return_value=["callback-topic"])
            mock_settings.notify_service_topic = "budnotify-topic"
            mock_settings.dapr_pubsub_name = "pubsub"

            published_topics = []

            async def capture_topic(topic, execution_id, event_type, payload):
                published_topics.append(topic)
                return True

            with patch.object(event_publisher, "_publish_single_topic", side_effect=capture_topic):
                topics = await event_publisher.publish_to_topics(
                    execution_id=execution_id,
                    event_type=EventType.WORKFLOW_PROGRESS,
                    data={"progress_percentage": 50.0},
                    subscriber_ids="user-123",
                )

                await asyncio.sleep(0.1)

        # Should include both budnotify topic and callback topic
        assert "budnotify-topic" in topics
        assert "callback-topic" in topics

    @pytest.mark.asyncio
    async def test_no_dual_publish_without_subscriber_ids(self, event_publisher, execution_id):
        """Test that without subscriber_ids, only callback topics are used."""
        with (
            patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service,
            patch("budpipeline.progress.publisher.settings") as mock_settings,
        ):
            mock_sub_service.get_active_topics = AsyncMock(return_value=["callback-topic"])
            mock_settings.notify_service_topic = "budnotify-topic"

            topics = await event_publisher.publish_to_topics(
                execution_id=execution_id,
                event_type=EventType.WORKFLOW_PROGRESS,
                data={"progress_percentage": 50.0},
            )

        # Only callback topics, no budnotify
        assert topics == ["callback-topic"]

    @pytest.mark.asyncio
    async def test_no_dual_publish_without_notify_topic(self, event_publisher, execution_id):
        """Test that without notify_service_topic config, no dual-publish occurs."""
        with (
            patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service,
            patch("budpipeline.progress.publisher.settings") as mock_settings,
        ):
            mock_sub_service.get_active_topics = AsyncMock(return_value=["callback-topic"])
            mock_settings.notify_service_topic = None

            topics = await event_publisher.publish_to_topics(
                execution_id=execution_id,
                event_type=EventType.WORKFLOW_PROGRESS,
                data={"progress_percentage": 50.0},
                subscriber_ids="user-123",
            )

        # Only callback topics even with subscriber_ids
        assert topics == ["callback-topic"]
