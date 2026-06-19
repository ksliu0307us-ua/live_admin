"""Date calculation utilities for deadline enrichment."""

from datetime import date


def days_until(target: date | None) -> int | None:
    """Calculate days from today until a target date. Negative means past."""
    if target is None:
        return None
    return (target - date.today()).days


def urgency_level(days_remaining: int | None) -> str:
    """Determine urgency based on days remaining."""
    if days_remaining is None:
        return "low"
    if days_remaining <= 3:
        return "high"
    if days_remaining <= 14:
        return "medium"
    return "low"


def human_time_description(days_remaining: int | None) -> str:
    """Create a human-readable time description."""
    if days_remaining is None:
        return ""
    if days_remaining < 0:
        return f"{abs(days_remaining)} days ago"
    if days_remaining == 0:
        return "today"
    if days_remaining == 1:
        return "tomorrow"
    if days_remaining <= 30:
        return f"in {days_remaining} days"
    weeks = days_remaining // 7
    return f"in {weeks} weeks"
