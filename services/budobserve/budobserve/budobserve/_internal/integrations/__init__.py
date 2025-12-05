"""Framework integrations for BudObserve SDK.

This package contains auto-instrumentation for common frameworks:
- FastAPI (Phase 4)
- SQLAlchemy (Phase 4)
- httpx (Phase 4)
- Redis (Phase 4)
- Dapr (Phase 6+)
- LLM providers: OpenAI, Anthropic, LiteLLM (Phase 5)

Each integration wraps OTEL instrumentation with BudObserve-specific
attribute handling and message templates.

Will be implemented in Phases 4-6.
"""

from __future__ import annotations

__all__: list[str] = []
