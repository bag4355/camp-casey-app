from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from camp_casey_app.config import Settings


def create_web_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=str(settings.template_dir))

    @router.get("/")
    def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "app_name": settings.app_name,
                "default_locale": settings.default_locale,
            },
        )

    return router
