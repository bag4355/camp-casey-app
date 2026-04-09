from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

from camp_casey_app.domain.models import BusDataset, HolidayDataset, StoreDataset, TrainDataset


class NormalizedRepository:
    def __init__(self, normalized_dir: Path):
        self.normalized_dir = normalized_dir

    def _read_json(self, file_name: str) -> dict:
        path = self.normalized_dir / file_name
        return json.loads(path.read_text(encoding="utf-8"))

    @cached_property
    def stores(self) -> StoreDataset:
        return StoreDataset.model_validate(self._read_json("stores.json"))

    @cached_property
    def holidays(self) -> HolidayDataset:
        return HolidayDataset.model_validate(self._read_json("holidays.json"))

    @cached_property
    def bus(self) -> BusDataset:
        return BusDataset.model_validate(self._read_json("bus.json"))

    @cached_property
    def trains(self) -> TrainDataset:
        return TrainDataset.model_validate(self._read_json("trains.json"))
