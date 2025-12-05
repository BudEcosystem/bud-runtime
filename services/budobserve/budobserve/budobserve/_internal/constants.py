"""Attribute constants for BudObserve SDK.

This module defines all attribute keys used by BudObserve, following:
- OTEL Semantic Conventions
- Bud-specific attributes (bud.* namespace)
- GenAI attributes for LLM observability (gen_ai.* namespace)

Centralized constants ensure consistency and prevent typos.

Will be expanded in Phase 2 (Unified Schema).
"""

from __future__ import annotations

# OTEL Semantic Convention attributes
SERVICE_NAME = "service.name"
SERVICE_VERSION = "service.version"
SERVICE_NAMESPACE = "service.namespace"
DEPLOYMENT_ENVIRONMENT = "deployment.environment"

# HTTP attributes
HTTP_METHOD = "http.method"
HTTP_URL = "http.url"
HTTP_STATUS_CODE = "http.status_code"
HTTP_REQUEST_BODY_SIZE = "http.request.body.size"
HTTP_RESPONSE_BODY_SIZE = "http.response.body.size"

# Database attributes
DB_SYSTEM = "db.system"
DB_NAME = "db.name"
DB_STATEMENT = "db.statement"
DB_OPERATION = "db.operation"

# Messaging attributes
MESSAGING_SYSTEM = "messaging.system"
MESSAGING_DESTINATION = "messaging.destination"
MESSAGING_OPERATION = "messaging.operation"

# Bud-specific attributes
BUD_PROJECT_ID = "bud.project.id"
BUD_ENDPOINT_ID = "bud.endpoint.id"
BUD_MODEL_ID = "bud.model.id"
BUD_CLUSTER_ID = "bud.cluster.id"
BUD_USER_ID = "bud.user.id"
BUD_TRACE_TYPE = "bud.trace.type"

# Message template attributes (following Logfire pattern)
MESSAGE_TEMPLATE = "budobserve.msg_template"
MESSAGE = "budobserve.msg"

# GenAI attributes (for LLM observability - Phase 5)
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"

__all__ = [
    "BUD_CLUSTER_ID",
    "BUD_ENDPOINT_ID",
    "BUD_MODEL_ID",
    "BUD_PROJECT_ID",
    "BUD_TRACE_TYPE",
    "BUD_USER_ID",
    "DB_NAME",
    "DB_OPERATION",
    "DB_STATEMENT",
    "DB_SYSTEM",
    "DEPLOYMENT_ENVIRONMENT",
    "GEN_AI_REQUEST_MAX_TOKENS",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_REQUEST_TEMPERATURE",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "GEN_AI_USAGE_TOTAL_TOKENS",
    "HTTP_METHOD",
    "HTTP_REQUEST_BODY_SIZE",
    "HTTP_RESPONSE_BODY_SIZE",
    "HTTP_STATUS_CODE",
    "HTTP_URL",
    "MESSAGE",
    "MESSAGE_TEMPLATE",
    "MESSAGING_DESTINATION",
    "MESSAGING_OPERATION",
    "MESSAGING_SYSTEM",
    "SERVICE_NAME",
    "SERVICE_NAMESPACE",
    "SERVICE_VERSION",
]
