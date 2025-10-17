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

"""Provides TTL tracking and cleanup services for notifications."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dapr.clients import DaprClient

from notify.commons import logging
from notify.commons.config import app_settings
from notify.shared.novu_service import NovuService


logger = logging.get_logger(__name__)


class TTLTrackingService:
    """Service for tracking notification TTL in Redis via Dapr state store."""

    def __init__(self) -> None:
        """Initialize the TTL tracking service."""
        self.state_store_name = app_settings.statestore_name or "statestore"
        self.ttl_key_prefix = "notification:ttl:"

    async def track_notification_ttl(
        self,
        transaction_id: str,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Track notification TTL in Redis state store.

        Args:
            transaction_id (str): The transaction ID of the notification from Novu.
            ttl_seconds (Optional[int]): TTL in seconds. If None, uses default from config.
            metadata (Optional[Dict]): Additional metadata to store (e.g., subscriber_id, category).
        """
        ttl = ttl_seconds or app_settings.default_ttl_seconds
        expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()

        tracking_data = {
            "transaction_id": transaction_id,
            "ttl_seconds": ttl,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
            "metadata": metadata or {},
        }

        key = f"{self.ttl_key_prefix}{transaction_id}"

        try:
            with DaprClient() as client:
                # Store in Redis with TTL
                # Add a buffer to Redis TTL to allow cleanup workflow to process it
                redis_ttl = ttl + 3600  # Add 1 hour buffer
                client.save_state(
                    store_name=self.state_store_name,
                    key=key,
                    value=json.dumps(tracking_data),
                    state_metadata={"ttlInSeconds": str(redis_ttl)},
                )
            logger.debug(f"Tracked notification TTL for transaction {transaction_id}, expires at {expires_at}")
        except Exception as err:
            logger.exception(f"Failed to track notification TTL for transaction {transaction_id}: {err}")
            # Don't raise - TTL tracking is best-effort and shouldn't break notification flow

    async def get_expired_notifications(self, batch_size: int = 100) -> List[str]:
        """Get transaction IDs of expired notifications that need cleanup.

        Args:
            batch_size (int): Maximum number of transaction IDs to return.

        Returns:
            List[str]: List of transaction IDs that have expired.
        """
        expired_transaction_ids = []

        try:
            with DaprClient() as client:
                # Query state store for expired notifications
                # Note: This is a simplified implementation. In production, you might want to use
                # Redis SCAN or a separate sorted set to efficiently track expiration times.
                query = {
                    "filter": {},  # We'll check expiration in Python since Dapr state store doesn't support time-based queries directly
                    "page": {"limit": batch_size},
                }

                # Get all notification TTL keys
                # This is a limitation of Dapr state store - for better performance,
                # consider using Redis directly with SCAN or sorted sets
                response = client.query_state(store_name=self.state_store_name, query=json.dumps(query))

                current_time = datetime.utcnow()
                for result in response.results:
                    if result.key.startswith(self.ttl_key_prefix):
                        try:
                            data = json.loads(result.value)
                            expires_at = datetime.fromisoformat(data["expires_at"])
                            if expires_at <= current_time:
                                expired_transaction_ids.append(data["transaction_id"])
                                if len(expired_transaction_ids) >= batch_size:
                                    break
                        except (json.JSONDecodeError, KeyError, ValueError) as parse_err:
                            logger.warning(f"Failed to parse TTL data for key {result.key}: {parse_err}")
                            continue

        except Exception as err:
            logger.exception(f"Failed to get expired notifications: {err}")

        return expired_transaction_ids

    async def remove_ttl_tracking(self, transaction_id: str) -> None:
        """Remove TTL tracking for a notification after cleanup.

        Args:
            transaction_id (str): The transaction ID of the notification.
        """
        key = f"{self.ttl_key_prefix}{transaction_id}"
        try:
            with DaprClient() as client:
                client.delete_state(store_name=self.state_store_name, key=key)
            logger.debug(f"Removed TTL tracking for transaction {transaction_id}")
        except Exception as err:
            logger.exception(f"Failed to remove TTL tracking for transaction {transaction_id}: {err}")


class NotificationCleanupService:
    """Service for cleaning up expired notifications."""

    def __init__(self) -> None:
        """Initialize the notification cleanup service."""
        self.ttl_service = TTLTrackingService()
        self.novu_service = NovuService()

    async def cleanup_expired_notifications(self, environment: str = "dev") -> Dict[str, int]:
        """Clean up expired notifications from Novu.

        Args:
            environment (str): The Novu environment to clean up (dev or prod).

        Returns:
            Dict[str, int]: Statistics about the cleanup operation.
        """
        logger.info("Starting notification cleanup workflow")
        stats = {"checked": 0, "deleted": 0, "failed": 0, "not_found": 0}

        try:
            # Get expired notifications from Redis
            batch_size = app_settings.cleanup_batch_size
            expired_transaction_ids = await self.ttl_service.get_expired_notifications(batch_size)
            stats["checked"] = len(expired_transaction_ids)

            logger.info(f"Found {len(expired_transaction_ids)} expired notifications to clean up")

            for transaction_id in expired_transaction_ids:
                try:
                    # Get messages by transaction ID
                    messages = await self.novu_service.get_all_messages(
                        transaction_id=transaction_id, environment=environment, limit=100
                    )

                    if not messages.data:
                        logger.debug(f"No messages found for transaction {transaction_id}")
                        stats["not_found"] += 1
                        # Remove TTL tracking since message doesn't exist
                        await self.ttl_service.remove_ttl_tracking(transaction_id)
                        continue

                    # Delete all messages for this transaction
                    for message in messages.data:
                        try:
                            await self.novu_service.delete_message(message._id, environment=environment)
                            stats["deleted"] += 1
                            logger.debug(f"Deleted message {message._id} for transaction {transaction_id}")
                        except Exception as delete_err:
                            logger.error(f"Failed to delete message {message._id}: {delete_err}")
                            stats["failed"] += 1

                    # Remove TTL tracking after successful cleanup
                    await self.ttl_service.remove_ttl_tracking(transaction_id)

                except Exception as transaction_err:
                    logger.error(f"Failed to process transaction {transaction_id}: {transaction_err}")
                    stats["failed"] += 1

        except Exception as err:
            logger.exception(f"Cleanup workflow failed: {err}")

        logger.info(f"Cleanup completed. Stats: {stats}")
        return stats
