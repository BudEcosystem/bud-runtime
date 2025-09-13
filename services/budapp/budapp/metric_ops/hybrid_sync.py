"""Hybrid metrics sync task that combines credential and user usage sync efficiently."""

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from budapp.billing_ops.services import BillingService
from budapp.commons.config import app_settings
from budapp.commons.constants import UserTypeEnum
from budapp.commons.database import SessionLocal
from budapp.commons.logging import get_logger
from budapp.credential_ops.services import CredentialService
from budapp.user_ops.models import User as UserModel


logger = get_logger(__name__)


class HybridMetricsSyncTask:
    """Unified task that handles both credential and user usage sync with smart filtering.

    Also checks and triggers billing alerts when users exceed their configured thresholds,
    ensuring timely notifications for approaching usage limits.
    """

    def __init__(self, incremental_interval: int = 60, full_sync_interval: int = 900):
        """Initialize the hybrid sync task.

        Args:
            incremental_interval: How often to sync active entities in seconds (default: 60)
            full_sync_interval: How often to sync all entities in seconds (default: 900 = 15 minutes)
        """
        self.incremental_interval = incremental_interval
        self.full_sync_interval = full_sync_interval
        self.running = False
        self.incremental_task: Optional[asyncio.Task] = None
        self.full_sync_task: Optional[asyncio.Task] = None

        # Stats tracking
        self.last_incremental_sync = None
        self.last_full_sync = None
        self.sync_stats = {
            "incremental_syncs": 0,
            "full_syncs": 0,
            "last_error": None,
            "active_credentials_avg": 0,
            "active_users_avg": 0,
            "total_alerts_triggered": 0,
            "total_alerts_failed": 0,
        }

    async def start(self):
        """Start both incremental and full sync loops."""
        if self.running:
            logger.warning("Hybrid metrics sync task is already running")
            return

        self.running = True
        self.incremental_task = asyncio.create_task(self._incremental_sync_loop())
        self.full_sync_task = asyncio.create_task(self._full_sync_loop())
        logger.info(
            f"Started hybrid metrics sync: incremental={self.incremental_interval}s, full={self.full_sync_interval}s"
        )

    async def stop(self):
        """Stop both sync loops."""
        self.running = False

        if self.incremental_task:
            self.incremental_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.incremental_task

        if self.full_sync_task:
            self.full_sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.full_sync_task

        logger.info("Stopped hybrid metrics sync task")

    async def _incremental_sync_loop(self):
        """Fast sync loop for recently active entities."""
        while self.running:
            try:
                await self._perform_sync(mode="incremental", threshold_minutes=5)
                self.sync_stats["incremental_syncs"] += 1
                self.last_incremental_sync = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(f"Error in incremental sync: {e}")
                self.sync_stats["last_error"] = str(e)

            await asyncio.sleep(self.incremental_interval)

    async def _full_sync_loop(self):
        """Periodic full sync for consistency."""
        while self.running:
            try:
                # For full sync, use a very large threshold to get ALL users with any historical activity
                # This ensures we sync all users with billing records regardless of recent activity
                await self._perform_sync(mode="full", threshold_minutes=525600)  # 1 year (365 days)
                self.sync_stats["full_syncs"] += 1
                self.last_full_sync = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(f"Error in full sync: {e}")
                self.sync_stats["last_error"] = str(e)

            await asyncio.sleep(self.full_sync_interval)

    async def _perform_sync(self, mode: str, threshold_minutes: int = 5) -> Dict[str, Any]:
        """Perform the actual sync operation."""
        try:
            # Prepare request payload
            payload = {
                "sync_mode": mode,
                "activity_threshold_minutes": threshold_minutes,
                "credential_sync": True,
                "user_usage_sync": True,
            }

            # For full sync, include admin users to ensure they get unlimited access even without activity
            if mode == "full":
                admin_user_ids = await self._get_admin_user_ids()
                if admin_user_ids:
                    payload["user_ids"] = [str(user_id) for user_id in admin_user_ids]
                    logger.info(f"Including {len(admin_user_ids)} active admin users in full sync")

            # Call the unified budmetrics endpoint
            dapr_url = f"{app_settings.dapr_base_url}/v1.0/invoke/budmetrics/method/observability/metrics-sync"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(dapr_url, json=payload)
                response.raise_for_status()

                data = response.json()

                # Process the response
                result = await self._process_sync_response(data)

                # Update stats - stats are directly at root level
                stats = data.get("stats", {})
                if mode == "incremental":
                    self.sync_stats["active_credentials_avg"] = stats.get("active_credentials", 0)
                    self.sync_stats["active_users_avg"] = stats.get("active_users", 0)

                # Update alert stats
                self.sync_stats["total_alerts_triggered"] += result.get("alerts_triggered", 0)
                self.sync_stats["total_alerts_failed"] += result.get("alerts_failed", 0)

                # Include alert information in sync completion log
                alert_info = ""
                if result.get("alerts_triggered", 0) > 0 or result.get("alerts_failed", 0) > 0:
                    alert_info = f", alerts_triggered={result.get('alerts_triggered', 0)}, alerts_failed={result.get('alerts_failed', 0)}"

                logger.info(
                    f"{mode.capitalize()} sync completed: "
                    f"credentials={stats.get('active_credentials', 0)}, "
                    f"users={stats.get('active_users', 0)}, "
                    f"updates={result.get('total_updates', 0)}{alert_info}"
                )

                return result

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during {mode} sync: {e}")
            return {"total_updates": 0, "errors": [str(e)]}
        except Exception as e:
            logger.error(f"Error during {mode} sync: {e}")
            return {"total_updates": 0, "errors": [str(e)]}

    async def _process_sync_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the sync response and update local data."""
        total_updates = 0
        errors = []

        try:
            # Data is directly at root level, not under "param" wrapper
            credential_usage = data.get("credential_usage", [])
            user_usage = data.get("user_usage", [])

            # Process credential usage updates
            if credential_usage:
                credential_result = await self._update_credential_usage(credential_usage)
                total_updates += credential_result.get("updated_count", 0)
                errors.extend(credential_result.get("errors", []))

            # Process user usage updates
            alerts_triggered = 0
            alerts_failed = 0
            if user_usage:
                user_result = await self._update_user_usage(user_usage)
                total_updates += user_result.get("updated_count", 0)
                alerts_triggered = user_result.get("alerts_triggered", 0)
                alerts_failed = user_result.get("alerts_failed", 0)
                errors.extend(user_result.get("errors", []))

            return {
                "total_updates": total_updates,
                "credential_updates": len(credential_usage),
                "user_updates": len(user_usage),
                "alerts_triggered": alerts_triggered,
                "alerts_failed": alerts_failed,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Error processing sync response: {e}")
            return {"total_updates": 0, "errors": [str(e)]}

    async def _update_credential_usage(self, credential_usage: list) -> Dict[str, Any]:
        """Update credential last_used_at timestamps."""
        try:
            # Convert to the format expected by CredentialService
            usage_dict = {}
            for item in credential_usage:
                cred_id = UUID(item["credential_id"])
                # Handle different datetime formats
                last_used_str = item["last_used_at"]
                if isinstance(last_used_str, str):
                    if last_used_str.endswith("Z"):
                        last_used_at = datetime.fromisoformat(last_used_str.replace("Z", "+00:00"))
                    else:
                        last_used_at = datetime.fromisoformat(last_used_str)
                else:
                    last_used_at = last_used_str

                usage_dict[cred_id] = last_used_at

            if not usage_dict:
                return {"updated_count": 0, "failed_count": 0, "errors": []}

            # Update credentials using existing service
            with SessionLocal() as session:
                credential_service = CredentialService(session)
                result = await credential_service.update_credential_last_used(usage_dict)
                return result

        except Exception as e:
            logger.error(f"Error updating credential usage: {e}")
            return {"updated_count": 0, "failed_count": len(credential_usage), "errors": [str(e)]}

    async def _update_user_usage(self, user_usage: list) -> Dict[str, Any]:
        """Update user usage limits in Redis with user_type support using efficient bulk processing."""
        if not user_usage:
            return {"updated_count": 0, "failed_count": 0, "errors": []}

        try:
            # Extract user IDs from the usage data
            user_ids = []
            for user_item in user_usage:
                try:
                    user_id = UUID(user_item["user_id"])
                    user_ids.append(user_id)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid user_id in usage data: {user_item.get('user_id')}: {e}")

            if not user_ids:
                return {"updated_count": 0, "failed_count": len(user_usage), "errors": ["No valid user IDs found"]}

            # Use bulk processing for maximum efficiency
            with SessionLocal() as session:
                billing_service = BillingService(session)

                # Process all users in a single bulk operation
                bulk_results = await billing_service.check_bulk_usage_limits(user_ids)

                # Check and trigger alerts for each user (non-admin users only)
                alert_check_results = {"triggered": 0, "failed": 0}
                for user_id in user_ids:
                    try:
                        # Skip alert checking for admin users (they have unlimited access)
                        user_result = bulk_results.get(str(user_id), {})
                        if user_result.get("status") == "admin_unlimited":
                            continue

                        # Check and trigger alerts for this user
                        triggered_alerts = await billing_service.check_and_trigger_alerts(user_id)
                        if triggered_alerts:
                            alert_check_results["triggered"] += len(triggered_alerts)
                            logger.info(f"Triggered {len(triggered_alerts)} alerts for user {user_id}")
                    except Exception as e:
                        alert_check_results["failed"] += 1
                        logger.warning(f"Failed to check alerts for user {user_id}: {e}")

                # Log alert checking summary
                if alert_check_results["triggered"] > 0 or alert_check_results["failed"] > 0:
                    logger.info(
                        f"Alert checking completed: "
                        f"triggered={alert_check_results['triggered']}, "
                        f"failed={alert_check_results['failed']}"
                    )

                # Count results
                updated_count = len([r for r in bulk_results.values() if r])  # Non-empty results
                failed_count = len(user_ids) - updated_count

                # Count admin users
                admin_count = sum(1 for result in bulk_results.values() if result.get("status") == "admin_unlimited")
                if admin_count > 0:
                    logger.info(f"Processed {admin_count} admin users with unlimited access")

                return {
                    "updated_count": updated_count,
                    "failed_count": failed_count,
                    "alerts_triggered": alert_check_results["triggered"],
                    "alerts_failed": alert_check_results["failed"],
                    "errors": [] if failed_count == 0 else [f"{failed_count} users failed processing"],
                }

        except Exception as e:
            logger.error(f"Error updating user usage with bulk method: {e}")
            return {
                "updated_count": 0,
                "failed_count": len(user_usage),
                "alerts_triggered": 0,
                "alerts_failed": 0,
                "errors": [str(e)],
            }

    async def _get_admin_user_ids(self) -> List[UUID]:
        """Get active admin user IDs to ensure they're included in full sync."""
        try:
            with SessionLocal() as session:
                admin_users = (
                    session.query(UserModel)
                    .filter(UserModel.user_type == UserTypeEnum.ADMIN, UserModel.status == "active")
                    .all()
                )
                admin_user_ids = [user.id for user in admin_users]
                return admin_user_ids
        except Exception as e:
            logger.error(f"Error getting admin user IDs: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get sync task statistics."""
        return {
            **self.sync_stats,
            "last_incremental_sync": self.last_incremental_sync.isoformat() if self.last_incremental_sync else None,
            "last_full_sync": self.last_full_sync.isoformat() if self.last_full_sync else None,
            "is_running": self.running,
            "incremental_interval": self.incremental_interval,
            "full_sync_interval": self.full_sync_interval,
        }


# Global instance of the sync task
hybrid_sync_task = HybridMetricsSyncTask()


async def start_hybrid_sync():
    """Start the hybrid metrics sync task."""
    await hybrid_sync_task.start()


async def stop_hybrid_sync():
    """Stop the hybrid metrics sync task."""
    await hybrid_sync_task.stop()


def get_hybrid_sync_stats() -> Dict[str, Any]:
    """Get hybrid sync task statistics."""
    return hybrid_sync_task.get_stats()
