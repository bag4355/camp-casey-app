from __future__ import annotations

import json
from datetime import date

from camp_casey_app.domain.models import HolidayDataset, HolidayEntry
from camp_casey_app.ingest.common import json_source
from camp_casey_app.utils.text import slugify


def parse_holiday_file(path) -> HolidayDataset:
    data = json.loads(path.read_text(encoding="utf-8"))
    holidays: list[HolidayEntry] = []
    for idx, item in enumerate(data.get("known_dates_provided_by_user", [])):
        holiday_date = date.fromisoformat(item["date"])
        source = json_source(
            file_name=path.name,
            label=f"{path.name} • {item['date']} • {item.get('holiday_name') or item.get('type')}",
            json_pointer=f"/known_dates_provided_by_user/{idx}",
            excerpt=item.get("reason"),
        )
        holidays.append(
            HolidayEntry(
                entry_id=slugify(f"{item['date']}-{item.get('type')}-{item.get('status')}"),
                date=holiday_date,
                status=item.get("status", "unknown"),
                holiday_type=item.get("type", "unknown"),
                holiday_name=item.get("holiday_name"),
                paired_with=date.fromisoformat(item["paired_with"]) if item.get("paired_with") else None,
                reason=item.get("reason"),
                notes=[],
                source_refs=[source],
            )
        )
    return HolidayDataset(
        location=data.get("location", "Unknown"),
        as_of=date.fromisoformat(data["as_of"]) if data.get("as_of") else None,
        notes=data.get("notes", {}),
        holidays=sorted(holidays, key=lambda entry: entry.date),
    )
