"""Ground truth derivation functions for prompt analytics tests.

These functions derive expected values from seeder JSON (single source of truth).
They mirror the MV transformation logic - if MV has bugs, tests will fail.

CRITICAL: DO NOT adjust these functions to match buggy MV behavior.
If tests fail, it indicates MV bugs that need fixing.

Architecture:
    Seeder JSON (otel_traces)
        │
        ├──→ INSERT to DB ──→ MV transforms ──→ ACTUAL InferenceFact
        │
        └──→ ground_truth.py functions ──→ EXPECTED InferenceFact
                                                  │
                                            ASSERT ACTUAL == EXPECTED
"""

from typing import Any


# =============================================================================
# HELPER FUNCTIONS (mirror MV logic)
# =============================================================================


def _coalesce(*values) -> Any:
    """Return first non-None, non-empty value (mirrors SQL COALESCE)."""
    for v in values:
        if v is not None and v != "":
            return v
    return None


def _to_int(value: Any) -> int | None:
    """Convert to int or None (mirrors toUInt32OrNull)."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> float | None:
    """Convert to float or None (mirrors toFloat64OrNull)."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_bool(value: Any) -> bool:
    """Convert to bool (mirrors '= true' comparison)."""
    return value == "true" or value is True


def _get_span_attr(span: dict | None, key: str) -> str | None:
    """Safely get SpanAttribute value."""
    if span is None:
        return None
    return span.get("SpanAttributes", {}).get(key) or None


def _find_span_by_name(spans: list[dict], name: str) -> dict | None:
    """Find first span with matching SpanName."""
    for span in spans:
        if span.get("SpanName") == name:
            return span
    return None


def _find_handler_span(spans: list[dict]) -> dict | None:
    """Find handler observability span (any *_handler_observability)."""
    for span in spans:
        span_name = span.get("SpanName", "")
        if span_name.endswith("_handler_observability"):
            return span
    return None


def _find_response_handler_span(spans: list[dict]) -> dict | None:
    """Find response_create_handler_observability span specifically."""
    return _find_span_by_name(spans, "response_create_handler_observability")


# =============================================================================
# MAIN DERIVATION FUNCTIONS
# =============================================================================


def get_expected_inference_fact(seeder_data: dict, scenario_key: str) -> dict:
    """Derive expected InferenceFact row from seeder otel_traces data.

    DEPRECATED: Use get_all_expected_inference_facts for multi-inference scenarios.

    This function mirrors the MV transformation logic exactly.
    For /v1/responses endpoint, uses mv_otel_response_to_inference_fact logic.
    For other endpoints, uses mv_otel_to_inference_fact logic.

    Args:
        seeder_data: Full seeder data dict
        scenario_key: Key for the scenario to derive expected values from

    Returns:
        Dict of expected InferenceFact column values (first inference only)
    """
    facts = get_all_expected_inference_facts(seeder_data, scenario_key)
    return facts[0] if facts else {}


def get_all_expected_inference_facts(seeder_data: dict, scenario_key: str) -> list[dict]:
    """Derive ALL expected InferenceFact rows from seeder otel_traces data.

    The MV creates rows based on:
    - response_create_handler_observability spans (for /v1/responses)
    - gateway_analytics spans with inference_id (for /v1/chat/completions, etc.)

    For gateway spans, handler data is only joined if inference_ids match.

    Args:
        seeder_data: Full seeder data dict
        scenario_key: Key for the scenario to derive expected values from

    Returns:
        List of expected InferenceFact column values
    """
    spans = seeder_data[scenario_key]
    facts = []

    # Find ALL response_create_handler_observability spans
    response_handlers = [s for s in spans if s.get("SpanName") == "response_create_handler_observability"]

    # Find ALL inference_handler_observability spans (for matching, not for iteration)
    inference_handlers = [s for s in spans if s.get("SpanName") == "inference_handler_observability"]

    # Find gateway spans for matching
    gateway_spans = [s for s in spans if s.get("SpanName") == "gateway_analytics"]

    # Process response handlers (for /v1/responses endpoint)
    for response_handler in response_handlers:
        # Find matching gateway span (same parent or by path)
        gateway = _find_matching_gateway_for_response(response_handler, gateway_spans)
        facts.append(_derive_response_endpoint_fact(response_handler, gateway))

    # Process gateway spans with inference_id (for /v1/chat/completions, etc.)
    # The MV creates rows from gateway spans, joining handler data if inference_ids match
    for gateway in gateway_spans:
        gw_inf_id = _get_span_attr(gateway, "gateway_analytics.inference_id")
        path = _get_span_attr(gateway, "gateway_analytics.path")

        # Skip /v1/responses gateways (handled by response_handlers)
        if path == "/v1/responses":
            continue

        # Skip gateways without inference_id
        if not gw_inf_id:
            continue

        # Find matching handler by inference_id
        handler = _find_handler_for_gateway(gateway, inference_handlers)
        facts.append(_derive_standard_endpoint_fact(handler, gateway))

    return facts


