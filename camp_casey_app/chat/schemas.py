from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from camp_casey_app.domain.models import SourceReference


class HistoryMessage(BaseModel):
    """단일 대화 메시지 (히스토리 항목)."""
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str
    locale: str = "ko"
    currency_mode: str = "usd_plus_krw"
    reference_time: datetime | None = None
    session_id: str | None = None


class IntentClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intent: str
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)


class SourceBasis(BaseModel):
    label: str
    excerpt: str | None = None
    source: SourceReference | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str
    locale: str
    intent: str
    answer: str
    tool_results: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceBasis] = Field(default_factory=list)
    used_llm: bool = False
    session_id: str | None = None
    history: list[HistoryMessage] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)
