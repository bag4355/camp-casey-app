from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional at runtime
    load_dotenv = None


@dataclass(slots=True)
class Settings:
    root_dir: Path
    data_root_dir: Path
    bundled_data_dir: Path
    raw_data_dir: Path
    normalized_data_dir: Path
    rag_dir: Path
    state_dir: Path
    template_dir: Path
    static_dir: Path
    timezone: str
    default_locale: str
    supported_locales: tuple[str, ...]
    default_bus_stop_query: str
    default_train_provider: str
    default_usd_to_krw: float
    openai_api_key: str | None
    openai_chat_model: str
    openai_embedding_model: str
    app_name: str
    app_version: str
    cors_allowed_origins: list[str]

    @property
    def raw_delivery_path(self) -> Path:
        return self.raw_data_dir / "delivery.json"

    @property
    def raw_holiday_path(self) -> Path:
        return self.raw_data_dir / "holiday.json"

    @property
    def raw_bus_path(self) -> Path:
        return self.raw_data_dir / "Hovey-Bus-TimeTable.xlsx"

    @property
    def raw_train_path(self) -> Path:
        return self.raw_data_dir / "Bosan-Train-TimeTable.xlsx"

    @property
    def stores_path(self) -> Path:
        return self.normalized_data_dir / "stores.json"

    @property
    def holidays_path(self) -> Path:
        return self.normalized_data_dir / "holidays.json"

    @property
    def bus_path(self) -> Path:
        return self.normalized_data_dir / "bus.json"

    @property
    def trains_path(self) -> Path:
        return self.normalized_data_dir / "trains.json"

    @property
    def manifest_path(self) -> Path:
        return self.normalized_data_dir / "manifest.json"

    @property
    def rag_chunks_path(self) -> Path:
        return self.rag_dir / "rag_chunks.jsonl"

    @property
    def rag_index_path(self) -> Path:
        return self.rag_dir / "rag_index.json"

    @property
    def exchange_rate_path(self) -> Path:
        return self.state_dir / "exchange_rate.json"


def _discover_root() -> Path:
    env_root = os.getenv("APP_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root_dir = _discover_root()
    env_file = root_dir / ".env"
    if load_dotenv and env_file.exists():
        load_dotenv(env_file)

    data_root_dir = Path(os.getenv("DATA_ROOT", root_dir / "data")).resolve()

    return Settings(
        root_dir=root_dir,
        data_root_dir=data_root_dir,
        bundled_data_dir=root_dir / "data",
        raw_data_dir=data_root_dir / "raw",
        normalized_data_dir=data_root_dir / "normalized",
        rag_dir=data_root_dir / "rag",
        state_dir=data_root_dir / "state",
        template_dir=root_dir / "camp_casey_app" / "web" / "templates",
        static_dir=root_dir / "camp_casey_app" / "web" / "static",
        timezone=os.getenv("APP_TIMEZONE", "Asia/Seoul"),
        default_locale=os.getenv("DEFAULT_LOCALE", "ko"),
        supported_locales=("ko", "en"),
        default_bus_stop_query=os.getenv("DEFAULT_BUS_STOP_QUERY", "CAC"),
        default_train_provider=os.getenv("DEFAULT_TRAIN_PROVIDER", "bosan"),
        default_usd_to_krw=float(os.getenv("DEFAULT_USD_TO_KRW", "1380")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        app_name=os.getenv("APP_NAME", "Camp Casey Living Helper"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        cors_allowed_origins=[
            origin.strip()
            for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
            if origin.strip()
        ],
    )
