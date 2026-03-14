"""A2A (Agent-to-Agent) protocol integration for BudPrompt."""

from .config_resolver import A2AConfigResolver
from .context_store import PostgreSQLContextStore
from .dependencies import get_api_key
from .executor import A2APromptExecutor, BudPromptAgentExecutor
from .helper import validate_a2a_version
from .models import A2AContext
from .routes import a2a_router, initialize_a2a_stores, shutdown_a2a_stores
from .streaming_adapter import A2AStreamingAdapter


__all__ = [
    "A2AConfigResolver",
    "A2AContext",
    "A2APromptExecutor",
    "A2AStreamingAdapter",
    "BudPromptAgentExecutor",
    "PostgreSQLContextStore",
    "a2a_router",
    "get_api_key",
    "initialize_a2a_stores",
    "shutdown_a2a_stores",
    "validate_a2a_version",
]
