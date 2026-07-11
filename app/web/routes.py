from fastapi import APIRouter, Depends, FastAPI, Path, Request
from fastapi.responses import JSONResponse

from app.schemas.models import Game, GameDetail
from app.services.achievements import AchievementsService
from app.errors import (
    SteamDataUnavailable,
    SteamRateLimitError,
    SteamUnavailableError,
)

router = APIRouter(prefix="/api")

_VALID_SORTS = {"playtime", "name", "percent", "ach_count"}
_VALID_GROUPS = {"genre"}

# SteamID64 tem 17 dígitos. Valida no path para dar 422 em lixo antes de
# chamar a Steam (o frontend também valida, mas isto é a rede de segurança).
_STEAMID = Path(pattern=r"^\d{17}$")


def get_service(request: Request) -> AchievementsService:
    return request.app.state.service


@router.get("/users/{steamid}/games", response_model=list[Game])
async def list_games(
    steamid: str = _STEAMID,
    sort: str = "playtime",
    group: str | None = None,
    service=Depends(get_service),
):
    if sort not in _VALID_SORTS:
        sort = "playtime"
    if group not in _VALID_GROUPS:
        group = None
    return await service.list_library(steamid, sort=sort, group=group)


@router.get("/users/{steamid}/games/{appid}", response_model=GameDetail)
async def game_detail(appid: int, steamid: str = _STEAMID, service=Depends(get_service)):
    return await service.game_detail(steamid, appid)


# Mapeamento de erro tipado → HTTP + mensagem amigável (pt-BR), em JSON.
_ERROR_MAP = {
    SteamDataUnavailable: (404, "Dados indisponíveis. O perfil pode estar privado."),
    SteamRateLimitError: (429, "A Steam limitou as requisições. Tente novamente em instantes."),
    SteamUnavailableError: (502, "A Steam está indisponível no momento."),
}


def register_error_handlers(app: FastAPI) -> None:
    async def handle(request: Request, exc: Exception):
        status, message = _ERROR_MAP[type(exc)]
        return JSONResponse({"detail": message}, status_code=status)

    for exc_type in _ERROR_MAP:
        app.add_exception_handler(exc_type, handle)
