"""HTTP Request Action.

Makes HTTP requests to external APIs with configurable
method, headers, body, and timeout.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)

logger = structlog.get_logger(__name__)

VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Private/internal IP ranges that should not be accessed (SSRF protection)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "169.254.169.254"}


def is_safe_url(url: str) -> tuple[bool, str]:
    """Check if URL is safe to request (SSRF protection).

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False, "URL has no hostname"

        # Check blocked hostnames
        hostname_lower = hostname.lower()
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False, f"Blocked hostname: {hostname}"

        # Try to resolve hostname to IP and check against blocked ranges
        try:
            ip = ipaddress.ip_address(hostname)
            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    return False, f"IP address {ip} is in blocked range"
        except ValueError:
            # hostname is not an IP address, that's fine
            pass

        return True, ""
    except Exception as e:
        return False, f"Invalid URL: {e}"


class HttpRequestExecutor(BaseActionExecutor):
    """Executor for HTTP requests."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute HTTP request."""
        url = context.params.get("url", "")
        method = context.params.get("method", "GET").upper()
        headers = context.params.get("headers", {})
        body = context.params.get("body")
        timeout = context.params.get("timeout_seconds", 30)

        # SSRF protection: validate URL before making request
        is_safe, ssrf_error = is_safe_url(url)
        if not is_safe:
            logger.warning(
                "http_request_blocked_ssrf",
                step_id=context.step_id,
                url=url,
                reason=ssrf_error,
            )
            return ActionResult(
                success=False,
                outputs={
                    "status_code": 0,
                    "body": None,
                    "headers": {},
                },
                error=f"Request blocked (SSRF protection): {ssrf_error}",
            )

        logger.info(
            "http_request_starting",
            step_id=context.step_id,
            method=method,
            url=url,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=body if method in ["POST", "PUT", "PATCH"] and body else None,
                    headers=headers if headers else None,
                )

                # Parse response body
                response_body: Any = None
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

                # Extract response headers
                response_headers = dict(response.headers)

                logger.info(
                    "http_request_completed",
                    step_id=context.step_id,
                    status_code=response.status_code,
                )

                return ActionResult(
                    success=response.is_success,
                    outputs={
                        "status_code": response.status_code,
                        "body": response_body,
                        "headers": response_headers,
                    },
                    error=None if response.is_success else f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            error_msg = f"Request timed out after {timeout}s"
            logger.error(
                "http_request_timeout",
                step_id=context.step_id,
                timeout=timeout,
            )
            return ActionResult(
                success=False,
                outputs={
                    "status_code": 0,
                    "body": None,
                    "headers": {},
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Request failed: {e!s}"
            logger.exception(
                "http_request_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "status_code": 0,
                    "body": None,
                    "headers": {},
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("url"):
            errors.append("url is required")

        url = params.get("url", "")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            errors.append("url must start with http:// or https://")

        method = params.get("method")
        if method is not None:
            if method.upper() not in VALID_METHODS:
                errors.append(f"method must be one of: {VALID_METHODS}")

        return errors


META = ActionMeta(
    type="http_request",
    version="1.0.0",
    name="HTTP Request",
    description="Makes HTTP requests to external APIs",
    category="Integration",
    icon="globe",
    color="#8B5CF6",  # Purple
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=60,
    idempotent=False,
    required_services=[],
    params=[
        ParamDefinition(
            name="url",
            label="URL",
            type=ParamType.STRING,
            description="The URL to send the request to",
            required=True,
            placeholder="https://api.example.com/endpoint",
        ),
        ParamDefinition(
            name="method",
            label="Method",
            type=ParamType.SELECT,
            description="HTTP method to use",
            default="GET",
            options=[
                {"value": "GET", "label": "GET"},
                {"value": "POST", "label": "POST"},
                {"value": "PUT", "label": "PUT"},
                {"value": "PATCH", "label": "PATCH"},
                {"value": "DELETE", "label": "DELETE"},
            ],
        ),
        ParamDefinition(
            name="headers",
            label="Headers",
            type=ParamType.JSON,
            description="Request headers as key-value pairs",
            required=False,
        ),
        ParamDefinition(
            name="body",
            label="Body",
            type=ParamType.JSON,
            description="Request body (for POST, PUT, PATCH)",
            required=False,
        ),
        ParamDefinition(
            name="timeout_seconds",
            label="Timeout",
            type=ParamType.NUMBER,
            description="Request timeout in seconds",
            default=30,
            validation={"min": 1, "max": 300},
        ),
    ],
    outputs=[
        OutputDefinition(
            name="status_code",
            type="number",
            description="HTTP response status code",
        ),
        OutputDefinition(
            name="body",
            type="any",
            description="Response body (parsed as JSON if possible)",
        ),
        OutputDefinition(
            name="headers",
            type="object",
            description="Response headers",
        ),
    ],
)


@register_action(META)
class HttpRequestAction:
    """Action for making HTTP requests."""

    meta = META
    executor_class = HttpRequestExecutor
