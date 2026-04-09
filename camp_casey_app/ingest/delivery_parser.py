from __future__ import annotations

import json
from datetime import date
from typing import Any

from camp_casey_app.domain.models import MenuItem, MenuPriceVariant, MenuSection, Store, StoreDataset, StoreHoursRule, TimeWindow
from camp_casey_app.ingest.common import json_source
from camp_casey_app.utils.money import parse_money
from camp_casey_app.utils.text import dedupe_keep_order, normalize_text, slugify
from camp_casey_app.utils.time import parse_time_range


COMMON_STORE_SUFFIXES = [
    " delivery menu",
    " delivery service",
    " restaurant delivery service",
    " delivery",
]

MANUAL_STORE_ALIASES = {
    "warrior-s-club-delivery-menu": ["warriors club", "warrior's club", "warrior club", "워리어스 클럽", "워리어스클럽"],
    "warrior-s-club-breakfast": ["warriors club", "warrior's club breakfast", "warrior breakfast", "워리어스 클럽 조식", "워리어스클럽 조식"],
    "thunder-east-casey-katusa-snack-bar": ["thunder", "east casey thunder", "썬더", "katusa snack bar"],
    "impact-zone": ["impact zone", "임팩트 존"],
    "casey-indianhead-golf-course-restaurant-delivery-service": ["indianhead", "golf course", "indianhead golf course", "인디언헤드"],
    "crack-chicken": ["crack chicken", "크랙 치킨"],
}


def _store_aliases(store_name: str, store_id: str) -> list[str]:
    aliases = [store_name]
    normalized = normalize_text(store_name)
    trimmed = normalized
    for suffix in COMMON_STORE_SUFFIXES:
        if trimmed.endswith(suffix):
            trimmed = trimmed[: -len(suffix)].strip()
    if trimmed and trimmed != normalized:
        aliases.append(trimmed.title())
        aliases.append(trimmed)
    aliases.extend(MANUAL_STORE_ALIASES.get(store_id, []))
    return dedupe_keep_order(aliases)


def _selector_to_rule_parts(selector: str) -> tuple[list[int], list[str]]:
    key = normalize_text(selector).replace(" ", "_").replace("-", "_")
    weekdays: list[int] = []
    day_types: list[str] = []

    if "mon_fri" in key:
        weekdays = [0, 1, 2, 3, 4]
    elif "sat_sun" in key:
        weekdays = [5, 6]
    elif "sun_thu" in key:
        weekdays = [6, 0, 1, 2, 3]
    elif "fri_sat" in key:
        weekdays = [4, 5]
    elif key == "open":
        weekdays = [0, 1, 2, 3, 4, 5, 6]

    if "us_holiday" in key:
        day_types.append("us_holiday")
    if "training_holiday" in key:
        day_types.append("training_holiday")
    if "rok_holiday" in key:
        day_types.append("rok_holiday")

    if "_holiday" in key and not any(item in key for item in ("us_holiday", "training_holiday", "rok_holiday")):
        day_types.extend(["us_holiday", "training_holiday", "rok_holiday"])

    return weekdays, day_types


def _parse_closed_weekdays(raw_value: str) -> set[int]:
    mapping = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    result: set[int] = set()
    parts = normalize_text(raw_value).replace("/", ",").split(",")
    for part in parts:
        token = part.strip()[:3]
        if token in mapping:
            result.add(mapping[token])
    return result


def _parse_hours_map(
    hours_map: dict[str, Any],
    *,
    channel: str,
    store_id: str,
    base_pointer: str,
    source_file: str,
    period_label: str | None = None,
) -> list[StoreHoursRule]:
    rules: list[StoreHoursRule] = []

    if "open" in hours_map:
        weekdays = [0, 1, 2, 3, 4, 5, 6]
        if "closed" in hours_map and isinstance(hours_map["closed"], str):
            weekdays = [day for day in weekdays if day not in _parse_closed_weekdays(hours_map["closed"])]
        start, end, overnight = parse_time_range(str(hours_map["open"]))
        rules.append(
            StoreHoursRule(
                rule_id=slugify(f"{store_id}-{channel}-{period_label or 'default'}-open"),
                channel=channel,
                period_label=period_label,
                selectors_raw="open",
                weekdays=weekdays,
                day_types=[],
                windows=[TimeWindow(start=start, end=end, overnight=overnight, raw_text=str(hours_map["open"]))],
                source_refs=[
                    json_source(
                        source_file,
                        f"{source_file} • {store_id} • {period_label or channel} open",
                        f"{base_pointer}/open",
                        excerpt=str(hours_map["open"]),
                    )
                ],
            )
        )
        return rules

    for selector, raw_value in hours_map.items():
        if selector == "closed":
            continue
        if not isinstance(raw_value, str):
            continue
        weekdays, day_types = _selector_to_rule_parts(selector)
        start, end, overnight = parse_time_range(raw_value)
        rules.append(
            StoreHoursRule(
                rule_id=slugify(f"{store_id}-{channel}-{period_label or 'default'}-{selector}"),
                channel=channel,
                period_label=period_label,
                selectors_raw=selector,
                weekdays=weekdays,
                day_types=day_types,
                windows=[TimeWindow(start=start, end=end, overnight=overnight, raw_text=raw_value)],
                source_refs=[
                    json_source(
                        source_file,
                        f"{source_file} • {store_id} • {period_label or channel} • {selector}",
                        f"{base_pointer}/{selector}",
                        excerpt=raw_value,
                    )
                ],
            )
        )
    return rules


