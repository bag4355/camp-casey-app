from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx

from camp_casey_app.domain.models import ExchangeRateSnapshot, MoneyValue
from camp_casey_app.repositories.exchange_rate_store import ExchangeRateFileStore
from camp_casey_app.utils.money import to_decimal

logger = logging.getLogger(__name__)

NAVER_RATE_URL = (
    "https://m.search.naver.com/p/csearch/content/qapirender.nhn"
    "?key=calculator&pkid=141&q=%ED%99%98%EC%9C%A8&where=m"
    "&u1=keb&u6=standardUnit&u7=0&u3=USD&u4=KRW&u8=down&u2=1"
)
_CACHE_TTL = 300  # 5 min


class NaverExchangeRateProvider:
    """Fetches the live KEB USD→KRW rate from Naver."""

    provider_id = "naver"

    def __init__(self, timezone: str, default_rate: float):
        self.timezone = timezone
        self.default_rate = Decimal(str(default_rate))
        self._cached: ExchangeRateSnapshot | None = None
        self._cached_at: float = 0

    def fetch(self) -> ExchangeRateSnapshot:
        now_ts = time.monotonic()
        if self._cached and (now_ts - self._cached_at) < _CACHE_TTL:
            return self._cached

        zone = ZoneInfo(self.timezone)
        try:
            resp = httpx.get(NAVER_RATE_URL, timeout=5, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            raw_value = data["country"][1]["value"]  # e.g. "1,479.20"
            rate = Decimal(raw_value.replace(",", ""))
            snapshot = ExchangeRateSnapshot(
                provider_id=self.provider_id,
                usd_to_krw=rate,
                updated_at=datetime.now(zone),
                status="active",
                is_auto=True,
                note="Naver KEB live rate",
            )
        except Exception:
            logger.warning("Naver rate fetch failed; using cached/default", exc_info=True)
            if self._cached:
                return self._cached
            snapshot = ExchangeRateSnapshot(
                provider_id=self.provider_id,
                usd_to_krw=self.default_rate,
                updated_at=datetime.now(zone),
                status="fallback",
                is_auto=True,
                note="Fallback to default rate",
            )

        self._cached = snapshot
        self._cached_at = now_ts
        return snapshot


class ExchangeRateService:
    def __init__(self, store: ExchangeRateFileStore, timezone: str, default_rate: float = 1500):
        self.store = store
        self.timezone = timezone
        self.naver = NaverExchangeRateProvider(timezone, default_rate)

    def get_active_exchange_rate(self) -> ExchangeRateSnapshot | None:
        return self.naver.fetch()

    @staticmethod
    def validate_rate(rate: Decimal) -> None:
        if rate <= 0:
            raise ValueError("Exchange rate must be greater than zero.")
        if rate > Decimal("100000"):
            raise ValueError("Exchange rate looks implausibly high.")

    def convert_usd_to_krw(self, amount_value, rate_value: Decimal | None = None) -> MoneyValue:
        amount = to_decimal(amount_value)
        rate = to_decimal(rate_value) if rate_value is not None else self._require_rate().usd_to_krw
        return MoneyValue(amount=(amount * rate).quantize(Decimal("1")), currency="KRW", approximate=True)

    def convert_krw_to_usd(self, amount_value, rate_value: Decimal | None = None) -> MoneyValue:
        amount = to_decimal(amount_value)
        rate = to_decimal(rate_value) if rate_value is not None else self._require_rate().usd_to_krw
        return MoneyValue(amount=(amount / rate).quantize(Decimal("0.01")), currency="USD", approximate=True)

    def _require_rate(self) -> ExchangeRateSnapshot:
        snapshot = self.get_active_exchange_rate()
        if not snapshot:
            raise ValueError("Exchange rate is not configured.")
        return snapshot

    def provider_statuses(self) -> list[dict]:
        active = self.get_active_exchange_rate()
        return [
            {
                "provider_id": "naver",
                "available": True,
                "active": True,
                "is_auto": True,
                "updated_at": active.updated_at if active else None,
            },
        ]
