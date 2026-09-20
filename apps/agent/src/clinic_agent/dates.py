"""The challenge's fixed date vocabulary, resolved in code against the moment the call connected.

The LLM only classifies what the caller said (kind + weekday/date + part of day);
the arithmetic happens here, in Europe/Madrid. Rules from the organizers' docs:
- nothing is booked same-day: "earliest" starts the day after the call;
- a weekday phrase means the first such weekday STRICTLY after the day of the call;
- morning is before 14:00, afternoon is from 14:00.
Whether the resolved day is open, and rolling forward when it is not, is the slot
search's job — it has the diary.
"""

from datetime import date, datetime, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_KINDS = ["earliest", "tomorrow", "day_after_tomorrow", "in_one_week", "in_two_weeks", "weekday", "date"]
PARTS_OF_DAY = ["any", "morning", "afternoon"]

_OFFSETS = {"tomorrow": 1, "day_after_tomorrow": 2, "in_one_week": 7, "in_two_weeks": 14}


def earliest_bookable(today: date) -> date:
    return today + timedelta(days=1)


def resolve_day(kind: str, today: date, weekday: str | None = None, iso_date: str | None = None) -> date | None:
    """The calendar day the caller means, or None for 'earliest' (no particular day)."""
    if kind == "earliest":
        return None
    if kind in _OFFSETS:
        return today + timedelta(days=_OFFSETS[kind])
    if kind == "weekday":
        if weekday not in WEEKDAYS:
            raise ValueError(f"weekday must be one of {WEEKDAYS}")
        ahead = (WEEKDAYS.index(weekday) - today.weekday() - 1) % 7 + 1  # 1..7, never today
        return today + timedelta(days=ahead)
    if kind == "date":
        if not iso_date:
            raise ValueError("date kind needs an ISO date")
        return date.fromisoformat(iso_date)
    raise ValueError(f"day kind must be one of {DAY_KINDS}")


def in_part_of_day(start: datetime, part: str) -> bool:
    if part == "morning":
        return start.hour < 14
    if part == "afternoon":
        return start.hour >= 14
    return True


def spoken(start: datetime) -> str:
    """'Monday 21 September at 09:15' — what the agent reads back."""
    return f"{start.strftime('%A')} {start.day} {start.strftime('%B')} at {start.strftime('%H:%M')}"
