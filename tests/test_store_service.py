from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("Asia/Seoul"))


def test_warriors_club_is_open_on_thursday_noon(container):
    store = container.store_service.get_store("warrior-s-club-delivery-menu")
    status = container.store_service.resolve_store_status(store, _dt(2026, 4, 9, 12, 0))
    assert status.open_now is True
    assert status.closes_at.strftime("%H:%M") == "22:00"


def test_casey_indianhead_gap_between_breakfast_and_lunch(container):
    store = container.store_service.get_store("casey-indianhead-golf-course-restaurant-delivery-service")
    status = container.store_service.resolve_store_status(store, _dt(2026, 4, 9, 10, 45))
    assert status.open_now is False
    assert status.closed_today is False
    assert status.opens_at.strftime("%H:%M") == "11:30"


def test_warriors_breakfast_holiday_rule_overrides_weekday_rule(container):
    store = container.store_service.get_store("warrior-s-club-breakfast")
    status = container.store_service.resolve_store_status(store, _dt(2026, 7, 3, 7, 30))
    assert status.open_now is False
    assert status.opens_at.strftime("%H:%M") == "08:00"


def test_thunder_closed_on_saturday(container):
    store = container.store_service.get_store("thunder-east-casey-katusa-snack-bar")
    status = container.store_service.resolve_store_status(store, _dt(2026, 4, 11, 12, 0))
    assert status.open_now is False
    assert status.closed_today is True
