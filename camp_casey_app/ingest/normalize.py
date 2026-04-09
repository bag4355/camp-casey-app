from __future__ import annotations

import json
from pathlib import Path

from camp_casey_app.config import Settings
from camp_casey_app.domain.models import ExchangeRateConfig, ExchangeRateSnapshot
from camp_casey_app.ingest.bus_parser import parse_bus_file
from camp_casey_app.ingest.delivery_parser import parse_delivery_file
from camp_casey_app.ingest.holiday_parser import parse_holiday_file
from camp_casey_app.ingest.rag import build_rag_chunks, write_rag_chunks
from camp_casey_app.ingest.train_parser import parse_train_file


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_full_ingest(settings: Settings) -> dict[str, int]:
    stores = parse_delivery_file(settings.raw_delivery_path)
    holidays = parse_holiday_file(settings.raw_holiday_path)
    bus = parse_bus_file(settings.raw_bus_path)
    trains = parse_train_file(settings.raw_train_path)

    _write_json(settings.stores_path, stores.model_dump(mode="json"))
    _write_json(settings.holidays_path, holidays.model_dump(mode="json"))
    _write_json(settings.bus_path, bus.model_dump(mode="json"))
    _write_json(settings.trains_path, trains.model_dump(mode="json"))

    manifest = {
        "stores": len(stores.stores),
        "sections": sum(len(store.sections) for store in stores.stores),
        "menu_items": sum(len(section.items) for store in stores.stores for section in store.sections),
        "holidays": len(holidays.holidays),
        "bus_stops": len(bus.stops),
        "bus_schedules": len(bus.schedules),
        "train_providers": len(trains.providers),
        "train_departures": sum(len(sheet.departures) for provider in trains.providers for sheet in provider.sheets),
    }
    _write_json(settings.manifest_path, manifest)

    chunks = build_rag_chunks(stores=stores, holidays=holidays, buses=bus, trains=trains)
    write_rag_chunks(settings.rag_chunks_path, chunks)
    if not settings.rag_index_path.exists():
        _write_json(settings.rag_index_path, {"model": None, "vectors": [], "embeddings_available": False})

    return manifest


def ensure_exchange_rate_seed(settings: Settings) -> None:
    if settings.exchange_rate_path.exists():
        return
    settings.exchange_rate_path.parent.mkdir(parents=True, exist_ok=True)
    config = ExchangeRateConfig(
        active_provider="manual",
        manual_snapshot=ExchangeRateSnapshot(
            provider_id="manual",
            usd_to_krw=settings.default_usd_to_krw,
            updated_at="2026-04-09T00:00:00+09:00",
            note="Default seeded manual rate",
            is_auto=False,
        ),
        auto_provider_enabled=False,
    )
    _write_json(settings.exchange_rate_path, config.model_dump(mode="json"))
