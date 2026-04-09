from __future__ import annotations

from datetime import date

from camp_casey_app.domain.models import DayTypeResolution, HolidayDataset
from camp_casey_app.utils.time import weekday_name


TYPE_MAP = {
    "federal_holiday": "us_holiday",
    "training_holiday": "training_holiday",
    "rok_holiday": "rok_holiday",
    "possible_local_donsa_or_training_holiday": "possible_local_holiday",
}

CONFIDENCE_MAP = {
    "confirmed_official": "high",
    "confirmed_pattern": "high",
    "likely_but_not_locally_confirmed": "medium",
    "unconfirmed_publicly": "low",
}


class DayTypeService:
    def __init__(self, dataset: HolidayDataset):
        self.dataset = dataset
        self._by_date = {entry.date: entry for entry in dataset.holidays}

    def resolve_day_type(self, target_date: date) -> DayTypeResolution:
        fallback_day_type = self._fallback_day_type(target_date)
        entry = self._by_date.get(target_date)
        if not entry:
            return DayTypeResolution(
                date=target_date,
                calendar_weekday=target_date.weekday(),
                calendar_label=weekday_name(target_date.weekday()),
                derived_day_type=fallback_day_type,
                fallback_day_type=fallback_day_type,
                status="calendar_derived",
                confidence="high",
                reason="No uploaded holiday override for this date. Calendar weekday rules apply.",
                notes=list(self.dataset.notes.values()),
                source_refs=[],
            )
        return DayTypeResolution(
            date=target_date,
            calendar_weekday=target_date.weekday(),
            calendar_label=weekday_name(target_date.weekday()),
            derived_day_type=TYPE_MAP.get(entry.holiday_type, "unknown"),
            fallback_day_type=fallback_day_type,
            status=entry.status,
            confidence=CONFIDENCE_MAP.get(entry.status, "medium"),
            reason=entry.reason,
            paired_with=entry.paired_with,
            holiday_name=entry.holiday_name,
            notes=list(self.dataset.notes.values()) + entry.notes,
            source_refs=entry.source_refs,
        )

    @staticmethod
    def _fallback_day_type(target_date: date) -> str:
        weekday = target_date.weekday()
        if weekday == 5:
            return "saturday"
        if weekday == 6:
            return "sunday"
        return "weekday"
