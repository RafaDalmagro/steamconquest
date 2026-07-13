from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.models import Game, GameDetail, Include, PlayerSummary, Sort
from app.services.achievements import AchievementsService
from app.errors import (
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamRateLimitError,
    SteamUnavailableError,
)

router = APIRouter(prefix="/api")

# SteamID64 tem 17 dígitos. Valida no path para dar 422 em lixo antes de
# chamar a Steam (o frontend também valida, mas isto é a rede de segurança).
_STEAMID = Path(pattern=r"^\d{17}$")


def get_service(request: Request) -> AchievementsService:
    return request.app.state.service


@router.get("/users/{steamid}/profile", response_model=PlayerSummary)
async def player_profile(steamid: str = _STEAMID, service=Depends(get_service)):
    return await service.player_summary(steamid)


@router.get("/users/{steamid}/games", response_model=list[Game])
async def list_games(
    steamid: str = _STEAMID,
    sort: Sort = "playtime",
    # Repetível (`?include=achievements&include=genres`): é a forma nativa do
    # FastAPI, que valida o vocabulário e o publica no OpenAPI sem parser à mão.
    include: Annotated[list[Include], Query()] = [],
    service=Depends(get_service),
):
    # Valor fora do vocabulário não chega aqui: os Literal fazem o FastAPI devolver
    # 422 (com o `detail` em pt-BR do handler abaixo) antes de tocar o serviço.
    return await service.list_library(steamid, sort=sort, include=include)


@router.get("/users/{steamid}/games/{appid}", response_model=GameDetail)
async def game_detail(appid: int, steamid: str = _STEAMID, service=Depends(get_service)):
    return await service.game_detail(steamid, appid)


# Mapeamento de erro tipado → HTTP + mensagem amigável (pt-BR), em JSON.
_ERROR_MAP = {
    SteamProfileNotFound: (404, "Steam ID não encontrado. Confira os 17 dígitos."),
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

    # O 422 padrão do FastAPI traz `detail` como array de erros de validação, que
    # o frontend não sabe exibir. Aqui ele passa a falar o mesmo contrato dos
    # demais erros — {"detail": "<pt-BR>"} — para steamid, appid, sort e include.
    async def handle_validation(request: Request, exc: Exception):
        return JSONResponse(
            {"detail": "Parâmetro inválido na URL. Confira o endereço e tente de novo."},
            status_code=422,
        )

    app.add_exception_handler(RequestValidationError, handle_validation)
