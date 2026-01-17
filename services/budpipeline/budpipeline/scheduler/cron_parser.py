"""Cron Parser - parses and evaluates cron expressions.

Uses croniter for cron expression handling with additional utilities
for validation, human-readable descriptions, and presets.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from croniter import croniter

from budpipeline.commons.exceptions import CronParseError

# Common cron presets
PRESETS = {
    "@every_minute": "* * * * *",
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}

# Validation ranges for cron fields
FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day_of_month": (1, 31),
    "month": (1, 12),
    "day_of_week": (0, 7),  # 0 and 7 both mean Sunday
}


@dataclass
class CronExpression:
    """Parsed cron expression with individual fields."""

    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str
    timezone: str = "UTC"
    original: str = ""

    def to_string(self) -> str:
        """Convert back to cron string."""
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week}"


class CronParser:
    """Parses and evaluates cron expressions."""

    @classmethod
    def parse(cls, expression: str, timezone: str = "UTC") -> CronExpression:
        """Parse a cron expression.

        Args:
            expression: Cron expression string (5 fields) or preset
            timezone: Timezone for the schedule (default: UTC)

        Returns:
            Parsed CronExpression

        Raises:
            CronParseError: If expression is invalid
        """
        if not expression or not expression.strip():
            raise CronParseError(expression or "", "Empty expression")

        expression = expression.strip()

        # Handle presets
        if expression.startswith("@"):
            if expression not in PRESETS:
                raise CronParseError(expression, f"Unknown preset: {expression}")
            expression = PRESETS[expression]

        # Split into fields
        fields = expression.split()

        if len(fields) < 5:
            raise CronParseError(expression, "Too few fields (expected 5)")
        if len(fields) > 5:
            raise CronParseError(expression, "Too many fields (expected 5)")

        minute, hour, day_of_month, month, day_of_week = fields

        # Validate each field
        cls._validate_field("minute", minute, FIELD_RANGES["minute"])
        cls._validate_field("hour", hour, FIELD_RANGES["hour"])
        cls._validate_field("day_of_month", day_of_month, FIELD_RANGES["day_of_month"])
        cls._validate_field("month", month, FIELD_RANGES["month"])
        cls._validate_field("day_of_week", day_of_week, FIELD_RANGES["day_of_week"])

        # Verify croniter can parse it
        try:
            croniter(expression)
        except (ValueError, KeyError) as e:
            raise CronParseError(expression, str(e)) from e

        return CronExpression(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month=month,
            day_of_week=day_of_week,
            timezone=timezone,
            original=expression,
        )

    @classmethod
    def _validate_field(cls, name: str, value: str, valid_range: tuple[int, int]) -> None:
        """Validate a cron field value.

        Args:
            name: Field name for error messages
            value: Field value to validate
            valid_range: (min, max) valid range

        Raises:
            CronParseError: If field is invalid
        """
        if value == "*":
            return

        min_val, max_val = valid_range

        # Handle step values (*/5, 0-30/5)
        if "/" in value:
            base, step = value.split("/", 1)
            if base != "*":
                cls._validate_field(name, base, valid_range)
            try:
                step_val = int(step)
                if step_val < 1:
                    raise CronParseError(value, f"Invalid step value for {name}")
            except ValueError:
                raise CronParseError(value, f"Invalid step value for {name}")
            return

        # Handle ranges (0-30)
        if "-" in value:
            parts = value.split("-")
            if len(parts) != 2:
                raise CronParseError(value, f"Invalid range for {name}")
            try:
                start, end = int(parts[0]), int(parts[1])
                if start < min_val or end > max_val or start > end:
                    raise CronParseError(
                        value, f"Range out of bounds for {name} ({min_val}-{max_val})"
                    )
            except ValueError:
                raise CronParseError(value, f"Invalid range values for {name}")
            return

        # Handle lists (1,3,5)
        if "," in value:
            for part in value.split(","):
                cls._validate_field(name, part.strip(), valid_range)
            return

        # Single value
        try:
            val = int(value)
            if val < min_val or val > max_val:
                raise CronParseError(
                    value,
                    f"Value {val} out of range for {name} ({min_val}-{max_val})",
                )
        except ValueError:
            raise CronParseError(value, f"Invalid value for {name}")

    @classmethod
    def is_valid(cls, expression: str) -> bool:
        """Check if a cron expression is valid.

        Args:
            expression: Cron expression to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            cls.parse(expression)
            return True
        except CronParseError:
            return False

    @classmethod
    def get_next(cls, expr: CronExpression, base_time: datetime | None = None) -> datetime:
        """Get next execution time.

        Args:
            expr: Parsed cron expression
            base_time: Base time (default: now)

        Returns:
            Next execution datetime (UTC)
        """
        if base_time is None:
            base_time = datetime.now(timezone.utc)

        cron = croniter(expr.to_string(), base_time)
        return cron.get_next(datetime)

    @classmethod
    def get_previous(cls, expr: CronExpression, base_time: datetime | None = None) -> datetime:
        """Get previous execution time.

        Args:
            expr: Parsed cron expression
            base_time: Base time (default: now)

        Returns:
            Previous execution datetime (UTC)
        """
        if base_time is None:
            base_time = datetime.now(timezone.utc)

        cron = croniter(expr.to_string(), base_time)
        return cron.get_prev(datetime)

    @classmethod
    def get_next_n(
        cls,
        expr: CronExpression,
        base_time: datetime | None = None,
        count: int = 10,
    ) -> list[datetime]:
        """Get next N execution times.

        Args:
            expr: Parsed cron expression
            base_time: Base time (default: now)
            count: Number of times to get

        Returns:
            List of next N execution datetimes
        """
        if base_time is None:
            base_time = datetime.now(timezone.utc)

        cron = croniter(expr.to_string(), base_time)
        return [cron.get_next(datetime) for _ in range(count)]

    @classmethod
    def matches(cls, expr: CronExpression, check_time: datetime) -> bool:
        """Check if a time matches the cron expression.

        Args:
            expr: Parsed cron expression
            check_time: Time to check

        Returns:
            True if time matches the cron schedule
        """
        # Use croniter's match method to check if time matches
        return croniter.match(expr.to_string(), check_time)

    @classmethod
    def describe(cls, expr: CronExpression) -> str:
        """Get human-readable description of cron expression.

        Args:
            expr: Parsed cron expression

        Returns:
            Human-readable description
        """
        minute, hour = expr.minute, expr.hour
        day_of_month, _month, day_of_week = (
            expr.day_of_month,
            expr.month,
            expr.day_of_week,
        )

        # Every minute
        if minute == "*" and hour == "*":
            return "Every minute"

        # Every hour at specific minute
        if minute != "*" and hour == "*" and day_of_month == "*":
            return f"Every hour at minute {minute}"

        # Hourly (at :00)
        if minute == "0" and hour == "*":
            return "Every hour at :00"

        # Daily at specific time
        if minute != "*" and hour != "*" and day_of_month == "*" and day_of_week == "*":
            hour_str = hour.zfill(2) if hour.isdigit() else hour
            min_str = minute.zfill(2) if minute.isdigit() else minute
            return f"Every day at {hour_str}:{min_str}"

        # Weekdays
        if day_of_week == "1-5":
            hour_str = hour.zfill(2) if hour.isdigit() else hour
            min_str = minute.zfill(2) if minute.isdigit() else minute
            return f"Every weekday (Monday-Friday) at {hour_str}:{min_str}"

        # Specific day of week
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        if day_of_week.isdigit():
            day_name = days[int(day_of_week) % 7]
            hour_str = hour.zfill(2) if hour.isdigit() else hour
            min_str = minute.zfill(2) if minute.isdigit() else minute
            return f"Every {day_name} at {hour_str}:{min_str}"

        # Default to cron syntax
        return f"Cron: {expr.to_string()}"
