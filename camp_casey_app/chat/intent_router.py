from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from camp_casey_app.chat.schemas import IntentClassification
from camp_casey_app.utils.text import normalize_text


_AMOUNT_RE = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>usd|krw|달러|원|\$|₩)?", re.IGNORECASE)
_DATE_RE = re.compile(r"(?P<year>20\d{2})[-/.](?P<month>\d{1,2})[-/.](?P<day>\d{1,2})")


class IntentRouter:
    def classify(self, query: str, *, reference_time: datetime) -> IntentClassification:
        normalized = normalize_text(query)
        entities: dict = {}
        filters: dict = {}
        confidence = 0.75

        parsed_date = self._parse_date(normalized, reference_time.date())
        if parsed_date:
            entities["date"] = parsed_date.isoformat()

        count_match = re.search(r"(?:다음|next)\s*(\d+)", normalized)
        if count_match:
            filters["count"] = int(count_match.group(1))

        money_limit = self._extract_limit(normalized)
        if money_limit is not None:
            filters["max_minimum_order"] = float(money_limit)

        rate_override = self._extract_rate_override(normalized)
        if rate_override is not None:
            filters["rate_override"] = float(rate_override)

        currency_amount = self._extract_currency_amount(normalized, rate_override=rate_override)
        if currency_amount:
            entities.update(currency_amount)

        if any(token in normalized for token in ["환율", "krw", "usd", "원화", "달러", "exchange", "convert", "변환"]):
            return IntentClassification(intent="exchange", confidence=0.9, entities=entities, filters=filters)
        if any(token in normalized for token in ["holiday", "휴일", "포데이", "family day", "training holiday", "day type"]):
            return IntentClassification(intent="holiday", confidence=0.9, entities=entities, filters=filters)
        if any(token in normalized for token in ["train", "전철", "기차", "보산", "bosan", "지행", "jihaeng", "역", "인천", "청량리", "광운대", "소요산"]):
            destination = self._extract_destination(normalized)
            if destination:
                entities["destination"] = destination
            provider = "jihaeng" if any(token in normalized for token in ["지행", "jihaeng"]) else "bosan"
            entities["provider"] = provider
            return IntentClassification(intent="train", confidence=0.9, entities=entities, filters=filters)
        if any(token in normalized for token in ["bus", "버스", "정류장", "cac", "web", "hovey", "casey", "shuttle"]):
            return IntentClassification(intent="bus", confidence=0.85, entities=entities, filters=filters)
        if any(token in normalized for token in ["open", "열", "배달", "delivery", "restaurant", "식당", "menu", "메뉴", "minimum order", "최소 주문", "warrior", "thunder", "impact", "chicken", "burger", "club"]):
            if "open" in normalized or "열" in normalized:
                filters["open_now"] = True
            return IntentClassification(intent="store", confidence=0.82, entities=entities, filters=filters)
        return IntentClassification(intent="general", confidence=confidence, entities=entities, filters=filters)

    @staticmethod
    def _parse_date(normalized_query: str, reference_date: date) -> date | None:
        if "오늘" in normalized_query or "today" in normalized_query:
            return reference_date
        if "내일" in normalized_query or "tomorrow" in normalized_query:
            return reference_date + timedelta(days=1)
        match = _DATE_RE.search(normalized_query)
        if match:
            return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
        return None

    @staticmethod
    def _extract_limit(normalized_query: str) -> Decimal | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:usd|달러|\$).*(?:이하|under|below|less)", normalized_query)
        if match:
            return Decimal(match.group(1))
        return None

    @staticmethod
    def _extract_rate_override(normalized_query: str) -> Decimal | None:
        match = re.search(r"(?:환율|rate)\s*(?:을|를|=|is|:)?\s*(\d+(?:\.\d+)?)", normalized_query)
        if match:
            return Decimal(match.group(1))
        return None

    @staticmethod
    def _extract_currency_amount(normalized_query: str, *, rate_override: Decimal | None = None) -> dict | None:
        match = _AMOUNT_RE.search(normalized_query)
        if not match:
            return None
        amount = Decimal(match.group("amount"))
        unit = (match.group("unit") or "").lower()
        if unit in {"원", "krw", "₩"}:
            return {"amount": float(amount), "amount_currency": "KRW"}
        if unit in {"달러", "usd", "$"}:
            return {"amount": float(amount), "amount_currency": "USD"}
        if rate_override is not None:
            return None
        return {"amount": float(amount)}

    @staticmethod
    def _extract_destination(normalized_query: str) -> str | None:
        for token in ["인천", "청량리", "광운대", "소요산", "incheon", "cheongnyangni", "gwangwoondae", "soyosan"]:
            if token in normalized_query:
                return token
        return None
