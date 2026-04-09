from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

from rapidfuzz import fuzz, process

from camp_casey_app.domain.models import DayTypeResolution, MenuItem, MoneyValue, Store, StoreDataset, StoreStatusResult, StoreSummary, StoreHoursRule
from camp_casey_app.services.day_type import DayTypeService
from camp_casey_app.utils.text import normalize_text, tokenize_for_search
from camp_casey_app.utils.time import combine_local, normalize_datetime


GENERIC_HOLIDAY_DAY_TYPES = {"us_holiday", "training_holiday", "rok_holiday"}


class StoreService:
    def __init__(self, dataset: StoreDataset, day_type_service: DayTypeService, timezone: str):
        self.dataset = dataset
        self.day_type_service = day_type_service
        self.timezone = timezone
        self.zone = ZoneInfo(timezone)
        self._by_id = {store.store_id: store for store in dataset.stores}
        self._search_index = [
            (
                store.store_id,
                " ".join(
                    [store.name, *store.aliases, *store.phones, *store.notes]
                    + [section.name for section in store.sections]
                    + [item.name for section in store.sections for item in section.items[:200]]
                ),
            )
            for store in dataset.stores
        ]

    def get_store(self, store_id: str) -> Store | None:
        return self._by_id.get(store_id)

    def resolve_store(self, query_or_id: str) -> list[Store]:
        if not query_or_id:
            return []
        if query_or_id in self._by_id:
            return [self._by_id[query_or_id]]
        normalized_query = normalize_text(query_or_id)
        exact = []
        for store in self.dataset.stores:
            alias_keys = {normalize_text(store.name), *[normalize_text(alias) for alias in store.aliases]}
            if normalized_query in alias_keys or any(alias and (alias in normalized_query or normalized_query in alias) for alias in alias_keys):
                exact.append(store)
        if exact:
            return exact
        scored = []
        for store_id, haystack in self._search_index:
            score = fuzz.WRatio(normalized_query, normalize_text(haystack))
            if score >= 55:
                scored.append((score, self._by_id[store_id]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [store for _, store in scored[:5]]

    def list_store_summaries(
        self,
        *,
        query: str | None = None,
        open_now: bool = False,
        max_minimum_order: Decimal | float | int | None = None,
        at: datetime | None = None,
        limit: int = 50,
    ) -> list[StoreSummary]:
        now = normalize_datetime(at, self.timezone)
        results: list[StoreSummary] = []
        filtered_stores = self.dataset.stores if not query else self.resolve_store(query)
        max_order_decimal = Decimal(str(max_minimum_order)) if max_minimum_order is not None else None

        for store in filtered_stores:
            status = self.resolve_store_status(store, now)
            min_order = store.minimum_delivery_order or store.minimum_order
            if open_now and not status.open_now:
                continue
            if max_order_decimal is not None and min_order and min_order.amount > max_order_decimal:
                continue
            item_count = sum(len(section.items) for section in store.sections)
            match_reason = None
            if query:
                match_reason = self._store_match_reason(store, query)
            results.append(
                StoreSummary(
                    store_id=store.store_id,
                    name=store.name,
                    aliases=store.aliases,
                    phones=store.phones,
                    updated_date=store.updated_date,
                    minimum_order=min_order,
                    delivery_charge=store.delivery_charge,
                    payment_methods=store.payment_methods,
                    status=status,
                    match_reason=match_reason,
                    item_count=item_count,
                    section_count=len(store.sections),
                    source_refs=store.source_refs,
                )
            )

        results.sort(
            key=lambda summary: (
                0 if summary.status and summary.status.open_now else 1,
                0 if summary.match_reason else 1,
                summary.name.lower(),
            )
        )
        return results[:limit]

    def search_menu(self, query: str, *, store_id: str | None = None, limit: int = 20) -> list[dict]:
        normalized_query = normalize_text(query)
        query_tokens = set(tokenize_for_search(query))
        candidates: list[tuple[float, Store, MenuItem, str]] = []
        stores = [self._by_id[store_id]] if store_id and store_id in self._by_id else self.dataset.stores

        for store in stores:
            store_tokens = set(tokenize_for_search(" ".join([store.name, *store.aliases])))
            for section in store.sections:
                section_tokens = set(tokenize_for_search(section.name))
                for item in section.items:
                    haystack = " ".join([item.name, item.description or "", " ".join(item.options), " ".join(item.flavors), section.name, store.name, " ".join(store.aliases)])
                    haystack_tokens = set(tokenize_for_search(haystack))
                    overlap = len(query_tokens & (haystack_tokens | section_tokens | store_tokens))
                    score = fuzz.WRatio(normalized_query, normalize_text(haystack)) + overlap * 18
                    if score < 55:
                        continue
                    candidates.append((score, store, item, section.name))
        candidates.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, store, item, section_name in candidates[:limit]:
            results.append(
                {
                    "score": score,
                    "store_id": store.store_id,
                    "store_name": store.name,
                    "section_name": section_name,
                    "item": item,
                    "source_refs": item.source_refs or store.source_refs,
                }
            )
        return results

    def resolve_store_status(self, store: Store, at: datetime | None = None, *, channel: str = "delivery") -> StoreStatusResult:
        now = normalize_datetime(at, self.timezone)
        rules = self._select_rule_set(store, channel=channel)
        if not rules:
            return StoreStatusResult(
                store_id=store.store_id,
                channel=channel,
                unsupported_schedule=True,
                message="No structured schedule was provided for this store.",
                source_refs=store.source_refs,
            )

        resolution = self.day_type_service.resolve_day_type(now.date())
        applicable_rules = self._rules_for_date(rules, resolution)
        if not applicable_rules:
            return StoreStatusResult(
                store_id=store.store_id,
                channel=channel,
                closed_today=True,
                message="No matching rule for this day type.",
                source_refs=store.source_refs,
            )

        active_windows: list[tuple[datetime, datetime, StoreHoursRule]] = []
        upcoming_windows: list[tuple[datetime, datetime, StoreHoursRule]] = []
        for rule in applicable_rules:
            for window in rule.windows:
                start_dt = combine_local(now.date(), window.start, self.timezone)
                end_dt = combine_local(now.date(), window.end, self.timezone, next_day=window.overnight)
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                if start_dt <= now < end_dt:
                    active_windows.append((start_dt, end_dt, rule))
                elif now < start_dt:
                    upcoming_windows.append((start_dt, end_dt, rule))

        if active_windows:
            start_dt, end_dt, rule = sorted(active_windows, key=lambda item: item[1])[0]
            closes_soon = (end_dt - now) <= timedelta(minutes=45)
            return StoreStatusResult(
                store_id=store.store_id,
                channel=channel,
                open_now=True,
                closes_soon=closes_soon,
                closes_at=end_dt.timetz().replace(tzinfo=None),
                matched_period_label=rule.period_label,
                matched_rule_labels=[rule.selectors_raw],
                source_refs=rule.source_refs,
            )

        if upcoming_windows:
            start_dt, _, rule = sorted(upcoming_windows, key=lambda item: item[0])[0]
            return StoreStatusResult(
                store_id=store.store_id,
                channel=channel,
                open_now=False,
                opens_at=start_dt.timetz().replace(tzinfo=None),
                closed_today=False,
                matched_period_label=rule.period_label,
                matched_rule_labels=[rule.selectors_raw],
                source_refs=rule.source_refs,
            )

        return StoreStatusResult(
            store_id=store.store_id,
            channel=channel,
            open_now=False,
            closed_today=True,
            matched_rule_labels=[rule.selectors_raw for rule in applicable_rules],
            source_refs=[ref for rule in applicable_rules for ref in rule.source_refs][:3],
        )

    def _select_rule_set(self, store: Store, *, channel: str) -> list[StoreHoursRule]:
        if channel == "delivery" and store.delivery_hours_rules:
            return store.delivery_hours_rules
        if channel == "regular" and store.hours_rules:
            return store.hours_rules
        return store.delivery_hours_rules or store.hours_rules

    def _rules_for_date(self, rules: Iterable[StoreHoursRule], resolution: DayTypeResolution) -> list[StoreHoursRule]:
        weekday = resolution.date.weekday()
        specific_matches: list[StoreHoursRule] = []
        weekday_matches: list[StoreHoursRule] = []
        for rule in rules:
            matched_specific = resolution.derived_day_type in set(rule.day_types)
            matched_weekday = weekday in set(rule.weekdays)
            if matched_specific:
                specific_matches.append(rule)
            elif matched_weekday:
                weekday_matches.append(rule)
        return specific_matches or weekday_matches

    def _store_match_reason(self, store: Store, query: str) -> str | None:
        query_tokens = set(tokenize_for_search(query))
        if not query_tokens:
            return None
        alias_tokens = {token for alias in store.aliases for token in tokenize_for_search(alias)}
        if query_tokens & alias_tokens:
            return "store_name"
        for section in store.sections:
            for item in section.items:
                item_tokens = set(tokenize_for_search(item.name))
                if query_tokens & item_tokens:
                    return f"menu:{item.name}"
        return None
