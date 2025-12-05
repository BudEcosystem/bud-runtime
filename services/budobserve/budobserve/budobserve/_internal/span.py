"""BudSpan - High-level span wrapper for BudObserve SDK.

This module provides BudSpan, a wrapper around OTEL Span that provides:
- Message template support for span names
- Automatic attribute handling
- Context manager interface
- Convenience methods for common operations

Architecture follows Logfire's span wrapper pattern.

Will be implemented in Phase 3 (High-Level Python SDK API).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.trace import Span

    from budobserve.types import Attributes


class BudSpan:
    """High-level wrapper around OTEL Span.

    Provides a more ergonomic API while delegating to the underlying
    OTEL Span for actual telemetry operations.

    Example:
        >>> with BudSpan("processing {item_id}", item_id=123) as span:
        ...     span.set_attribute("result", "success")
        ...     # work happens here
    """

    def __init__(
        self,
        span: Span,
        message_template: str,
        **template_args: Any,
    ) -> None:
        """Initialize BudSpan wrapper.

        Args:
            span: The underlying OTEL Span.
            message_template: Message template for the span name.
            **template_args: Arguments for the message template.
        """
        self._span = span
        self._message_template = message_template
        self._template_args = template_args

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a single attribute on the span.

        Args:
            key: Attribute key.
            value: Attribute value.
        """
        self._span.set_attribute(key, value)

    def set_attributes(self, attributes: Attributes) -> None:
        """Set multiple attributes on the span.

        Args:
            attributes: Dictionary of attributes to set.
        """
        self._span.set_attributes(dict(attributes))

    def record_exception(self, exception: BaseException) -> None:
        """Record an exception on the span.

        Args:
            exception: The exception to record.
        """
        self._span.record_exception(exception)

    def __enter__(self) -> BudSpan:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, recording any exception."""
        if exc_val is not None:
            self.record_exception(exc_val)
        self._span.end()
