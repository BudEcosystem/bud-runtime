"""Unit tests for the telemetry span tree builder in ObservabilityMetricsService."""

from datetime import datetime, timezone

from budmetrics.observability.services import ObservabilityMetricsService
from budmetrics.observability.schemas import (
    DEFAULT_SELECT_COLUMNS,
    TelemetryQueryRequest,
)


def _make_request(**overrides) -> TelemetryQueryRequest:
    """Create a minimal valid TelemetryQueryRequest."""
    defaults = {
        "prompt_id": "test_prompt",
        "from_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "project_id": "proj-123",
        "depth": 0,
    }
    defaults.update(overrides)
    return TelemetryQueryRequest(**defaults)


def _column_names(request: TelemetryQueryRequest | None = None) -> list[str]:
    """Build column names matching the row tuple layout.

    Mirrors ObservabilityMetricsService._get_telemetry_column_names logic.
    """
    cols = list(DEFAULT_SELECT_COLUMNS)
    if request is None or (request.span_names is None and not request.include_all_attributes):
        cols.append("_internal:prompt_id")
        cols.append("_internal:project_id")
    return cols


def _make_row(
    timestamp="2026-01-01T00:00:00",
    trace_id="trace1",
    span_id="span1",
    parent_span_id="",
    trace_state="",
    span_name="gateway_analytics",
    span_kind="INTERNAL",
    service_name="bud-gateway",
    scope_name="",
    scope_version="",
    duration=1000,
    status_code="OK",
    status_message="",
    prompt_id="test_prompt",
    project_id="proj-123",
) -> tuple:
    """Create a row tuple matching DEFAULT_SELECT_COLUMNS + internal columns order."""
    return (
        timestamp,
        trace_id,
        span_id,
        parent_span_id,
        trace_state,
        span_name,
        span_kind,
        service_name,
        scope_name,
        scope_version,
        duration,
        status_code,
        status_message,
        prompt_id,
        project_id,
    )


# Trace structure for testing:
#   gateway_analytics (span1, root)
#     └── POST /v1/responses (span2)
#           └── handler (span3)
#                 └── chat gpt (span4)
_FLAT_ROWS = [
    _make_row(span_id="span1", parent_span_id="", span_name="gateway_analytics"),
    _make_row(span_id="span2", parent_span_id="span1", span_name="POST /v1/responses"),
    _make_row(span_id="span3", parent_span_id="span2", span_name="handler"),
    _make_row(span_id="span4", parent_span_id="span3", span_name="chat gpt"),
]


class TestDepthZero:
    """Test depth=0 returns target spans only with empty children."""

    def test_returns_target_spans_only(self):
        """depth=0 returns gateway_analytics with children=[]."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        assert len(result) == 1
        assert result[0].span_name == "gateway_analytics"
        assert result[0].children == []

    def test_child_count_includes_all_descendants(self):
        """child_count is total descendants (3), not just direct children (1)."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        assert result[0].child_count == 3


class TestDepthOne:
    """Test depth=1 returns target spans + direct children."""

    def test_includes_direct_children(self):
        """depth=1 nests direct children only."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=1)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        assert len(result) == 1
        root = result[0]
        assert len(root.children) == 1
        assert root.children[0].span_name == "POST /v1/responses"
        # Direct child should have empty children at depth=1
        assert root.children[0].children == []

    def test_child_has_correct_child_count(self):
        """Direct child still reports total descendants."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=1)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        child = result[0].children[0]
        assert child.child_count == 2  # handler + chat gpt


class TestDepthTwo:
    """Test depth=2 returns two levels of nesting."""

    def test_two_levels(self):
        """depth=2 nests two levels."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=2)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        root = result[0]
        assert len(root.children) == 1
        child = root.children[0]
        assert len(child.children) == 1
        assert child.children[0].span_name == "handler"
        # Third level pruned
        assert child.children[0].children == []


class TestDepthUnlimited:
    """Test depth=-1 returns full tree."""

    def test_full_tree(self):
        """depth=-1 returns complete nested tree."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=-1)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        root = result[0]
        assert root.span_name == "gateway_analytics"
        assert len(root.children) == 1
        level1 = root.children[0]
        assert level1.span_name == "POST /v1/responses"
        assert len(level1.children) == 1
        level2 = level1.children[0]
        assert level2.span_name == "handler"
        assert len(level2.children) == 1
        level3 = level2.children[0]
        assert level3.span_name == "chat gpt"
        assert level3.children == []
        assert level3.child_count == 0


