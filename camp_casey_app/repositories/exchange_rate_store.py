from __future__ import annotations

import json
from pathlib import Path

from camp_casey_app.domain.models import ExchangeRateConfig


class ExchangeRateFileStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> ExchangeRateConfig:
        if not self.path.exists():
            return ExchangeRateConfig()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return ExchangeRateConfig.model_validate(payload)

    def save(self, config: ExchangeRateConfig) -> ExchangeRateConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        return config
