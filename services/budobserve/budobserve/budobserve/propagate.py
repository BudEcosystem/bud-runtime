"""Context propagation utilities for BudObserve SDK.

This module provides utilities for propagating trace context across
service boundaries (HTTP headers, message queues, etc.).

Example:
    >>> from budobserve.propagate import inject_context, extract_context
    >>> headers = {}
    >>> inject_context(headers)  # Add trace context to headers
    >>> # Send request with headers
    >>> context = extract_context(incoming_headers)  # Extract on receiver

Will be implemented in Phase 1 (Core OTEL Wrapper).
"""

from __future__ import annotations

__all__: list[str] = []
