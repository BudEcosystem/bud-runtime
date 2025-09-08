"""Utility functions for billing operations."""

from datetime import datetime, timezone
from typing import Optional, Tuple

from dateutil.relativedelta import relativedelta


def calculate_billing_cycle(
    created_at: Optional[datetime], reference_date: Optional[datetime] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Calculate the current billing cycle start and end dates.

    Args:
        created_at: The creation date of the billing record
        reference_date: The reference date to calculate the cycle for (defaults to now)

    Returns:
        Tuple of (billing_cycle_start, billing_cycle_end) as ISO format strings,
        or (None, None) if created_at is None
    """
    if not created_at:
        return None, None

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    # Ensure created_at has timezone info
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    # Calculate which billing cycle we're in
    # Start from the creation date and find the cycle that contains reference_date

    # Calculate rough months since creation to get close to the right cycle
    months_since_start = (reference_date.year - created_at.year) * 12 + (reference_date.month - created_at.month)

    # Handle the case where reference_date's day is before created_at's day
    if reference_date.day < created_at.day:
        months_since_start -= 1

    # Find the start of current billing cycle
    cycle_start = created_at + relativedelta(months=months_since_start)
    cycle_end = cycle_start + relativedelta(months=1)

    # Verify we're in the right cycle - if reference_date is before cycle_start, go back one cycle
    if reference_date < cycle_start:
        months_since_start -= 1
        cycle_start = created_at + relativedelta(months=months_since_start)
        cycle_end = cycle_start + relativedelta(months=1)

    # If we've passed the cycle end, move to next cycle
    elif reference_date >= cycle_end:
        months_since_start += 1
        cycle_start = created_at + relativedelta(months=months_since_start)
        cycle_end = cycle_start + relativedelta(months=1)

    return cycle_start.isoformat(), cycle_end.isoformat()


def get_new_billing_cycle(reference_date: Optional[datetime] = None) -> Tuple[str, str]:
    """Get a new billing cycle starting from the reference date.

    Args:
        reference_date: The start date for the new cycle (defaults to now)

    Returns:
        Tuple of (billing_cycle_start, billing_cycle_end) as ISO format strings
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    # Ensure reference_date has timezone info
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    billing_cycle_start = reference_date.isoformat()
    billing_cycle_end = (reference_date + relativedelta(months=1)).isoformat()

    return billing_cycle_start, billing_cycle_end