def _parse_hours_block(
    raw_block: dict[str, Any] | None,
    *,
    channel: str,
    store_id: str,
    base_pointer: str,
    source_file: str,
) -> list[StoreHoursRule]:
    if not raw_block:
        return []
    if all(isinstance(value, str) for value in raw_block.values()):
        return _parse_hours_map(
            raw_block,
            channel=channel,
            store_id=store_id,
            base_pointer=base_pointer,
            source_file=source_file,
        )
    rules: list[StoreHoursRule] = []
    for period_label, value in raw_block.items():
        if isinstance(value, dict):
            rules.extend(
                _parse_hours_map(
                    value,
                    channel=channel,
                    store_id=store_id,
                    base_pointer=f"{base_pointer}/{period_label}",
                    source_file=source_file,
                    period_label=period_label,
                )
            )
    return rules


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        result: list[str] = []
        for key, items in value.items():
            if isinstance(items, list):
                result.append(f"{key.title()}: {', '.join(str(item) for item in items)}")
            else:
                result.append(f"{key.title()}: {items}")
        return result
    text = str(value).strip()
    return [text] if text else []


def _build_pricing_variants(raw_item: dict[str, Any]) -> tuple[list[MenuPriceVariant], list[MenuPriceVariant]]:
    pricing: list[MenuPriceVariant] = []
    addons: list[MenuPriceVariant] = []

    quantity = raw_item.get("quantity")
    if raw_item.get("price") is not None:
        pricing.append(MenuPriceVariant(label=str(quantity) if quantity else None, price=parse_money(raw_item.get("price"))))

    for key, label in (("small", "Small"), ("large", "Large"), ("small_price", "Small"), ("large_price", "Large")):
        if raw_item.get(key) is not None:
            pricing.append(MenuPriceVariant(label=label, price=parse_money(raw_item.get(key))))

    for option in raw_item.get("price_options", []) or []:
        if not isinstance(option, dict):
            continue
        label = option.get("type") or option.get("size") or option.get("quantity") or option.get("name")
        pricing.append(MenuPriceVariant(label=str(label) if label else None, price=parse_money(option.get("price"))))

    if raw_item.get("price_delta") is not None:
        addons.append(MenuPriceVariant(label="Extra", price=parse_money(raw_item.get("price_delta"))))

    for key, value in raw_item.items():
        if key.startswith("add_"):
            label = key.removeprefix("add_").replace("_", " ").title()
            addons.append(MenuPriceVariant(label=label, price=parse_money(value)))

    return pricing, addons


def _base_item_from_raw(store_id: str, section_id: str, raw_item: dict[str, Any], item_name: str, source_file: str, pointer: str, *, is_auxiliary: bool = False) -> MenuItem:
    pricing, addons = _build_pricing_variants(raw_item)
    notes = []
    for key in ("note", "extra_note"):
        if raw_item.get(key):
            notes.append(str(raw_item[key]))
    notes.extend(_string_list(raw_item.get("notes")))
    source_ref = json_source(source_file, f"{source_file} • {item_name}", pointer, excerpt=raw_item.get("description"))
    return MenuItem(
        item_id=slugify(f"{store_id}-{section_id}-{item_name}"),
        store_id=store_id,
        section_id=section_id,
        name=item_name,
        description=raw_item.get("description"),
        pricing=[variant for variant in pricing if variant.price is not None],
        addons=[variant for variant in addons if variant.price is not None],
        quantity=str(raw_item.get("quantity")) if raw_item.get("quantity") else None,
        options=_string_list(raw_item.get("options")),
        flavors=_string_list(raw_item.get("flavors")),
        notes=notes,
        tags=_string_list(raw_item.get("tags")),
        is_auxiliary=is_auxiliary,
        source_refs=[source_ref],
    )


