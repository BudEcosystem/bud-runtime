"""Tests for Cron Parser - TDD approach.

Tests cron expression parsing and next execution time calculation.
"""

from datetime import datetime, timedelta, timezone

import pytest

from budpipeline.commons.exceptions import CronParseError
from budpipeline.scheduler.cron_parser import CronParser


class TestCronParsing:
    """Test cron expression parsing."""

    def test_parse_standard_expression(self) -> None:
        """Should parse standard 5-field cron expression."""
        expr = CronParser.parse("0 12 * * *")
        assert expr is not None
        assert expr.minute == "0"
        assert expr.hour == "12"
        assert expr.day_of_month == "*"
        assert expr.month == "*"
        assert expr.day_of_week == "*"

    def test_parse_every_minute(self) -> None:
        """Should parse every minute expression."""
        expr = CronParser.parse("* * * * *")
        assert expr.minute == "*"
        assert expr.hour == "*"

    def test_parse_specific_values(self) -> None:
        """Should parse specific values."""
        expr = CronParser.parse("30 14 15 6 3")
        assert expr.minute == "30"
        assert expr.hour == "14"
        assert expr.day_of_month == "15"
        assert expr.month == "6"
        assert expr.day_of_week == "3"

    def test_parse_range_values(self) -> None:
        """Should parse range values."""
        expr = CronParser.parse("0-30 9-17 * * *")
        assert expr.minute == "0-30"
        assert expr.hour == "9-17"

    def test_parse_step_values(self) -> None:
        """Should parse step values."""
        expr = CronParser.parse("*/5 * * * *")
        assert expr.minute == "*/5"

    def test_parse_list_values(self) -> None:
        """Should parse list values."""
        expr = CronParser.parse("0 9,12,18 * * *")
        assert expr.hour == "9,12,18"

    def test_parse_combined_values(self) -> None:
        """Should parse combined range and list values."""
        expr = CronParser.parse("0 9-17/2 * * 1-5")
        assert expr.hour == "9-17/2"
        assert expr.day_of_week == "1-5"

    def test_parse_with_timezone(self) -> None:
        """Should accept optional timezone."""
        expr = CronParser.parse("0 12 * * *", timezone="America/New_York")
        assert expr.timezone == "America/New_York"

    def test_parse_default_timezone_utc(self) -> None:
        """Should default to UTC timezone."""
        expr = CronParser.parse("0 12 * * *")
        assert expr.timezone == "UTC"


class TestCronParsingErrors:
    """Test cron parsing error handling."""

    def test_parse_empty_expression(self) -> None:
        """Should raise error for empty expression."""
        with pytest.raises(CronParseError):
            CronParser.parse("")

    def test_parse_too_few_fields(self) -> None:
        """Should raise error for too few fields."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 12 *")

    def test_parse_too_many_fields(self) -> None:
        """Should raise error for too many fields."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 12 * * * * *")

    def test_parse_invalid_minute(self) -> None:
        """Should raise error for invalid minute value."""
        with pytest.raises(CronParseError):
            CronParser.parse("60 12 * * *")

    def test_parse_invalid_hour(self) -> None:
        """Should raise error for invalid hour value."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 24 * * *")

    def test_parse_invalid_day(self) -> None:
        """Should raise error for invalid day value."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 12 32 * *")

    def test_parse_invalid_month(self) -> None:
        """Should raise error for invalid month value."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 12 * 13 *")

    def test_parse_invalid_day_of_week(self) -> None:
        """Should raise error for invalid day of week."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 12 * * 8")

    def test_parse_invalid_characters(self) -> None:
        """Should raise error for invalid characters."""
        with pytest.raises(CronParseError):
            CronParser.parse("0 12 * * abc")


class TestNextExecutionTime:
    """Test next execution time calculation."""

    def test_next_every_minute(self) -> None:
        """Should calculate next minute."""
        expr = CronParser.parse("* * * * *")
        now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        next_run = CronParser.get_next(expr, now)

        assert next_run > now
        assert next_run.minute == 31

    def test_next_specific_minute(self) -> None:
        """Should calculate next specific minute."""
        expr = CronParser.parse("30 * * * *")
        now = datetime(2024, 1, 15, 10, 15, 0, tzinfo=timezone.utc)
        next_run = CronParser.get_next(expr, now)

        assert next_run.minute == 30
        assert next_run.hour == 10

    def test_next_specific_hour(self) -> None:
        """Should calculate next specific hour."""
        expr = CronParser.parse("0 14 * * *")
        now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        next_run = CronParser.get_next(expr, now)

        assert next_run.hour == 14
        assert next_run.minute == 0

    def test_next_rolls_to_next_day(self) -> None:
        """Should roll to next day if time passed."""
        expr = CronParser.parse("0 9 * * *")
        now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        next_run = CronParser.get_next(expr, now)

        assert next_run.day == 16
        assert next_run.hour == 9

    def test_next_specific_day_of_week(self) -> None:
        """Should calculate next specific day of week."""
        expr = CronParser.parse("0 9 * * 1")  # Monday
        # January 15, 2024 is a Monday
        now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        next_run = CronParser.get_next(expr, now)

        # Should be next Monday
        assert next_run.weekday() == 0  # Monday
        assert next_run.day == 22

    def test_next_with_step(self) -> None:
        """Should handle step values."""
        expr = CronParser.parse("*/15 * * * *")
        now = datetime(2024, 1, 15, 10, 7, 0, tzinfo=timezone.utc)
        next_run = CronParser.get_next(expr, now)

        assert next_run.minute == 15


