from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def normalize_datetime(value: datetime | None, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    if value is None:
        return datetime.now(zone)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def parse_time_token(raw: str | time) -> tuple[time, bool]:
    if isinstance(raw, time):
        return raw, False
    token = str(raw).strip().upper().replace(".", ":")
    token = token.replace(" ", "")
    if token in {"2400", "24:00"}:
        return time(0, 0), True
    if ":" in token:
        parts = token.split(":")
        if len(parts) == 2:
            hour, minute = int(parts[0]), int(parts[1])
            if hour == 24:
                return time(0, minute), True
            return time(hour, minute), False
    if len(token) == 4 and token.isdigit():
        hour, minute = int(token[:2]), int(token[2:])
        if hour == 24:
            return time(0, minute), True
        return time(hour, minute), False
    if len(token) in {1, 2} and token.isdigit():
        hour = int(token)
        if hour == 24:
            return time(0, 0), True
        return time(hour, 0), False
    raise ValueError(f"Unsupported time token: {raw}")


def parse_time_range(raw: str) -> tuple[time, time, bool]:
    cleaned = str(raw).strip().replace("~", "-").replace("–", "-").replace("—", "-")
    cleaned = cleaned.replace(" to ", "-")
    if "-" not in cleaned:
        raise ValueError(f"Unsupported time range: {raw}")
    start_raw, end_raw = [part.strip() for part in cleaned.split("-", 1)]
    start_time, start_rollover = parse_time_token(start_raw)
    end_time, end_rollover = parse_time_token(end_raw)
    overnight = end_rollover or (end_time <= start_time and not start_rollover)
    return start_time, end_time, overnight


def combine_local(service_date: date, at_time: time, timezone: str, *, next_day: bool = False) -> datetime:
    zone = ZoneInfo(timezone)
    base = datetime.combine(service_date, at_time, tzinfo=zone)
    if next_day:
        return base + timedelta(days=1)
    return base


def clock_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def minutes_since_anchor(value: time, anchor: time) -> int:
    value_minutes = clock_minutes(value)
    anchor_minutes = clock_minutes(anchor)
    if value_minutes < anchor_minutes:
        value_minutes += 24 * 60
    return value_minutes - anchor_minutes


def countdown_label(minutes: int) -> str:
    if minutes < 1:
        return "now"
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    return f"{mins}m"


def weekday_name(weekday: int) -> str:
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]
