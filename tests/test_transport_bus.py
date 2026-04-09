from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("Asia/Seoul"))


def test_next_bus_cac_weekday(container):
    result = container.bus_service.get_next_bus("CAC", at=_dt(2026, 4, 9, 12, 0), count=3)
    assert result.service_profile == "weekday"
    assert result.departures[0].time.strftime("%H:%M") == "12:09"
    assert result.departures[0].countdown_minutes == 9


def test_bus_midnight_rollover(container):
    result = container.bus_service.get_next_bus("Bus Terminal", at=_dt(2026, 4, 9, 23, 50), count=3)
    assert result.departures[0].time.strftime("%H:%M") == "00:00"
    assert result.departures[0].is_next_day is True


def test_bus_weekend_profile(container):
    result = container.bus_service.get_next_bus("CAC", at=_dt(2026, 4, 11, 6, 50), count=3)
    assert result.service_profile == "weekend_us_training"
    assert result.departures[0].time.strftime("%H:%M") == "07:04"
