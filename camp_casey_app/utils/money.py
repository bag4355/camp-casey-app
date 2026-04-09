from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from camp_casey_app.domain.models import MoneyValue


_money_re = re.compile(r"(?P<sign>[+-])?\s*\$?\s*(?P<num>\d+(?:[.,]\d+)?)")


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if value is None:
        raise ValueError("Missing numeric value")
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid numeric value: {value}") from exc


def parse_money(raw_value: Any, *, currency: str = "USD", approximate: bool = False) -> MoneyValue | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, MoneyValue):
        return raw_value
    if isinstance(raw_value, (int, float, Decimal)):
        return MoneyValue(amount=to_decimal(raw_value), currency=currency, raw_text=str(raw_value), approximate=approximate)

    raw_text = str(raw_value).strip()
    if not raw_text:
        return None
    match = _money_re.search(raw_text.replace(",", ""))
    if not match:
        return None
    amount = Decimal(match.group("num"))
    if match.group("sign") == "-":
        amount = -amount
    return MoneyValue(amount=amount, currency=currency, raw_text=raw_text, approximate=approximate)
