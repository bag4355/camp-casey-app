from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from camp_casey_app.chat.intent_router import IntentRouter
from camp_casey_app.chat.schemas import ChatRequest


def _dt():
    return datetime(2026, 4, 9, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def test_intent_router_smoke():
    router = IntentRouter()
    now = _dt()
    assert router.classify("보산역 다음 인천행 언제야?", reference_time=now).intent == "train"
    assert router.classify("지금 CAC 가는 다음 버스 언제야?", reference_time=now).intent == "bus"
    assert router.classify("오늘 포데이야?", reference_time=now).intent == "holiday"
    assert router.classify("환율 1400으로 보면 워리어스클럽 버거 얼마 정도야?", reference_time=now).intent == "exchange"


def test_chat_basic_interaction(container):
    response = container.chat_agent.invoke(ChatRequest(query="지금 워리어스클럽 열었어?", locale="ko", reference_time=_dt()))
    assert response.intent == "store"
    assert "Warrior" in response.answer
    assert response.sources
