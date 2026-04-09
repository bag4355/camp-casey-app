from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from camp_casey_app.api.app import create_app
from camp_casey_app.config import Settings
from camp_casey_app.container import build_container
from camp_casey_app.ingest.normalize import ensure_exchange_rate_seed, run_full_ingest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_settings(data_root: Path) -> Settings:
    return Settings(
        root_dir=REPO_ROOT,
        data_root_dir=data_root,
        bundled_data_dir=REPO_ROOT / "data",
        raw_data_dir=data_root / "raw",
        normalized_data_dir=data_root / "normalized",
        rag_dir=data_root / "rag",
        state_dir=data_root / "state",
        template_dir=REPO_ROOT / "camp_casey_app" / "web" / "templates",
        static_dir=REPO_ROOT / "camp_casey_app" / "web" / "static",
        timezone="Asia/Seoul",
        default_locale="ko",
        supported_locales=("ko", "en"),
        default_bus_stop_query="CAC",
        default_train_provider="bosan",
        default_usd_to_krw=1380.0,
        openai_api_key=None,
        openai_chat_model="gpt-4.1-mini",
        openai_embedding_model="text-embedding-3-small",
        app_name="Camp Casey Living Helper",
        app_version="0.1.0",
    )


@pytest.fixture(scope="session")
def session_settings(tmp_path_factory) -> Settings:
    data_root = tmp_path_factory.mktemp("camp_casey_data")
    settings = _make_settings(data_root)
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    for source in (REPO_ROOT / "data" / "raw").iterdir():
        if source.is_file():
            shutil.copy2(source, settings.raw_data_dir / source.name)
    run_full_ingest(settings)
    ensure_exchange_rate_seed(settings)
    return settings


@pytest.fixture(scope="session")
def container(session_settings):
    return build_container(session_settings)


@pytest.fixture(scope="session")
def app(session_settings):
    return create_app(session_settings)


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app)
