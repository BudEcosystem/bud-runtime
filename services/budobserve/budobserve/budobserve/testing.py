"""Test utilities for BudObserve SDK.

This module provides utilities for testing code that uses BudObserve.
It allows capturing spans, metrics, and logs during tests without
sending data to real backends.

Example:
    >>> from budobserve.testing import TestExporter
    >>> with TestExporter() as exporter:
    ...     # Code that creates spans
    ...     spans = exporter.get_spans()
    ...     assert len(spans) == 1

Will be implemented in Phase 7 (Testing Strategy).
"""

from __future__ import annotations

__all__: list[str] = []
