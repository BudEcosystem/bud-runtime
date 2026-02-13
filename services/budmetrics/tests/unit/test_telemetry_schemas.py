"""Unit tests for TelemetryQueryRequest schema validation."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from budmetrics.observability.schemas import (
    FilterCondition,
    FilterOperator,
    TelemetryQueryRequest,
)


def _make_request(**overrides) -> TelemetryQueryRequest:
    """Create a minimal valid TelemetryQueryRequest."""
    defaults = {
        "prompt_id": "test_prompt",
        "from_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return TelemetryQueryRequest(**defaults)


class TestDepthValidation:
    """Test depth field constraints."""

    def test_rejects_depth_below_minus_one(self):
        """Depth < -1 is rejected."""
        with pytest.raises(ValidationError):
            _make_request(depth=-2)

    def test_rejects_depth_above_ten(self):
        """Depth > 10 is rejected."""
        with pytest.raises(ValidationError):
            _make_request(depth=11)

    def test_accepts_valid_depths(self):
        """Depth in [-1, 0, 1, ..., 10] is accepted."""
        for d in [-1, 0, 1, 5, 10]:
            request = _make_request(depth=d)
            assert request.depth == d


class TestTimeRangeValidation:
    """Test time range constraints."""

    def test_rejects_range_over_90_days(self):
        """Time range > 90 days is rejected."""
        with pytest.raises(ValidationError, match="90 days"):
            _make_request(
                from_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )

    def test_accepts_90_day_range(self):
        """Exactly 90 days is accepted."""
        from_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        to_dt = from_dt + timedelta(days=90)
        request = _make_request(from_date=from_dt, to_date=to_dt)
        assert request.to_date == to_dt

    def test_rejects_to_date_before_from_date(self):
        """to_date before from_date is rejected."""
        with pytest.raises(ValidationError, match="to_date must be after from_date"):
            _make_request(
                from_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
                to_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )


class TestSelectAttributesValidation:
    """Test select_attributes constraints."""

    def test_rejects_over_50_select_attributes(self):
        """More than 50 select_attributes is rejected."""
        attrs = [f"attr_{i}" for i in range(51)]
        with pytest.raises(ValidationError):
            _make_request(select_attributes=attrs)

    def test_rejects_invalid_attribute_keys(self):
        """Invalid attribute keys in select_attributes are rejected."""
        with pytest.raises(ValidationError):
            _make_request(select_attributes=["valid.key", "bad'key"])


class TestFilterLimits:
    """Test filter count limits."""

    def test_rejects_over_20_span_filters(self):
        """More than 20 span_filters is rejected."""
        filters = [
            FilterCondition(field=f"field_{i}", op=FilterOperator.eq, value="v")
            for i in range(21)
        ]
        with pytest.raises(ValidationError):
            _make_request(span_filters=filters)

    def test_rejects_over_20_resource_filters(self):
        """More than 20 resource_filters is rejected."""
        filters = [
            FilterCondition(field=f"field_{i}", op=FilterOperator.eq, value="v")
            for i in range(21)
        ]
        with pytest.raises(ValidationError):
            _make_request(resource_filters=filters)


class TestSpanNamesLimits:
    """Test span_names count limit."""

    def test_rejects_over_20_span_names(self):
        """More than 20 span_names is rejected."""
        names = [f"span_{i}" for i in range(21)]
        with pytest.raises(ValidationError):
            _make_request(span_names=names)


class TestMinimalRequest:
    """Test that minimal valid request works."""

    def test_accepts_minimal_request(self):
        """Just prompt_id + from_date is valid."""
        request = _make_request()
        assert request.prompt_id == "test_prompt"
        assert request.depth == 0
        assert request.limit == 50
        assert request.offset == 0
        assert request.span_names is None
        assert request.span_filters is None
        assert request.resource_filters is None