def _find_handler_for_gateway(gateway: dict, inference_handlers: list[dict]) -> dict | None:
    """Find inference_handler_observability span that matches the gateway by inference_id.

    The MV joins handler data only when handler.inference_id == gateway.inference_id.
    """
    gw_inf_id = _get_span_attr(gateway, "gateway_analytics.inference_id")
    trace_id = gateway.get("TraceId")

    if not gw_inf_id:
        return None

    for handler in inference_handlers:
        if handler.get("TraceId") != trace_id:
            continue
        handler_inf_id = _get_span_attr(handler, "model_inference_details.inference_id")
        if handler_inf_id == gw_inf_id:
            return handler

    return None


def _find_matching_gateway_for_response(response_handler: dict, gateway_spans: list[dict]) -> dict | None:
    """Find gateway span that matches the response handler.

    Looks for gateway with path=/v1/responses in the same trace.
    """
    trace_id = response_handler.get("TraceId")
    for gw in gateway_spans:
        if gw.get("TraceId") == trace_id:
            path = _get_span_attr(gw, "gateway_analytics.path")
            if path == "/v1/responses":
                return gw
    # Fallback to first gateway in trace
    for gw in gateway_spans:
        if gw.get("TraceId") == trace_id:
            return gw
    return None


def _find_matching_gateway_for_inference(inference_handler: dict, gateway_spans: list[dict]) -> dict | None:
    """Find gateway span that matches the inference handler.

    Matches by inference_id or parent span relationship.
    """
    handler_inf_id = _get_span_attr(inference_handler, "model_inference_details.inference_id")
    trace_id = inference_handler.get("TraceId")

    # Try to match by inference_id
    for gw in gateway_spans:
        if gw.get("TraceId") == trace_id:
            gw_inf_id = _get_span_attr(gw, "gateway_analytics.inference_id")
            if gw_inf_id and gw_inf_id == handler_inf_id:
                return gw

    # Fallback: find gateway with /v1/chat/completions path in same trace
    for gw in gateway_spans:
        if gw.get("TraceId") == trace_id:
            path = _get_span_attr(gw, "gateway_analytics.path")
            if path and "/chat/completions" in path:
                return gw

    # Last resort: first non-response gateway in trace
    for gw in gateway_spans:
        if gw.get("TraceId") == trace_id:
            path = _get_span_attr(gw, "gateway_analytics.path")
            if path != "/v1/responses":
                return gw
    return None