class TestPreviousExecutionTime:
    """Test previous execution time calculation."""

    def test_previous_every_minute(self) -> None:
        """Should calculate previous minute."""
        expr = CronParser.parse("* * * * *")
        now = datetime(2024, 1, 15, 10, 30, 30, tzinfo=timezone.utc)
        prev_run = CronParser.get_previous(expr, now)

        assert prev_run < now
        assert prev_run.minute == 30
        assert prev_run.second == 0

    def test_previous_specific_hour(self) -> None:
        """Should calculate previous specific hour."""
        expr = CronParser.parse("0 9 * * *")
        now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        prev_run = CronParser.get_previous(expr, now)

        assert prev_run.hour == 9
        assert prev_run.day == 15


class TestCronValidation:
    """Test cron expression validation."""

    def test_validate_valid_expression(self) -> None:
        """Should validate valid expression."""
        assert CronParser.is_valid("0 12 * * *") is True

    def test_validate_invalid_expression(self) -> None:
        """Should invalidate bad expression."""
        assert CronParser.is_valid("invalid") is False

    def test_validate_empty_expression(self) -> None:
        """Should invalidate empty expression."""
        assert CronParser.is_valid("") is False


class TestCronExpressionHumanReadable:
    """Test human-readable cron description."""

    def test_describe_every_minute(self) -> None:
        """Should describe every minute."""
        expr = CronParser.parse("* * * * *")
        desc = CronParser.describe(expr)
        assert "every minute" in desc.lower()

    def test_describe_specific_time(self) -> None:
        """Should describe specific time."""
        expr = CronParser.parse("30 9 * * *")
        desc = CronParser.describe(expr)
        assert "9:30" in desc or "09:30" in desc

    def test_describe_hourly(self) -> None:
        """Should describe hourly schedule."""
        expr = CronParser.parse("0 * * * *")
        desc = CronParser.describe(expr)
        assert "every hour" in desc.lower()

    def test_describe_daily(self) -> None:
        """Should describe daily schedule."""
        expr = CronParser.parse("0 9 * * *")
        desc = CronParser.describe(expr)
        assert "every day" in desc.lower() or "daily" in desc.lower()

    def test_describe_weekdays(self) -> None:
        """Should describe weekday schedule."""
        expr = CronParser.parse("0 9 * * 1-5")
        desc = CronParser.describe(expr)
        assert "weekday" in desc.lower() or "monday" in desc.lower()


class TestCronPresets:
    """Test common cron presets."""

    def test_preset_every_minute(self) -> None:
        """Should parse @every_minute preset."""
        expr = CronParser.parse("@every_minute")
        assert expr.minute == "*"
        assert expr.hour == "*"

    def test_preset_hourly(self) -> None:
        """Should parse @hourly preset."""
        expr = CronParser.parse("@hourly")
        assert expr.minute == "0"
        assert expr.hour == "*"

    def test_preset_daily(self) -> None:
        """Should parse @daily preset."""
        expr = CronParser.parse("@daily")
        assert expr.minute == "0"
        assert expr.hour == "0"

    def test_preset_weekly(self) -> None:
        """Should parse @weekly preset."""
        expr = CronParser.parse("@weekly")
        assert expr.day_of_week == "0"

    def test_preset_monthly(self) -> None:
        """Should parse @monthly preset."""
        expr = CronParser.parse("@monthly")
        assert expr.day_of_month == "1"

    def test_preset_yearly(self) -> None:
        """Should parse @yearly preset."""
        expr = CronParser.parse("@yearly")
        assert expr.month == "1"
        assert expr.day_of_month == "1"


class TestCronMultipleExecutions:
    """Test getting multiple execution times."""

    def test_get_next_n(self) -> None:
        """Should get next N execution times."""
        expr = CronParser.parse("0 * * * *")  # Every hour
        now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        next_runs = CronParser.get_next_n(expr, now, count=5)

        assert len(next_runs) == 5
        assert all(run > now for run in next_runs)
        # Should be consecutive hours
        for i in range(1, len(next_runs)):
            diff = next_runs[i] - next_runs[i - 1]
            assert diff == timedelta(hours=1)

    def test_get_next_n_default_count(self) -> None:
        """Should default to 10 runs."""
        expr = CronParser.parse("* * * * *")
        now = datetime.now(timezone.utc)
        next_runs = CronParser.get_next_n(expr, now)

        assert len(next_runs) == 10


class TestCronWindowCheck:
    """Test checking if time falls within cron window."""

    def test_matches_current_time(self) -> None:
        """Should detect if current time matches cron."""
        expr = CronParser.parse("30 10 * * *")
        check_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        assert CronParser.matches(expr, check_time) is True

    def test_does_not_match_different_time(self) -> None:
        """Should not match different time."""
        expr = CronParser.parse("30 10 * * *")
        check_time = datetime(2024, 1, 15, 10, 31, 0, tzinfo=timezone.utc)

        assert CronParser.matches(expr, check_time) is False

    def test_matches_with_wildcards(self) -> None:
        """Should match with wildcards."""
        expr = CronParser.parse("* 10 * * *")
        check_time = datetime(2024, 1, 15, 10, 45, 0, tzinfo=timezone.utc)

        assert CronParser.matches(expr, check_time) is True
