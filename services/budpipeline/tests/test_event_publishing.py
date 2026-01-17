"""Unit tests for event publishing.

Tests for T043 (002-pipeline-event-persistence):
- Multi-topic publishing (FR-013)
- Event types (FR-012)
- Non-blocking publishing (FR-014)
- Correlation IDs in events (FR-015)
- Retry queue (FR-046)
"""

import asyncio
from datetime import datetime
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
        """Test workflow progress event structure."""
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
                    progress_percentage=Decimal("75.00"),
                    eta_seconds=120,
                    current_step="Processing data",
                )

                # Give async task time to run
                await asyncio.sleep(0.1)

        assert len(published_payloads) == 1
        payload = published_payloads[0]
        assert payload["type"] == EventType.WORKFLOW_PROGRESS
        assert payload["data"]["progress_percentage"] == 75.0
        assert payload["data"]["eta_seconds"] == 120
        assert payload["data"]["current_step"] == "Processing data"

    @pytest.mark.asyncio
    async def test_step_started_event(self, event_publisher, execution_id):
        """Test step started event structure."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
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
        assert payload["type"] == EventType.STEP_STARTED
        assert payload["step_id"] == "step1"
        assert payload["data"]["step_name"] == "First Step"
        assert payload["data"]["sequence_number"] == 1

    @pytest.mark.asyncio
    async def test_step_completed_event(self, event_publisher, execution_id):
        """Test step completed event structure."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
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
        assert payload["type"] == EventType.STEP_COMPLETED
        assert payload["data"]["duration_seconds"] == 30

    @pytest.mark.asyncio
    async def test_step_failed_event(self, event_publisher, execution_id):
        """Test step failed event structure."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
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
        assert payload["type"] == EventType.STEP_FAILED
        assert payload["data"]["error_message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_workflow_completed_success_event(self, event_publisher, execution_id):
        """Test workflow completed (success) event structure."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
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
        assert payload["type"] == EventType.WORKFLOW_COMPLETED
        assert payload["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_workflow_completed_failure_event(self, event_publisher, execution_id):
        """Test workflow completed (failure) event structure."""
        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, execution_id, event_type, payload):
                published_payloads.append(payload)
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
        assert payload["type"] == EventType.WORKFLOW_FAILED
        assert payload["data"]["success"] is False


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

            async def capture_payload(topic, exec_id, event_type, payload):
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
        assert payload["execution_id"] == str(execution_id)

    @pytest.mark.asyncio
    async def test_step_id_included_for_step_events(self, event_publisher, execution_id):
        """Test that step ID is included for step-level events."""
        step_id = "step1"

        with patch("budpipeline.progress.publisher.subscription_service") as mock_sub_service:
            mock_sub_service.get_active_topics = AsyncMock(return_value=["topic1"])

            published_payloads = []

            async def capture_payload(topic, exec_id, event_type, payload):
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
        assert payload["step_id"] == step_id


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
            with patch("budpipeline.progress.publisher.DaprClient") as mock_dapr:
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
    """Tests for event payload structure."""

    def test_build_event_payload_required_fields(self, event_publisher, execution_id):
        """Test that required fields are always present."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={"test": "data"},
        )

        assert "type" in payload
        assert "execution_id" in payload
        assert "timestamp" in payload
        assert "data" in payload

    def test_build_event_payload_optional_fields(self, event_publisher, execution_id):
        """Test optional fields are included when provided."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.STEP_COMPLETED,
            execution_id=execution_id,
            data={"test": "data"},
            correlation_id="corr-123",
            step_id="step1",
        )

        assert payload["correlation_id"] == "corr-123"
        assert payload["step_id"] == "step1"

    def test_build_event_payload_timestamp_format(self, event_publisher, execution_id):
        """Test that timestamp is in ISO format."""
        payload = event_publisher._build_event_payload(
            event_type=EventType.WORKFLOW_PROGRESS,
            execution_id=execution_id,
            data={},
        )

        # Should be parseable as ISO format
        timestamp = payload["timestamp"]
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