def _derive_response_endpoint_fact(response_handler: dict, gateway: dict | None) -> dict:
    """Derive expected InferenceFact for /v1/responses endpoint.

    Mirrors mv_otel_response_to_inference_fact logic.
    """
    def r_attr(key: str) -> str | None:
        return _get_span_attr(response_handler, key)

    def g_attr(key: str) -> str | None:
        return _get_span_attr(gateway, key) if gateway else None

    # Derive is_success: false if error fields present or status is failed
    error_type = r_attr("error.type")
    error_message = r_attr("error.message")
    response_status = r_attr("gen_ai.response.status")
    is_success = not (error_type or error_message or response_status == "failed")

    return {
        # Core identifiers
        "trace_id": response_handler.get("TraceId"),
        "span_id": response_handler.get("SpanId"),
        "inference_id": r_attr("gen_ai.inference_id"),
        "project_id": r_attr("bud.project_id"),
        "endpoint_id": r_attr("bud.endpoint_id"),
        "model_id": None,  # Model resolved dynamically
        "api_key_id": r_attr("bud.api_key_id"),
        "api_key_project_id": r_attr("bud.api_key_project_id"),
        "user_id": r_attr("bud.user_id"),

        # Status
        "is_success": is_success,
        "status_code": _to_int(g_attr("gateway_analytics.status_code")),
        "cost": None,

        # Model info
        "model_name": _coalesce(
            r_attr("gen_ai.response.model"),
            r_attr("gen_ai.request.model"),
            ""
        ),
        "model_provider": "budprompt",  # Always budprompt for /v1/responses
        "endpoint_type": "response",

        # Performance metrics
        "input_tokens": _to_int(r_attr("gen_ai.usage.input_tokens")),
        "output_tokens": _to_int(r_attr("gen_ai.usage.output_tokens")),
        "response_time_ms": _to_int(r_attr("gen_ai.response_time_ms")),
        "ttft_ms": _to_int(r_attr("gen_ai.ttft_ms")),
        "cached": False,
        "finish_reason": None,

        # Processing time
        "processing_time_ms": _to_int(r_attr("gen_ai.processing_time_ms")),

        # Gateway analytics
        "method": g_attr("gateway_analytics.method"),
        "path": g_attr("gateway_analytics.path"),
        "country_code": g_attr("gateway_analytics.country_code"),
        "device_type": g_attr("gateway_analytics.device_type"),
        "browser_name": g_attr("gateway_analytics.browser_name"),
        "is_blocked": _to_bool(g_attr("gateway_analytics.is_blocked")),
        "gateway_processing_ms": _to_int(g_attr("gateway_analytics.gateway_processing_ms")),
        "total_duration_ms": _to_int(g_attr("gateway_analytics.total_duration_ms")),

        # Error tracking
        "error_code": r_attr("error.type"),
        "error_message": r_attr("error.message"),
        "error_type": r_attr("error.type"),

        # Prompt analytics (key fields for /v1/responses)
        "prompt_id": r_attr("bud.prompt_id"),
        "client_prompt_id": r_attr("gen_ai.prompt.id"),
        "prompt_version": r_attr("gen_ai.prompt.version"),
        "prompt_variables": r_attr("gen_ai.prompt.variables"),
        "response_id": r_attr("gen_ai.response.id"),
        "response_status": r_attr("gen_ai.response.status"),

        # Blocking event data
        "blocking_event_id": g_attr("gateway_blocking_events.id"),
        "rule_id": g_attr("gateway_blocking_events.rule_id"),
        "rule_type": g_attr("gateway_blocking_events.rule_type"),
        "rule_name": g_attr("gateway_blocking_events.rule_name"),
        "rule_priority": _to_int(g_attr("gateway_blocking_events.rule_priority")),
        "block_reason": g_attr("gateway_analytics.block_reason"),
        "block_reason_detail": g_attr("gateway_blocking_events.block_reason"),
        "action_taken": g_attr("gateway_blocking_events.action_taken"),

        # Content fields
        "system_prompt": r_attr("gen_ai.system.instructions"),
        "input_messages": r_attr("gen_ai.input.messages"),
        "output": r_attr("gen_ai.output.messages"),
        "raw_request": r_attr("gen_ai.raw_request"),
        "raw_response": r_attr("gen_ai.raw_response"),
    }


