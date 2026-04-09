from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from camp_casey_app.api.langserve_routes import maybe_add_langserve
from camp_casey_app.api.routes import router as api_router
from camp_casey_app.api.web import create_web_router
from camp_casey_app.config import Settings, get_settings
from camp_casey_app.container import build_container


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    container = build_container(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Camp Casey / Hovey / Bosan helper app with deterministic services and an optional LangServe wrapper.",
    )
    app.state.container = container
    app.state.langserve_enabled = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
    app.include_router(api_router)
    app.include_router(create_web_router(settings))

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "version": settings.app_version,
            "openai_available": container.openai_service.is_available(),
            "langgraph_enabled": container.chat_agent.graph is not None,
            "langserve_enabled": app.state.langserve_enabled,
        }

    app.state.langserve_enabled = maybe_add_langserve(app, container)
    return app
