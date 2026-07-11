from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.core.cache import TTLCache
from app.services.achievements import AchievementsService
from app.steam.client import SteamClient
from app.web.routes import register_error_handlers, router

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    http = httpx.AsyncClient(timeout=settings.http_timeout)
    # language="brazilian" é default do SteamClient (config de produto, não de deploy).
    # O steamid vem por request (path /api/users/{steamid}/...), não do env.
    client = SteamClient(http, settings.steam_api_key)
    app.state.service = AchievementsService(client, TTLCache(), settings.steam_concurrency)
    try:
        yield
    finally:
        await http.aclose()


class SPAStaticFiles(StaticFiles):
    """Serve o build do frontend; para rotas de cliente (ex.: /game/220), que não
    existem em disco, devolve index.html (deep-link do React Router)."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Fallback só para rotas de cliente: nunca em /api (contrato JSON
            # preservado) nem em requisições de asset (têm extensão de arquivo).
            is_client_route = not path.startswith("api/") and "." not in path.rsplit("/", 1)[-1]
            if exc.status_code == 404 and is_client_route:
                return await super().get_response("index.html", scope)
            raise


def create_app() -> FastAPI:
    app = FastAPI(title="Conquistas Steam", lifespan=lifespan)
    app.include_router(router)
    register_error_handlers(app)
    # /api tem precedência (registrado antes). Em produção o build estático é
    # servido daqui; em dev o Vite serve o frontend e este mount nem existe.
    if _DIST.is_dir():
        app.mount("/", SPAStaticFiles(directory=_DIST, html=True), name="spa")
    return app


app = create_app()