def _derive_standard_endpoint_fact(handler: dict | None, gateway: dict | None) -> dict:
    """Derive expected InferenceFact for standard endpoints (chat, embedding, etc).

    Mirrors mv_otel_to_inference_fact logic.
    """
    def h_attr(key: str) -> str | None:
        return _get_span_attr(handler, key) if handler else None

    def g_attr(key: str) -> str | None:
        return _get_span_attr(gateway, key) if gateway else None

    # Derive is_success using MV logic
    is_success = _derive_is_success(h_attr, g_attr)

    # Derive endpoint_type
    endpoint_type = _derive_endpoint_type(h_attr, g_attr)

    return {
        # Core identifiers (COALESCE handler → gateway)
        "trace_id": gateway.get("TraceId") if gateway else (handler.get("TraceId") if handler else None),
        "span_id": _coalesce(
            handler.get("SpanId") if handler else None,
            gateway.get("SpanId") if gateway else None
        ),
        "inference_id": _coalesce(
            h_attr("model_inference_details.inference_id"),
            g_attr("gateway_analytics.inference_id")
        ),
        "project_id": _coalesce(
            h_attr("model_inference_details.project_id"),
            g_attr("bud.project_id")
        ),
        "endpoint_id": _coalesce(
            h_attr("model_inference_details.endpoint_id"),
            g_attr("bud.endpoint_id")
        ),
        "model_id": h_attr("model_inference_details.model_id"),
        "api_key_id": _coalesce(
            h_attr("model_inference_details.api_key_id"),
            g_attr("bud.api_key_id")
        ),
        "api_key_project_id": _coalesce(
            h_attr("model_inference_details.api_key_project_id"),
            g_attr("bud.project_id")
        ),
        "user_id": _coalesce(
            h_attr("model_inference_details.user_id"),
            g_attr("bud.user_id")
        ),

        # Status
        "is_success": is_success,
        "status_code": _to_int(_coalesce(
            h_attr("model_inference_details.status_code"),
            g_attr("gateway_analytics.status_code")
        )),
        "cost": _to_float(h_attr("model_inference_details.cost")),

        # Model info (prefer handler, fallback to gateway, then empty string)
        "model_name": _coalesce(
            h_attr("model_inference.model_name"),
            g_attr("gateway_analytics.model_name"),
            ""
        ),
        "model_provider": _coalesce(
            h_attr("model_inference.model_provider_name"),
            g_attr("gateway_analytics.model_provider"),
            ""
        ),
        "endpoint_type": endpoint_type,

        # Performance metrics
        "input_tokens": _to_int(h_attr("model_inference.input_tokens")),
        "output_tokens": _to_int(h_attr("model_inference.output_tokens")),
        "response_time_ms": _to_int(h_attr("model_inference.response_time_ms")),
        "ttft_ms": _to_int(h_attr("model_inference.ttft_ms")),
        "cached": _to_bool(h_attr("model_inference.cached")),
        "finish_reason": h_attr("model_inference.finish_reason"),

        # Chat inference
        "chat_inference_id": h_attr("chat_inference.id"),
        "episode_id": h_attr("chat_inference.episode_id"),
        "function_name": h_attr("chat_inference.function_name"),
        "variant_name": h_attr("chat_inference.variant_name"),
        "processing_time_ms": _to_int(_coalesce(
            h_attr("chat_inference.processing_time_ms"),
            h_attr("gen_ai.processing_time_ms")
        )),

        # Gateway analytics
        "method": g_attr("gateway_analytics.method"),
        "path": g_attr("gateway_analytics.path"),
        "country_code": g_attr("gateway_analytics.country_code"),
        "device_type": g_attr("gateway_analytics.device_type"),
        "browser_name": g_attr("gateway_analytics.browser_name"),
        "is_blocked": _to_bool(g_attr("gateway_analytics.is_blocked")),
        "gateway_processing_ms": _to_int(g_attr("gateway_analytics.gateway_processing_ms")),
        "total_duration_ms": _to_int(g_attr("gateway_analytics.total_duration_ms")),

        # Prompt analytics (NULL for non-response endpoints)
        "prompt_id": None,
        "client_prompt_id": None,
        "prompt_version": None,
        "prompt_variables": None,
        "response_id": None,
        "response_status": None,

        # Error tracking
        "error_code": h_attr("model_inference_details.error_code"),
        "error_message": _coalesce(
            h_attr("model_inference_details.error_message"),
            h_attr("error.message"),
            g_attr("gateway_analytics.error_message")
        ),
        "error_type": _coalesce(
            h_attr("model_inference_details.error_type"),
            h_attr("error.type"),
            g_attr("gateway_analytics.error_type")
        ),

        # Blocking event data
        "blocking_event_id": g_attr("gateway_blocking_events.id"),
        "rule_id": g_attr("gateway_blocking_events.rule_id"),
        "rule_type": g_attr("gateway_blocking_events.rule_type"),
        "rule_name": g_attr("gateway_blocking_events.rule_name"),
        "rule_priority": _to_int(g_attr("gateway_blocking_events.rule_priority")),
        "block_reason": g_attr("gateway_analytics.block_reason"),
        "block_reason_detail": g_attr("gateway_blocking_events.block_reason"),
        "action_taken": g_attr("gateway_blocking_events.action_taken"),

        # Audio endpoint data
        "audio_duration_seconds": _to_float(h_attr("audio_inference.duration_seconds")),
        "audio_language": h_attr("audio_inference.language"),
        "audio_detected_language": h_attr("audio_inference.detected_language"),
        "audio_voice": h_attr("audio_inference.voice"),
        "audio_response_format": h_attr("audio_inference.response_format"),
        "tts_character_count": _to_int(h_attr("audio_inference.character_count")),

        # Image endpoint data
        "images_generated": _to_int(h_attr("image_inference.images_generated")),
        "image_size": h_attr("image_inference.size"),
        "image_quality": h_attr("image_inference.quality"),
        "image_style": h_attr("image_inference.style"),

        # Embedding endpoint data
        "embedding_input_count": _to_int(h_attr("embedding_inference.input_count")),
        "embedding_dimensions": _to_int(h_attr("embedding_inference.dimensions")),
        "embedding_encoding_format": h_attr("embedding_inference.encoding_format"),

        # Document endpoint data
        "document_page_count": _to_int(h_attr("document_inference.page_count")),

        # Content fields
        "system_prompt": h_attr("model_inference.system"),
        "input_messages": h_attr("model_inference.input_messages"),
        "output": h_attr("model_inference.output"),
        "raw_request": h_attr("model_inference.raw_request"),
        "raw_response": h_attr("model_inference.raw_response"),
        "gateway_request": h_attr("model_inference.gateway_request"),
        "gateway_response": h_attr("model_inference.gateway_response"),
        "guardrail_scan_summary": h_attr("model_inference.guardrail_scan_summary"),
        "chat_input": h_attr("chat_inference.input"),
        "chat_output": h_attr("chat_inference.output"),
        "tags": h_attr("chat_inference.tags"),
        "inference_params": h_attr("chat_inference.inference_params"),
        "extra_body": h_attr("chat_inference.extra_body"),
        "tool_params": h_attr("chat_inference.tool_params"),
    }


