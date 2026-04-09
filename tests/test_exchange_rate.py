from __future__ import annotations

from decimal import Decimal

import pytest

from camp_casey_app.repositories.exchange_rate_store import ExchangeRateFileStore
from camp_casey_app.services.exchange_rate import ExchangeRateService, FutureAutoExchangeRateProvider


@pytest.fixture()
def exchange_service(tmp_path):
    return ExchangeRateService(ExchangeRateFileStore(tmp_path / "exchange_rate.json"), "Asia/Seoul")


def test_manual_exchange_rate_validation(exchange_service):
    with pytest.raises(ValueError):
        exchange_service.set_manual_exchange_rate(0)
    snapshot = exchange_service.set_manual_exchange_rate("1400.5")
    assert snapshot.usd_to_krw == Decimal("1400.5")


def test_exchange_conversion(exchange_service):
    exchange_service.set_manual_exchange_rate(1380)
    krw = exchange_service.convert_usd_to_krw("12.95")
    usd = exchange_service.convert_krw_to_usd(18000)
    assert float(krw.amount) == 17871.0
    assert float(usd.amount) == 13.04


def test_future_auto_provider_placeholder():
    provider = FutureAutoExchangeRateProvider()
    status = provider.status()
    assert status["available"] is False
    assert "scaffolded" in status["message"]