def _normalize_item(store_id: str, section_id: str, raw_item: Any, source_file: str, pointer: str) -> list[MenuItem]:
    if isinstance(raw_item, str):
        return [
            MenuItem(
                item_id=slugify(f"{store_id}-{section_id}-{raw_item}"),
                store_id=store_id,
                section_id=section_id,
                name=raw_item.strip(),
                source_refs=[json_source(source_file, f"{source_file} • {raw_item}", pointer)],
            )
        ]

    if not isinstance(raw_item, dict):
        return []

    item_name = str(raw_item.get("name") or raw_item.get("title") or "Unnamed Item").strip()

    if raw_item.get("sizes"):
        nested_items: list[MenuItem] = []
        for size_index, size_group in enumerate(raw_item.get("sizes") or []):
            if not isinstance(size_group, dict):
                continue
            size_label = size_group.get("size") or f"Variant {size_index + 1}"
            for nested_index, nested_item in enumerate(size_group.get("items") or []):
                if isinstance(nested_item, dict):
                    copied = dict(nested_item)
                    copied["name"] = f"{item_name} / {size_label} / {nested_item.get('name', 'Option')}"
                    nested_items.extend(
                        _normalize_item(
                            store_id,
                            section_id,
                            copied,
                            source_file,
                            f"{pointer}/sizes/{size_index}/items/{nested_index}",
                        )
                    )
        for extra_index, extra_option in enumerate(raw_item.get("extra_options") or []):
            if isinstance(extra_option, dict):
                copied = dict(extra_option)
                copied["name"] = f"{item_name} / {extra_option.get('name', 'Extra')}"
                nested_items.append(
                    _base_item_from_raw(
                        store_id,
                        section_id,
                        copied,
                        copied["name"],
                        source_file,
                        f"{pointer}/extra_options/{extra_index}",
                        is_auxiliary=True,
                    )
                )
        return nested_items

    if raw_item.get("items") and not any(raw_item.get(key) is not None for key in ("price", "price_options", "small", "large", "small_price", "large_price")):
        nested_items: list[MenuItem] = []
        for nested_index, nested_item in enumerate(raw_item.get("items") or []):
            if isinstance(nested_item, dict):
                copied = dict(nested_item)
                copied["name"] = f"{item_name} / {nested_item.get('name', 'Item')}"
                nested_items.extend(
                    _normalize_item(
                        store_id,
                        section_id,
                        copied,
                        source_file,
                        f"{pointer}/items/{nested_index}",
                    )
                )
            else:
                nested_items.extend(
                    _normalize_item(
                        store_id,
                        section_id,
                        {"name": f"{item_name} / {nested_item}"},
                        source_file,
                        f"{pointer}/items/{nested_index}",
                    )
                )
        return nested_items

    return [_base_item_from_raw(store_id, section_id, raw_item, item_name, source_file, pointer)]


def _extract_supporting_lists(section_raw: dict[str, Any]) -> tuple[dict[str, list[str]], list[MenuItem], list[str]]:
    supporting_lists: dict[str, list[str]] = {}
    auxiliary_items: list[MenuItem] = []
    notes: list[str] = []
    # This helper is completed inside _normalize_sections where IDs are available.
    return supporting_lists, auxiliary_items, notes