def _derive_is_success(h_attr, g_attr) -> bool:
    """Derive is_success using MV logic.

    MV logic:
    - If model_inference_details.is_success = 'true', return true
    - If model_inference_details.is_success = 'false', return false
    - Otherwise, derive from status_code < 400
    """
    explicit = h_attr("model_inference_details.is_success")
    if explicit == "true":
        return True
    if explicit == "false":
        return False
    # Fallback: status_code < 400
    status = _to_int(_coalesce(
        h_attr("model_inference_details.status_code"),
        g_attr("gateway_analytics.status_code")
    )) or 500
    return status < 400


def _derive_endpoint_type(h_attr, g_attr) -> str:
    """Derive endpoint_type from handler or gateway path.

    MV logic:
    - If handler has endpoint_type, use it
    - Otherwise derive from gateway path
    """
    handler_type = h_attr("model_inference.endpoint_type")
    if handler_type:
        return handler_type

    path = g_attr("gateway_analytics.path") or ""

    # Order matters - more specific paths first
    if "/chat/completions" in path:
        return "chat"
    if "/completions" in path:
        return "completion"
    if "/embeddings" in path:
        return "embedding"
    if "/messages" in path:
        return "anthropic"
    if "/audio/transcriptions" in path:
        return "audio_transcription"
    if "/audio/translations" in path:
        return "audio_translation"
    if "/audio/speech" in path:
        return "text_to_speech"
    if "/images/generations" in path:
        return "image_generation"
    if "/images/edits" in path:
        return "image_edit"
    if "/images/variations" in path:
        return "image_variation"
    if "/moderations" in path:
        return "moderation"
    if "/classify" in path:
        return "classify"
    if "/documents" in path:
        return "document"
    if "/responses" in path:
        return "response"
    if "/realtime" in path:
        return "realtime"

    return "unknown"


