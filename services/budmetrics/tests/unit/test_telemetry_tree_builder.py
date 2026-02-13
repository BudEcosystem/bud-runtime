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
) -> tuple:
    """Create a row tuple matching DEFAULT_SELECT_COLUMNS order."""
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
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
        )

        assert len(result) == 1
        assert result[0].span_name == "gateway_analytics"
        assert result[0].children == []

    def test_child_count_includes_all_descendants(self):
        """child_count is total descendants (3), not just direct children (1)."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
        )

        assert result[0].child_count == 3


class TestDepthOne:
    """Test depth=1 returns target spans + direct children."""

    def test_includes_direct_children(self):
        """depth=1 nests direct children only."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=1)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
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
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
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
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
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
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
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
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
        )

        assert len(result) == 1
        assert result[0].span_name == "gateway_analytics"

    def test_single_span_name(self):
        """span_names=['POST /v1/responses'] selects only those spans."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(span_names=["POST /v1/responses"], depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
        )

        assert len(result) == 1
        assert result[0].span_name == "POST /v1/responses"
        assert result[0].child_count == 2

    def test_multiple_span_names(self):
        """span_names=['chat gpt', 'handler'] selects both."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(span_names=["chat gpt", "handler"], depth=0)
        result = service._build_telemetry_span_tree(
            _FLAT_ROWS, list(DEFAULT_SELECT_COLUMNS), request
        )

        names = {s.span_name for s in result}
        assert names == {"chat gpt", "handler"}


class TestEmptyData:
    """Test edge cases."""

    def test_empty_rows(self):
        """Empty trace data returns empty list."""
        service = ObservabilityMetricsService.__new__(ObservabilityMetricsService)
        request = _make_request(depth=0)
        result = service._build_telemetry_span_tree(
            [], list(DEFAULT_SELECT_COLUMNS), request
        )

        assert result == []
