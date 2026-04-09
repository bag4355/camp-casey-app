from __future__ import annotations

from datetime import date

from camp_casey_app.domain.models import HolidayDataset, HolidayEntry


class HolidayService:
    def __init__(self, dataset: HolidayDataset):
        self.dataset = dataset

    def list_holidays(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        confirmed_only: bool = False,
        statuses: set[str] | None = None,
        holiday_types: set[str] | None = None,
    ) -> list[HolidayEntry]:
        items = []
        for holiday in self.dataset.holidays:
            if from_date and holiday.date < from_date:
                continue
            if to_date and holiday.date > to_date:
                continue
            if confirmed_only and not holiday.status.startswith("confirmed"):
                continue
            if statuses and holiday.status not in statuses:
                continue
            if holiday_types and holiday.holiday_type not in holiday_types:
                continue
            items.append(holiday)
        return items

    def get(self, target_date: date) -> HolidayEntry | None:
        for holiday in self.dataset.holidays:
            if holiday.date == target_date:
                return holiday
        return None

    @property
    def notes(self) -> dict[str, str]:
        return self.dataset.notes