# =============================================================================
# AGGREGATE HELPER FUNCTIONS
# =============================================================================


def get_expected_row_count(seeder_data: dict, scenario_keys: list[str] | None = None) -> int:
    """Get expected InferenceFact row count from seeder.

    The MV creates rows from:
    - response_create_handler_observability spans (for /v1/responses)
    - gateway_analytics spans with inference_id (for /v1/chat/completions, etc.)

    Args:
        seeder_data: Full seeder data dict
        scenario_keys: Optional list of scenario keys to count (default: all)

    Returns:
        Expected row count
    """
    keys = scenario_keys or list(seeder_data.keys())
    count = 0
    for key in keys:
        spans = seeder_data.get(key, [])
        # Count gateway_analytics spans with inference_id (for non-response endpoints)
        gateway_count = sum(
            1 for s in spans
            if (s.get("SpanName") == "gateway_analytics"
                and _get_span_attr(s, "gateway_analytics.inference_id")
                and _get_span_attr(s, "gateway_analytics.path") != "/v1/responses")
        )
        # Count response_create_handler_observability spans (for /v1/responses)
        response_count = sum(
            1 for s in spans
            if s.get("SpanName") == "response_create_handler_observability"
        )
        count += gateway_count + response_count
    return count


def get_expected_rollup_totals(seeder_data: dict) -> dict:
    """Get expected rollup totals derived from seeder.

    Returns aggregated values that rollup tables should contain.

    Args:
        seeder_data: Full seeder data dict

    Returns:
        Dict with request_count, total_input_tokens, total_output_tokens,
        unique_prompt_ids, success_count, error_count
    """
    total_requests = 0
    total_input_tokens = 0
    total_output_tokens = 0
    prompt_ids = set()
    success_count = 0
    error_count = 0

    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            total_requests += 1
            total_input_tokens += expected.get("input_tokens") or 0
            total_output_tokens += expected.get("output_tokens") or 0

            if expected.get("prompt_id"):
                prompt_ids.add(expected["prompt_id"])

            if expected.get("is_success"):
                success_count += 1
            else:
                error_count += 1

    return {
        "request_count": total_requests,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "unique_prompt_ids": prompt_ids,
        "success_count": success_count,
        "error_count": error_count,
    }


def get_expected_blocked_count(seeder_data: dict) -> int:
    """Get expected count of blocked requests."""
    count = 0
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            if expected.get("is_blocked"):
                count += 1
    return count


def get_expected_rows_with_tokens(seeder_data: dict) -> int:
    """Get expected count of rows with non-NULL tokens."""
    count = 0
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            if expected.get("input_tokens") is not None:
                count += 1
    return count


def get_expected_performance_totals(seeder_data: dict) -> dict:
    """Get expected performance metric totals."""
    totals = {
        "total_response_time_ms": 0,
        "total_ttft_ms": 0,
        "total_processing_time_ms": 0,
        "total_gateway_processing_ms": 0,
        "total_duration_ms": 0,
    }
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            totals["total_response_time_ms"] += expected.get("response_time_ms") or 0
            totals["total_ttft_ms"] += expected.get("ttft_ms") or 0
            totals["total_processing_time_ms"] += expected.get("processing_time_ms") or 0
            totals["total_gateway_processing_ms"] += expected.get("gateway_processing_ms") or 0
            totals["total_duration_ms"] += expected.get("total_duration_ms") or 0
    return totals


def get_expected_dimension_values(seeder_data: dict, dimension: str) -> set:
    """Get all expected values for a dimension UUID."""
    values = set()
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            val = expected.get(dimension)
            if val:
                values.add(str(val))
    return values


def get_expected_endpoint_type_counts(seeder_data: dict) -> dict:
    """Get expected count per endpoint_type."""
    counts = {}
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            ep_type = expected.get("endpoint_type") or "unknown"
            counts[ep_type] = counts.get(ep_type, 0) + 1
    return counts


def get_expected_prompt_analytics_counts(seeder_data: dict) -> dict:
    """Get expected prompt analytics counts."""
    counts = {
        "with_prompt_id": 0,
        "with_client_prompt_id": 0,
        "with_response_id": 0,
    }
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            if expected.get("prompt_id"):
                counts["with_prompt_id"] += 1
            if expected.get("client_prompt_id"):
                counts["with_client_prompt_id"] += 1
            if expected.get("response_id"):
                counts["with_response_id"] += 1
    return counts


