from __future__ import annotations

import json
from pathlib import Path

from camp_casey_app.domain.models import BusDataset, HolidayDataset, RAGChunk, StoreDataset, TrainDataset
from camp_casey_app.utils.text import tokenize_for_search


def _chunk_to_line(chunk: RAGChunk) -> str:
    return json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False)


def build_rag_chunks(
    *,
    stores: StoreDataset,
    holidays: HolidayDataset,
    buses: BusDataset,
    trains: TrainDataset,
) -> list[RAGChunk]:
    chunks: list[RAGChunk] = []

    for store in stores.stores:
        sections = ", ".join(section.name for section in store.sections[:8])
        phones = ", ".join(store.phones)
        text = (
            f"Store: {store.name}\n"
            f"Aliases: {', '.join(store.aliases)}\n"
            f"Phones: {phones}\n"
            f"Minimum delivery order: {store.minimum_delivery_order or store.minimum_order}\n"
            f"Delivery charge: {store.delivery_charge}\n"
            f"Sections: {sections}\n"
            f"Notes: {'; '.join(store.notes)}"
        )
        chunks.append(
            RAGChunk(
                chunk_id=f"store::{store.store_id}",
                title=store.name,
                text=text,
                kind="store",
                metadata={"store_id": store.store_id},
                source_refs=store.source_refs,
                lexical_tokens=tokenize_for_search(text),
            )
        )
        for section in store.sections:
            items_preview = "; ".join(
                f"{item.name} "
                + ", ".join(
                    f"{variant.label + ' ' if variant.label else ''}{variant.price.raw_text or variant.price.amount}"
                    for variant in item.pricing[:3]
                    if variant.price
                )
                for item in section.items[:15]
            )
            section_text = (
                f"Store: {store.name}\n"
                f"Section: {section.name}\n"
                f"Items: {items_preview}\n"
                f"Notes: {'; '.join(section.notes)}\n"
                f"Supporting lists: {section.supporting_lists}"
            )
            chunks.append(
                RAGChunk(
                    chunk_id=f"section::{store.store_id}::{section.section_id}",
                    title=f"{store.name} / {section.name}",
                    text=section_text,
                    kind="menu_section",
                    metadata={"store_id": store.store_id, "section_id": section.section_id},
                    source_refs=section.source_refs or store.source_refs,
                    lexical_tokens=tokenize_for_search(section_text),
                )
            )

    holiday_note_text = " ".join(f"{key}: {value}" for key, value in holidays.notes.items())
    for holiday in holidays.holidays:
        text = (
            f"Date: {holiday.date}\n"
            f"Status: {holiday.status}\n"
            f"Type: {holiday.holiday_type}\n"
            f"Holiday name: {holiday.holiday_name or ''}\n"
            f"Reason: {holiday.reason or ''}\n"
            f"Paired with: {holiday.paired_with or ''}\n"
            f"Dataset notes: {holiday_note_text}"
        )
        chunks.append(
            RAGChunk(
                chunk_id=f"holiday::{holiday.entry_id}",
                title=f"Holiday {holiday.date}",
                text=text,
                kind="holiday",
                metadata={"date": holiday.date.isoformat(), "status": holiday.status, "holiday_type": holiday.holiday_type},
                source_refs=holiday.source_refs,
                lexical_tokens=tokenize_for_search(text),
            )
        )

    for stop in buses.stops:
        weekday_schedule = next((sched for sched in buses.schedules if sched.stop_id == stop.stop_id and sched.service_profile == "weekday"), None)
        weekend_schedule = next((sched for sched in buses.schedules if sched.stop_id == stop.stop_id and sched.service_profile == "weekend_us_training"), None)
        text = (
            f"Bus stop: {stop.name}\n"
            f"Aliases: {', '.join(stop.aliases)}\n"
            f"Weekday departures begin: {weekday_schedule.departures[:5] if weekday_schedule else []}\n"
            f"Weekend / US / Training departures begin: {weekend_schedule.departures[:5] if weekend_schedule else []}"
        )
        chunks.append(
            RAGChunk(
                chunk_id=f"bus::{stop.stop_id}",
                title=f"Bus stop {stop.name}",
                text=text,
                kind="bus_stop",
                metadata={"stop_id": stop.stop_id},
                source_refs=stop.source_refs,
                lexical_tokens=tokenize_for_search(text),
            )
        )

    for provider in trains.providers:
        text = (
            f"Train provider: {provider.station_name}\n"
            f"Available: {provider.available}\n"
            f"Notes: {'; '.join(provider.notes)}\n"
            f"Not available reason: {provider.not_available_reason or ''}"
        )
        chunks.append(
            RAGChunk(
                chunk_id=f"train_provider::{provider.provider_id}",
                title=provider.station_name,
                text=text,
                kind="train_provider",
                metadata={"provider_id": provider.provider_id, "available": provider.available},
                source_refs=provider.source_refs,
                lexical_tokens=tokenize_for_search(text),
            )
        )
        for sheet in provider.sheets:
            destinations = ", ".join(sorted({departure.destination for departure in sheet.departures}))
            preview = ", ".join(f"{departure.departure_time.strftime('%H:%M')} {departure.destination}" for departure in sheet.departures[:10])
            sheet_text = (
                f"Station: {provider.station_name}\n"
                f"Service: {sheet.service_label}\n"
                f"Direction: {sheet.direction_label}\n"
                f"Destinations: {destinations}\n"
                f"Preview departures: {preview}"
            )
            chunks.append(
                RAGChunk(
                    chunk_id=f"train_sheet::{provider.provider_id}::{sheet.service_key}",
                    title=f"{provider.station_name} / {sheet.service_label}",
                    text=sheet_text,
                    kind="train_sheet",
                    metadata={"provider_id": provider.provider_id, "service_key": sheet.service_key},
                    source_refs=sheet.source_refs or provider.source_refs,
                    lexical_tokens=tokenize_for_search(sheet_text),
                )
            )

    return chunks


def write_rag_chunks(path: Path, chunks: list[RAGChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_chunk_to_line(chunk) for chunk in chunks), encoding="utf-8")
