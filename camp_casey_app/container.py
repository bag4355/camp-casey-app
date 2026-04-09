from __future__ import annotations

from dataclasses import dataclass

from camp_casey_app.ai.openai_client import OpenAIService
from camp_casey_app.bootstrap import ensure_data_ready
from camp_casey_app.chat.langgraph_workflow import CampCaseyChatAgent
from camp_casey_app.chat.session_store import SessionStore
from camp_casey_app.config import Settings
from camp_casey_app.repositories.exchange_rate_store import ExchangeRateFileStore
from camp_casey_app.repositories.normalized_repository import NormalizedRepository
from camp_casey_app.repositories.rag_repository import RAGRepository
from camp_casey_app.services.day_type import DayTypeService
from camp_casey_app.services.exchange_rate import ExchangeRateService
from camp_casey_app.services.holidays import HolidayService
from camp_casey_app.services.search import SearchService
from camp_casey_app.services.stores import StoreService
from camp_casey_app.services.transport import BusService, TrainService


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    repository: NormalizedRepository
    day_type_service: DayTypeService
    holiday_service: HolidayService
    bus_service: BusService
    train_service: TrainService
    store_service: StoreService
    exchange_service: ExchangeRateService
    search_service: SearchService
    rag_repository: RAGRepository
    openai_service: OpenAIService
    session_store: SessionStore
    chat_agent: CampCaseyChatAgent


def build_container(settings: Settings) -> ServiceContainer:
    ensure_data_ready(settings)
    repository = NormalizedRepository(settings.normalized_data_dir)
    day_type_service = DayTypeService(repository.holidays)
    holiday_service = HolidayService(repository.holidays)
    bus_service = BusService(repository.bus, day_type_service, settings.timezone)
    train_service = TrainService(repository.trains, settings.timezone)
    store_service = StoreService(repository.stores, day_type_service, settings.timezone)
    exchange_service = ExchangeRateService(ExchangeRateFileStore(settings.exchange_rate_path), settings.timezone, settings.default_usd_to_krw)
    openai_service = OpenAIService(settings)
    rag_repository = RAGRepository(settings.rag_chunks_path, settings.rag_index_path, openai_service)
    search_service = SearchService(store_service, bus_service, train_service)
    session_store = SessionStore()
    chat_agent = CampCaseyChatAgent(
        bus_service=bus_service,
        train_service=train_service,
        store_service=store_service,
        holiday_service=holiday_service,
        exchange_service=exchange_service,
        search_service=search_service,
        rag_repository=rag_repository,
        openai_service=openai_service,
        session_store=session_store,
        timezone=settings.timezone,
        default_bus_stop_query=settings.default_bus_stop_query,
    )
    return ServiceContainer(
        settings=settings,
        repository=repository,
        day_type_service=day_type_service,
        holiday_service=holiday_service,
        bus_service=bus_service,
        train_service=train_service,
        store_service=store_service,
        exchange_service=exchange_service,
        search_service=search_service,
        rag_repository=rag_repository,
        openai_service=openai_service,
        session_store=session_store,
        chat_agent=chat_agent,
    )