def get_expected_prompt_analytics_values(seeder_data: dict, field: str) -> set:
    """Get all expected values for a prompt analytics field."""
    values = set()
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            val = expected.get(field)
            if val:
                values.add(str(val))
    return values


def get_expected_model_values(seeder_data: dict, field: str) -> set:
    """Get all expected values for model info fields."""
    values = set()
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            val = expected.get(field)
            if val:
                values.add(str(val))
    return values


def get_expected_finish_reason_counts(seeder_data: dict) -> dict:
    """Get expected count per finish_reason."""
    counts = {}
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            reason = expected.get("finish_reason")
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
    return counts


def get_expected_cached_count(seeder_data: dict) -> int:
    """Get expected count of cached=true rows."""
    count = 0
    for scenario_key in seeder_data:
        facts = get_all_expected_inference_facts(seeder_data, scenario_key)
        for expected in facts:
            if expected.get("cached"):
                count += 1
    return count


def get_scenario_trace_ids(seeder_data: dict, scenario_key: str) -> list[str]:
    """Get all trace_ids for a scenario (handles multi-inference traces)."""
    spans = seeder_data.get(scenario_key, [])
    return list(set(s["TraceId"] for s in spans))


def get_scenario_inference_ids(seeder_data: dict, scenario_key: str) -> list[str]:
    """Get all expected inference_ids for a scenario."""
    spans = seeder_data.get(scenario_key, [])
    inference_ids = []

    for span in spans:
        attrs = span.get("SpanAttributes", {})
        # Check multiple possible sources of inference_id
        inf_id = (
            attrs.get("gateway_analytics.inference_id") or
            attrs.get("model_inference_details.inference_id") or
            attrs.get("gen_ai.inference_id")
        )
        if inf_id:
            inference_ids.append(inf_id)

    return list(set(inference_ids))


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================


# Columns to skip in comparison (auto-generated or format-dependent)
SKIP_COLUMNS = {
    "id",                    # Generated UUID
    "timestamp",             # DateTime format comparison
    "request_arrival_time",  # DateTime
    "request_forward_time",  # DateTime
    "request_timestamp",     # DateTime
    "response_timestamp",    # DateTime
    "blocked_at",            # DateTime
    "model_inference_timestamp",  # UInt64 timestamp
    "input_messages",        # Large JSON content
    "output",                # Large content
    "raw_request",           # Large content
    "raw_response",          # Large content
    "gateway_request",       # Large content
    "gateway_response",      # Large content
    "chat_input",            # Large content
    "chat_output",           # Large content
    "system_prompt",         # Large content
    "prompt_variables",      # JSON comparison
    "inference_params",      # JSON comparison
    "extra_body",            # JSON comparison
    "tool_params",           # JSON comparison
    "tags",                  # JSON comparison
    "guardrail_scan_summary",  # Large content
    "request_headers",       # JSON comparison
    "response_headers",      # JSON comparison
    "gateway_tags",          # JSON comparison
}


def compare_values(expected: Any, actual: Any, column: str) -> bool:
    """Type-aware comparison handling ClickHouse NULL representations.

    Args:
        expected: Expected value from ground_truth
        actual: Actual value from ClickHouse query
        column: Column name for context

    Returns:
        True if values match, False otherwise
    """
    # None/NULL handling
    if expected is None:
        # ClickHouse can return empty string, 0, or NULL for NULL values
        return actual is None or actual == "" or actual == "0.0.0.0" or actual == 0

    # Boolean
    if isinstance(expected, bool):
        if isinstance(actual, bool):
            return expected == actual
        # Handle string representations
        return expected == (actual == "true" or actual == 1 or actual is True)

    # Numeric with tolerance
    if isinstance(expected, (int, float)):
        try:
            actual_num = float(actual) if actual not in (None, "") else 0
            return abs(expected - actual_num) < 0.0001
        except (ValueError, TypeError):
            return False

    # String comparison
    return str(expected) == str(actual)
