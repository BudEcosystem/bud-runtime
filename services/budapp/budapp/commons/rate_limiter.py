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

"""Rate limiting decorator for FastAPI endpoints."""

from functools import wraps
from typing import Callable, Optional

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from ..shared.redis_service import RedisService
from . import logging
from .config import app_settings


logger = logging.get_logger(__name__)


class RateLimiter:
    """Rate limiter using Redis for tracking requests."""

    def __init__(self, max_requests: int, window_seconds: int, key_prefix: str = "rate_limit"):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
            key_prefix: Prefix for Redis keys
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.redis_service = RedisService()

    def _get_identifier(self, request: Request, user_id: Optional[str] = None) -> str:
        """Get identifier for rate limiting (IP address or user ID).

        Args:
            request: FastAPI request object
            user_id: Optional user ID for user-based rate limiting

        Returns:
            Identifier string
        """
        if user_id:
            return user_id

        # Get client IP address
        # Check for forwarded IP first (for proxy/load balancer scenarios)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return client_ip

    async def check_rate_limit(self, request: Request, user_id: Optional[str] = None) -> None:
        """Check if request exceeds rate limit.

        Args:
            request: FastAPI request object
            user_id: Optional user ID for user-based rate limiting

        Raises:
            HTTPException: If rate limit is exceeded
        """
        identifier = self._get_identifier(request, user_id)
        key = f"{self.key_prefix}:{request.url.path}:{identifier}"

        try:
            # Increment counter
            current_count = await self.redis_service.incr(key)

            # Set expiry on first request
            if current_count == 1:
                await self.redis_service.set(key, current_count, ex=self.window_seconds)

            # Check if limit exceeded
            if current_count > self.max_requests:
                # Get TTL to inform user when to retry
                ttl = await self.redis_service.ttl(key)
                logger.warning(
                    f"Rate limit exceeded for {identifier} on {request.url.path}. "
                    f"Count: {current_count}, Limit: {self.max_requests}"
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Please try again in {ttl} seconds.",
                    headers={"Retry-After": str(ttl)},
                )

        except HTTPException:
            raise
        except aioredis.RedisError as e:
            logger.error(f"Rate limiting Redis error for key {key}: {e}")
        except Exception as e:
            # Log error but don't block request if Redis fails
            logger.error(f"Unexpected rate limiting error for key {key}: {e}")


def rate_limit(max_requests: int, window_seconds: int, use_user_id: bool = False):
    """Decorator for rate limiting FastAPI endpoints.

    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds
        use_user_id: If True, rate limit by user ID instead of IP

    Example:
        @rate_limit(max_requests=10, window_seconds=60)
        async def my_endpoint(request: Request):
            return {"message": "Hello"}

    Note:
        Rate limiting can be disabled by setting RATE_LIMIT_ENABLED=false
        environment variable. This is useful for testing environments.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip rate limiting if disabled via app settings
            if not app_settings.rate_limit_enabled:
                logger.debug(f"Rate limiting disabled for {func.__name__}")
                return await func(*args, **kwargs)

            # Find request object in args/kwargs
            request = None
            # Check positional args
            for i, arg in enumerate(args):
                # Skip self argument if present
                if i == 0 and hasattr(arg, "__self__"):
                    continue
                # Use duck typing to detect Request-like objects
                if hasattr(arg, "url") and hasattr(arg, "client") and hasattr(arg, "headers"):
                    request = arg
                    break

            # Check kwargs if not found in args
            if not request:
                request = kwargs.get("request")
                # Verify it's Request-like
                if request and (
                    hasattr(request, "url") and hasattr(request, "client") and hasattr(request, "headers")
                ):
                    pass  # Valid request
                else:
                    request = None

            if not request:
                # If no request object found, skip rate limiting
                logger.error(f"No request object found for rate limiting in {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object missing for rate limiting.",
                )
                # return await func(*args, **kwargs)

            logger.debug("Request found, proceeding with rate limiting")

            # Get user_id if needed
            user_id = None
            if use_user_id:
                # Try to get current_user from kwargs (for authenticated endpoints)
                current_user = kwargs.get("current_user")
                if current_user and hasattr(current_user, "id"):
                    user_id = str(current_user.id)

            # Create limiter instance lazily to allow for mocking
            limiter = RateLimiter(max_requests, window_seconds)

            # Check rate limit
            await limiter.check_rate_limit(request, user_id)

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator
