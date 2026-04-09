from __future__ import annotations


def test_root_and_health(client):
    root = client.get("/")
    health = client.get("/health")
    assert root.status_code == 200
    assert "Camp Casey" in root.text
    assert health.status_code == 200
    assert health.json()["ok"] is True


def test_bootstrap_and_core_endpoints(client):
    bootstrap = client.get("/api/bootstrap")
    bus = client.get("/api/bus/next", params={"stop": "CAC"})
    train = client.get("/api/train/next", params={"provider": "bosan", "destination": "인천"})
    stores = client.get("/api/stores", params={"open_now": True})
    chat = client.post("/api/chat", json={"query": "보산역 다음 인천행 언제야?", "locale": "ko"})
    assert bootstrap.status_code == 200
    assert bus.status_code == 200
    assert train.status_code == 200
    assert stores.status_code == 200
    assert chat.status_code == 200
    assert chat.json()["intent"] == "train"


def test_exchange_rate_settings_flow(client):
    before = client.get("/api/exchange-rate").json()
    update = client.post("/api/exchange-rate", json={"rate": 1400, "note": "test override"})
    converted = client.get("/api/exchange-rate/convert", params={"amount": 12.95, "from": "USD"})
    restore = client.post("/api/exchange-rate", json={"rate": 1380, "note": "restore"})
    assert before["snapshot"] is not None
    assert update.status_code == 200
    assert converted.status_code == 200
    assert converted.json()["currency"] == "KRW"
    assert restore.status_code == 200