def _normalize_sections(
    store_id: str,
    sections_raw: list[dict[str, Any]],
    *,
    source_file: str,
    base_pointer: str,
    parent_section_id: str | None = None,
) -> list[MenuSection]:
    sections: list[MenuSection] = []
    for index, raw_section in enumerate(sections_raw or []):
        if not isinstance(raw_section, dict):
            continue
        section_name = str(raw_section.get("section_name") or raw_section.get("name") or f"Section {index + 1}").strip()
        section_id = slugify(f"{store_id}-{parent_section_id or 'root'}-{section_name}")
        source_ref = json_source(source_file, f"{source_file} • {section_name}", f"{base_pointer}/{index}")

        notes = []
        if raw_section.get("note"):
            notes.append(str(raw_section["note"]))
        notes.extend(_string_list(raw_section.get("notes")))
        if raw_section.get("combo_note"):
            notes.append(str(raw_section["combo_note"]))
        if raw_section.get("size"):
            notes.append(f"Size: {raw_section['size']}")
        if raw_section.get("delivery_hours"):
            notes.append(f"Section delivery hours: {raw_section['delivery_hours']}")

        supporting_lists: dict[str, list[str]] = {}
        for key in ("combo_options", "dressings", "sauces", "pizza_toppings"):
            if raw_section.get(key):
                supporting_lists[key] = _string_list(raw_section.get(key))

        for key in ("sauce_option", "sauce_option_4oz", "dressing_option_4oz", "salad_dressing_3_25oz"):
            if raw_section.get(key):
                notes.append(f"{key.replace('_', ' ').title()}: {raw_section[key]}")

        items: list[MenuItem] = []
        for item_index, raw_item in enumerate(raw_section.get("items", []) or []):
            items.extend(_normalize_item(store_id, section_id, raw_item, source_file, f"{base_pointer}/{index}/items/{item_index}"))

        for extra_key in ("extras", "extra_options", "extra_toppings"):
            for extra_index, extra_item in enumerate(raw_section.get(extra_key, []) or []):
                if isinstance(extra_item, dict):
                    copied = dict(extra_item)
                    copied["name"] = f"{extra_key.replace('_', ' ').title()} / {extra_item.get('name', 'Extra')}"
                    items.append(
                        _base_item_from_raw(
                            store_id,
                            section_id,
                            copied,
                            copied["name"],
                            source_file,
                            f"{base_pointer}/{index}/{extra_key}/{extra_index}",
                            is_auxiliary=True,
                        )
                    )
                else:
                    supporting_lists.setdefault(extra_key, []).append(str(extra_item))

        flags = []
        if "alternate board" in normalize_text(section_name):
            flags.append("alternate_board")

        section = MenuSection(
            section_id=section_id,
            store_id=store_id,
            name=section_name,
            parent_section_id=parent_section_id,
            note=raw_section.get("note"),
            notes=notes,
            items=items,
            supporting_lists=supporting_lists,
            flags=flags,
            section_hours_text=raw_section.get("delivery_hours"),
            source_refs=[source_ref],
        )
        sections.append(section)

        subsection_raw = raw_section.get("subsections") or []
        child_sections = _normalize_sections(
            store_id,
            subsection_raw,
            source_file=source_file,
            base_pointer=f"{base_pointer}/{index}/subsections",
            parent_section_id=section_id,
        )
        section.child_section_ids = [child.section_id for child in child_sections]
        sections.extend(child_sections)
    return sections


def parse_delivery_file(path) -> StoreDataset:
    data = json.loads(path.read_text(encoding="utf-8"))
    stores: list[Store] = []

    for store_index, raw_store in enumerate(data.get("stores", [])):
        store_name = str(raw_store.get("store_name", f"Store {store_index + 1}")).strip()
        store_id = slugify(store_name)
        pointer = f"/stores/{store_index}"
        source_ref = json_source(path.name, f"{path.name} • {store_name}", pointer)

        hours_rules = _parse_hours_block(
            raw_store.get("hours"),
            channel="general",
            store_id=store_id,
            base_pointer=f"{pointer}/hours",
            source_file=path.name,
        )
        delivery_hours_rules = _parse_hours_block(
            raw_store.get("delivery_hours"),
            channel="delivery",
            store_id=store_id,
            base_pointer=f"{pointer}/delivery_hours",
            source_file=path.name,
        )
        regular_hours_rules = _parse_hours_block(
            raw_store.get("regular_hours_of_operation"),
            channel="regular",
            store_id=store_id,
            base_pointer=f"{pointer}/regular_hours_of_operation",
            source_file=path.name,
        )
        hours_rules.extend(regular_hours_rules)

        sections = _normalize_sections(
            store_id,
            raw_store.get("sections") or [],
            source_file=path.name,
            base_pointer=f"{pointer}/sections",
        )

        updated_date = None
        if raw_store.get("updated_date"):
            updated_date = date.fromisoformat(raw_store["updated_date"])

        stores.append(
            Store(
                store_id=store_id,
                name=store_name,
                aliases=_store_aliases(store_name, store_id),
                phones=_string_list(raw_store.get("phone")) + _string_list(raw_store.get("delivery_service_number")),
                instagram=raw_store.get("instagram"),
                address=raw_store.get("address"),
                updated_date=updated_date,
                minimum_order=parse_money(raw_store.get("minimum_order")),
                minimum_delivery_order=parse_money(raw_store.get("minimum_delivery_order")),
                delivery_charge=parse_money(raw_store.get("delivery_charge")),
                payment_methods=_string_list(raw_store.get("payment")),
                last_order_note=raw_store.get("last_order_note"),
                notes=_string_list(raw_store.get("notes")),
                hours_rules=hours_rules,
                delivery_hours_rules=delivery_hours_rules,
                sections=sections,
                additions=_string_list(raw_store.get("additions")),
                recommended_menu=_string_list(raw_store.get("recommended_menu")),
                source_refs=[source_ref],
            )
        )

    return StoreDataset(stores=stores)
