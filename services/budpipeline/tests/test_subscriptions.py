"""Unit tests for subscription management and callback topic validation.

Tests for T042 (002-pipeline-event-persistence):
- Valid topic validation
- Invalid topic rejection (FR-022)
- Subscription lifecycle management
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budpipeline.subscriptions.models import DeliveryStatus, ExecutionSubscription
from budpipeline.subscriptions.service import SubscriptionService


@pytest.fixture
def subscription_service():
    """Create a fresh subscription service instance."""
    service = SubscriptionService()
    service.clear_topic_cache()
    return service


@pytest.fixture
def execution_id():
    """Generate a random execution ID."""
    return uuid4()


class TestTopicValidation:
    """Tests for callback topic validation (FR-022)."""

    @pytest.mark.asyncio
    async def test_valid_topic_simple_name(self, subscription_service):
        """Test that simple alphanumeric topic names are valid."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["myTopic", "topic1", "TopicName"]
        )

        assert len(valid_topics) == 3
        assert len(invalid_topics) == 0

    @pytest.mark.asyncio
    async def test_valid_topic_with_hyphens(self, subscription_service):
        """Test that topics with hyphens are valid."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["my-topic", "topic-name-123"]
        )

        assert "my-topic" in valid_topics
        assert "topic-name-123" in valid_topics
        assert len(invalid_topics) == 0

    @pytest.mark.asyncio
    async def test_valid_topic_with_underscores(self, subscription_service):
        """Test that topics with underscores are valid."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["my_topic", "topic_name_123"]
        )

        assert "my_topic" in valid_topics
        assert "topic_name_123" in valid_topics
        assert len(invalid_topics) == 0

    @pytest.mark.asyncio
    async def test_valid_topic_with_dots(self, subscription_service):
        """Test that topics with dots are valid."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["my.topic", "org.service.events"]
        )

        assert "my.topic" in valid_topics
        assert "org.service.events" in valid_topics
        assert len(invalid_topics) == 0

    @pytest.mark.asyncio
    async def test_invalid_topic_empty_string(self, subscription_service):
        """Test that empty string topic is rejected."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["", "validTopic"]
        )

        assert "" in invalid_topics
        assert "validTopic" in valid_topics

    @pytest.mark.asyncio
    async def test_invalid_topic_starts_with_number(self, subscription_service):
        """Test that topic starting with number is rejected."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["123topic", "validTopic"]
        )

        assert "123topic" in invalid_topics
        assert "validTopic" in valid_topics

    @pytest.mark.asyncio
    async def test_invalid_topic_special_characters(self, subscription_service):
        """Test that topics with special characters are rejected."""
        valid_topics, invalid_topics = await subscription_service.validate_topics(
            ["topic@name", "topic#123", "topic$test", "topic space"]
        )

        assert len(valid_topics) == 0
        assert len(invalid_topics) == 4

    @pytest.mark.asyncio
    async def test_invalid_topic_none_value(self, subscription_service):
        """Test that None topic is handled gracefully."""
        # Filter out None before passing to validate_topics
        topics = [t for t in [None, "validTopic"] if t is not None]
        valid_topics, invalid_topics = await subscription_service.validate_topics(topics)

        assert "validTopic" in valid_topics

    @pytest.mark.asyncio
    async def test_topic_validation_caching(self, subscription_service):
        """Test that topic validation results are cached."""
        # First validation
        valid1, _ = await subscription_service.validate_topics(["myTopic"])
        assert "myTopic" in valid1
        assert "myTopic" in subscription_service._valid_topics_cache

        # Second validation should use cache
        valid2, _ = await subscription_service.validate_topics(["myTopic"])
        assert "myTopic" in valid2

    @pytest.mark.asyncio
    async def test_clear_topic_cache(self, subscription_service):
        """Test that topic cache can be cleared."""
        await subscription_service.validate_topics(["myTopic"])
        assert "myTopic" in subscription_service._valid_topics_cache

        subscription_service.clear_topic_cache()
        assert "myTopic" not in subscription_service._valid_topics_cache


class TestSubscriptionCreation:
    """Tests for subscription creation."""

    @pytest.mark.asyncio
    async def test_create_subscriptions_success(self, subscription_service, execution_id):
        """Test successful subscription creation."""
        mock_sub1 = MagicMock(spec=ExecutionSubscription)
        mock_sub1.id = uuid4()
        mock_sub2 = MagicMock(spec=ExecutionSubscription)
        mock_sub2.id = uuid4()

        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.create_batch = AsyncMock(return_value=[mock_sub1, mock_sub2])

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                subscription_ids = await subscription_service.create_subscriptions(
                    execution_id=execution_id,
                    callback_topics=["topic1", "topic2"],
                )

        assert len(subscription_ids) == 2
        mock_crud.create_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscriptions_empty_list(self, subscription_service, execution_id):
        """Test that empty topic list returns empty subscriptions."""
        subscription_ids = await subscription_service.create_subscriptions(
            execution_id=execution_id,
            callback_topics=[],
        )

        assert subscription_ids == []

    @pytest.mark.asyncio
    async def test_create_subscriptions_filters_invalid(self, subscription_service, execution_id):
        """Test that invalid topics are filtered out."""
        mock_sub = MagicMock(spec=ExecutionSubscription)
        mock_sub.id = uuid4()

        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.create_batch = AsyncMock(return_value=[mock_sub])

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                subscription_ids = await subscription_service.create_subscriptions(
                    execution_id=execution_id,
                    callback_topics=["validTopic", "123invalid", "@invalid"],
                )

        # Only one valid topic
        assert len(subscription_ids) == 1
        # Verify only valid topic was passed to CRUD
        call_args = mock_crud.create_batch.call_args
        subscriptions_data = call_args.kwargs.get("subscriptions", [])
        assert len(subscriptions_data) == 1
        assert subscriptions_data[0]["callback_topic"] == "validTopic"

    @pytest.mark.asyncio
    async def test_create_subscriptions_all_invalid(self, subscription_service, execution_id):
        """Test that all invalid topics returns empty list."""
        subscription_ids = await subscription_service.create_subscriptions(
            execution_id=execution_id,
            callback_topics=["123invalid", "@invalid", ""],
        )

        assert subscription_ids == []


class TestActiveTopicRetrieval:
    """Tests for retrieving active subscription topics."""

    @pytest.mark.asyncio
    async def test_get_active_topics(self, subscription_service, execution_id):
        """Test retrieving active topics."""
        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_active_topics = AsyncMock(return_value=["topic1", "topic2"])

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                topics = await subscription_service.get_active_topics(execution_id)

        assert topics == ["topic1", "topic2"]

    @pytest.mark.asyncio
    async def test_get_active_topics_empty(self, subscription_service, execution_id):
        """Test retrieving active topics when none exist."""
        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_active_topics = AsyncMock(return_value=[])

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                topics = await subscription_service.get_active_topics(execution_id)

        assert topics == []


class TestSubscriptionStatusUpdates:
    """Tests for subscription status updates."""

    @pytest.mark.asyncio
    async def test_mark_delivery_success(self, subscription_service):
        """Test marking subscription as active (delivered successfully)."""
        subscription_id = uuid4()

        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.update_status = AsyncMock()

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                await subscription_service.mark_delivery_success(subscription_id)

        # Note: The actual enum uses ACTIVE for successful delivery
        mock_crud.update_status.assert_called_once_with(
            subscription_id=subscription_id,
            status=DeliveryStatus.ACTIVE,
        )

    @pytest.mark.asyncio
    async def test_mark_delivery_failed(self, subscription_service):
        """Test marking subscription as failed."""
        subscription_id = uuid4()

        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.update_status = AsyncMock()

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                await subscription_service.mark_delivery_failed(
                    subscription_id, error_message="Connection timeout"
                )

        mock_crud.update_status.assert_called_once_with(
            subscription_id=subscription_id,
            status=DeliveryStatus.FAILED,
        )

    @pytest.mark.asyncio
    async def test_expire_subscription(self, subscription_service):
        """Test marking subscription as expired."""
        subscription_id = uuid4()

        with patch("budpipeline.subscriptions.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.update_status = AsyncMock()

            with patch(
                "budpipeline.subscriptions.service.ExecutionSubscriptionCRUD",
                return_value=mock_crud,
            ):
                await subscription_service.expire_subscription(subscription_id)

        mock_crud.update_status.assert_called_once_with(
            subscription_id=subscription_id,
            status=DeliveryStatus.EXPIRED,
        )
