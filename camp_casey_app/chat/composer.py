from __future__ import annotations

import json
from datetime import date, datetime

from camp_casey_app.ai.openai_client import OpenAIService
from camp_casey_app.utils.text import compact_whitespace

_KO_WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
_EN_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _build_context_block(reference_time: datetime | None, locale: str) -> str:
    """Return a short natural-language context string for the LLM prompt."""
    now = reference_time or datetime.now()
    wd_ko = _KO_WEEKDAYS[now.weekday()]
    wd_en = _EN_WEEKDAYS[now.weekday()]
    if locale == "ko":
        return (
            f"현재 시각: {now.strftime('%Y년 %m월 %d일 %H:%M')} ({wd_ko}). "
            "이 정보는 버스/열차 시간 질문이나 '지금', '오늘', '몇 시' 같은 표현이 포함된 경우에 활용하세요."
        )
    return (
        f"Current time: {now.strftime('%Y-%m-%d %H:%M')} ({wd_en}). "
        "Use this when the user asks about 'now', 'today', or relative times."
    )


class GroundedAnswerComposer:
    def __init__(self, openai_service: OpenAIService | None):
        self.openai_service = openai_service

    def compose(
        self,
        *,
        query: str,
        locale: str,
        intent: str,
        tool_payload: dict,
        retrieved_payload: list[dict],
        reference_time: datetime | None = None,
        history: list[dict] | None = None,
    ) -> tuple[str, bool]:
        if self.openai_service and self.openai_service.is_available():
            try:
                return self._compose_with_openai(
                    query=query, locale=locale, intent=intent,
                    tool_payload=tool_payload, retrieved_payload=retrieved_payload,
                    reference_time=reference_time,
                    history=history or [],
                ), True
            except Exception:
                pass
        return self._compose_fallback(
            query=query, locale=locale, intent=intent,
            tool_payload=tool_payload, retrieved_payload=retrieved_payload,
        ), False

    def _compose_with_openai(
        self, *, query: str, locale: str, intent: str,
        tool_payload: dict, retrieved_payload: list[dict],
        reference_time: datetime | None = None,
        history: list[dict] | None = None,
    ) -> str:
        lang = "Korean" if locale == "ko" else "English"
        context_block = _build_context_block(reference_time, locale)
        system_prompt = (
            "You are a helpful assistant for the Camp Casey Information App (for Bravo Battery, 1-38 FA). "
            "Your primary knowledge source is the tool results and retrieved documents provided in this message. "
            "You MUST NOT invent or fabricate specific facts such as bus schedules, train times, store data, holidays, or exchange rates "
            "that are not in the provided data. "
            "However, you MAY use the context information (current time, date, day of week) and natural language reasoning "
            "to answer questions naturally — for example, computing how many minutes until a departure. "
            "You SHOULD answer questions that fall into ANY of the following categories: "
            "1) questions about this app or chatbot itself, "
            "2) questions about Camp Casey, the US military base, or general military life topics, "
            "3) questions related to the data in this app (buses, trains, delivery stores, holidays, exchange rates). "
            "Only decline to answer if the question is COMPLETELY unrelated to all three categories above "
            "(e.g., general trivia, unrelated countries, unrelated topics). "
            "If the user refers to something mentioned earlier in the conversation (e.g., 'that', 'it', 'the one before'), "
            "use the conversation history to resolve the reference. "
            "Do NOT show sources, references, or internal reasoning — only give the direct answer. "
            f"Answer in {lang}. Be concise."
        )
        # 현재 턴의 tool/rag 데이터를 user 메시지 본문으로 구성
        current_user_content = json.dumps(
            {
                "context": context_block,
                "query": query,
                "intent": intent,
                "tool_payload": tool_payload,
                "retrieved_payload": retrieved_payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        return compact_whitespace(
            self.openai_service.complete_text_with_history(
                system_prompt=system_prompt,
                history=history or [],
                user_prompt=current_user_content,
            )
        )

    def _compose_fallback(self, *, query: str, locale: str, intent: str, tool_payload: dict, retrieved_payload: list[dict]) -> str:
        if intent == "bus" and tool_payload.get("bus"):
            payload = tool_payload["bus"]
            stop_name = payload.get("stop", {}).get("name")
            departures = payload.get("departures", [])
            if not departures:
                return "다음 버스를 찾지 못했습니다." if locale == "ko" else "No upcoming bus departures were found."
            snippets = ", ".join(
                f"{item['time']} ({item['countdown_label']})" + (" +1d" if item.get("is_next_day") else "")
                for item in departures[:3]
            )
            if locale == "ko":
                return f"{stop_name} 기준 다음 버스는 {snippets} 입니다. 적용 프로필은 {payload.get('service_profile_label')} 입니다."
            return f"Next buses at {stop_name}: {snippets}. Applied profile: {payload.get('service_profile_label')}."

        if intent == "train" and tool_payload.get("train"):
            payload = tool_payload["train"]
            provider_name = payload.get("provider", {}).get("station_name")
            if not payload.get("available", True):
                return payload.get("message") or ("데이터가 아직 없습니다." if locale == "ko" else "Data is not available yet.")
            departures = payload.get("departures", [])
            if not departures:
                return "다음 열차를 찾지 못했습니다." if locale == "ko" else "No upcoming train departures were found."
            snippets = ", ".join(
                f"{item['time']} {item.get('destination', '')} ({item['countdown_label']})".strip()
                for item in departures[:3]
            )
            if locale == "ko":
                return f"{provider_name} 기준 다음 열차는 {snippets} 입니다. 적용 시트는 {payload.get('service_label')} 입니다."
            return f"Next trains at {provider_name}: {snippets}. Applied sheet: {payload.get('service_label')}."

        if intent == "holiday" and tool_payload.get("holiday"):
            payload = tool_payload["holiday"]
            date_label = payload.get("date")
            derived = payload.get("derived_day_type")
            status = payload.get("status")
            holiday_name = payload.get("holiday_name")
            reason = payload.get("reason")
            if locale == "ko":
                base = f"{date_label}의 day type은 {derived} 입니다."
                if holiday_name:
                    base += f" {holiday_name}."
                if status:
                    base += f" 상태는 {status}."
                if reason:
                    base += f" 근거: {reason}"
                return base
            base = f"The day type for {date_label} is {derived}."
            if holiday_name:
                base += f" {holiday_name}."
            if status:
                base += f" Status: {status}."
            if reason:
                base += f" Basis: {reason}"
            return base

        if intent == "store" and tool_payload.get("stores") is not None:
            items = tool_payload["stores"]
            if not items:
                return "조건에 맞는 매장을 찾지 못했습니다." if locale == "ko" else "No stores matched the current filters."
            pieces = []
            for store in items[:4]:
                status = store.get("status") or {}
                if locale == "ko":
                    if status.get("open_now"):
                        state_text = f"현재 영업 중, {status.get('closes_at') or ''}까지"
                    elif status.get("opens_at"):
                        state_text = f"현재 닫힘, {status.get('opens_at')}에 오픈"
                    elif status.get("unsupported_schedule"):
                        state_text = "운영시간 미제공"
                    else:
                        state_text = "오늘 영업 종료"
                    pieces.append(f"{store['name']} ({state_text})")
                else:
                    if status.get("open_now"):
                        state_text = f"open now, closes {status.get('closes_at') or ''}"
                    elif status.get("opens_at"):
                        state_text = f"closed now, opens {status.get('opens_at')}"
                    elif status.get("unsupported_schedule"):
                        state_text = "hours unavailable"
                    else:
                        state_text = "closed for the rest of today"
                    pieces.append(f"{store['name']} ({state_text})")
            joiner = "; ".join(pieces)
            if locale == "ko":
                return f"매장 결과: {joiner}."
            return f"Store results: {joiner}."

        if intent == "exchange" and tool_payload.get("exchange") is not None:
            payload = tool_payload["exchange"]
            matched = payload.get("matched_menu_item") or {}
            if locale == "ko":
                base = payload.get("message_ko") or payload.get("message_en") or "환율 정보를 처리했습니다."
                if matched:
                    return f"{matched.get('store_name')}의 {matched.get('item_name')} 기준: {base}"
                return base
            base = payload.get("message_en") or payload.get("message_ko") or "Exchange-rate information processed."
            if matched:
                return f"For {matched.get('item_name')} at {matched.get('store_name')}: {base}"
            return base

        if retrieved_payload:
            top = retrieved_payload[0]
            if locale == "ko":
                return f"{top.get('title')}: {top.get('text')[:240]}"
            return f"{top.get('title')}: {top.get('text')[:240]}"
        if locale == "ko":
            return "해당 내용에 대한 정보가 없어서 정확히 답변드리기 어렵습니다. 버스·기차 시간표, 배달 매장, 휴일, 환율 또는 캠프 케이시·군 생활 관련 질문을 해주세요."
        return "I don't have specific information on that topic. Feel free to ask about bus/train schedules, delivery stores, holidays, exchange rates, or Camp Casey / military life."
