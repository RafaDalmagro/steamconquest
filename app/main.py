from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import Settings
from app.core.cache import TTLCache
from app.services.achievements import AchievementsService
from app.steam.client import SteamClient
from app.web.routes import register_error_handlers, router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    http = httpx.AsyncClient(timeout=settings.http_timeout)
    # language="brazilian" é default do SteamClient (config de produto, não de deploy).
    client = SteamClient(http, settings.steam_api_key, settings.steam_id)
    app.state.service = AchievementsService(client, TTLCache(), settings.steam_concurrency)
    try:
        yield
    finally:
        await http.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Conquistas Steam", lifespan=lifespan)
    app.include_router(router)
    register_error_handlers(app)
    return app


app = create_app()
