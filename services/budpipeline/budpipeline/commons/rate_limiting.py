"""Rate limiting for budpipeline API endpoints.

This module provides rate limiting functionality to prevent abuse
of polling endpoints (002-pipeline-event-persistence - T068).
"""

import time
from collections import defaultdict
from datetime import datetime

from budpipeline.commons.observability import get_logger

logger = get_logger(__name__)

# Default rate limit: 1000 requests per minute per client (C-005)
DEFAULT_RATE_LIMIT = 1000
DEFAULT_WINDOW_SECONDS = 60


class RateLimiter:
    """Simple in-memory rate limiter using sliding window.

    Implements rate limiting per client (identified by IP or API key).
    Uses a sliding window counter algorithm for accurate limiting.
    """

    def __init__(
        self,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ):
        """Initialize rate limiter.

        Args:
            rate_limit: Maximum requests allowed per window.
            window_seconds: Window duration in seconds.
        """
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        # Client -> list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Clean up every minute

    def _cleanup_old_requests(self, client_id: str, current_time: float) -> None:
        """Remove expired request timestamps for a client.

        Args:
            client_id: Client identifier.
            current_time: Current timestamp.
        """
        window_start = current_time - self.window_seconds
        self._requests[client_id] = [ts for ts in self._requests[client_id] if ts > window_start]

    def _maybe_cleanup_all(self, current_time: float) -> None:
        """Periodically clean up all stale entries."""
        if current_time - self._last_cleanup > self._cleanup_interval:
            window_start = current_time - self.window_seconds
            for client_id in list(self._requests.keys()):
                self._requests[client_id] = [
                    ts for ts in self._requests[client_id] if ts > window_start
                ]
                if not self._requests[client_id]:
                    del self._requests[client_id]
            self._last_cleanup = current_time

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check if a request from client is allowed.

        Args:
            client_id: Client identifier (IP, API key, etc.).

        Returns:
            Tuple of (is_allowed, remaining_requests).
        """
        current_time = time.time()

        # Periodic cleanup
        self._maybe_cleanup_all(current_time)

        # Clean up this client's old requests
        self._cleanup_old_requests(client_id, current_time)

        # Count requests in current window
        request_count = len(self._requests[client_id])
        remaining = max(0, self.rate_limit - request_count)

        if request_count >= self.rate_limit:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                requests=request_count,
                limit=self.rate_limit,
            )
            return False, 0

        return True, remaining

    def record_request(self, client_id: str) -> None:
        """Record a request from a client.

        Args:
            client_id: Client identifier.
        """
        current_time = time.time()
        self._requests[client_id].append(current_time)

    def check_and_record(self, client_id: str) -> tuple[bool, int]:
        """Check if allowed and record request atomically.

        Args:
            client_id: Client identifier.

        Returns:
            Tuple of (is_allowed, remaining_requests).
        """
        allowed, remaining = self.is_allowed(client_id)
        if allowed:
            self.record_request(client_id)
            remaining = max(0, remaining - 1)
        return allowed, remaining

    def get_stats(self, client_id: str) -> dict:
        """Get rate limit stats for a client.

        Args:
            client_id: Client identifier.

        Returns:
            Dictionary with rate limit stats.
        """
        current_time = time.time()
        self._cleanup_old_requests(client_id, current_time)

        request_count = len(self._requests[client_id])
        remaining = max(0, self.rate_limit - request_count)

        # Calculate reset time
        if self._requests[client_id]:
            oldest_request = min(self._requests[client_id])
            reset_at = oldest_request + self.window_seconds
        else:
            reset_at = current_time + self.window_seconds

        return {
            "limit": self.rate_limit,
            "remaining": remaining,
            "reset_at": datetime.fromtimestamp(reset_at).isoformat(),
            "window_seconds": self.window_seconds,
        }


def get_client_id(request) -> str:
    """Extract client identifier from request.

    Uses the following priority:
    1. X-API-Key header (for authenticated clients)
    2. X-Forwarded-For header (for proxied requests)
    3. Client IP address

    Args:
        request: FastAPI request object.

    Returns:
        Client identifier string.
    """
    # Check for API key
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"api:{api_key[:8]}..."  # Partial key for logging

    # Check for forwarded IP
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take first IP in chain (original client)
        return f"ip:{forwarded_for.split(',')[0].strip()}"

    # Fall back to direct client IP
    if request.client:
        return f"ip:{request.client.host}"

    return "unknown"


# Global rate limiter instance for GET endpoints
execution_rate_limiter = RateLimiter(
    rate_limit=DEFAULT_RATE_LIMIT,
    window_seconds=DEFAULT_WINDOW_SECONDS,
)
