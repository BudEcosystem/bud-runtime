"""Unit tests for the TelemetryQueryBuilder."""

from datetime import datetime, timezone

import pytest

from budmetrics.observability.services import TelemetryQueryBuilder
from budmetrics.observability.schemas import (
    FilterCondition,
    FilterOperator,
    OrderBySpec,
    TelemetryQueryRequest,
    validate_attribute_key,
)


def _make_request(**overrides) -> TelemetryQueryRequest:
    """Create a minimal valid TelemetryQueryRequest with optional overrides."""
    defaults = {
        "prompt_id": "test_prompt",
        "from_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "project_id": "proj-123",
    }
    defaults.update(overrides)
    return TelemetryQueryRequest(**defaults)


class TestBuildQueryDefault:
    """Test default query generation (no span_names, no filters)."""

    def test_default_query_contains_gateway_analytics(self):
        """Default query filters on gateway_analytics spans."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        data_query, count_query, params = builder.build_query(request)

        assert "SpanName = 'gateway_analytics'" in count_query
        assert "gateway_analytics.prompt_id" in count_query
        assert "gateway_analytics.project_id" in count_query
        assert "%(prompt_id)s" in count_query
        assert "%(project_id)s" in count_query

    def test_count_query_uses_distinct_trace_id(self):
        """Count query counts distinct traces, not individual spans."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        _, count_query, _ = builder.build_query(request)

        assert "count(DISTINCT TraceId)" in count_query

    def test_default_query_has_timestamp_filters(self):
        """Default query includes timestamp range conditions."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        _, count_query, params = builder.build_query(request)

        assert "Timestamp >= %(from_date)s" in count_query
        assert "Timestamp <= %(to_date)s" in count_query
        assert params["from_date"] == request.from_date
        assert "to_date" in params

    def test_data_query_uses_trace_id_subquery(self):
        """Data query fetches all spans for matching trace IDs."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        data_query, _, _ = builder.build_query(request)

        assert "TraceId IN" in data_query
        assert "SELECT DISTINCT TraceId" in data_query
        assert "ORDER BY Timestamp ASC" in data_query

    def test_params_contain_required_keys(self):
        """Parameters include prompt_id, project_id, from_date, to_date, limit, offset."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        _, _, params = builder.build_query(request)

        assert params["prompt_id"] == "test_prompt"
        assert params["project_id"] == "proj-123"
        assert params["limit"] == 50
        assert params["offset"] == 0


class TestSpanNames:
    """Test span_names-based query generation."""

    def test_span_names_generates_in_clause(self):
        """span_names produces SpanName IN clause in count query."""
        builder = TelemetryQueryBuilder()
        request = _make_request(span_names=["POST /v1/responses"])
        _, count_query, params = builder.build_query(request)

        assert "SpanName IN" in count_query
        assert "%(span_name_0)s" in count_query
        assert params["span_name_0"] == "POST /v1/responses"

    def test_multiple_span_names(self):
        """Multiple span_names produces correct IN clause."""
        builder = TelemetryQueryBuilder()
        request = _make_request(span_names=["chat gpt", "POST"])
        _, count_query, params = builder.build_query(request)

        assert "%(span_name_0)s" in count_query
        assert "%(span_name_1)s" in count_query
        assert params["span_name_0"] == "chat gpt"
        assert params["span_name_1"] == "POST"


class TestVersionAndTraceId:
    """Test version and trace_id filter conditions."""

    def test_version_filter(self):
        """Version adds prompt_version condition."""
        builder = TelemetryQueryBuilder()
        request = _make_request(version="1")
        _, count_query, params = builder.build_query(request)

        assert "gateway_analytics.prompt_version" in count_query
        assert "%(version)s" in count_query
        assert params["version"] == "1"

    def test_trace_id_filter(self):
        """trace_id adds TraceId condition."""
        builder = TelemetryQueryBuilder()
        request = _make_request(trace_id="abc123")
        _, count_query, params = builder.build_query(request)

        assert "TraceId = %(trace_id)s" in count_query
        assert params["trace_id"] == "abc123"


class TestSpanFilters:
    """Test span_filters on SpanAttributes."""

    def test_eq_filter(self):
        """Eq operator produces = comparison."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="gateway_analytics.status_code", op=FilterOperator.eq, value="200")]
        )
        _, count_query, params = builder.build_query(request)

        assert "SpanAttributes['gateway_analytics.status_code'] = %(span_f0)s" in count_query
        assert params["span_f0"] == "200"

    def test_neq_filter(self):
        """Neq operator produces != comparison."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="status", op=FilterOperator.neq, value="error")]
        )
        _, count_query, params = builder.build_query(request)

        assert "SpanAttributes['status'] != %(span_f0)s" in count_query

    def test_gt_filter(self):
        """Gt operator produces numeric > comparison via toFloat64OrZero."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="duration_ms", op=FilterOperator.gt, value="5000")]
        )
        _, count_query, params = builder.build_query(request)

        assert "toFloat64OrZero(SpanAttributes['duration_ms']) > toFloat64OrZero(%(span_f0)s)" in count_query

    def test_gte_filter(self):
        """Gte operator produces numeric >= comparison via toFloat64OrZero."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="count", op=FilterOperator.gte, value="10")]
        )
        _, count_query, params = builder.build_query(request)

        assert "toFloat64OrZero(SpanAttributes['count']) >= toFloat64OrZero(%(span_f0)s)" in count_query

    def test_lt_filter(self):
        """Lt operator produces numeric < comparison via toFloat64OrZero."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="count", op=FilterOperator.lt, value="10")]
        )
        _, count_query, params = builder.build_query(request)

        assert "toFloat64OrZero(SpanAttributes['count']) < toFloat64OrZero(%(span_f0)s)" in count_query

    def test_lte_filter(self):
        """Lte operator produces numeric <= comparison via toFloat64OrZero."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="count", op=FilterOperator.lte, value="10")]
        )
        _, count_query, params = builder.build_query(request)

        assert "toFloat64OrZero(SpanAttributes['count']) <= toFloat64OrZero(%(span_f0)s)" in count_query

    def test_like_filter(self):
        """Like operator produces LIKE comparison."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="name", op=FilterOperator.like, value="%test%")]
        )
        _, count_query, params = builder.build_query(request)

        assert "SpanAttributes['name'] LIKE %(span_f0)s" in count_query

    def test_in_filter(self):
        """in_ operator produces IN clause."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="status", op=FilterOperator.in_, value=["200", "201"])]
        )
        _, count_query, params = builder.build_query(request)

        assert "SpanAttributes['status'] IN" in count_query
        assert "%(span_f0_0)s" in count_query
        assert "%(span_f0_1)s" in count_query

    def test_not_in_filter(self):
        """not_in operator produces NOT IN clause."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="status", op=FilterOperator.not_in, value=["500", "503"])]
        )
        _, count_query, params = builder.build_query(request)

        assert "SpanAttributes['status'] NOT IN" in count_query

    def test_is_null_filter(self):
        """is_null operator produces = '' comparison."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="optional_field", op=FilterOperator.is_null)]
        )
        _, count_query, _ = builder.build_query(request)

        assert "SpanAttributes['optional_field'] = ''" in count_query

    def test_is_not_null_filter(self):
        """is_not_null operator produces != '' comparison."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="optional_field", op=FilterOperator.is_not_null)]
        )
        _, count_query, _ = builder.build_query(request)

        assert "SpanAttributes['optional_field'] != ''" in count_query