class TestSpanNamesSelection:
    """Test span_names-based target selection."""

    def test_default_selects_gateway_analytics(self):
        """span_names=None selects gateway_analytics as targets."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        assert len(result) == 1
        assert result[0].span_name == "gateway_analytics"

    def test_single_span_name(self):
        """span_names=['POST /v1/responses'] selects only those spans."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(span_names=["POST /v1/responses"], depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        assert len(result) == 1
        assert result[0].span_name == "POST /v1/responses"
        assert result[0].child_count == 2

    def test_multiple_span_names(self):
        """span_names=['chat gpt', 'handler'] selects both."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(span_names=["chat gpt", "handler"], depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, _column_names(request), request
        )

        names = {s.span_name for s in result}
        assert names == {"chat gpt", "handler"}


class TestMultiPromptTraceFiltering:
    """Test that gateway_analytics spans from other prompts sharing the same trace are excluded."""

    def test_filters_out_other_prompt_gateway_analytics(self):
        """Only gateway_analytics spans matching request prompt_id/project_id are targets."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(prompt_id="prompt_A", project_id="proj-1", depth=0)

        # Two gateway_analytics spans in the same trace but for different prompts
        rows = [
            _make_row(
                trace_id="shared_trace",
                span_id="ga1",
                parent_span_id="",
                span_name="gateway_analytics",
                prompt_id="prompt_A",
                project_id="proj-1",
            ),
            _make_row(
                trace_id="shared_trace",
                span_id="ga2",
                parent_span_id="",
                span_name="gateway_analytics",
                prompt_id="prompt_B",
                project_id="proj-1",
            ),
            _make_row(
                trace_id="shared_trace",
                span_id="child1",
                parent_span_id="ga1",
                span_name="handler",
                prompt_id="",
                project_id="",
            ),
        ]

        result = service._build_telemetry_span_tree(rows, _column_names(request), request)

        # Only the gateway_analytics for prompt_A should be a target
        assert len(result) == 1
        assert result[0].span_id == "ga1"

    def test_filters_out_other_project_gateway_analytics(self):
        """gateway_analytics span with wrong project_id is excluded."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(prompt_id="prompt_A", project_id="proj-1", depth=0)

        rows = [
            _make_row(
                trace_id="trace1",
                span_id="ga1",
                span_name="gateway_analytics",
                prompt_id="prompt_A",
                project_id="proj-1",
            ),
            _make_row(
                trace_id="trace1",
                span_id="ga2",
                span_name="gateway_analytics",
                prompt_id="prompt_A",
                project_id="proj-WRONG",
            ),
        ]

        result = service._build_telemetry_span_tree(rows, _column_names(request), request)

        assert len(result) == 1
        assert result[0].span_id == "ga1"

    def test_include_all_attributes_uses_attributes_for_filtering(self):
        """When include_all_attributes=True, filtering uses span attributes dict."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(
            prompt_id="prompt_A",
            project_id="proj-1",
            depth=0,
            include_all_attributes=True,
        )

        # With include_all_attributes, rows include SpanAttributes + ResourceAttributes maps
        # instead of internal columns. Build column list matching this mode.
        cols = list(DEFAULT_SELECT_COLUMNS) + ["SpanAttributes", "ResourceAttributes"]

        row_matching = (
            "2026-01-01T00:00:00", "trace1", "ga1", "", "", "gateway_analytics",
            "INTERNAL", "bud-gateway", "", "", 1000, "OK", "",
            {"gateway_analytics.prompt_id": "prompt_A", "gateway_analytics.project_id": "proj-1"},
            {},
        )
        row_other = (
            "2026-01-01T00:00:00", "trace1", "ga2", "", "", "gateway_analytics",
            "INTERNAL", "bud-gateway", "", "", 1000, "OK", "",
            {"gateway_analytics.prompt_id": "prompt_B", "gateway_analytics.project_id": "proj-1"},
            {},
        )

        result = service._build_telemetry_span_tree([row_matching, row_other], cols, request)

        assert len(result) == 1
        assert result[0].span_id == "ga1"


class TestEmptyData:
    """Test edge cases."""

    def test_empty_rows(self):
        """Empty trace data returns empty list."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=0)
        result = service._build_telemetry_span_tree(
            [], _column_names(request), request
        )

        assert result == []
