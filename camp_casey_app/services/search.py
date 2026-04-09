from __future__ import annotations

from datetime import datetime

from camp_casey_app.services.stores import StoreService
from camp_casey_app.services.transport import BusService, TrainService


class SearchService:
    def __init__(self, store_service: StoreService, bus_service: BusService, train_service: TrainService):
        self.store_service = store_service
        self.bus_service = bus_service
        self.train_service = train_service

    def search_all(self, query: str, *, at: datetime | None = None) -> dict:
        return {
            "stores": self.store_service.list_store_summaries(query=query, at=at, limit=8),
            "menu": self.store_service.search_menu(query, limit=8),
            "bus_stops": self.bus_service.search_stops(query, limit=8),
            "train_providers": self.train_service.list_providers(),
        }
