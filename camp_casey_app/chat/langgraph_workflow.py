from __future__ import annotations

from datetime import date, datetime
from typing import Any

from camp_casey_app.chat.composer import GroundedAnswerComposer
from camp_casey_app.chat.intent_router import IntentRouter
from camp_casey_app.chat.schemas import ChatRequest, ChatResponse, HistoryMessage, SourceBasis
from camp_casey_app.chat.session_store import SessionStore
from camp_casey_app.domain.models import MenuItem, Store
from camp_casey_app.services.exchange_rate import ExchangeRateService
from camp_casey_app.services.holidays import HolidayService
from camp_casey_app.services.search import SearchService
from camp_casey_app.services.stores import StoreService
from camp_casey_app.services.transport import BusService, TrainService
from camp_casey_app.utils.money import parse_money
from camp_casey_app.utils.text import normalize_text
from camp_casey_app.utils.time import normalize_datetime

try:  # pragma: no cover - optional dependency in grading env
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"
    StateGraph = None


class CampCaseyChatAgent:
    def __init__(
        self,
        *,
        bus_service: BusService,
        train_service: TrainService,
        store_service: StoreService,
        holiday_service: HolidayService,
        exchange_service: ExchangeRateService,
        search_service: SearchService,
        rag_repository,
        openai_service=None,
        session_store: SessionStore | None = None,
        timezone: str = "Asia/Seoul",
        default_bus_stop_query: str = "CAC",
    ):
        self.bus_service = bus_service
        self.train_service = train_service
        self.store_service = store_service
        self.holiday_service = holiday_service
        self.exchange_service = exchange_service
        self.search_service = search_service
        self.rag_repository = rag_repository
        self.router = IntentRouter()
        self.composer = GroundedAnswerComposer(openai_service)
        self.session_store = session_store or SessionStore()
        self.timezone = timezone
        self.default_bus_stop_query = default_bus_stop_query
        self.graph = self._build_graph()

    def invoke(self, request: ChatRequest) -> ChatResponse:
        # 세션 히스토리 로드
        session_id = request.session_id
        history: list[dict] = []
        if session_id:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in self.session_store.get_history(session_id)
            ]

        if self.graph is not None:
            state = self.graph.invoke({
                "request": request.model_dump(mode="python"),
                "history": history,
            })
        else:
            state = self._manual_invoke_state(request, history)

        response: ChatResponse = state["response"]

        # 응답 후 히스토리 저장
        if session_id:
            self.session_store.append(session_id, "user", request.query)
            self.session_store.append(session_id, "assistant", response.answer)
            updated_history = [
                HistoryMessage(role=m["role"], content=m["content"])
                for m in self.session_store.get_history(session_id)
            ]
            response = response.model_copy(update={
                "session_id": session_id,
                "history": updated_history,
            })

        return response

    def _manual_invoke_state(self, request: ChatRequest, history: list[dict]) -> dict[str, Any]:
        state: dict[str, Any] = {
            "request": request.model_dump(mode="python"),
            "history": history,
        }
        state = self._classify_intent_node(state)
        intent = state["classification"]["intent"]
        if intent == "bus":
            state = self._bus_node(state)
        elif intent == "train":
            state = self._train_node(state)
        elif intent == "store":
            state = self._store_node(state)
        elif intent == "holiday":
            state = self._holiday_node(state)
        elif intent == "exchange":
            state = self._exchange_node(state)
        state = self._rag_node(state)
        state = self._compose_node(state)
        return state

    def _build_graph(self):
        if StateGraph is None:
            return None

        graph = StateGraph(dict)
        graph.add_node("classify", self._classify_intent_node)
        graph.add_node("bus", self._bus_node)
        graph.add_node("train", self._train_node)
        graph.add_node("store", self._store_node)
        graph.add_node("holiday", self._holiday_node)
        graph.add_node("exchange", self._exchange_node)
        graph.add_node("rag", self._rag_node)
        graph.add_node("compose", self._compose_node)
        graph.set_entry_point("classify")
        graph.add_conditional_edges(
            "classify",
            self._route_from_intent,
            {
                "bus": "bus",
                "train": "train",
                "store": "store",
                "holiday": "holiday",
                "exchange": "exchange",
                "general": "rag",
            },
        )
        graph.add_edge("bus", "rag")
        graph.add_edge("train", "rag")
        graph.add_edge("store", "rag")
        graph.add_edge("holiday", "rag")
        graph.add_edge("exchange", "rag")
        graph.add_edge("rag", "compose")
        graph.add_edge("compose", END)
        return graph.compile()

    def _route_from_intent(self, state: dict) -> str:
        return state["classification"]["intent"]

    def _classify_intent_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        reference_time = normalize_datetime(request.reference_time, self.timezone)
        classification = self.router.classify(request.query, reference_time=reference_time)
        state["classification"] = classification.model_dump(mode="python")
        state["reference_time"] = reference_time
        return state

    def _bus_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        filters = state["classification"].get("filters", {})
        count = int(filters.get("count", 3))
        stop_matches = self.bus_service.search_stops(request.query, limit=1)
        stop_query = stop_matches[0].stop_id if stop_matches else self.default_bus_stop_query
        result = self.bus_service.get_next_bus(stop_query, at=state["reference_time"], count=count)
        state["tool_payload"] = {"bus": result.model_dump(mode="json")}
        state["tool_sources"] = result.stop.source_refs if result.stop else []
        return state

    def _train_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        entities = state["classification"].get("entities", {})
        filters = state["classification"].get("filters", {})
        count = int(filters.get("count", 3))
        provider = entities.get("provider", "bosan")
        destination = entities.get("destination")
        result = self.train_service.get_next_train(provider, at=state["reference_time"], count=count, destination=destination)
        state["tool_payload"] = {"train": result.model_dump(mode="json")}
        state["tool_sources"] = result.provider.source_refs if result.provider else []
        return state

    def _store_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        filters = state["classification"].get("filters", {})
        stores = self.store_service.list_store_summaries(
            query=request.query,
            open_now=bool(filters.get("open_now")),
            max_minimum_order=filters.get("max_minimum_order"),
            at=state["reference_time"],
            limit=6,
        )
        state["tool_payload"] = {"stores": [store.model_dump(mode="json") for store in stores]}
        state["tool_sources"] = [ref for store in stores for ref in store.source_refs][:6]
        return state

    def _holiday_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        entities = state["classification"].get("entities", {})
        target_date = date.fromisoformat(entities["date"]) if entities.get("date") else state["reference_time"].date()
        resolution = self.store_service.day_type_service.resolve_day_type(target_date)
        state["tool_payload"] = {"holiday": resolution.model_dump(mode="json")}
        state["tool_sources"] = resolution.source_refs
        return state

    def _exchange_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        normalized_query = normalize_text(request.query)
        entities = state["classification"].get("entities", {})
        filters = state["classification"].get("filters", {})
        snapshot = self.exchange_service.get_active_exchange_rate()
        rate_override = filters.get("rate_override")
        applied_rate = rate_override if rate_override is not None else (float(snapshot.usd_to_krw) if snapshot else None)

        if rate_override is not None and any(token in normalized_query for token in ["설정", "저장", "set", "save"]):
            updated = self.exchange_service.set_manual_exchange_rate(rate_override, note="Set from chat request")
            payload = {
                "snapshot": updated.model_dump(mode="json"),
                "message_ko": f"수동 환율을 1 USD = {float(updated.usd_to_krw):,.2f} KRW로 저장했습니다.",
                "message_en": f"Saved manual rate: 1 USD = {float(updated.usd_to_krw):,.2f} KRW.",
            }
            state["tool_payload"] = {"exchange": payload}
            state["tool_sources"] = []
            return state

        amount = entities.get("amount")
        amount_currency = entities.get("amount_currency")
        matched_menu_item = None
        if amount is None:
            menu_hits = self.store_service.search_menu(request.query, limit=1)
            if menu_hits:
                top_hit = menu_hits[0]
                item = top_hit["item"]
                price = self._best_item_price(item)
                if price:
                    amount = float(price.amount)
                    amount_currency = "USD"
                    matched_menu_item = {
                        "store_name": top_hit["store_name"],
                        "section_name": top_hit["section_name"],
                        "item_name": item.name,
                        "price": price.model_dump(mode="json"),
                    }

        payload: dict[str, Any] = {
            "snapshot": snapshot.model_dump(mode="json") if snapshot else None,
            "matched_menu_item": matched_menu_item,
            "applied_rate": applied_rate,
        }

        if amount is not None and amount_currency in {None, "USD"} and applied_rate is not None:
            converted = self.exchange_service.convert_usd_to_krw(amount, applied_rate)
            payload["converted"] = converted.model_dump(mode="json")
            payload["message_ko"] = f"{amount:g} USD는 환율 {applied_rate:,.2f} 기준 약 {float(converted.amount):,.0f} KRW입니다."
            payload["message_en"] = f"{amount:g} USD is about {float(converted.amount):,.0f} KRW at {applied_rate:,.2f} KRW per USD."
        elif amount is not None and amount_currency == "KRW" and applied_rate is not None:
            converted = self.exchange_service.convert_krw_to_usd(amount, applied_rate)
            payload["converted"] = converted.model_dump(mode="json")
            payload["message_ko"] = f"{amount:g} KRW는 환율 {applied_rate:,.2f} 기준 약 {float(converted.amount):,.2f} USD입니다."
            payload["message_en"] = f"{amount:g} KRW is about {float(converted.amount):,.2f} USD at {applied_rate:,.2f} KRW per USD."
        else:
            if snapshot:
                payload["message_ko"] = f"현재 수동 환율은 1 USD = {float(snapshot.usd_to_krw):,.2f} KRW입니다."
                payload["message_en"] = f"Current manual rate: 1 USD = {float(snapshot.usd_to_krw):,.2f} KRW."
            else:
                payload["message_ko"] = "현재 저장된 환율이 없습니다."
                payload["message_en"] = "No exchange rate is currently configured."

        state["tool_payload"] = {"exchange": payload}
        state["tool_sources"] = []
        return state

    def _rag_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        query = request.query
        retrieved = self.rag_repository.retrieve(query, top_k=4) if self.rag_repository else []
        state["retrieved"] = [
            {
                "title": chunk.title,
                "text": chunk.text,
                "kind": chunk.kind,
                "metadata": chunk.metadata,
                "source_refs": [ref.model_dump(mode="json") for ref in chunk.source_refs],
            }
            for chunk in retrieved
        ]
        return state

    def _compose_node(self, state: dict) -> dict:
        request = ChatRequest.model_validate(state["request"])
        intent = state["classification"]["intent"]
        tool_payload = state.get("tool_payload", {})
        retrieved_payload = state.get("retrieved", [])
        history = state.get("history", [])
        answer, used_llm = self.composer.compose(
            query=request.query,
            locale=request.locale,
            intent=intent,
            tool_payload=tool_payload,
            retrieved_payload=retrieved_payload,
            reference_time=state.get("reference_time"),
            history=history,
        )

        sources = self._build_sources(tool_payload=tool_payload, retrieved_payload=retrieved_payload)
        state["response"] = ChatResponse(
            query=request.query,
            locale=request.locale,
            intent=intent,
            answer=answer,
            tool_results=tool_payload,
            sources=sources,
            used_llm=used_llm,
            debug={
                "graph_mode": "langgraph" if self.graph is not None else "manual_fallback",
                "retrieved_count": len(retrieved_payload),
                "history_turns": len(history) // 2,
            },
        )
        return state

    @staticmethod
    def _best_item_price(item: MenuItem):
        for variant in item.pricing:
            if variant.price:
                return variant.price
        for variant in item.addons:
            if variant.price:
                return variant.price
        return None

    @staticmethod
    def _build_sources(*, tool_payload: dict, retrieved_payload: list[dict]) -> list[SourceBasis]:
        seen: set[str] = set()
        sources: list[SourceBasis] = []

        def add_source(label: str, excerpt: str | None = None, source_dict: dict | None = None):
            key = f"{label}|{excerpt}"
            if key in seen:
                return
            seen.add(key)
            source = None
            if source_dict:
                from camp_casey_app.domain.models import SourceReference
                source = SourceReference.model_validate(source_dict)
            sources.append(SourceBasis(label=label, excerpt=excerpt, source=source))

        def collect_refs(obj: Any):
            if isinstance(obj, dict):
                if {"file_name", "label", "source_type"} <= set(obj.keys()):
                    add_source(obj["label"], obj.get("excerpt"), obj)
                for value in obj.values():
                    collect_refs(value)
            elif isinstance(obj, list):
                for item in obj:
                    collect_refs(item)

        collect_refs(tool_payload)
        for chunk in retrieved_payload:
            add_source(chunk.get("title", "Retrieved chunk"), chunk.get("text", "")[:160], None)
            collect_refs(chunk.get("source_refs", []))
        return sources[:8]
