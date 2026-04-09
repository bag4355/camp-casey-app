from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("Asia/Seoul"))


def test_bosan_destination_filter(container):
    result = container.train_service.get_next_train("bosan", at=_dt(2026, 4, 9, 12, 0), destination="인천")
    assert result.service_key == "weekday"
    assert result.departures[0].time.strftime("%H:%M") == "12:39"
    assert result.departures[0].destination == "인천"


def test_train_saturday_sheet(container):
    result = container.train_service.get_next_train("bosan", at=_dt(2026, 4, 11, 12, 0))
    assert result.service_key == "saturday"


def test_jihaeng_placeholder(container):
    result = container.train_service.get_next_train("jihaeng", at=_dt(2026, 4, 9, 12, 0))
    assert result.available is False
    assert "not been uploaded yet" in (result.message or "")
