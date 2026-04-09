from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from rapidfuzz import fuzz

from camp_casey_app.domain.models import (
    BusDataset,
    BusNextResult,
    BusStop,
    BusStopSchedule,
    DepartureOccurrence,
    TrainDataset,
    TrainNextResult,
    TrainProvider,
)
from camp_casey_app.services.day_type import DayTypeService
from camp_casey_app.utils.text import dedupe_keep_order, normalize_text
from camp_casey_app.utils.time import combine_local, countdown_label, minutes_since_anchor, normalize_datetime


BUS_HOLIDAY_PROFILES = {"saturday", "sunday", "us_holiday", "training_holiday"}
TRAIN_DESTINATION_ALIASES = {
    "인천": ["인천", "incheon"],
    "청량리": ["청량리", "cheongnyangni"],
    "소요산": ["소요산", "soyosan"],
    "광운대": ["광운대", "gwangwoon", "gwangwoondae"],
}


class BusService:
    def __init__(self, dataset: BusDataset, day_type_service: DayTypeService, timezone: str):
        self.dataset = dataset
        self.day_type_service = day_type_service
        self.timezone = timezone
        self.zone = ZoneInfo(timezone)
        self._stops = {stop.stop_id: stop for stop in dataset.stops}
        self._schedules = {(schedule.service_profile, schedule.stop_id): schedule for schedule in dataset.schedules}

    def search_stops(self, query: str | None = None, *, limit: int = 20) -> list[BusStop]:
        if not query:
            return self.dataset.stops[:limit]
        normalized_query = normalize_text(query)
        exact_matches = [
            stop
            for stop in self.dataset.stops
            if normalized_query == normalize_text(stop.name) or normalized_query in {normalize_text(alias) for alias in stop.aliases}
        ]
        if exact_matches:
            return exact_matches[:limit]

        scored: list[tuple[int, BusStop]] = []
        for stop in self.dataset.stops:
            haystack = " ".join([stop.name, *stop.aliases, *[str(number) for number in stop.stop_numbers]])
            score = fuzz.WRatio(normalized_query, normalize_text(haystack))
            if score >= 55:
                scored.append((score, stop))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [stop for _, stop in scored[:limit]]

    def resolve_stop(self, query_or_id: str) -> BusStop | None:
        if not query_or_id:
            return None
        if query_or_id in self._stops:
            return self._stops[query_or_id]
        matches = self.search_stops(query_or_id, limit=1)
        return matches[0] if matches else None

    def get_next_bus(self, stop_query: str, *, at: datetime | None = None, count: int = 3) -> BusNextResult:
        now = normalize_datetime(at, self.timezone)
        stop = self.resolve_stop(stop_query)
        if not stop:
            return BusNextResult(available=False, message="No matching bus stop was found.", matched_query=stop_query)

        departures = []
        full_day_times: list = []
        for service_date in [now.date() - timedelta(days=1), now.date(), now.date() + timedelta(days=1)]:
            profile = self._profile_for_date(service_date)
            schedule = self._schedules.get((profile, stop.stop_id))
            if not schedule:
                continue
            full_day_times = schedule.departures if service_date == now.date() else full_day_times
            occurrences = self._schedule_occurrences(schedule, service_date, reference_time=now)
            departures.extend(occurrences)

        departures = [occurrence for occurrence in departures if occurrence.departure_datetime >= now]
        departures.sort(key=lambda item: item.departure_datetime)
        selected = departures[:count]

        service_profile = self._profile_for_date(now.date())
        return BusNextResult(
            stop=stop,
            matched_query=stop_query,
            available=True,
            service_profile=service_profile,
            service_profile_label=self.dataset.service_profile_labels.get(service_profile, service_profile),
            day_type=self.day_type_service.resolve_day_type(now.date()),
            departures=selected,
            full_day_times=full_day_times,
            message=None if selected else "No upcoming departures were found in the loaded timetable window.",
        )

    def get_full_schedule(self, stop_query: str, *, service_date: date) -> BusNextResult:
        stop = self.resolve_stop(stop_query)
        if not stop:
            return BusNextResult(available=False, message="No matching bus stop was found.", matched_query=stop_query)
        profile = self._profile_for_date(service_date)
        schedule = self._schedules.get((profile, stop.stop_id))
        if not schedule:
            return BusNextResult(
                stop=stop,
                matched_query=stop_query,
                available=False,
                service_profile=profile,
                service_profile_label=self.dataset.service_profile_labels.get(profile, profile),
                day_type=self.day_type_service.resolve_day_type(service_date),
                message="No schedule rows were found for this stop/profile combination.",
            )
        return BusNextResult(
            stop=stop,
            matched_query=stop_query,
            available=True,
            service_profile=profile,
            service_profile_label=self.dataset.service_profile_labels.get(profile, profile),
            day_type=self.day_type_service.resolve_day_type(service_date),
            departures=self._schedule_occurrences(schedule, service_date, reference_time=combine_local(service_date, self.dataset.service_profile_start_times[profile], self.timezone)),
            full_day_times=schedule.departures,
        )

    def _profile_for_date(self, service_date: date) -> str:
        resolution = self.day_type_service.resolve_day_type(service_date)
        if resolution.derived_day_type in BUS_HOLIDAY_PROFILES:
            return "weekend_us_training"
        return "weekday"

    def _schedule_occurrences(self, schedule: BusStopSchedule, service_date: date, *, reference_time: datetime) -> list[DepartureOccurrence]:
        anchor = self.dataset.service_profile_start_times[schedule.service_profile]
        occurrences: list[DepartureOccurrence] = []
        for departure_time in schedule.departures:
            next_day = departure_time < anchor
            departure_datetime = combine_local(service_date, departure_time, self.timezone, next_day=next_day)
            delta = departure_datetime - reference_time
            countdown_minutes = max(int(delta.total_seconds() // 60), 0)
            occurrences.append(
                DepartureOccurrence(
                    time=departure_time,
                    departure_datetime=departure_datetime,
                    countdown_minutes=countdown_minutes,
                    countdown_label=countdown_label(countdown_minutes),
                    is_next_day=next_day,
                    source_refs=schedule.source_refs[:3],
                )
            )
        occurrences.sort(key=lambda item: item.departure_datetime)
        return occurrences


class TrainService:
    def __init__(self, dataset: TrainDataset, timezone: str):
        self.dataset = dataset
        self.timezone = timezone
        self.zone = ZoneInfo(timezone)
        self._providers = {provider.provider_id: provider for provider in dataset.providers}

    def list_providers(self) -> list[TrainProvider]:
        return self.dataset.providers

    def resolve_provider(self, query_or_id: str) -> TrainProvider | None:
        if not query_or_id:
            return None
        if query_or_id in self._providers:
            return self._providers[query_or_id]
        normalized_query = normalize_text(query_or_id)
        for provider in self.dataset.providers:
            if normalized_query == normalize_text(provider.station_name):
                return provider
            if normalized_query in {normalize_text(alias) for alias in provider.aliases}:
                return provider
        scored: list[tuple[int, TrainProvider]] = []
        for provider in self.dataset.providers:
            haystack = " ".join([provider.station_name, *provider.aliases])
            score = fuzz.WRatio(normalized_query, normalize_text(haystack))
            if score >= 55:
                scored.append((score, provider))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored else None

    def get_next_train(
        self,
        provider_query: str,
        *,
        at: datetime | None = None,
        count: int = 3,
        destination: str | None = None,
    ) -> TrainNextResult:
        now = normalize_datetime(at, self.timezone)
        provider = self.resolve_provider(provider_query)
        if not provider:
            return TrainNextResult(available=False, message="No matching train provider was found.", matched_query=provider_query)
        if not provider.available:
            return TrainNextResult(provider=provider, available=False, message=provider.not_available_reason, matched_query=provider_query)

        departures: list[DepartureOccurrence] = []
        matched_destination = self._resolve_destination(destination) if destination else None
        for service_date in [now.date(), now.date() + timedelta(days=1)]:
            sheet = self._sheet_for_date(provider, service_date)
            if not sheet:
                continue
            for departure in sheet.departures:
                if matched_destination and departure.destination != matched_destination:
                    continue
                departure_datetime = combine_local(service_date, departure.departure_time, self.timezone)
                if departure_datetime < now:
                    continue
                delta_minutes = max(int((departure_datetime - now).total_seconds() // 60), 0)
                departures.append(
                    DepartureOccurrence(
                        time=departure.departure_time,
                        departure_datetime=departure_datetime,
                        countdown_minutes=delta_minutes,
                        countdown_label=countdown_label(delta_minutes),
                        destination=departure.destination,
                        source_refs=departure.source_refs,
                    )
                )
        departures.sort(key=lambda item: item.departure_datetime)
        sheet = self._sheet_for_date(provider, now.date())
        return TrainNextResult(
            provider=provider,
            matched_query=provider_query,
            matched_destination=matched_destination,
            available=True,
            service_key=sheet.service_key if sheet else None,
            service_label=sheet.service_label if sheet else None,
            departures=departures[:count],
            message=None if departures else "No upcoming departures were found for the current window.",
        )

    def get_full_schedule(self, provider_query: str, *, service_date: date, destination: str | None = None) -> TrainNextResult:
        provider = self.resolve_provider(provider_query)
        if not provider:
            return TrainNextResult(available=False, message="No matching train provider was found.", matched_query=provider_query)
        if not provider.available:
            return TrainNextResult(provider=provider, available=False, message=provider.not_available_reason, matched_query=provider_query)
        matched_destination = self._resolve_destination(destination) if destination else None
        sheet = self._sheet_for_date(provider, service_date)
        if not sheet:
            return TrainNextResult(provider=provider, available=False, message="No schedule sheet found for the selected date.")
        departures = []
        for departure in sheet.departures:
            if matched_destination and departure.destination != matched_destination:
                continue
            departure_datetime = combine_local(service_date, departure.departure_time, self.timezone)
            departures.append(
                DepartureOccurrence(
                    time=departure.departure_time,
                    departure_datetime=departure_datetime,
                    countdown_minutes=0,
                    countdown_label="",
                    destination=departure.destination,
                    source_refs=departure.source_refs,
                )
            )
        return TrainNextResult(
            provider=provider,
            matched_query=provider_query,
            matched_destination=matched_destination,
            available=True,
            service_key=sheet.service_key,
            service_label=sheet.service_label,
            departures=departures,
        )

    @staticmethod
    def _sheet_for_date(provider: TrainProvider, service_date: date):
        weekday = service_date.weekday()
        key = "weekday"
        if weekday == 5:
            key = "saturday"
        elif weekday == 6:
            key = "sunday"
        for sheet in provider.sheets:
            if sheet.service_key == key:
                return sheet
        return None

    @staticmethod
    def _resolve_destination(raw_query: str | None) -> str | None:
        if not raw_query:
            return None
        normalized_query = normalize_text(raw_query)
        for destination, aliases in TRAIN_DESTINATION_ALIASES.items():
            alias_keys = {normalize_text(alias) for alias in aliases}
            if normalized_query in alias_keys:
                return destination
        return raw_query
