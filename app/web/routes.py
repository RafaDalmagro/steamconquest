from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.achievements import AchievementsService
from app.errors import (
    SteamDataUnavailable,
    SteamRateLimitError,
    SteamUnavailableError,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_VALID_SORTS = {"playtime", "name", "percent", "ach_count"}


def get_service(request: Request) -> AchievementsService:
    return request.app.state.service


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, sort: str = "playtime", service=Depends(get_service)):
    if sort not in _VALID_SORTS:
        sort = "playtime"
    games = await service.list_library(sort=sort)
    return templates.TemplateResponse(request, "index.html", {"games": games, "sort": sort})


@router.get("/game/{appid}", response_class=HTMLResponse)
async def game(request: Request, appid: int, service=Depends(get_service)):
    detail = await service.game_detail(appid)
    return templates.TemplateResponse(request, "game.html", {"detail": detail})


# Mapeamento de erro tipado → HTTP + página amigável (pt-BR).
_ERROR_MAP = {
    SteamDataUnavailable: (404, "Dados indisponíveis. O perfil pode estar privado."),
    SteamRateLimitError: (429, "A Steam limitou as requisições. Tente novamente em instantes."),
    SteamUnavailableError: (502, "A Steam está indisponível no momento."),
}


def register_error_handlers(app: FastAPI) -> None:
    async def handle(request: Request, exc: Exception):
        status, message = _ERROR_MAP[type(exc)]
        return templates.TemplateResponse(
            request, "error.html", {"message": message}, status_code=status
        )

    for exc_type in _ERROR_MAP:
        app.add_exception_handler(exc_type, handle)
