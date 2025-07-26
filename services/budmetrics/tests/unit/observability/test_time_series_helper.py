"""Unit tests for TimeSeriesHelper class."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from budmetrics.observability.models import TimeSeriesHelper, Frequency, FrequencyUnit


class TestTimeSeriesHelper:
    """Test cases for TimeSeriesHelper class."""

    def test_get_time_format_standard_frequencies(self):
        """Test time format for standard frequencies."""
        # Test with standard frequencies (value=None)
        freq = Frequency(None, FrequencyUnit.HOUR)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str == "toStartOfHour({time_field})"

        freq = Frequency(None, FrequencyUnit.DAY)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str == "toDate({time_field})"

        freq = Frequency(None, FrequencyUnit.WEEK)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str == "toStartOfWeek({time_field})"

        freq = Frequency(None, FrequencyUnit.MONTH)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str == "toStartOfMonth({time_field})"

        freq = Frequency(None, FrequencyUnit.QUARTER)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str == "toStartOfQuarter({time_field})"

        freq = Frequency(None, FrequencyUnit.YEAR)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str == "toStartOfYear({time_field})"

    def test_get_time_format_custom_frequencies(self):
        """Test time format for custom frequencies."""
        # Test with custom frequencies (value is not None)
        freq = Frequency(7, FrequencyUnit.DAY)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str is None  # Custom frequencies return None

        freq = Frequency(3, FrequencyUnit.HOUR)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str is None

        # Even value=1 returns None for custom handling
        freq = Frequency(1, FrequencyUnit.DAY)
        format_str = TimeSeriesHelper.get_time_format(freq)
        assert format_str is None

    def test_get_time_bucket_expression_standard(self):
        """Test time bucket expression for standard frequencies."""
        time_field = "request_arrival_time"

        # Test standard frequencies
        freq = Frequency(None, FrequencyUnit.HOUR)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, time_field)
        assert expr == "toStartOfHour(request_arrival_time)"

        freq = Frequency(None, FrequencyUnit.DAY)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, time_field)
        assert expr == "toDate(request_arrival_time)"

        freq = Frequency(None, FrequencyUnit.WEEK)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, time_field)
        assert expr == "toStartOfWeek(request_arrival_time)"

    def test_get_time_bucket_expression_custom_without_from_date(self):
        """Test custom frequency without from_date alignment."""
        time_field = "request_arrival_time"

        # Custom frequency without from_date uses standard interval
        freq = Frequency(7, FrequencyUnit.DAY)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, time_field)

        # Should use toStartOfInterval for custom frequencies
        assert "toStartOfInterval" in expr
        assert "request_arrival_time" in expr
        assert "INTERVAL 7 DAY" in expr

    def test_get_time_bucket_expression_custom_with_from_date(self):
        """Test custom frequency with from_date alignment."""
        time_field = "request_arrival_time"
        from_date = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Custom frequency with from_date alignment
        freq = Frequency(7, FrequencyUnit.DAY)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, time_field, from_date)

        # Should calculate buckets aligned to from_date
        # Expected format: toDateTime(from_timestamp + floor((toUnixTimestamp(time_field) - from_timestamp) / interval) * interval)
        assert "toDateTime" in expr
        assert "floor" in expr
        assert "toUnixTimestamp(request_arrival_time)" in expr
        # The implementation uses formatted date string, not timestamp
        assert "2024-01-15 10:00:00" in expr  # from_date formatted
        assert str(7 * 86400) in expr  # 7 days in seconds

    def test_get_interval_seconds(self):
        """Test _get_interval_seconds calculation."""
        # Test various intervals
        test_cases = [
            (Frequency(1, FrequencyUnit.HOUR), 3600),
            (Frequency(3, FrequencyUnit.HOUR), 10800),
            (Frequency(1, FrequencyUnit.DAY), 86400),
            (Frequency(7, FrequencyUnit.DAY), 604800),
            (Frequency(1, FrequencyUnit.WEEK), 604800),
            (Frequency(2, FrequencyUnit.WEEK), 1209600),
        ]

        for freq, expected_seconds in test_cases:
            seconds = TimeSeriesHelper._get_interval_seconds(freq)
            assert seconds == expected_seconds


    def test_edge_cases(self):
        """Test edge cases for TimeSeriesHelper."""
        # Test with different time fields
        custom_field = "custom_timestamp"
        freq = Frequency(None, FrequencyUnit.DAY)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, custom_field)
        assert expr == "toDate(custom_timestamp)"

        # Test large custom intervals
        freq = Frequency(30, FrequencyUnit.DAY)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, "request_arrival_time")
        assert "INTERVAL 30 DAY" in expr

        # Test small custom intervals
        freq = Frequency(5, FrequencyUnit.HOUR)
        expr = TimeSeriesHelper.get_time_bucket_expression(freq, "request_arrival_time")
        assert "INTERVAL 5 HOUR" in expr

    def test_frequency_name_property(self):
        """Test the name property of Frequency."""
        # Standard frequencies
        freq = Frequency(None, FrequencyUnit.HOUR)
        assert freq.name == "hourly"

        freq = Frequency(None, FrequencyUnit.DAY)
        assert freq.name == "dayly"  # Note: actual implementation has this typo

        # Custom frequencies with value=1
        freq = Frequency(1, FrequencyUnit.DAY)
        assert freq.name == "dayly"

        # Custom frequencies with value > 1
        freq = Frequency(7, FrequencyUnit.DAY)
        assert freq.name == "every_7_days"

        freq = Frequency(3, FrequencyUnit.HOUR)
        assert freq.name == "every_3_hours"

    def test_to_clickhouse_interval(self):
        """Test conversion to ClickHouse INTERVAL syntax."""
        # Standard frequency (value=None, defaults to 1)
        freq = Frequency(None, FrequencyUnit.DAY)
        assert freq.to_clickhouse_interval() == "INTERVAL 1 DAY"
        assert freq.to_clickhouse_interval("desc") == "INTERVAL -1 DAY"

        # Custom frequency
        freq = Frequency(7, FrequencyUnit.DAY)
        assert freq.to_clickhouse_interval() == "INTERVAL 7 DAY"
        assert freq.to_clickhouse_interval("desc") == "INTERVAL -7 DAY"

        # Test all units
        unit_map = {
            FrequencyUnit.HOUR: "HOUR",
            FrequencyUnit.DAY: "DAY",
            FrequencyUnit.WEEK: "WEEK",
            FrequencyUnit.MONTH: "MONTH",
            FrequencyUnit.QUARTER: "QUARTER",
            FrequencyUnit.YEAR: "YEAR"
        }

        for unit, expected_str in unit_map.items():
            freq = Frequency(2, unit)
            assert freq.to_clickhouse_interval() == f"INTERVAL 2 {expected_str}"
