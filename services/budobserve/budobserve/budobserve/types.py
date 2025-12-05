"""Public type definitions for BudObserve SDK.

This module contains all public types that users can import for type hints.
Types are intentionally kept separate from implementation to provide a clean
public API surface.

Example:
    >>> from budobserve.types import SpanKind, AttributeValue
    >>> def process(kind: SpanKind) -> AttributeValue:
    ...     pass
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# Attribute value types following OTEL specification
AttributeValue = str | bool | int | float | Sequence[str] | Sequence[bool] | Sequence[int] | Sequence[float]

# Attributes dictionary type
Attributes = Mapping[str, AttributeValue]

# JSON-serializable types for message template arguments
JsonValue = str | int | float | bool | None | dict[str, Any] | list[Any]

__all__ = [
    "AttributeValue",
    "Attributes",
    "JsonValue",
]
