from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder

from camp_casey_app.chat.schemas import ChatRequest
from camp_casey_app.container import ServiceContainer


router = APIRouter(prefix="/api")


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def as_json(payload):
    return jsonable_encoder(payload, by_alias=True)



@router.get("/meta")
def get_meta(container: Annotated[ServiceContainer, Depends(get_container)]):
    return {
        "app_name": container.settings.app_name,
        "version": container.settings.app_version,
        "timezone": container.settings.timezone,
        "default_locale": container.settings.default_locale,
        "supported_locales": list(container.settings.supported_locales),
        "openai_available": container.openai_service.is_available(),
        "langgraph_enabled": container.chat_agent.graph is not None,
    }


@router.get("/bootstrap")
def get_bootstrap(container: Annotated[ServiceContainer, Depends(get_container)]):
    zone = ZoneInfo(container.settings.timezone)
    now = datetime.now(zone)
    open_stores = container.store_service.list_store_summaries(open_now=True, at=now, limit=5)
    default_stop = container.bus_service.search_stops(container.settings.default_bus_stop_query, limit=1)
    next_bus = container.bus_service.get_next_bus(default_stop[0].stop_id if default_stop else container.settings.default_bus_stop_query, at=now, count=3)
    next_train = container.train_service.get_next_train(container.settings.default_train_provider, at=now, count=3)
    day_type = container.day_type_service.resolve_day_type(now.date())
    return as_json(
        {
            "app": {
                "name": container.settings.app_name,
                "version": container.settings.app_version,
                "default_locale": container.settings.default_locale,
                "supported_locales": list(container.settings.supported_locales),
            },
            "today_day_type": day_type,
            "exchange_rate": container.exchange_service.get_active_exchange_rate(),
            "exchange_providers": container.exchange_service.provider_statuses(),
            "bus_stops": container.repository.bus.stops,
            "train_providers": container.repository.trains.providers,
            "home": {
                "default_bus_stop_query": container.settings.default_bus_stop_query,
                "next_bus": next_bus,
                "next_train": next_train,
                "open_stores": open_stores,
            },
            "holiday_notes": container.holiday_service.notes,
        }
    )


@router.get("/day-type")
def get_day_type(
    date_value: Annotated[date | None, Query(alias="date")] = None,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    zone = ZoneInfo(container.settings.timezone)
    target_date = date_value or datetime.now(zone).date()
    return as_json(container.day_type_service.resolve_day_type(target_date))


@router.get("/holidays")
def list_holidays(
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    confirmed_only: bool = False,
    status: list[str] | None = Query(default=None),
    holiday_type: list[str] | None = Query(default=None),
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(
        {
            "items": container.holiday_service.list_holidays(
                from_date=from_date,
                to_date=to_date,
                confirmed_only=confirmed_only,
                statuses=set(status or []),
                holiday_types=set(holiday_type or []),
            ),
            "notes": container.holiday_service.notes,
        }
    )


@router.get("/bus/stops")
def list_bus_stops(
    query: str | None = None,
    limit: int = 20,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(container.bus_service.search_stops(query, limit=limit))


@router.get("/bus/next")
def get_next_bus(
    stop: str,
    count: int = 3,
    at: datetime | None = None,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(container.bus_service.get_next_bus(stop, at=at, count=count))


@router.get("/bus/schedule")
def get_bus_schedule(
    stop: str,
    date_value: Annotated[date, Query(alias="date")],
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(container.bus_service.get_full_schedule(stop, service_date=date_value))


@router.get("/train/providers")
def list_train_providers(container: Annotated[ServiceContainer, Depends(get_container)]):
    return as_json(container.train_service.list_providers())


@router.get("/train/next")
def get_next_train(
    provider: str,
    count: int = 3,
    at: datetime | None = None,
    destination: str | None = None,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(container.train_service.get_next_train(provider, at=at, count=count, destination=destination))


@router.get("/train/schedule")
def get_train_schedule(
    provider: str,
    date_value: Annotated[date, Query(alias="date")],
    destination: str | None = None,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(container.train_service.get_full_schedule(provider, service_date=date_value, destination=destination))


@router.get("/stores")
def list_stores(
    query: str | None = None,
    open_now: bool = False,
    max_minimum_order: Decimal | None = None,
    at: datetime | None = None,
    limit: int = 50,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(
        container.store_service.list_store_summaries(
            query=query,
            open_now=open_now,
            max_minimum_order=max_minimum_order,
            at=at,
            limit=limit,
        )
    )


@router.get("/stores/{store_id}")
def get_store_detail(
    store_id: str,
    at: datetime | None = None,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    store = container.store_service.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    status = container.store_service.resolve_store_status(store, at)
    return as_json({"store": store, "status": status})


@router.get("/menu/search")
def search_menu(
    query: str,
    store_id: str | None = None,
    limit: int = 20,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    return as_json(container.store_service.search_menu(query, store_id=store_id, limit=limit))


@router.get("/exchange-rate")
def get_exchange_rate(container: Annotated[ServiceContainer, Depends(get_container)]):
    return as_json(
        {
            "snapshot": container.exchange_service.get_active_exchange_rate(),
            "providers": container.exchange_service.provider_statuses(),
        }
    )


@router.get("/exchange-rate/convert")
def convert_currency(
    amount: Decimal,
    source_currency: Annotated[str, Query(alias="from")],
    rate: Decimal | None = None,
    container: Annotated[ServiceContainer, Depends(get_container)] = None,
):
    source_upper = source_currency.upper()
    if source_upper == "USD":
        return as_json(container.exchange_service.convert_usd_to_krw(amount, rate))
    if source_upper == "KRW":
        return as_json(container.exchange_service.convert_krw_to_usd(amount, rate))
    raise HTTPException(status_code=400, detail="Unsupported source currency")


@router.post("/chat")
def chat(
    payload: Annotated[ChatRequest, Body(...)],
    container: Annotated[ServiceContainer, Depends(get_container)],
):
    return as_json(container.chat_agent.invoke(payload))


@router.delete("/chat/session/{session_id}")
def clear_session(
    session_id: str,
    container: Annotated[ServiceContainer, Depends(get_container)],
):
    """세션 대화 히스토리를 초기화한다."""
    container.session_store.clear(session_id)
    return {"ok": True, "session_id": session_id}


@router.get("/chat/session/{session_id}/history")
def get_session_history(
    session_id: str,
    container: Annotated[ServiceContainer, Depends(get_container)],
):
    """세션의 현재 대화 히스토리를 반환한다."""
    history = container.session_store.get_history(session_id)
    return {
        "session_id": session_id,
        "turn_count": len(history) // 2,
        "message_count": len(history),
        "history": history,
    }


@router.get("/search")
def search_everything(
    query: str,
    container: Annotated[ServiceContainer, Depends(get_container)],
):
    return as_json(container.search_service.search_all(query))


@router.get("/debug/manifest")
def get_manifest(container: Annotated[ServiceContainer, Depends(get_container)]):
    return as_json(
        {
            "stores": len(container.repository.stores.stores),
            "holidays": len(container.repository.holidays.holidays),
            "bus_stops": len(container.repository.bus.stops),
            "train_providers": len(container.repository.trains.providers),
            "rag_chunks": len(container.rag_repository.chunks),
        }
    )
