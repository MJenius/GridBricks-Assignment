"""Time helpers. Compare in UTC, interpret calendar dates in Europe/London."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from app.config import LONDON


def ensure_utc(value: datetime) -> datetime:
    """Return ``value`` as tz-aware UTC. Naive datetimes are rejected."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime is not allowed; timestamps must carry an offset")
    return value.astimezone(UTC)


def parse_utc(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp with offset to UTC; ``None`` if invalid."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ensure_utc(parsed)
    except ValueError:
        return None


def to_london(value: datetime) -> datetime:
    return ensure_utc(value).astimezone(LONDON)


def delivery_date_for(decision_date: date, lead_days: int) -> date:
    return decision_date + timedelta(days=lead_days)


def decision_date_for(delivery_date: date, lead_days: int) -> date:
    return delivery_date - timedelta(days=lead_days)


def decision_cutoff_utc(delivery_date: date, cutoff_local: time, lead_days: int) -> datetime:
    """UTC instant of the decision cutoff for ``delivery_date``.

    The cutoff is ``cutoff_local`` Europe/London wall-clock time on the decision
    date (``delivery_date - lead_days``). DST is resolved by zoneinfo.
    """
    decision = decision_date_for(delivery_date, lead_days)
    return datetime.combine(decision, cutoff_local, tzinfo=LONDON).astimezone(UTC)


def london_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a Europe/London calendar day, in UTC (23/24/25h)."""
    start = datetime.combine(day, time(0), tzinfo=LONDON).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=LONDON).astimezone(UTC)
    return start, end


def interval_starts(day: date, step_minutes: int) -> list[datetime]:
    """All UTC interval starts within a London day at a fixed step."""
    start, end = london_day_bounds_utc(day)
    out: list[datetime] = []
    current = start
    step = timedelta(minutes=step_minutes)
    while current < end:
        out.append(current)
        current += step
    return out
