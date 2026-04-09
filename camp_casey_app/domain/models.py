from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AppModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_encoders={
            Decimal: lambda value: float(value),
            date: lambda value: value.isoformat(),
            datetime: lambda value: value.isoformat(),
            time: lambda value: value.strftime("%H:%M"),
            Path: str,
        },
    )


class SourceReference(AppModel):
    source_type: Literal["json", "xlsx", "generated", "config"]
    file_name: str
    label: str
    sheet_name: str | None = None
    row: int | None = None
    column: int | None = None
    json_pointer: str | None = None
    excerpt: str | None = None


class MoneyValue(AppModel):
    amount: Decimal
    currency: Literal["USD", "KRW"] = "USD"
    raw_text: str | None = None
    approximate: bool = False


class TimeWindow(AppModel):
    start: time
    end: time
    overnight: bool = False
    raw_text: str | None = None


class StoreHoursRule(AppModel):
    rule_id: str
    channel: Literal["delivery", "regular", "general"] = "general"
    period_label: str | None = None
    selectors_raw: str
    weekdays: list[int] = Field(default_factory=list)
    day_types: list[str] = Field(default_factory=list)
    windows: list[TimeWindow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class MenuPriceVariant(AppModel):
    label: str | None = None
    price: MoneyValue | None = None


class MenuItem(AppModel):
    item_id: str
    store_id: str
    section_id: str
    name: str
    description: str | None = None
    pricing: list[MenuPriceVariant] = Field(default_factory=list)
    addons: list[MenuPriceVariant] = Field(default_factory=list)
    quantity: str | None = None
    options: list[str] = Field(default_factory=list)
    flavors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_auxiliary: bool = False
    source_refs: list[SourceReference] = Field(default_factory=list)


class MenuSection(AppModel):
    section_id: str
    store_id: str
    name: str
    parent_section_id: str | None = None
    note: str | None = None
    notes: list[str] = Field(default_factory=list)
    items: list[MenuItem] = Field(default_factory=list)
    child_section_ids: list[str] = Field(default_factory=list)
    supporting_lists: dict[str, list[str]] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    section_hours_text: str | None = None
    source_refs: list[SourceReference] = Field(default_factory=list)


class Store(AppModel):
    store_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    instagram: str | None = None
    address: str | None = None
    updated_date: date | None = None
    minimum_order: MoneyValue | None = None
    minimum_delivery_order: MoneyValue | None = None
    delivery_charge: MoneyValue | None = None
    payment_methods: list[str] = Field(default_factory=list)
    last_order_note: str | None = None
    notes: list[str] = Field(default_factory=list)
    hours_rules: list[StoreHoursRule] = Field(default_factory=list)
    delivery_hours_rules: list[StoreHoursRule] = Field(default_factory=list)
    sections: list[MenuSection] = Field(default_factory=list)
    additions: list[str] = Field(default_factory=list)
    recommended_menu: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class StoreDataset(AppModel):
    stores: list[Store]


class HolidayEntry(AppModel):
    entry_id: str
    date: date
    status: str
    holiday_type: str
    holiday_name: str | None = None
    paired_with: date | None = None
    reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class HolidayDataset(AppModel):
    location: str
    as_of: date | None = None
    notes: dict[str, str] = Field(default_factory=dict)
    holidays: list[HolidayEntry]


class DayTypeResolution(AppModel):
    date: date
    calendar_weekday: int
    calendar_label: str
    derived_day_type: str
    fallback_day_type: str
    status: str
    confidence: str
    reason: str | None = None
    paired_with: date | None = None
    holiday_name: str | None = None
    notes: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class BusStop(AppModel):
    stop_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    stop_numbers: list[int] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class BusStopSchedule(AppModel):
    stop_id: str
    service_profile: str
    departures: list[time] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class BusDataset(AppModel):
    route_id: str
    route_name: str
    source_file: str
    service_profile_labels: dict[str, str] = Field(default_factory=dict)
    service_profile_start_times: dict[str, time] = Field(default_factory=dict)
    stops: list[BusStop] = Field(default_factory=list)
    schedules: list[BusStopSchedule] = Field(default_factory=list)


class TrainDeparture(AppModel):
    departure_time: time
    destination: str
    source_refs: list[SourceReference] = Field(default_factory=list)


class TrainServiceSheet(AppModel):
    provider_id: str
    service_key: str
    service_label: str
    direction_label: str
    departures: list[TrainDeparture] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class TrainProvider(AppModel):
    provider_id: str
    station_name: str
    aliases: list[str] = Field(default_factory=list)
    available: bool = True
    not_available_reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    sheets: list[TrainServiceSheet] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)


class TrainDataset(AppModel):
    providers: list[TrainProvider]


class ExchangeRateSnapshot(AppModel):
    provider_id: str
    usd_to_krw: Decimal
    updated_at: datetime
    status: str = "active"
    is_auto: bool = False
    note: str | None = None


class ExchangeRateConfig(AppModel):
    active_provider: str = "manual"
    manual_snapshot: ExchangeRateSnapshot | None = None
    auto_provider_enabled: bool = False


class RAGChunk(AppModel):
    chunk_id: str
    title: str
    text: str
    kind: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[SourceReference] = Field(default_factory=list)
    lexical_tokens: list[str] = Field(default_factory=list)


class DepartureOccurrence(AppModel):
    time: time
    departure_datetime: datetime
    countdown_minutes: int
    countdown_label: str
    is_next_day: bool = False
    destination: str | None = None
    source_refs: list[SourceReference] = Field(default_factory=list)


class BusNextResult(AppModel):
    stop: BusStop | None = None
    matched_query: str | None = None
    available: bool = True
    message: str | None = None
    service_profile: str | None = None
    service_profile_label: str | None = None
    day_type: DayTypeResolution | None = None
    departures: list[DepartureOccurrence] = Field(default_factory=list)
    full_day_times: list[time] = Field(default_factory=list)


class TrainNextResult(AppModel):
    provider: TrainProvider | None = None
    matched_query: str | None = None
    matched_destination: str | None = None
    available: bool = True
    message: str | None = None
    service_key: str | None = None
    service_label: str | None = None
    departures: list[DepartureOccurrence] = Field(default_factory=list)


class StoreStatusResult(AppModel):
    store_id: str
    channel: str = "delivery"
    open_now: bool = False
    closes_soon: bool = False
    closes_at: time | None = None
    opens_at: time | None = None
    closed_today: bool = False
    unsupported_schedule: bool = False
    matched_period_label: str | None = None
    matched_rule_labels: list[str] = Field(default_factory=list)
    message: str | None = None
    source_refs: list[SourceReference] = Field(default_factory=list)


class StoreSummary(AppModel):
    store_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    updated_date: date | None = None
    minimum_order: MoneyValue | None = None
    delivery_charge: MoneyValue | None = None
    payment_methods: list[str] = Field(default_factory=list)
    status: StoreStatusResult | None = None
    match_reason: str | None = None
    item_count: int = 0
    section_count: int = 0
    source_refs: list[SourceReference] = Field(default_factory=list)