class TestResourceFilters:
    """Test resource_filters on ResourceAttributes."""

    def test_resource_filter(self):
        """resource_filters produce ResourceAttributes conditions."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            resource_filters=[FilterCondition(field="service.name", op=FilterOperator.eq, value="bud-gateway")]
        )
        _, count_query, params = builder.build_query(request)

        assert "ResourceAttributes['service.name'] = %(resource_f0)s" in count_query
        assert params["resource_f0"] == "bud-gateway"

    def test_resource_filter_not_in_subquery_when_span_names_set(self):
        """resource_filters must not apply to trace_id subquery when span_names is set."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_names=["chat gpt"],
            resource_filters=[FilterCondition(field="service.name", op=FilterOperator.eq, value="budprompt")],
        )
        data_query, count_query, params = builder.build_query(request)

        # resource_filter should appear in count_query (targets the named spans)
        assert "ResourceAttributes['service.name']" in count_query

        # The trace_id subquery inside data_query should NOT have the resource filter
        # because the subquery always queries gateway_analytics spans
        subquery_start = data_query.index("SELECT DISTINCT TraceId")
        subquery_section = data_query[subquery_start:]
        assert "ResourceAttributes['service.name']" not in subquery_section


class TestSelectClause:
    """Test SELECT clause building."""

    def test_select_attributes(self):
        """select_attributes add SpanAttributes['key'] to SELECT."""
        builder = TelemetryQueryBuilder()
        request = _make_request(select_attributes=["gen_ai.usage.input_tokens"])
        data_query, _, _ = builder.build_query(request)

        assert "SpanAttributes['gen_ai.usage.input_tokens']" in data_query

    def test_default_select_includes_internal_prompt_project_columns(self):
        """Default SELECT includes internal prompt_id and project_id for tree builder filtering."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        data_query, _, _ = builder.build_query(request)

        assert "SpanAttributes['gateway_analytics.prompt_id']" in data_query
        assert "SpanAttributes['gateway_analytics.project_id']" in data_query

    def test_internal_columns_omitted_with_include_all_attributes(self):
        """Internal columns not added when include_all_attributes is True (already available)."""
        builder = TelemetryQueryBuilder()
        request = _make_request(include_all_attributes=True)
        data_query, _, _ = builder.build_query(request)

        # The full SpanAttributes map is included, so internal columns are unnecessary
        assert "SpanAttributes" in data_query
        # Should not have the specific internal column extractions
        select_part = data_query.split("FROM")[0]
        # Count occurrences - SpanAttributes appears once as the map, not as individual keys
        assert "gateway_analytics.prompt_id" not in select_part

    def test_internal_columns_omitted_with_span_names(self):
        """Internal columns not added when span_names is set."""
        builder = TelemetryQueryBuilder()
        request = _make_request(span_names=["POST /v1/responses"])
        data_query, _, _ = builder.build_query(request)

        select_part = data_query.split("FROM")[0]
        assert "gateway_analytics.prompt_id" not in select_part

    def test_include_all_attributes(self):
        """include_all_attributes adds SpanAttributes, ResourceAttributes."""
        builder = TelemetryQueryBuilder()
        request = _make_request(include_all_attributes=True)
        data_query, _, _ = builder.build_query(request)

        assert "SpanAttributes" in data_query
        assert "ResourceAttributes" in data_query

    def test_include_events(self):
        """include_events adds Events columns."""
        builder = TelemetryQueryBuilder()
        request = _make_request(include_events=True)
        data_query, _, _ = builder.build_query(request)

        assert "Events.Timestamp" in data_query
        assert "Events.Name" in data_query
        assert "Events.Attributes" in data_query

    def test_include_links(self):
        """include_links adds Links columns."""
        builder = TelemetryQueryBuilder()
        request = _make_request(include_links=True)
        data_query, _, _ = builder.build_query(request)

        assert "Links.TraceId" in data_query
        assert "Links.SpanId" in data_query
        assert "Links.TraceState" in data_query
        assert "Links.Attributes" in data_query


class TestOrderBy:
    """Test ORDER BY clause generation."""

    def test_default_order(self):
        """Default order is Timestamp DESC."""
        builder = TelemetryQueryBuilder()
        request = _make_request()
        data_query, _, _ = builder.build_query(request)

        # The subquery should have ORDER BY Timestamp DESC
        assert "ORDER BY Timestamp DESC" in data_query

    def test_custom_order(self):
        """Custom order_by generates correct clause."""
        builder = TelemetryQueryBuilder()
        request = _make_request(order_by=[OrderBySpec(field="duration", direction="desc")])
        data_query, _, _ = builder.build_query(request)

        assert "ORDER BY Duration DESC" in data_query

    def test_invalid_order_field_rejected(self):
        """Invalid order_by field raises ValueError."""
        with pytest.raises(ValueError, match="Invalid order_by field"):
            OrderBySpec(field="invalid_column", direction="desc")


class TestAttributeKeyValidation:
    """Test attribute key security validation."""

    def test_rejects_single_quote(self):
        """Keys with single quotes are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key("key'value")

    def test_rejects_double_quote(self):
        """Keys with double quotes are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key('key"value')

    def test_rejects_semicolon(self):
        """Keys with semicolons are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key("key;value")

    def test_rejects_double_dash(self):
        """Keys with SQL comments (--) are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key("key--value")

    def test_rejects_block_comment(self):
        """Keys with block comments (/*) are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key("key/*value")

    def test_rejects_empty_string(self):
        """Empty keys are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key("")

    def test_rejects_long_string(self):
        """Keys > 200 characters are rejected."""
        with pytest.raises(ValueError):
            validate_attribute_key("a" * 201)

    def test_accepts_valid_dotted_key(self):
        """Valid dotted keys (like OTel conventions) pass."""
        assert validate_attribute_key("gen_ai.usage.input_tokens") == "gen_ai.usage.input_tokens"


class TestParameterization:
    """Test that all values are parameterized (never interpolated)."""

    def test_no_raw_value_in_queries(self):
        """User-supplied values should never appear directly in SQL."""
        builder = TelemetryQueryBuilder()
        request = _make_request(
            span_filters=[FilterCondition(field="key", op=FilterOperator.eq, value="danger_value")],
            resource_filters=[FilterCondition(field="svc", op=FilterOperator.eq, value="my-service")],
        )
        data_query, count_query, params = builder.build_query(request)

        # The actual values should only be in params, never in the query text
        assert "danger_value" not in data_query
        assert "danger_value" not in count_query
        assert "my-service" not in data_query
        assert "my-service" not in count_query

        # But they should be in params
        assert "danger_value" in params.values()
        assert "my-service" in params.values()
