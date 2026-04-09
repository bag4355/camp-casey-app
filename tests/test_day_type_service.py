from __future__ import annotations

from datetime import date


def test_confirmed_official_holiday(container):
    resolution = container.day_type_service.resolve_day_type(date(2026, 5, 25))
    assert resolution.derived_day_type == "us_holiday"
    assert resolution.status == "confirmed_official"
    assert resolution.holiday_name == "Memorial Day"


def test_likely_training_holiday(container):
    resolution = container.day_type_service.resolve_day_type(date(2026, 10, 9))
    assert resolution.derived_day_type == "training_holiday"
    assert resolution.status == "likely_but_not_locally_confirmed"
    assert resolution.confidence == "medium"
